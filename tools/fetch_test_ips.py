#!/usr/bin/env python3
"""为每个已命名国家补充 IP 测试数据。

从 maxmind 样本中提取 IP，用 ip2location API 查询后保存到缓存。

用法：
  python tools/fetch_test_ips.py --countries KW,KI  # 补充指定国家
  python tools/fetch_test_ips.py --all              # 补充所有有 maxmind 样本的国家
  python tools/fetch_test_ips.py --missing          # 只补充缺失 ip2loc 缓存的国家
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MAXMIND_DIR = os.path.join(ROOT, "tests", "data", "maxmind_samples")
IP2LOC_DIR = os.path.join(ROOT, "tests", "data", "ip2loc_lookup")
IPAPI_DIR = os.path.join(ROOT, "tests", "data", "ipapi_lookup")

IP2LOCATION_KEY = os.environ.get("IP2LOCATION_KEY", "2A7EF69522DEDB7664CD69A4FA11D5A0")
IP2LOC_URL = "https://api.ip2location.io/"


def ip2loc_lookup(ip, key, timeout=15):
    """调用 ip2location API"""
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


def get_named_countries():
    """从 SVG 中提取已命名的国家代码"""
    import re
    svg_path = os.path.join(ROOT, "src", "world-states-provinces.svg")
    with open(svg_path, encoding="utf-8") as f:
        content = f.read()
    
    ids = re.findall(r'\bid="([^"]+)"', content)
    ccs = set()
    for i in ids:
        # 匹配 XX-YYY 格式（省份）或 xx 格式（国家轮廓）
        m = re.fullmatch(r"([A-Z]{2})-([A-Z0-9a-z-]+)", i)
        if m:
            ccs.add(m.group(1))
        elif len(i) == 2 and i.isalpha():
            ccs.add(i.upper())
    return ccs


def load_existing_ips(cc):
    """加载已有的 IP 缓存"""
    cache_file = os.path.join(IP2LOC_DIR, f"{cc}.csv")
    existing = {}
    if os.path.exists(cache_file):
        with open(cache_file, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                existing[row["ip"]] = row
    return existing


def load_maxmind_ips(cc):
    """从 maxmind 样本和 ipapi_lookup 中加载 IP"""
    ips = []
    
    # maxmind_samples
    mm_file = os.path.join(MAXMIND_DIR, f"{cc}.csv")
    if os.path.exists(mm_file):
        with open(mm_file, newline="", encoding="utf-8") as f:
            rd = csv.reader(f)
            header = next(rd, None)
            for row in rd:
                if len(row) >= 3 and row[2]:
                    ips.append(row[2])
                elif len(row) >= 1 and row[0] and "." in row[0]:
                    parts = row[0].split("/")
                    if parts:
                        ips.append(parts[0])
    
    # ipapi_lookup
    ipapi_file = os.path.join(IPAPI_DIR, f"{cc}.csv")
    if os.path.exists(ipapi_file):
        with open(ipapi_file, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                if row.get("ip"):
                    ips.append(row["ip"])
    
    return ips[:20]  # 限制每国最多 20 个


def save_cache(cc, data):
    """保存 IP 缓存"""
    os.makedirs(IP2LOC_DIR, exist_ok=True)
    cache_file = os.path.join(IP2LOC_DIR, f"{cc}.csv")
    with open(cache_file, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, ["ip", "cc", "region_code", "region_name", "city"])
        w.writeheader()
        for ip in sorted(data.keys()):
            w.writerow(data[ip])
    print(f"  [saved] {cache_file} ({len(data)} IPs)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", help="指定国家代码，逗号分隔")
    ap.add_argument("--all", action="store_true", help="处理所有有 maxmind 样本的国家")
    ap.add_argument("--missing", action="store_true", help="只处理缺失 ip2loc 缓存的国家")
    ap.add_argument("--key", default=IP2LOCATION_KEY)
    ap.add_argument("--limit", type=int, default=5, help="每国最多查询 IP 数")
    ap.add_argument("--pause", type=float, default=0.3, help="API 调用间隔（秒）")
    args = ap.parse_args()

    if not args.key:
        print("[!] 需要提供 IP2LOCATION_KEY")
        return

    named_ccs = get_named_countries()
    print(f"SVG 已命名国家: {len(named_ccs)} 个")

    to_process = []
    if args.countries:
        to_process = [c.strip().upper() for c in args.countries.split(",")]
    elif args.missing:
        for cc in named_ccs:
            cache_file = os.path.join(IP2LOC_DIR, f"{cc}.csv")
            if not os.path.exists(cache_file):
                mm_file = os.path.join(MAXMIND_DIR, f"{cc}.csv")
                if os.path.exists(mm_file):
                    to_process.append(cc)
    elif args.all:
        for cc in named_ccs:
            mm_file = os.path.join(MAXMIND_DIR, f"{cc}.csv")
            if os.path.exists(mm_file):
                to_process.append(cc)
    else:
        print("请指定 --countries, --all 或 --missing")
        return

    print(f"待处理: {len(to_process)} 个国家")
    
    total_new = 0
    for idx, cc in enumerate(sorted(to_process), 1):
        print(f"\n[{idx}/{len(to_process)}] {cc}")
        
        existing = load_existing_ips(cc)
        mm_ips = load_maxmind_ips(cc)
        
        print(f"  已有 IP: {len(existing)}, maxmind 样本: {len(mm_ips)}")
        
        new_count = 0
        for ip in mm_ips[:args.limit]:
            if ip in existing:
                continue
            
            result = ip2loc_lookup(ip, args.key)
            if result:
                existing[ip] = result
                new_count += 1
                total_new += 1
            
            time.sleep(args.pause)
        
        if new_count > 0:
            save_cache(cc, existing)
        else:
            print(f"  [skip] 无新增 IP")
    
    print(f"\n完成！共新增 {total_new} 条 IP 记录")


if __name__ == "__main__":
    main()
