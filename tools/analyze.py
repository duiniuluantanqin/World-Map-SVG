#!/usr/bin/env python3
"""分析每个剩余组：SVG 魔数叶单元数 vs NE admin-1 要素数，辅助判断可自动命名性。"""
import json
import re
import os
import sys
import xml.etree.ElementTree as ET
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svgname import leaf_regions, NEIndex

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NE_PATH = os.environ.get("NE_PATH", r"D:\work\other\svg-naming\data\ne_10m_admin_1_states_provinces.geojson")
SRC = os.path.join(ROOT, "src", "world-states-provinces.svg")

MAGIC = re.compile(r"(path|g|circle|polygon|ellipse|rect|use)\d+$")


def tag(e):
    return e.tag.split("}")[-1]


def main():
    ne = NEIndex(NE_PATH)
    root = ET.parse(SRC).getroot()
    # 分组：国家组 -> [叶子魔数 id]
    leaf = leaf_regions(root)
    # 建立 叶id -> 父国家组
    by_country = {}

    def rec(el, anc):
        for c in el:
            if tag(c) not in ('path', 'g', 'svg', 'a', 'circle', 'polygon', 'polyline', 'ellipse', 'rect'):
                continue
            i = c.get('id')
            kids = [k for k in c if k.get('id')]
            if i and not kids:
                if MAGIC.fullmatch(i):
                    by_country.setdefault(anc[0] if anc else '?', []).append(i)
            else:
                rec(c, anc + ([i] if i else []))

    for g in root:
        if tag(g) == 'g' and g.get('id'):
            rec(g, [g.get('id')])
        else:
            rec(g, [])

    rows = []
    for cc in sorted(by_country):
        n = len(by_country[cc])
        ne_items = ne.buckets.get(cc, [])
        ne_n = len({x['iso'] for x in ne_items})  # 唯一 iso 数量
        # NE 是否字母码/数字码
        kinds = set()
        for x in ne_items:
            suf = x['iso'].split('-', 1)[1] if '-' in x['iso'] else ''
            kinds.add('letter' if (suf and suf.isalpha()) else ('digit' if suf.isdigit() else 'none'))
        rows.append((cc, n, len(ne_items), ne_n, ','.join(sorted(kinds))))

    print("%-10s %6s %6s %6s  %s" % ("cc", "svg", "ne_feat", "ne_uniq", "kind"))
    for cc, n, nf, nu, k in rows:
        match = "OK" if (n == nu or n == nf) else "MISMATCH"
        print("%-10s %6d %6d %6d  %-6s %s" % (cc, n, nf, nu, k, match))


if __name__ == "__main__":
    main()