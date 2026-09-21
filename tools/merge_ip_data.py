#!/usr/bin/env python3
"""合并 tests/data 下的三个 IP 数据源到 ip2loc_lookup。

数据源：
  - maxmind_samples/: cc,region,ip,name (99 国)
  - ipapi_lookup/: ip,cc,region,city (31 国)
  - ip2loc_lookup/: ip,cc,region_code,region_name,city (目标)

合并策略：
  1. 读取所有现有数据
  2. 用 ip2location API 查询缺失 region_code 的 IP
  3. 统一写入 ip2loc_lookup/<CC>.csv

用法：
  python tools/merge_ip_data.py --dry-run    # 预览
  python tools/merge_ip_data.py --merge      # 合并并写入
  python tools/merge_ip_data.py --refresh    # 重新查询所有 IP
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MAXMIND_DIR = os.path.join(ROOT, "tests", "data", "maxmind_samples")
IPAPI_DIR = os.path.join(ROOT, "tests", "data", "ipapi_lookup")
IP2LOC_DIR = os.path.join(ROOT, "tests", "data", "ip2loc_lookup")

IP2LOCATION_KEY = os.environ.get("IP2LOCATION_KEY", "2A7EF69522DEDB7664CD69A4FA11D5A0")
IP2LOC_URL = "https://api.ip2location.io/"


def ip2loc_lookup(ip, key, timeout=15):
    """调用 ip2location API，返回完整信息"""
    url = f"{IP2LOC_URL}?key={key}&ip={ip}"
    req = urllib.request.Request(url, headers={"User-Agent": "svg-naming/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
            if "country_code" in d:
                reg = d.get("region") or {}
                return {
                    "ip": ip,
                    "cc": d.get("country_code", ""),
                    "region_code": reg.get("code", ""),
                    "region_name": reg.get("name", ""),
                    "city": d.get("city_name", "")
                }
    except Exception as e:
        print(f"  [error] {ip}: {e}")
    return None


def load_maxmind():
    """加载 maxmind_samples 数据"""
    data = defaultdict(list)  # {cc: [{ip, region, name}]}
    if not os.path.isdir(MAXMIND_DIR):
        return data
    
    for fname in os.listdir(MAXMIND_DIR):
        if not fname.endswith(".csv"):
            continue
        cc = fname.replace(".csv", "")
        fpath = os.path.join(MAXMIND_DIR, fname)
        with open(fpath, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                if row.get("ip"):
                    data[cc].append({
                        "ip": row["ip"],
                        "region": row.get("region", ""),
                        "name": row.get("name", "")
                    })
    return data


def load_ipapi():
    """加载 ipapi_lookup 数据"""
    data = defaultdict(list)  # {cc: [{ip, region, city}]}
    if not os.path.isdir(IPAPI_DIR):
        return data
    
    for fname in os.listdir(IPAPI_DIR):
        if not fname.endswith(".csv"):
            continue
        cc = fname.replace(".csv", "")
        fpath = os.path.join(IPAPI_DIR, fname)
        with open(fpath, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                if row.get("ip"):
                    data[cc].append({
                        "ip": row["ip"],
                        "region": row.get("region", ""),
                        "city": row.get("city", "")
                    })
    return data


def load_ip2loc():
    """加载 ip2loc_lookup 数据"""
    data = defaultdict(dict)  # {cc: {ip: {region_code, region_name, city}}}
    if not os.path.isdir(IP2LOC_DIR):
        return data
    
    for fname in os.listdir(IP2LOC_DIR):
        if not fname.endswith(".csv"):
            continue
        cc = fname.replace(".csv", "")
        fpath = os.path.join(IP2LOC_DIR, fname)
        with open(fpath, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                if row.get("ip"):
                    data[cc][row["ip"]] = {
                        "region_code": row.get("region_code", ""),
                        "region_name": row.get("region_name", ""),
                        "city": row.get("city", "")
                    }
    return data


def save_ip2loc(data):
    """保存到 ip2loc_lookup"""
    os.makedirs(IP2LOC_DIR, exist_ok=True)
    total = 0
    for cc in sorted(data.keys()):
        ips = data[cc]
        if not ips:
            continue
        fpath = os.path.join(IP2LOC_DIR, f"{cc}.csv")
        with open(fpath, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["ip", "cc", "region_code", "region_name", "city"])
            w.writeheader()
            for ip in sorted(ips.keys()):
                info = ips[ip]
                w.writerow({
                    "ip": ip,
                    "cc": cc,
                    "region_code": info.get("region_code", ""),
                    "region_name": info.get("region_name", ""),
                    "city": info.get("city", "")
                })
        total += len(ips)
    print(f"已保存 {len(data)} 个国家，共 {total} 条 IP 记录")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    ap.add_argument("--merge", action="store_true", help="合并数据源（不重新查询）")
    ap.add_argument("--refresh", action="store_true", help="重新查询所有 IP")
    ap.add_argument("--key", default=IP2LOCATION_KEY)
    ap.add_argument("--pause", type=float, default=0.3)
    args = ap.parse_args()

    print("加载数据源...")
    maxmind = load_maxmind()
    ipapi = load_ipapi()
    ip2loc = load_ip2loc()

    print(f"  maxmind_samples: {len(maxmind)} 国")
    print(f"  ipapi_lookup: {len(ipapi)} 国")
    print(f"  ip2loc_lookup: {len(ip2loc)} 国")

    # 合并所有 IP
    all_ips_by_cc = defaultdict(set)
    for cc, ips in maxmind.items():
        for item in ips:
            all_ips_by_cc[cc].add(item["ip"])
    for cc, ips in ipapi.items():
        for item in ips:
            all_ips_by_cc[cc].add(item["ip"])
    for cc, ips in ip2loc.items():
        for ip in ips:
            all_ips_by_cc[cc].add(ip)

    print(f"\n合并后共 {len(all_ips_by_cc)} 国，{sum(len(v) for v in all_ips_by_cc.values())} 条 IP")

    if args.dry_run:
        for cc in sorted(all_ips_by_cc.keys()):
            ips = all_ips_by_cc[cc]
            print(f"  {cc}: {len(ips)} IPs")
        return

    # 需要查询的 IP
    need_query = []
    if args.refresh:
        # 重新查询所有
        for cc, ips in all_ips_by_cc.items():
            for ip in ips:
                need_query.append((cc, ip))
    elif args.merge:
        # 只查询没有 region_code 的
        for cc, ips in all_ips_by_cc.items():
            for ip in ips:
                if ip not in ip2loc.get(cc, {}) or not ip2loc[cc].get(ip, {}).get("region_code"):
                    need_query.append((cc, ip))
    else:
        print("请指定 --merge 或 --refresh")
        return

    print(f"\n需查询 {len(need_query)} 条 IP...")
    
    # 查询并更新
    updated = 0
    for idx, (cc, ip) in enumerate(need_query, 1):
        if idx % 10 == 0:
            print(f"  进度: {idx}/{len(need_query)}")
        
        result = ip2loc_lookup(ip, args.key)
        if result:
            ip2loc.setdefault(cc, {})[ip] = {
                "region_code": result.get("region_code", ""),
                "region_name": result.get("region_name", ""),
                "city": result.get("city", "")
            }
            updated += 1
        time.sleep(args.pause)

    print(f"\n已更新 {updated} 条记录")
    
    # 保存
    save_ip2loc(ip2loc)


if __name__ == "__main__":
    main()
