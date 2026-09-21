#!/usr/bin/env python3
"""用「行政单元质心 + 英文名」对 SVG 魔数 id 做最近邻命名（无多边形数据时的兜底）。

数据源：仅需每单元的 (name_en, lat, lon)，见 tools/data/admin1/<CC>.csv（列：iso,name_en,lat,lon）。
匹配：SVG 叶 path 的投影质心 → 换算经纬度 → 全局贪心最近邻（每县只配一次），
      按距离升序 + 冲突回退；距离异常（>120km）会标注 flag 供人工复核。

命名规则（同 svgname.base_id）：iso 后缀是字母 → `CC-XX`；否 → `CC-<英文名 kebab>`。

用法：
  python tools/batch_centroid.py KE                # 试算
  python tools/batch_centroid.py KE --apply --commit "batch 27: KE"   # 应用并提交（不 push）
"""
import argparse
import csv
import math
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import svgname as sn

SRC = os.path.join(ROOT, "src", "world-states-provinces.svg")
DATA = os.path.join(HERE, "data", "admin1")
MAGIC = re.compile(r"(path|g|circle)\d+$")
R = 6371.0


def tag(e):
    return e.tag.split("}")[-1]


def country_magic_leaves(g):
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
    return {k: v for k, v in res.items() if MAGIC.match(k)}


def gcd(a, b):
    return math.hypot(math.radians(b[0] - a[0]) * R,
                      math.radians(b[1] - a[1]) * R * math.cos(math.radians((a[0] + b[0]) / 2)))


def base_id(cc, iso, name_en):
    """按命名规范生成基础 id（同 svgname.base_id）：
    - ISO 后缀是字母 → `CC-SUFFIX`（大写）
    - ISO 后缀是数字 → `CC-数字`（直接使用数字码）
    - 无 ISO 码 → `CC-英文名 kebab-case`
    """
    suf = iso.split('-', 1)[1] if '-' in iso else ''
    if suf:
        if suf.isalpha() or suf.isdigit():
            return iso.upper()
    nm = sn.kebab(name_en)
    return "%s-%s" % (cc, nm) if nm else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cc")
    ap.add_argument("--data", default=None, help="质心 CSV（默认 tools/data/admin1/<CC>.csv）")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--commit", default=None)
    ap.add_argument("--max-dist", type=float, default=120.0, help="距离阈值(km)，超阈标注 flag")
    args = ap.parse_args()
    cc = args.cc.upper()

    dataf = args.data or os.path.join(DATA, cc + ".csv")
    if not os.path.exists(dataf):
        print("[!] 缺少质心数据 %s" % dataf)
        return

    units = []
    with open(dataf, newline="", encoding="utf-8") as f:
        rd = list(csv.reader(f))
    header = rd[0]
    rows = rd[1:] if header and header[0] in ("iso", "name_en", "name") else rd
    for r in rows:
        if not r or not any(x.strip() for x in r):
            continue
        # 支持 iso 空（用英文名）或有 iso 两种
        if len(r) >= 4 and r[1].strip() and r[2].strip():
            units.append((r[0].strip(), r[1].strip(), float(r[2]), float(r[3])))
        elif len(r) >= 3 and r[0].strip() and r[1].strip():
            units.append((cc + "-", r[0].strip(), float(r[1]), float(r[2])))

    root = ET.parse(SRC).getroot()
    groups = {g.get("id"): g for g in root if tag(g) == "g" and g.get("id")}
    g = groups.get(cc)
    if g is None:
        print("[!] 无国家组", cc)
        return
    magic = country_magic_leaves(g)
    if not magic:
        print(cc, "无魔数叶")
        return

    # 每个 path 质心 -> (lat, lon)
    pts = {}
    for k, v in magic.items():
        c = sn.centroid(v)
        pts[k] = sn.xy_to_lonlat(*c) if c else None

    # 全局贪心最近邻
    assigned = set()   # 已占县名
    rows_out = []
    skip = []
    probe = []
    for k in sorted(magic, key=lambda x: -sum(sn.poly_area_xy(p) for p in magic[x])):
        c = pts[k]
        if c is None:
            skip.append((k, "无质心"))
            continue
        ds = sorted((gcd(c, (u[2], u[3])), u) for u in units)
        best = None
        for d, u in ds:
            if u[1] not in assigned:
                best = (d, u)
                break
        if best is None:
            skip.append((k, "无可用单元"))
            continue
        d, u = best
        new = base_id(cc, u[0], u[1])
        assigned.add(u[1])
        flag = "远(%.0fkm)" % d if d > args.max_dist else ""
        probe.append((k, new, u[1], d, flag))

    # 处理同名（split 块）：同 base_id 多块 → 加后缀
    import collections
    by = collections.defaultdict(list)
    for k, new, name, d, flag in probe:
        by[new].append((k, d, flag))
    existing = {e.get("id") for e in root.iter() if e.get("id")}
    taken = set(existing)
    final = []
    for new, items in by.items():
        items.sort(key=lambda x: -max((sum(sn.poly_area_xy(p) for p in magic[x[0]])), 0))
        for i, (k, d, flag) in enumerate(items):
            nid = new if i == 0 else "%s-%d" % (new, i)
            if nid in taken:
                j = 2
                while "%s-%d" % (new, j) in taken:
                    j += 1
                nid = "%s-%d" % (new, j)
            taken.add(nid)
            final.append((k, nid, d, flag))

    print("== %s 魔数 %d 单元 %d 提议 %d 跳过 %d" % (cc, len(magic), len(units), len(final), len(skip)))
    for k, nid, d, flag in sorted(final, key=lambda x: -x[2]):
        print("   %-14s -> %-26s %6.1f km %s" % (k, nid, d, flag))
    for k, why in skip:
        print("   ✗ %-14s 跳过: %s" % (k, why))

    if args.apply:
        if final:
            ok = _apply(final)
            if ok:
                ids = [e.get("id") for e in ET.parse(SRC).getroot().iter() if e.get("id")]
                print("\n应用 %d 个 id；全局唯一性 %s (共 %d)" % (
                    len(final), "OK" if len(ids) == len(set(ids)) else "FAIL", len(ids)))
            else:
                print("校验未通过，未写回。")
        else:
            print("无可应用提议。")
    if args.apply and args.commit and final:
        subprocess.run(["git", "add", SRC], check=True)
        subprocess.run(["git", "commit", "-m", args.commit], check=True)
        print("已提交: %s" % args.commit)


def _apply(rows):
    raw = open(SRC, encoding="utf-8").read()
    new = raw
    seen = set()
    problems = []
    for k, nid, d, flag in rows:
        if nid in seen:
            problems.append((k, nid, "重复"))
            continue
        if not all(ord(ch) < 128 for ch in nid):
            problems.append((k, nid, "非 ASCII"))
            continue
        pat = 'id="%s"' % k
        if new.count(pat) != 1:
            problems.append((k, nid, "未找到/不唯一(%d)" % new.count(pat)))
            continue
        new = new.replace(pat, 'id="%s"' % nid, 1)
        seen.add(nid)
    if problems:
        print("异常，未写回：")
        for p in problems:
            print("  ", p)
        return False
    try:
        ET.fromstring(new)
    except Exception as e:
        print("XML 失败: %s" % e)
        return False
    open(SRC, "w", encoding="utf-8").write(new)
    return True


if __name__ == "__main__":
    main()