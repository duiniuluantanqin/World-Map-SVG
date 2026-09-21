#!/usr/bin/env python3
"""SVG 世界地图命名工具核心库（自包含，无外部依赖除 PIL）。

提供：
- SVG path 解析：把 `d` 属性拆成若干子多边形（polygon ring）。
- 叶区域提取：找到 `<g>` 结构里最末端、带 id 且不含带 id 子元素的 path/g 单元。
- Robinson 投影互转：本项目地图专用校准（宽高比 1.9716，中央经线 +10.03°）。
- Natural Earth admin-1 索引：读 geojson，按国家分组、质心落点 / 最近邻查询。
- id 生成：ASCII 转写（deacc）、kebab-case、ISO 后缀字母/数字规则。

数据源路径可在调用侧配置（见 batch.py 的 NE_PATH）。
"""

import re
import math
import json
import unicodedata


# ---------------- SVG path 解析 ----------------

TOK = re.compile(r'([MmLlHhVvCcSsZz])|([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)')
NARGS = {'M': 2, 'L': 2, 'H': 1, 'V': 1, 'C': 6, 'S': 4}


def parse_path(d):
    toks = []
    for m in TOK.finditer(d):
        toks.append(m.group(1) if m.group(1) else float(m.group(2)))
    subs = []
    cur = []
    pos = (0.0, 0.0)
    start = (0.0, 0.0)
    i = 0
    cmd = None

    def bez(p0, p1, p2, p3, n=4):
        out = []
        for k in range(1, n + 1):
            t = k / n
            mt = 1 - t
            out.append((mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0],
                        mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]))
        return out

    while i < len(toks):
        if isinstance(toks[i], str):
            cmd = toks[i]
            i += 1
        if cmd is None:
            break
        C = cmd.upper()
        rel = cmd.islower()
        if C == 'Z':
            if cur:
                cur.append(start)
                subs.append(cur)
                cur = []
            pos = start
            cmd = None
            continue
        k = NARGS[C]
        if i + k > len(toks):
            break
        a = toks[i:i + k]
        i += k
        if C == 'M':
            x, y = a
            if rel:
                x += pos[0]
                y += pos[1]
            if cur:
                subs.append(cur)
            pos = (x, y)
            start = pos
            cur = [pos]
            cmd = 'l' if rel else 'L'
            continue
        if C == 'L':
            x, y = a
            if rel:
                x += pos[0]
                y += pos[1]
            pos = (x, y)
            cur.append(pos)
        elif C == 'H':
            x = a[0] + (pos[0] if rel else 0)
            pos = (x, pos[1])
            cur.append(pos)
        elif C == 'V':
            y = a[0] + (pos[1] if rel else 0)
            pos = (pos[0], y)
            cur.append(pos)
        elif C == 'C':
            x1, y1, x2, y2, x, y = a
            if rel:
                x1 += pos[0]
                y1 += pos[1]
                x2 += pos[0]
                y2 += pos[1]
                x += pos[0]
                y += pos[1]
            cur += bez(pos, (x1, y1), (x2, y2), (x, y))
            pos = (x, y)
        elif C == 'S':
            x2, y2, x, y = a
            if rel:
                x2 += pos[0]
                y2 += pos[1]
                x += pos[0]
                y += pos[1]
            cur.append((x, y))
            pos = (x, y)
    if cur:
        subs.append(cur)
    return [s for s in subs if len(s) > 2]


def polys_of(el):
    out = []
    for p in el.iter():
        if p.tag.split('}')[-1] == 'path' and p.get('d'):
            out += parse_path(p.get('d'))
    return out


def _tag(el):
    return el.tag.split('}')[-1]


_LEAF_TAGS = ('path', 'g', 'svg', 'a', 'circle', 'polygon', 'polyline', 'ellipse', 'rect')


def leaf_regions(root):
    """返回 {leaf_id: [polygons,...]}，叶元素=带 id 且无带 id 子元素的元素。"""
    res = {}

    def rec(el):
        for c in el:
            if _tag(c) not in _LEAF_TAGS:
                continue
            kids = [k for k in c if k.get('id')]
            i = c.get('id')
            if i and not kids:
                ps = polys_of(c)
                if ps:
                    res[i] = ps
            else:
                rec(c)

    rec(root)
    return res


def bbox(pts):
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def centroid(polys):
    tot = 0.0
    cx = 0.0
    cy = 0.0
    for poly in polys:
        s = sx = sy = 0.0
        for p, q in zip(poly, poly[1:] + poly[:1]):
            cr = p[0] * q[1] - q[0] * p[1]
            s += cr
            sx += (p[0] + q[0]) * cr
            sy += (p[1] + q[1]) * cr
        A = s / 2.0
        if A == 0:
            continue
        sg = 1 if A > 0 else -1
        cx += sg * sx / 6.0
        cy += sg * sy / 6.0
        tot += abs(A)
    if tot == 0:
        return None
    return (cx / tot, cy / tot)


def poly_area_xy(poly):
    """平面多边形面积（投影坐标），用于拆分块大小排序。"""
    return abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1]))) / 2.0


# ---------------- Robinson 投影（本项目专用校准） ----------------

AA = [1, 0.9986, 0.9954, 0.99, 0.9822, 0.973, 0.96, 0.9427, 0.9216, 0.8962,
      0.8679, 0.835, 0.7986, 0.7597, 0.7186, 0.6732, 0.6213, 0.5722, 0.5322]
BB = [0, 0.062, 0.124, 0.186, 0.248, 0.31, 0.372, 0.434, 0.4958, 0.5571,
      0.6176, 0.6769, 0.7346, 0.7903, 0.8435, 0.8936, 0.9394, 0.9761, 1.0]


def _interp(tab, phi):
    a = abs(phi) / 5.0
    i = min(int(a), 17)
    f = a - i
    return tab[i] * (1 - f) + tab[i + 1] * f


RX = 1000.0 / (2 * 0.8487 * math.pi)
RY = 507.209 / (2 * 1.3523)
LON0 = 10.03


def lonlat_to_xy(lat, lon):
    lon = lon - LON0
    aa = _interp(AA, lat)
    bb = _interp(BB, lat)
    return (500 + 0.8487 * math.radians(lon) * aa * RX,
            RY * (1.3523 - (1.3523 * bb if lat >= 0 else -1.3523 * bb)))


def xy_to_lonlat(x, y):
    yn = 1.3523 - y / RY
    sign = 1 if yn >= 0 else -1
    t = abs(yn) / 1.3523
    lo, hi = 0.0, 90.0
    for _ in range(80):
        m = (lo + hi) / 2
        if _interp(BB, m) < t:
            lo = m
        else:
            hi = m
    lat = sign * (lo + hi) / 2
    aa = _interp(AA, lat)
    lon = math.degrees(((x - 500) / RX) / (0.8487 * aa)) + LON0
    return lat, lon


# ---------------- Natural Earth 索引 ----------------

class NEIndex:
    def __init__(self, path):
        d = json.load(open(path, encoding='utf-8'))
        self.items = []
        for ft in d['features']:
            pr = ft['properties']
            g = ft['geometry']
            if g['type'] == 'Polygon':
                polys = [g['coordinates']]
            elif g['type'] == 'MultiPolygon':
                polys = g['coordinates']
            else:
                continue
            rings = []
            bb = [1e9, 1e9, -1e9, -1e9]
            for poly in polys:
                xs = [c[0] for c in poly[0]]
                ys = [c[1] for c in poly[0]]
                bb[0] = min(bb[0], min(xs))
                bb[1] = min(bb[1], min(ys))
                bb[2] = max(bb[2], max(xs))
                bb[3] = max(bb[3], max(ys))
                rings.append(poly)
            self.items.append({
                'iso': (pr.get('iso_3166_2') or '').strip(),
                'name': (pr.get('name') or '').strip(),
                'name_en': (pr.get('name_en') or '').strip(),
                'adm0': (pr.get('iso_a2') or '').strip(),
                'admin': pr.get('admin') or '',
                'type': pr.get('type_en') or '',
                'lat': pr.get('latitude'),
                'lon': pr.get('longitude'),
                'wikidata': pr.get('wikidataid') or '',
                'rings': rings,
                'bbox': tuple(bb),
            })
        self.buckets = {}
        self.byi = {}
        for it in self.items:
            self.buckets.setdefault(it['adm0'], []).append(it)
            self.byi.setdefault(it['iso'].upper(), []).append(it)

    def find(self, lat, lon, adm0=None):
        cands = self.buckets.get(adm0, []) if adm0 else self.items
        for it in cands:
            b = it['bbox']
            if lon < b[0] or lon > b[2] or lat < b[1] or lat > b[3]:
                continue
            if _in_rings(it['rings'], lon, lat):
                return it
        return None

    def nearest(self, lat, lon, adm0=None, maxdeg=3.0):
        cands = self.buckets.get(adm0, []) if adm0 else self.items
        best = None
        for it in cands:
            if it['lat'] is None:
                continue
            dd = math.hypot((it['lat'] - lat), (it['lon'] - lon) * math.cos(math.radians(lat)))
            if best is None or dd < best[0]:
                best = (dd, it)
        return best[1] if best and best[0] <= maxdeg else None


def _pt_in_ring(ring, x, y):
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _in_rings(polys, x, y):
    for poly in polys:
        hit = False
        for ring in poly:
            if _pt_in_ring(ring, x, y):
                hit = not hit
        if hit:
            return True
    return False


# ---------------- id 生成 ----------------

_DEACC = [(chr(0xdf), 'ss'), (chr(0xf8), 'o'), (chr(0xd8), 'O'),
          (chr(0x111), 'd'), (chr(0x110), 'D'), (chr(0x142), 'l'),
          (chr(0x141), 'L'), (chr(0xe6), 'ae'), (chr(0xc6), 'AE'),
          (chr(0x153), 'oe'), (chr(0x152), 'OE'), (chr(0xfe), 'th'),
          (chr(0xf0), 'd'), (chr(0x131), 'i'), (chr(0x130), 'I')]


def deacc(s):
    for a, b in _DEACC:
        s = s.replace(a, b)
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def kebab(s):
    s = deacc(s or '').lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s.strip())
    return re.sub(r"-+", "-", s)


def base_id(cc, iso, name_en):
    """按命名规范生成基础 id：
    - ISO 后缀是字母 → `CC-SUFFIX`（大写）
    - ISO 后缀是数字 → `CC-英文名 kebab-case`
    """
    suf = iso.split('-', 1)[1] if '-' in iso else ''
    if suf and suf.isalpha():
        return iso.upper()
    nm = kebab(name_en)
    return "%s-%s" % (cc, nm) if nm else None