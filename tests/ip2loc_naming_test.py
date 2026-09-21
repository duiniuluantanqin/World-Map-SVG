#!/usr/bin/env python3
"""基于 ip2location.io 的 SVG id 连通性校验（替代 ip-api）。

与 ip_naming_test.py 的差异：
  - 数据源换成 ip2location.io（会员 key 限流更宽松，且返回完整的 region.code，形如
    "US-IL" / "VN-54" / "KR-11"，对数字码国家也能直接拼出 code）。
  - 匹配口径（正向）：把候选真实 IP 交给 ip2location，得到 (country_code, region.code, region.name)，
    拼出候选 id = region.code（字母码国家命中 CC-XX）或 CC-kebab(region.name)（数字码国家命中英文名），
    只要任一候选 id 存在于 SVG 已命名集合即为命中。

用法：
  python tests/ip2loc_naming_test.py --countries us,vn,kr        # 默认离线读缓存
  python tests/ip2loc_naming_test.py --countries us,vn,kr --refresh   # 联网刷新该国的 ip2location 缓存
  python tests/ip2loc_naming_test.py --offline                   # 只看缓存覆盖

key 通过环境变量 IP2LOCATION_KEY 或 --key 传入（不落库）。
"""
import argparse
import csv
import os
import re
import sys
import time
import urllib.request
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, HERE)

import ip_naming_test as base            # 复用 load_svg_ids / IP 池
from svgname import kebab

IP2LOC_URL = "https://api.ip2location.io/"
IP2LOC_DIR = os.path.join(HERE, "data", "ip2loc_lookup")  # <CC>.csv: ip,cc,region_code,region_name,city
MAGIC = re.compile(r"(path|g|circle)\d+$")


def ip2loc_path(cc):
    return os.path.join(IP2LOC_DIR, cc + ".csv")


def ip2loc_lookup(ip, key, timeout=20):
    """返回 (country_code, region_code, region_name, city) 或 None。"""
    url = IP2LOC_URL + "?key=" + key + "&ip=" + ip
    req = urllib.request.Request(url, headers={"User-Agent": "svg-naming/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except Exception:
        return None
    if not d or "country_code" not in d:
        return None
    reg = d.get("region") or {}
    return (d.get("country_code") or "", reg.get("code") or "", reg.get("name") or "",
            d.get("city_name") or "")


def load_cache(cc_list):
    cache = {}
    if cc_list is None:
        if not os.path.isdir(IP2LOC_DIR):
            return cache
        cc_list = sorted(os.path.splitext(f)[0] for f in os.listdir(IP2LOC_DIR) if f.endswith(".csv"))
    for cc in cc_list:
        p = ip2loc_path(cc)
        if not os.path.exists(p):
            continue
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.reader(f):
                if len(r) >= 1 and r[0] and not r[0].startswith("ip"):
                    cache[r[0]] = (r[1] if len(r) > 1 else "",
                                  r[2] if len(r) > 2 else "",
                                  r[3] if len(r) > 3 else "",
                                  r[4] if len(r) > 4 else "")
    return cache


def save_cache(cache, cc_list):
    by_cc = {}
    for ip, (cc, rc, rn, city) in cache.items():
        by_cc.setdefault(cc, []).append((ip, rc, rn, city))
    os.makedirs(IP2LOC_DIR, exist_ok=True)
    written = 0
    for cc in (cc_list or sorted(by_cc)):
        rows = by_cc.get(cc)
        if not rows:
            continue
        with open(ip2loc_path(cc), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ip", "cc", "region_code", "region_name", "city"])
            for ip, rc, rn, city in sorted(rows, key=lambda x: x[0]):
                w.writerow([ip, cc, rc, rn, city])
        written += 1
    print("已写 %d 个国家的 ip2location 缓存 -> %s" % (written, IP2LOC_DIR))


def candidate_ips(cc_list):
    """从仓库内已有 IP 池采集候选 IP：maxmind_samples + ipapi_lookup。返回 {cc: [ip,...]}。"""
    pool = {}
    for cc in cc_list:
        ips = set()
        # ipapi_lookup/<CC>.csv
        p = os.path.join(HERE, "data", "ipapi_lookup", cc + ".csv")
        if os.path.exists(p):
            with open(p, newline="", encoding="utf-8") as f:
                for r in list(csv.reader(f))[1:]:
                    if r and r[0]:
                        ips.add(r[0])
        # maxmind_samples/<CC>.csv
        p = os.path.join(HERE, "data", "maxmind_samples", cc + ".csv")
        if os.path.exists(p):
            with open(p, newline="", encoding="utf-8") as f:
                for r in list(csv.reader(f))[1:]:
                    if len(r) > 2 and r[2]:
                        ips.add(r[2])
        if ips:
            pool[cc] = sorted(ips)
    return pool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", default="")
    ap.add_argument("--refresh", action="store_true", help="联网刷新 ip2location 缓存")
    ap.add_argument("--offline", action="store_true", help="只看缓存覆盖，不联网")
    ap.add_argument("--key", default=os.environ.get("IP2LOCATION_KEY", ""))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pause", type=float, default=0.2)
    args = ap.parse_args()

    named, _ = base.load_svg_ids()
    print("SVG 已命名 id: %d（跳过魔数）" % len(named))

    # 过滤国家
    if args.countries:
        cc_list = sorted(set(c.upper().strip() for c in args.countries.split(",") if c.strip()))
    else:
        cc_list = sorted({m.group(1) for i in named for m in [re.fullmatch(r"([A-Z]{2})-[A-Za-z0-9-]+", i)] if m})

    pool = candidate_ips(cc_list)
    cache = load_cache(cc_list)
    print("候选 IP 池: %d 个国家" % len(pool))

    if args.refresh and not args.key:
        print("[!] --refresh 需要 key（环境变量 IP2LOCATION_KEY 或 --key）")
        return

    hit_by_id = {}
    got_extra = {}

    # 对每个国家的候选 IP 做 lookup，统计命中
    total_looked = 0
    for cc in cc_list:
        ips = pool.get(cc, [])
        if args.limit:
            ips = ips[:args.limit]
        for ip in ips:
            res = cache.get(ip)
            if res is None and args.refresh and args.key:
                res = ip2loc_lookup(ip, args.key)
                if res:
                    cache[ip] = res
                time.sleep(args.pause)
            if res is None:
                continue
            got_cc, region_code, region_name, city = res
            if not got_cc:
                continue
            cand = []
            if region_code and region_code not in ("-", ""):
                cand.append(region_code)
            if region_name:
                cand.append(got_cc + "-" + kebab(region_name))
            for cid in cand:
                if cid in named:
                    hit_by_id.setdefault(cid, []).append(ip)
                else:
                    got_extra.setdefault(cid, []).append(ip)

    if args.refresh:
        save_cache(cache, cc_list)

    # 干净字母 id 统计
    clean = [(m.group(1), m.group(2), i) for i in named
             for m in [re.fullmatch(r"([A-Z]{2})-([A-Z]{1,3})", i)] if m]
    if args.countries:
        clean = [(c, r, i) for (c, r, i) in clean if c in cc_list]
    hit_clean = [i for (c, r, i) in clean if i in hit_by_id]
    print("\n== ip2location 正向校验 ==")
    print("干净字母 id 命中: %d / %d (%.1f%%)" % (
        len(hit_clean), len(clean), 100.0 * len(hit_clean) / max(1, len(clean))))
    print("命中明细（非字母码/英文名 id）：")
    for cid, ips in sorted(hit_by_id.items()):
        if cid not in {i for (c, r, i) in clean}:
            print("   %-24s (例IP %s)" % (cid, ips[0]))
    if got_extra:
        print("\nip2location 能拼出但 SVG 不存在的 id（可能缺口）：")
        for cid, ips in sorted(got_extra.items()):
            print("   %-24s (例IP %s)" % (cid, ips[0]))


if __name__ == "__main__":
    main()