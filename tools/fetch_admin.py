#!/usr/bin/env python3
"""从 openadmindata.org 拉取某国行政区（质心 + 英文名 + ISO 码），生成 tools/data/admin1/<CC>.csv。

用法：
  python tools/fetch_admin.py KE          # 默认取该国的第一级（meta.levels[0]）
  python tools/fetch_admin.py KE --level county
  python tools/fetch_admin.py KE --level region   # 指定层级 key

产出的 CSV 列：iso,name_en,lat,lon（用于 batch_centroid.py 的最近邻命名）。
来源：openadmindata.org（OCHA COD-AB + geoBoundaries，CC BY-IGO），仅拉质心/名称/编码，非多边形。
"""
import argparse
import csv
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "admin1")
BASE = "https://openadmindata.org/api/v1/countries/{cc}.json"


def fetch(cc):
    req = urllib.request.Request(BASE.format(cc=cc.lower()), headers={"User-Agent": "svg-naming/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=30))


def normalize_iso(raw):
    """把 'KE030' 之类归一为 'KE-30'（尽量对齐 ISO 3166-2 的 CC-NN）。"""
    raw = (raw or "").strip()
    if "-" in raw:
        return raw
    m = len(raw)
    for cut in (2, 3):
        if m > cut and raw[cut].isdigit():
            return raw[:cut] + "-" + str(int(raw[cut:]))
    return raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cc")
    ap.add_argument("--level", default=None)
    args = ap.parse_args()
    cc = args.cc.upper()

    d = fetch(cc)
    meta = d.get("meta", {})
    levels = meta.get("levels", [])
    level = args.level or (levels[0]["key"] if levels else None)
    if level is None:
        print("[!] 无法确定层级：", cc)
        return
    data = d.get("data", {}).get(level)
    if not data:
        print("[!] 该层级无数据：", cc, level)
        return

    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, cc + ".csv")
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iso", "name_en", "lat", "lon"])
        for r in data:
            iso = normalize_iso(r.get("id", ""))
            name = r.get("name_en") or r.get("name_local") or ""
            lat = r.get("lat")
            lon = r.get("lon")
            if name and lat is not None and lon is not None:
                w.writerow([iso, name, lat, lon])
                n += 1
    print("已写 %d 个单元 -> %s（层级 %s）" % (n, path, level))


if __name__ == "__main__":
    main()