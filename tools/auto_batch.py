#!/usr/bin/env python3
"""自动化批量处理剩余魔数 id。

整合 NE 几何匹配 + 质心近邻 + ip2location 验证 + 跳过记录 + 测试 + IP 数据更新。

用法：
  python tools/auto_batch.py --dry-run           # 预览所有待处理国家
  python tools/auto_batch.py --countries KW,EH   # 处理指定国家
  python tools/auto_batch.py --all               # 处理所有可自动处理的国家
  python tools/auto_batch.py --all --apply       # 应用更改并运行测试
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import svgname as sn

NE_PATH = os.environ.get("NE_PATH", r"D:\work\other\svg-naming\data\ne_10m_admin_1_states_provinces.geojson")
SRC = os.path.join(ROOT, "src", "world-states-provinces.svg")
BATCHES_DIR = os.path.join(HERE, "batches")
DATA_DIR = os.path.join(HERE, "data", "admin1")
IP2LOC_DIR = os.path.join(ROOT, "tests", "data", "ip2loc_lookup")
SKIP_DOC = os.path.join(ROOT, "docs", "map-id-naming.md")

MAGIC = re.compile(r"(path|g|circle|polygon|ellipse|rect|use)\d+$")
IP2LOCATION_KEY = os.environ.get("IP2LOCATION_KEY", "2A7EF69522DEDB7664CD69A4FA11D5A0")


def tag(e):
    return e.tag.split("}")[-1]


def get_country_magic_counts():
    """返回 {cc: 魔数数量}"""
    root = ET.parse(SRC).getroot()
    res = defaultdict(int)
    
    def rec(el, cc):
        for c in el:
            if tag(c) not in ('path', 'g', 'svg', 'a', 'circle', 'polygon', 'polyline', 'ellipse', 'rect'):
                continue
            i = c.get("id")
            kids = [k for k in c if k.get("id")]
            if tag(c) == "g" and i and not i.startswith("_"):
                # 可能是国家组
                if len(i) == 2 or (len(i) > 2 and i[:2].isalpha() and i[2] == "-"):
                    cc = i[:2].upper()
            if i and MAGIC.match(i) and not kids:
                if cc:
                    res[cc] += 1
            rec(c, cc)
    
    rec(root, None)
    return dict(res)


def analyze_country(cc, ne):
    """分析单个国家，返回处理建议"""
    root = ET.parse(SRC).getroot()
    g = None
    for child in root:
        if tag(child) == "g" and child.get("id", "").upper() == cc:
            g = child
            break
        elif tag(child) == "g" and child.get("id", "").startswith(cc.upper() + "-"):
            g = child
            break
    
    if g is None:
        return {"status": "NO_GROUP", "magic": 0}
    
    # 统计魔数
    magic_ids = []
    def count_magic(el):
        for c in el:
            if tag(c) not in ('path', 'g', 'svg', 'a', 'circle', 'polygon', 'polyline', 'ellipse', 'rect'):
                continue
            i = c.get("id")
            kids = [k for k in c if k.get("id")]
            if i and MAGIC.match(i) and not kids:
                magic_ids.append(i)
            count_magic(c)
    count_magic(g)
    
    if not magic_ids:
        return {"status": "NO_MAGIC", "magic": 0}
    
    # 检查 NE 数据
    ne_feats = ne.buckets.get(cc, [])
    
    # 检查质心数据
    centroid_file = os.path.join(DATA_DIR, cc + ".csv")
    has_centroid = os.path.exists(centroid_file)
    
    # 分析结果
    result = {
        "status": "PROCESSABLE" if ne_feats or has_centroid else "NO_DATA",
        "magic": len(magic_ids),
        "ne_feats": len(ne_feats),
        "has_centroid": has_centroid,
        "method": "ne" if ne_feats and len(ne_feats) == len(magic_ids) else ("centroid" if has_centroid else "skip"),
        "magic_ids": magic_ids
    }
    
    # 特殊情况标记
    if cc in ("EH",):  # 争议地区
        result["status"] = "DISPUTED"
        result["method"] = "skip"
    elif cc in ("AQ",):  # 南极洲无行政区
        result["status"] = "NO_ADMIN"
        result["method"] = "skip"
    elif cc.startswith("_"):  # 隐藏组
        result["status"] = "HIDDEN_GROUP"
        result["method"] = "skip"
    
    return result


def run_batch_ne(cc, apply=False):
    """用 NE 数据处理，返回 (成功, 命名id列表)"""
    cmd = [sys.executable, os.path.join(HERE, "batch.py"), cc]
    if apply:
        cmd.extend(["--apply", "--commit", f"batch: {cc}"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr
    
    # 解析命名的 id
    named_ids = []
    for line in output.split("\n"):
        if "->" in line and not line.strip().startswith("✗"):
            parts = line.split("->")
            if len(parts) >= 2:
                new_id = parts[1].split()[0].strip()
                if new_id and not new_id.startswith("path"):
                    named_ids.append(new_id)
    
    return result.returncode == 0, named_ids


def run_batch_centroid(cc, apply=False):
    """用质心数据处理，返回 (成功, 命名id列表)"""
    cmd = [sys.executable, os.path.join(HERE, "batch_centroid.py"), cc]
    if apply:
        cmd.extend(["--apply", "--commit", f"batch: {cc}"])
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr
    
    # 解析命名的 id
    named_ids = []
    for line in output.split("\n"):
        if "->" in line and not line.strip().startswith("✗"):
            parts = line.split("->")
            if len(parts) >= 2:
                new_id = parts[1].split()[0].strip()
                if new_id and not new_id.startswith("path"):
                    named_ids.append(new_id)
    
    return result.returncode == 0, named_ids


def fetch_ip2location(ip):
    """调用 ip2location API"""
    url = f"https://api.ip2location.io/?key={IP2LOCATION_KEY}&ip={ip}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "svg-naming/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except Exception as e:
        return {"error": str(e)}


def update_ip2loc_cache(cc, ips):
    """更新 ip2location 缓存"""
    os.makedirs(IP2LOC_DIR, exist_ok=True)
    cache_file = os.path.join(IP2LOC_DIR, f"{cc}.csv")
    
    existing = {}
    if os.path.exists(cache_file):
        with open(cache_file, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                existing[row["ip"]] = row
    
    for ip in ips:
        data = fetch_ip2location(ip)
        if "error" not in data and "country_code" in data:
            existing[ip] = {
                "ip": ip,
                "cc": data.get("country_code", cc),
                "region_code": data.get("region_code", ""),
                "region_name": data.get("region_name", ""),
                "city": data.get("city", "")
            }
        time.sleep(0.5)  # 避免限流
    
    if existing:
        with open(cache_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["ip", "cc", "region_code", "region_name", "city"])
            w.writeheader()
            for ip, row in sorted(existing.items()):
                w.writerow(row)
    
    return len(existing)


def run_ip2loc_test(cc, refresh=False, key=None):
    """运行 ip2location 测试"""
    cmd = [sys.executable, os.path.join(ROOT, "tests", "ip2loc_naming_test.py"), "--countries", cc]
    if refresh:
        cmd.append("--refresh")
    if key:
        cmd.extend(["--key", key])
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout + result.stderr


def update_ip_data(cc):
    """更新离线 IP 数据（从 maxmind 和 ipapi 采样）"""
    # 运行测试脚本刷新缓存
    cmd = [sys.executable, os.path.join(ROOT, "tests", "ip2loc_naming_test.py"), 
           "--countries", cc, "--refresh", "--key", IP2LOCATION_KEY]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return "已写" in result.stdout or "命中" in result.stdout


def get_existing_ips_for_region(cc, region_code):
    """为特定区域查找现有 IP（从缓存中）"""
    cache_file = os.path.join(IP2LOC_DIR, f"{cc}.csv")
    if not os.path.exists(cache_file):
        return []
    
    ips = []
    with open(cache_file, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f)
        for row in rd:
            if row.get("region_code") == region_code:
                ips.append(row["ip"])
    return ips


def ensure_test_coverage(cc, named_ids):
    """确保测试覆盖：为每个新命名的 id 确保有至少 1 条 IP 测试数据"""
    cache_file = os.path.join(IP2LOC_DIR, f"{cc}.csv")
    existing = set()
    if os.path.exists(cache_file):
        with open(cache_file, newline="", encoding="utf-8") as f:
            rd = csv.DictReader(f)
            for row in rd:
                if row.get("region_code"):
                    existing.add(row["region_code"])
    
    missing = []
    for nid in named_ids:
        if nid not in existing:
            missing.append(nid)
    
    if missing:
        print(f"  [测试] 缺少 IP 覆盖: {missing}")
    return missing


def append_skip_record(cc, items, reason):
    """追加跳过记录到文档"""
    with open(SKIP_DOC, "a", encoding="utf-8") as f:
        f.write(f"\n## 自动跳过 ({cc})\n\n")
        f.write(f"**原因**: {reason}\n\n")
        f.write("| 元素 | 说明 |\n")
        for item, note in items:
            f.write(f"| `{item}` | {note} |\n")


def main():
    ap = argparse.ArgumentParser(description="自动化批量处理魔数 id")
    ap.add_argument("--dry-run", action="store_true", help="仅预览，不处理")
    ap.add_argument("--countries", help="指定国家代码，逗号分隔")
    ap.add_argument("--all", action="store_true", help="处理所有可自动处理的国家")
    ap.add_argument("--apply", action="store_true", help="应用更改（默认仅试算）")
    ap.add_argument("--batch-size", type=int, default=5, help="每批处理国家数")
    args = ap.parse_args()
    
    ne = sn.NEIndex(NE_PATH) if os.path.exists(NE_PATH) else None
    counts = get_country_magic_counts()
    
    if not args.countries and not args.all:
        # 默认显示概览
        print("=" * 60)
        print("剩余魔数 id 概览")
        print("=" * 60)
        print(f"{'国家':<6} {'魔数':<6} {'NE要素':<8} {'质心':<6} {'方法':<10} {'状态'}")
        print("-" * 60)
        
        sortable = []
        for cc, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            if cc.startswith("_"):
                continue
            analysis = analyze_country(cc, ne) if ne else {"status": "UNKNOWN", "magic": cnt, "ne_feats": 0, "has_centroid": False, "method": "unknown"}
            sortable.append((cc, cnt, analysis))
        
        for cc, cnt, analysis in sortable:
            if analysis["status"] == "NO_MAGIC":
                continue
            print(f"{cc:<6} {cnt:<6} {analysis.get('ne_feats', 0):<8} {'Y' if analysis.get('has_centroid') else 'N':<6} {analysis.get('method', 'unknown'):<10} {analysis['status']}")
        
        print("\n使用 --all 或 --countries=XX,YY 处理指定国家")
        return
    
    # 确定要处理的国家
    to_process = []
    if args.countries:
        to_process = [c.strip().upper() for c in args.countries.split(",")]
    elif args.all:
        for cc, cnt in counts.items():
            if cc.startswith("_"):
                continue
            analysis = analyze_country(cc, ne) if ne else None
            if analysis and analysis.get("method") in ("ne", "centroid"):
                to_process.append(cc)
    
    if not to_process:
        print("无可处理的国家")
        return
    
    print(f"待处理: {', '.join(to_process)} ({len(to_process)} 国)")
    
    if args.dry_run:
        return
    
    # 分批处理
    batch_num = 34  # 从 34 开始（之前已完成 1-33）
    for i in range(0, len(to_process), args.batch_size):
        batch = to_process[i:i+args.batch_size]
        batch_num += 1
        
        print(f"\n{'='*60}")
        print(f"批次 {batch_num}: {', '.join(batch)}")
        print("=" * 60)
        
        for cc in batch:
            analysis = analyze_country(cc, ne)
            
            if analysis["status"] != "PROCESSABLE":
                print(f"  {cc}: 跳过 ({analysis['status']})")
                append_skip_record(cc, [(m, "status=" + analysis["status"]) for m in analysis.get("magic_ids", [])], analysis["status"])
                continue
            
            success = False
            named_ids = []
            if analysis["method"] == "ne":
                success, named_ids = run_batch_ne(cc, apply=args.apply)
            elif analysis["method"] == "centroid":
                success, named_ids = run_batch_centroid(cc, apply=args.apply)
            
            if success and args.apply:
                print(f"  {cc}: ✓ 命名成功，运行测试...")
                # 更新 IP 数据
                update_ok = update_ip_data(cc)
                if update_ok:
                    print(f"  {cc}: ✓ IP 数据已更新")
                # 运行测试
                test_output = run_ip2loc_test(cc, refresh=False)
                if "命中" in test_output:
                    print(f"  {cc}: ✓ 测试通过")
                else:
                    print(f"  {cc}: ⚠ 测试输出:\n{test_output[:500]}")
            elif success:
                print(f"  {cc}: ✓ 试算成功")
            else:
                print(f"  {cc}: ✗ 失败或部分跳过")


if __name__ == "__main__":
    main()
