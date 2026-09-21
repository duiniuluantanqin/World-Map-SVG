#!/usr/bin/env python3
"""枚举 SVG 中剩余魔数 id（pathNNNN/gNNNN/circleNNNN 等），按父国家分组统计。

用法：
  python tools/enumerate.py                     # 统计两个 svg
  python tools/enumerate.py --file src/world-states.svg
  python tools/enumerate.py --detail            # 逐条列出（默认只汇总）
"""
import argparse
import re
import os
import sys
import collections
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MAGIC = re.compile(r"(path|g|circle|polygon|ellipse|rect|use)\d+$")
PROV = os.path.join(ROOT, "src", "world-states-provinces.svg")
STATES = os.path.join(ROOT, "src", "world-states.svg")


def tag(el):
    return el.tag.split("}")[-1]


def leaf_regions_with_country(root):
    """返回 {leaf_id: [country_group_ids...]}，仅叶元素（有 id 且无带 id 的子元素的 path/g）。

    走树时维护祖先国家组 id 栈。"""
    res = {}

    def rec(el, anc):
        for c in el:
            if tag(c) not in ("path", "g", "svg", "a", "circle", "polygon", "polyline", "ellipse", "rect"):
                continue
            i = c.get("id")
            kids = [k for k in c if k.get("id")]
            if i and not kids:
                res.setdefault(i, []).extend(anc)
            else:
                rec(c, anc + ([i] if i else []))

    for g in root:
        if tag(g) == "g" and g.get("id"):
            rec(g, [g.get("id")])
        else:
            rec(g, [])
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="")
    ap.add_argument("--detail", action="store_true")
    args = ap.parse_args()

    files = [args.file] if args.file else [PROV, STATES]
    for f in files:
        if not os.path.exists(f):
            print("缺失: %s" % f)
            continue
        root = ET.parse(f).getroot()
        leaf = leaf_regions_with_country(root)
        by_country = collections.defaultdict(list)
        others = []
        for lid, anc in leaf.items():
            if MAGIC.fullmatch(lid):
                cc = anc[0] if anc else "?"
                by_country[cc].append(lid)
        # 只保留仍有魔数的国家
        by_country = {cc: ids for cc, ids in by_country.items() if ids}
        total = sum(len(v) for v in by_country.values())
        rel = os.path.relpath(f, ROOT)
        print("=" * 60)
        print("%s : 剩余魔数 id 共 %d 条，分布在 %d 个组" % (rel, total, len(by_country)))
        for cc in sorted(by_country):
            ids = by_country[cc]
            print("  %-4s %3d" % (cc, len(ids)))
            if args.detail:
                for i in ids:
                    print("        %s" % i)


if __name__ == "__main__":
    main()