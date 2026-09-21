#!/usr/bin/env python3
"""批量命名魔数 id 的可复现 pipeline。

流程（对每个国家）：propose（几何匹配 NE admin-1） -> apply（仅替换 id 属性） -> verify。

用法：
  python tools/batch.py KW ST                 # 试算提议（只打印，不改文件）
  python tools/batch.py KW ST --apply         # 应用提议，写回 SVG（仅改 id 属性）
  python tools/batch.py KW ST --apply --commit "batch 26: KW ST"   # 应用后 git 提交（不 push）

约束：
  - 只重命名“叶”魔数 id（pathNNNN/gNNNN/circleNNNN）；带 id 子元素的容器组不动。
  - 匹配顺序：质心落点（点入面）→ 并集 bbox IoU → 最近邻兜底；都不满足则跳过。
  - 命名规则见 svgname.base_id（字母后缀 → 大写 ISO；数字后缀 → 英文名 kebab）。
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import svgname as sn

NE_PATH = os.environ.get("NE_PATH", r"D:\work\other\svg-naming\data\ne_10m_admin_1_states_provinces.geojson")
SRC = os.path.join(ROOT, "src", "world-states-provinces.svg")

MAGIC = re.compile(r"(path|g|circle|polygon|ellipse|rect|use)\d+$")


def tag(e):
    return e.tag.split("}")[-1]


def country_leaves(g):
    """该国家组子树内的叶元素：{id: polys}。"""
    res = {}

    def rec(el):
        for c in el:
            if tag(c) not in ('path', 'g', 'svg', 'a', 'circle', 'polygon', 'polyline', 'ellipse', 'rect'):
                continue
            kids = [k for k in c if k.get('id')]
            i = c.get('id')
            if i and not kids:
                ps = sn.polys_of(c)
                if ps:
                    res[i] = ps
            else:
                rec(c)

    rec(g)
    return res


def _frame(b, N=256):
    if b[2] <= b[0] or b[3] <= b[1]:
        return None
    s = min(N / (b[2] - b[0]), N / (b[3] - b[1]))
    ox = (b[0] + b[2]) / 2 - N / 2 / s
    oy = (b[1] + b[3]) / 2 - N / 2 / s
    return s, ox, oy


def raster(polys, fr, N=256):
    if fr is None:
        return 0
    s, ox, oy = fr
    img = Image.new("1", (N, N), 0)
    dr = ImageDraw.Draw(img)
    for poly in polys:
        dr.polygon([((p[0] - ox) * s, (p[1] - oy) * s) for p in poly], fill=1)
    return int.from_bytes(img.tobytes(), "big")


def iou(a, b):
    u = (a | b).bit_count()
    return (a & b).bit_count() / u if u else 0.0


def compute_name(cc, f):
    """按 NE 要素生成基础 id。f: NE item dict。"""
    return sn.base_id(cc, f["iso"], f["name_en"])


def propose(cc, ne, root):
    g = {g.get("id"): g for g in root if tag(g) == "g" and g.get("id")}.get(cc)
    if g is None:
        return None
    leaves = country_leaves(g)
    magic = {k: v for k, v in leaves.items() if MAGIC.fullmatch(k)}
    if not magic:
        return None

    allp = [p for v in leaves.values() for p in v]
    b = sn.bbox([pt for p in allp for pt in p])
    fr = _frame(b)

    # 轮廓主路径：id == cc.lower()，否则全图最大叶
    outline = cc.lower() if cc.lower() in leaves else None
    if outline is None and len(leaves) > 2:
        areas = {k: sum(sn.poly_area_xy(p) for p in v) for k, v in leaves.items()}
        big = max(areas, key=lambda k: areas[k])
        rb = raster(leaves[big], fr)
        acc = 0
        for k, v in leaves.items():
            if k != big:
                acc |= raster(v, fr)
        if rb and acc and (rb & acc).bit_count() / (rb | acc).bit_count() > 0.7:
            outline = big
    magic = {k: v for k, v in magic.items() if k != outline}
    if not magic:
        return None

    feats = ne.buckets.get(cc, [])
    # 取 NE 定义 id 的键：优先 iso；若 iso 大量重复（如 MG 六省 vs 22 区）改用 name_en
    uniq_iso = {f["iso"] for f in feats}
    use_name = len(uniq_iso) < len(feats) * 0.6 and len(feats) > 2

    def feat_key(f):
        return (f["name_en"] or f["name"]) if use_name else f["iso"]

    by_key = {}
    for f in feats:
        rings_px = [[sn.lonlat_to_xy(c[1], c[0]) for c in r] for poly in f["rings"] for r in poly]
        key = feat_key(f)
        if not key:
            continue
        by_key[key] = (int.from_bytes(_raster_rings(rings_px, fr).tobytes(), "big"), f)

    res = {}
    for k, v in magic.items():
        c = sn.centroid(v)
        area = sum(sn.poly_area_xy(p) for p in v)
        if c is None:
            res[k] = dict(key=None, base=None, hit=None, iou=0.0, note="无质心", lat=None, lon=None, area=area)
            continue
        lat, lon = sn.xy_to_lonlat(*c)
        m = raster(v, fr)
        scores = sorted(((iou(m, mm), key) for key, (mm, f) in by_key.items()), reverse=True)
        top = scores[0] if scores else (0.0, None)
        second = scores[1] if len(scores) > 1 else (0.0, None)

        hit = ne.find(lat, lon, cc)
        key = base = None
        note = ""
        if hit is not None:
            hk = feat_key(hit)
            if hk in by_key:
                key, base = hk, compute_name(cc, hit)
                note = "质心落点"
        if key is None and top[0] >= 0.55 and (top[0] - second[0]) >= 0.12:
            key = top[1]
            base = by_key[key][1] and compute_name(cc, by_key[key][1])
            note = "IoU %.2f" % top[0]
        res[k] = dict(key=key, base=base, hit=hit, iou=top[0], note=note, lat=lat, lon=lon, area=area)
    return dict(res=res, outline=outline, use_name=use_name)


def _raster_rings(rings, fr, N=256):
    if fr is None:
        return Image.new("1", (N, N), 0)
    s, ox, oy = fr
    img = Image.new("1", (N, N), 0)
    dr = ImageDraw.Draw(img)
    for ring in rings:
        dr.polygon([((p[0] - ox) * s, (p[1] - oy) * s) for p in ring], fill=1)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("countries", nargs="+")
    ap.add_argument("--apply", action="store_true", help="写回 SVG（默认仅试算）")
    ap.add_argument("--commit", default=None, help="apply 后执行 git commit（不 push）")
    ap.add_argument("--out-csv", default=None, help="额外写出提议 CSV")
    args = ap.parse_args()

    ne = sn.NEIndex(NE_PATH)
    root = ET.parse(SRC).getroot()
    existing = {e.get("id") for e in root.iter() if e.get("id")}

    all_rows = []
    all_skip = []
    for cc in args.countries:
        cc = cc.upper()
        p = propose(cc, ne, root)
        if not p:
            print("%-4s 无魔数叶单元" % cc)
            continue
        res, outline = p["res"], p["outline"]
        import collections
        bybase = collections.defaultdict(list)
        for k, d in res.items():
            bybase[d["base"]].append((k, d))

        taken = set(existing)
        rows = []
        for base, items in bybase.items():
            if base is None:
                continue
            items.sort(key=lambda t: -t[1]["area"])
            for i, (k, d) in enumerate(items):
                new = base if i == 0 else "%s-%d" % (base, i)
                if new in taken:
                    j = 2
                    while "%s-%d" % (base, j) in taken:
                        j += 1
                    new = "%s-%d" % (base, j)
                taken.add(new)
                rows.append((cc, k, base, new, d["note"], round(d["iou"], 3), d["lat"], d["lon"]))
        # 跳过
        skips = []
        for k, d in res.items():
            if d["base"] is None:
                skips.append((cc, k, d["note"], round(d["iou"], 3)))
                all_skip.append((cc, k, d["note"], round(d["iou"], 3)))

        print("== %s 魔数 %d 提议 %d 跳过 %d%s" % (
            cc, len(res), len(rows), len(skips),
            "（轮廓=%s）" % outline if outline else ""))
        for r in rows:
            print("   %-18s -> %-26s %-10s (iou %.2f @%.2f,%.2f)" % (r[1], r[3], r[4], r[5], r[6], r[7]))
        for s in skips:
            print("   ✗ %-18s 跳过: %s (iou %.2f)" % (s[1], s[2], s[3]))
        all_rows += rows

    if args.out_csv:
        with open(args.out_csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["cc", "old_id", "base", "new_id", "note", "iou", "lat", "lon"])
            w.writerows(all_rows)

    if args.apply:
        if all_rows:
            ok = apply_and_verify(all_rows)
            if ok:
                ids = [e.get("id") for e in ET.parse(SRC).getroot().iter() if e.get("id")]
                print("\n应用 %d 个 id；全局 id 唯一性 %s (共 %d)" % (
                    len(all_rows), "OK" if len(ids) == len(set(ids)) else "FAIL", len(ids)))
            else:
                print("校验未通过，未写回。")
        else:
            print("无可应用的提议。")

    if args.apply and args.commit and all_rows:
        subprocess.run(["git", "add", SRC], check=True)
        subprocess.run(["git", "commit", "-m", args.commit], check=True)
        print("已提交: %s" % args.commit)


def apply_and_verify(rows):
    raw = open(SRC, encoding="utf-8").read()
    new = raw
    seen = set()
    problems = []
    for r in rows:
        old, newid = r[1], r[3]
        if newid in seen:
            problems.append((old, newid, "重复"))
            continue
        if not all(ord(ch) < 128 for ch in newid):
            problems.append((old, newid, "非 ASCII"))
            continue
        pat = 'id="%s"' % old
        if new.count(pat) != 1:
            problems.append((old, newid, "未找到/不唯一(%d)" % new.count(pat)))
            continue
        new = new.replace(pat, 'id="%s"' % newid, 1)
        seen.add(newid)
    if problems:
        print("发现异常，未写回：")
        for p in problems:
            print("  ", p)
        return False
    try:
        ET.fromstring(new)
    except Exception as e:
        print("XML 解析失败，未写回: %s" % e)
        return False
    open(SRC, "w", encoding="utf-8").write(new)
    return True


if __name__ == "__main__":
    main()