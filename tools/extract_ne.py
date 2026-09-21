#!/usr/bin/env python3
"""从 Natural Earth 10m admin-1 提取某国的 (iso, 名称, 中心点) 生成质心 CSV。

用于：openadmindata 质心缺/错位时，用 NE 的 label point（latidude/longitude）兜底。
注意 NE 的 `iso_3166_2` 偶有错（如 MG 是 6 省旧码、而特征是 22 区），故名称字段可选。

用法：
  python tools/extract_ne.py MG --name name        # 用本地名（MG 的 22 区名在 name 字段）
  python tools/extract_ne.py MG --name name_en
"""
import argparse
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "admin1")
NE = os.environ.get("NE_PATH", r"D:\work\other\svg-naming\data\ne_10m_admin_1_states_provinces.geojson")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cc")
    ap.add_argument("--name", default="name_en", choices=["name", "name_en"])
    ap.add_argument("--no-iso", action="store_true", help="不写 NE iso 码（当 NE iso 与本层级不一致时，如 MG 的 22 区 vs 6 省码）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    cc = args.cc.upper()

    d = json.load(open(NE, encoding="utf-8"))
    rows = []
    for ft in d["features"]:
        p = ft["properties"]
        if p.get("iso_a2") != cc:
            continue
        name = p.get(args.name, "") or p.get("name", "") or ""
        iso = (p.get("iso_3166_2") or "").strip() or (cc + "-")
        if args.no_iso:
            iso = ""
        lat = p.get("latitude")
        lon = p.get("longitude")
        if name and lat is not None and lon is not None:
            rows.append((iso, name, lat, lon))

    os.makedirs(OUT, exist_ok=True)
    path = args.out or os.path.join(OUT, cc + ".csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iso", "name_en", "lat", "lon"])
        # 去重（按 name）
        seen = set()
        for iso, name, lat, lon in rows:
            if name in seen:
                continue
            seen.add(name)
            w.writerow([iso, name, lat, lon])
    print("已写 %d 个单元 -> %s（名称字段 %s）" % (len(seen), path, args.name))


if __name__ == "__main__":
    main()