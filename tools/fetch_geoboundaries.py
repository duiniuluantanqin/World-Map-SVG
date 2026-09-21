#!/usr/bin/env python3
"""从 geoBoundaries（GitHub LFS 媒体源）拉某国 admin 边界，算多边形质心 → data/admin1/<CC>.csv。

geoBoundaries 的 raw 文件是 Git LFS 指针，实际内容在 media.githubusercontent.com，故用媒体 URL。
数据：geoBoundaries gbOpen（admin 边界，CC BY 4.0）；ADM{level} 里 ADM1=一级行政区、ADM2=二级，可对齐
「图比 NE 粗/细」的层级错配。

用法：
  python tools/fetch_geoboundaries.py BF        # ADM1
  python tools/fetch_geoboundaries.py BF --level 2
"""
import argparse
import csv
import json
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "data", "admin1")
URL = "https://media.githubusercontent.com/media/wmgeolab/geoBoundaries/main/releaseData/gbOpen/{iso3}/ADM{level}/geoBoundaries-{iso3}-ADM{level}.geojson"


def fetch(iso3, level):
    url = URL.format(iso3=iso3, level=level)
    req = urllib.request.Request(url, headers={"User-Agent": "svg-naming/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=60))


def ring_centroid(ring):
    """外环（[lon,lat] 列表）的面积加权质心，返回 (lon, lat)；退化返回 None。"""
    n = len(ring)
    if n < 3:
        return None
    # 闭合
    pts = ring if not (ring[0] == ring[-1]) else ring
    A = 0.0
    Cx = 0.0
    Cy = 0.0
    for i in range(len(pts) - 1):
        x0, y0 = pts[i][0], pts[i][1]
        x1, y1 = pts[i + 1][0], pts[i + 1][1]
        cr = x0 * y1 - x1 * y0
        A += cr
        Cx += (x0 + x1) * cr
        Cy += (y0 + y1) * cr
    if abs(A) < 1e-12:
        return None
    return (Cx / (3.0 * A), Cy / (3.0 * A))  # 除以 6A 的一半面积：这里 A=signed*2，故 3A


def feature_centroid(geom):
    """Polygon/MultiPolygon 取最大外环的质心。"""
    best = None
    best_area = -1

    def visit(poly):
        nonlocal best, best_area
        ring = poly[0]
        if len(ring) < 3:
            return
        # 面积（用于挑最大）
        a = 0.0
        for i in range(len(ring) - 1):
            a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
        a = abs(a) / 2.0
        if a > best_area:
            best_area = a
            c = ring_centroid(ring)
            if c:
                best = c

    if geom["type"] == "Polygon":
        visit(geom["coordinates"])
    elif geom["type"] == "MultiPolygon":
        for poly in geom["coordinates"]:
            visit(poly)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cc", help="ISO 3166-1 alpha-2，如 BF")
    ap.add_argument("--level", type=int, default=1)
    args = ap.parse_args()
    cc = args.cc.upper()
    iso3 = cc  # geoBoundaries 的 iso3 用 alpha-3；这里接受 alpha-2，尝试转 alpha-3
    # 简单 alpha2→alpha3（仅覆盖本项目涉及的国家，缺失时直接要求传 alpha-3）
    a2to3 = {"BF": "BFA", "GN": "GIN", "SI": "SVN", "LK": "LKA", "NP": "NPL",
             "BT": "BTN", "BA": "BIH", "AZ": "AZE", "CV": "CPV", "LV": "LVA",
             "PS": "PSE", "MG": "MDG", "MW": "MWI", "MK": "MKD", "KE": "KEN",
             "CY": "CYP"}
    iso3 = a2to3.get(cc, cc)
    if len(iso3) != 3:
        iso3 = cc

    d = fetch(iso3, args.level)
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, cc + ".csv")
    n = 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["iso", "name_en", "lat", "lon"])
        for ft in d["features"]:
            pr = ft["properties"]
            name = pr.get("shapeName") or pr.get("NAME_1") or ""
            c = feature_centroid(ft["geometry"])
            if not name or not c:
                continue
            lon, lat = c
            w.writerow([cc + "-", name, round(lat, 5), round(lon, 5)])
            n += 1
    print("已写 %d 个单元 -> %s（geoBoundaries ADM%d）" % (n, path, args.level))


if __name__ == "__main__":
    main()