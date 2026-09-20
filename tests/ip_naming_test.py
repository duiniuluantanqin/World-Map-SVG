#!/usr/bin/env python3
"""测试 SVG 中已命名的行政区 id 能否通过 ip-api 的真实 IP 反查命中。

验证链路（反向严格校验）：
  1. 从 src/world-states-provinces.svg 提取"已命名 id"集合（跳过 path/g/circle 魔数）。
  2. 只考虑"干净 id"：CC-XX（XX 为 2 位字母，与 ISO 3166-2 / ip-api 命名同构），
     CC__XX 等姓名、岛屿碎块（如 CN-FJ-mainland）、英文名后缀（如 AL-tirana）不在此列。
  3. 用 maxminddb(GeoLite2-City) + iptoasn 的按国家 IP 段，为该省的 (country_code, region)
     挑选代表 IP；随后用 ip-api 反查，检查返回的 countryCode+region 是否【精确等于】该 id。
  4. 输出命中 / 未命中统计与明细。

用法：command:editor.contrib.icubeGuideNotice.GoToConfigAction?{%22language%22:%22python%22,%22doNotShowAgain%22:false}
  python tests/ip_naming_test.py --offline                    # 离线：检查干净 id 能否从 maxmind 找到代表 IP
  python tests/ip_naming_test.py --countries cn,us            # 在线：对指定国家做 ip-api 严格反向校验
  python tests/ip_naming_test.py --countries cn --vote 5      # 每省采样多个 IP 投票，采样首票为准提升可信度
"""

import argparse
import csv
import gzip
import ipaddress
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse

SRC = os.path.join(os.path.dirname(__file__), "..", "src", "world-states-provinces.svg")
MAGIC = re.compile(r"(path|g|circle)\d+$")
IP2COUNTRY = os.path.join(os.environ.get("TEMP", ""), "ip2country-v4.tsv.gz")
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MAXMIND_DIR = os.path.join(DATA_DIR, "maxmind_samples")  # <CC>.csv: cc,region,ip,name
IPAPI_DIR = os.path.join(DATA_DIR, "ipapi_lookup")       # <CC>.csv: ip,cc,region,city

# 可选的 IP 复写表：某些国家级 region maxmind 与 ip-api 不同，或缺少省样本。
# 手动补充真实 IP 以覆盖无法自动定位的 id。
MANUAL_IP = {
}


def load_svg_ids():
    """从 SVG 提取已命名 id 集合（跳过 path/g/circle 魔数）。"""
    raw = open(SRC, encoding="utf-8").read()
    ids = set(re.findall(r'\bid="([^"]+)"', raw))
    named = {i for i in ids if not MAGIC.fullmatch(i)}
    return named, ids


def scan_maxmind(reader, desired=None):
    """"用 maxminddb 生成每个 (country, subdivision) 的代表 IP 样本池。

    遍历 iptoasn 按国家 IP 段，高密度采样 + 针对性补采，收集 country+subdivision 对应的真实 IP。
    desired: 可选的 {(cc, region): True} 目标集合；未在该集合中的 region 会被忽略（跳过多余省份），
             集合中但没采到的会做定向补采。
    返回: ({(cc, region): ip}, {(cc, region): name}, {(cc, region): [ip,...]})。
    """
    try:
        from geolite2 import geolite2
    except ImportError:
        print("[!] 缺少 maxminddb-geolite2，请先安装: pip install maxminddb-geolite2")
        return {}, {}, {}

    reader = geolite2.reader()
    country_prefix = {}
    if os.path.exists(IP2COUNTRY):
        with gzip.open(IP2COUNTRY, "rt", errors="replace") as f:
            for line in f:
                p = line.rstrip("\n").split("\t")
                if len(p) < 3 or p[0].startswith("#"):
                    continue
                a, b, cc = p[0].strip(), p[1].strip(), p[2].strip()
                if not cc or cc == "None":
                    continue
                country_prefix.setdefault(cc, [])
                try:
                    country_prefix[cc].append((int(ipaddress.ip_address(a)),
                                               int(ipaddress.ip_address(b))))
                except ValueError:
                    continue
    # 每国需要的 region 集合（desired 未提供则视为不限）
    need = {}
    if desired:
        for (cc, rg) in desired:
            need.setdefault(cc, set()).add(rg)

    seen_region = {}
    names = {}
    country_ips = {}  # cc -> [ip,...]，每个国家若干代表 IP（含无省数据国家）

    def record(rcc, region, ip):
        # 仅记录期望的 region（若提供了 desired）
        if desired and (rcc, region) not in desired:
            return
        key = (rcc, region)
        seen_region.setdefault(key, [])
        if len(seen_region[key]) < 5:
            seen_region[key].append(ip)

    def probe_segment(r, seed):
        a, b = r
        if a >= b:
            return None
        ip_num = a + (seed * 7919) % (b - a + 1)
        try:
            return str(ipaddress.ip_address(ip_num))
        except ValueError:
            return None

    # 第一遍：黄金比例散列高密度采样每国段
    for cc, ranges in country_prefix.items():
        total = len(ranges)
        if total == 0:
            continue
        probe = min(2000, max(100, total * 6))
        for k in range(probe):
            r = ranges[(k * 2654435761) % total]
            ip = probe_segment(r, k)
            if ip is None:
                continue
            rec = reader.get(ip)
            if not rec or "country" not in rec:
                continue
            if rec["country"].get("iso_code", "") != cc:
                continue
            # 每个国家累积少量代表 IP（用于无省数据时兜底）
            if len(country_ips.setdefault(cc, [])) < 8:
                country_ips[cc].append(ip)
            subs = rec.get("subdivisions") or []
            if not subs:
                continue
            region = subs[0].get("iso_code")
            record(cc, region, ip)
            if region and (cc, region) not in names:
                names[(cc, region)] = subs[0].get("names", {}).get("en", "")

    # 第三遍：定向补采——对需要却没采到的 (cc, region)，大范围扫该国段
    if desired:
        for cc, rgs in need.items():
            ranges = country_prefix.get(cc, [])
            total = len(ranges)
            if total == 0:
                continue
            missing = [rg for rg in rgs if (cc, rg) not in seen_region]
            if not missing:
                continue
            wanted = set(missing)
            probe = min(60000, max(2000, total * 10))
            for k in range(probe):
                r = ranges[(k * 1103515245 + 12345) % total]
                ip = probe_segment(r, k)
                if ip is None:
                    continue
                rec = reader.get(ip)
                if not rec or "country" not in rec:
                    continue
                if rec["country"].get("iso_code", "") != cc:
                    continue
                subs = rec.get("subdivisions") or []
                if not subs:
                    continue
                region = subs[0].get("iso_code")
                if region in wanted:
                    record(cc, region, ip)
                    if region and (cc, region) not in names:
                        names[(cc, region)] = subs[0].get("names", {}).get("en", "")
                    wanted.discard(region)
                if not wanted:
                    break
    reader.close()

    sample = {}
    mult = {}
    for key, ips in seen_region.items():
        sample[key] = ips[0]
        mult[key] = ips
    return sample, names, mult, country_ips


def maxmind_path(cc):
    return os.path.join(MAXMIND_DIR, cc + ".csv")


def ipapi_path(cc):
    return os.path.join(IPAPI_DIR, cc + ".csv")


def load_maxmind_cache(cc_list=None):
    """从 tests/data/maxmind_samples/<CC>.csv 读取采样缓存。

    cc_list: 国家码列表；None 表示读取目录下所有国家文件。
    返回 (sample, names, mult, country_ips)，与 scan_maxmind 相同结构。
    """
    sample, names, mult, country_ips = {}, {}, {}, {}
    if cc_list is None:
        if not os.path.isdir(MAXMIND_DIR):
            return sample, names, mult, country_ips
        cc_list = sorted(os.path.splitext(f)[0] for f in os.listdir(MAXMIND_DIR)
                         if f.endswith(".csv"))
    for cc in cc_list:
        p = maxmind_path(cc)
        if not os.path.exists(p):
            continue
        with open(p, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        for r in rows[1:]:  # 跳过表头
            if len(r) < 3:
                continue
            rcc, region, ip = r[0].strip(), r[1].strip(), r[2].strip()
            if rcc != cc:
                continue
            name = r[3] if len(r) > 3 else ""
            key = (rcc, region)
            sample[key] = ip
            mult.setdefault(key, []).append(ip)
            names[key] = name
            country_ips.setdefault(rcc, [])
            if ip not in country_ips[rcc]:
                country_ips[rcc].append(ip)
    return sample, names, mult, country_ips


def save_maxmind_cache(sample, names, mult, country_ips, cc_list=None):
    """把采样结果按国家写入 tests/data/maxmind_samples/<CC>.csv。"""
    # 聚合：cc -> [(region, ip, name)]
    by_cc = {}
    for (cc, region), ips in mult.items():
        for ip in ips:
            by_cc.setdefault(cc, set()).add((region, ip, names.get((cc, region), "")))
    for cc, ips in country_ips.items():
        if (cc, "") not in mult:
            for ip in ips:
                by_cc.setdefault(cc, set()).add(("", ip, ""))
    os.makedirs(MAXMIND_DIR, exist_ok=True)
    if cc_list is None:
        cc_list = sorted(by_cc)
    written = 0
    for cc in cc_list:
        rows = by_cc.get(cc)
        if not rows:
            continue
        with open(maxmind_path(cc), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["cc", "region", "ip", "name"])
            for region, ip, name in sorted(rows, key=lambda x: (x[0], x[1])):
                w.writerow([cc, region, ip, name])
        written += 1
    print("已写 %d 个国家的采样缓存 -> %s" % (written, MAXMIND_DIR))


def load_ipapi_cache(cc_list=None):
    """从 tests/data/ipapi_lookup/<CC>.csv 读取已反查结果。返回 {ip: (cc, region, city)}。"""
    cache = {}
    if cc_list is None:
        if not os.path.isdir(IPAPI_DIR):
            return cache
        cc_list = sorted(os.path.splitext(f)[0] for f in os.listdir(IPAPI_DIR)
                         if f.endswith(".csv"))
    for cc in cc_list:
        p = ipapi_path(cc)
        if not os.path.exists(p):
            continue
        with open(p, newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        for r in rows[1:]:
            if len(r) >= 4:
                cache[r[0]] = (r[1], r[2], r[3])
    return cache


def save_ipapi_cache(cache, cc_list=None):
    """把 ip-api 反查结果按国家写入 tests/data/ipapi_lookup/<CC>.csv。"""
    by_cc = {}
    for ip, (cc, rg, city) in cache.items():
        by_cc.setdefault(cc, []).append((ip, rg, city))
    os.makedirs(IPAPI_DIR, exist_ok=True)
    if cc_list is None:
        cc_list = sorted(by_cc)
    written = 0
    for cc in cc_list:
        rows = by_cc.get(cc)
        if not rows:
            continue
        with open(ipapi_path(cc), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["ip", "cc", "region", "city"])
            for ip, rg, city in sorted(rows, key=lambda x: x[0]):
                w.writerow([ip, cc, rg or "", city or ""])
        written += 1
    print("已写 %d 个国家的 ip-api 缓存 -> %s" % (written, IPAPI_DIR))


def ipapi_batch(ips, pause=1.5, key=None):
    """ip-api 批量 POST 反查（免费单次上限 100 个 IP）。返回 {ip: (cc, region, city) or None}。"""
    out = {}
    url = "http://ip-api.com/batch"
    if key:
        url += "?key=" + key
    for i in range(0, len(ips), 100):
        chunk = ips[i:i + 100]
        body = json.dumps([{"query": ip,
                            "fields": "status,country,countryCode,region,regionName,city"} for ip in chunk]).encode()
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=25) as r:
                    arr = json.load(r)
                qf = 0
                for q, res in zip(chunk, arr):
                    if res and res.get("status") == "success":
                        out[q] = (res.get("countryCode", ""), res.get("region", ""), res.get("city", ""))
                    else:
                        out[q] = None
                        qf += 1
                # 若大量失败视为触发限流，等待更长再继续下一批
                if qf > len(chunk) * 0.5:
                    time.sleep(10)
                else:
                    time.sleep(pause)
                break
            except Exception:
                if attempt == 2:
                    for q in chunk:
                        out[q] = None
                time.sleep(pause + attempt * 4)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="只做离线覆盖检查，不发 ip-api 请求")
    ap.add_argument("--refresh-maxmind", action="store_true", help="重新用 maxmind 采样并写回缓存（默认读缓存）")
    ap.add_argument("--refresh-ipapi", action="store_true", help="对缺失命中的 IP 联网反查并写回缓存")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--countries", default="")
    ap.add_argument("--vote", type=int, default=1, help="每省采样多个 IP 投票（>=2 时启用投票模式）")
    ap.add_argument("--key", default=None, help="ip-api 付费 key（可选，提升限流）")
    args = ap.parse_args()

    named, all_ids = load_svg_ids()
    print("SVG 已命名 id: %d（跳过魔数）" % len(named))

    # 从 SVG 已命名 id 中筛出"干净 id"：CC-XX，XX=二位字母（ISO 3166-2 同构），作为采样目标
    clean = []
    for i in named:
        m = re.fullmatch(r"([A-Z]{2})-([A-Z]{1,3})", i)
        if m:
            clean.append((m.group(1), m.group(2), i))
    print("其中后缀为纯大写字母的干净 id（ISO 3166-2 字母码）: %d 条" % len(clean))

    # 过滤国家
    ccs_all = None
    if args.countries:
        ccs_all = set(c.upper() for c in args.countries.split(",") if c.strip())
        clean = [(c, r, i) for (c, r, i) in clean if c in ccs_all]
        print("过滤后国家: %s  -> 干净 id: %d 条" % (",".join(sorted(ccs_all)), len(clean)))
    # 本轮涉及的国家码列表（用于读写分文件缓存）
    if ccs_all:
        cc_list = sorted(ccs_all)
    else:
        cc_list = sorted({c for (c, r, i) in clean})

    # ---------- 采样缓存（maxmind） ----------
    if args.refresh_maxmind:
        desired = {(c, r) for (c, r, i) in clean}
        sample, names, mult, country_ips = scan_maxmind(object(), desired=desired)
        print("重新采样 maxmind：共 %d 个省样本" % len(sample))
        save_maxmind_cache(sample, names, mult, country_ips, cc_list=cc_list)
    else:
        sample, names, mult, country_ips = load_maxmind_cache(cc_list=cc_list)
        print("读取 maxmind 采样缓存：%d 条（要用最新数据请加 --refresh-maxmind）" % len(sample))

    if args.limit:
        clean = clean[:args.limit]

    # 每个干净 id 是否有候选 IP（maxmind 采样缓存）；有候选 IP 的才可能被 ip-api 命中
    has_candidate = {}
    for (c, r, i) in clean:
        has_candidate[i] = (c, r) in mult and bool(mult[(c, r)])
    with_cand = [i for i in has_candidate if has_candidate[i]]
    no_cand = [(c, r, i) for (c, r, i) in clean if not has_candidate[i]]
    print("有候选 IP 的干净 id: %d / %d（无候选 IP: %d）" % (len(with_cand), len(clean), len(no_cand)))

    # ---------- 纯离线模式：只看 maxmind 采样覆盖 ----------
    if args.offline:
        print("\n== 离线覆盖校验（有候选 IP 的干净 id 比例）==")
        print("覆盖的国家数: %d" % len({c for (c, r, i) in clean}))
        missing_by_country = {}
        for (c, r, i) in no_cand:
            missing_by_country.setdefault(c, []).append(r)
        print("无候选 IP 的省份涉及国家数: %d" % len(missing_by_country))
        print("无候选 IP 明细（前 60 条）：")
        for (c, r, i) in no_cand[:60]:
            print("   %s  (后缀 %s 在采样缓存中无候选 IP)" % (i, r))
        return

    # ---------- 候选 IP 池：每个地区的全部 maxmind 采样 IP ----------
    # 正向口径下不预先假设省份归属，把所有候选 IP 都交给 ip-api 反查，
    # 看能被解析成哪些 SVG id。
    candidate_ips = []
    _seen = set()
    for (c, r), ips in mult.items():
        for ip in ips:
            if ip not in _seen:
                _seen.add(ip)
                candidate_ips.append(ip)
    for c, ips in country_ips.items():
        for ip in ips:
            if ip not in _seen:
                _seen.add(ip)
                candidate_ips.append(ip)

    if not candidate_ips:
        print("缓存中没有任何候选 IP，结束。")
        return

    # ---------- 读取 ip-api 反查缓存 ----------
    ipcache = load_ipapi_cache(cc_list=cc_list)
    print("读取 ip-api 反查缓存：%d 条（候选 IP %d 个）" % (len(ipcache), len(candidate_ips)))

    # 只在 --refresh-ipapi 时联网补查未缓存的候选 IP
    resmap = {ip: ipcache.get(ip) for ip in candidate_ips}
    if args.refresh_ipapi:
        need = [ip for ip in candidate_ips if ip not in ipcache]
        if need:
            print("联网反查 %d 个未缓存 IP ..." % len(need))
            online = ipapi_batch(need, pause=1.5, key=args.key)
            fresh = dict(ipcache)
            for ip in need:
                if online.get(ip):
                    fresh[ip] = online[ip]
                    resmap[ip] = online[ip]
            save_ipapi_cache(fresh, cc_list=cc_list)

    # ---------- 正向口径：候选 IP -> ip-api -> CC-REGION -> 是否在 SVG ----------
    id_to_ips = {}
    id_extra = {}
    for ip in candidate_ips:
        res = resmap.get(ip)
        if res is None or res[0] is None:
            continue
        got = res[0] + "-" + res[1]
        if got in named:
            id_to_ips.setdefault(got, []).append(ip)
        else:
            id_extra.setdefault(got, []).append(ip)

    # 统计：SVG 干净 id 中有多少被 ip-api 解析命中
    hit = 0
    miss_list = []
    for (c, r, i) in clean:
        if i in id_to_ips:
            hit += 1
            ips = id_to_ips[i]
            src = "缓存" if all(x in ipcache for x in ips) else "混合"
            print("   OK  %-20s [%s] ip-api 解析命中(%s)" % (i, src, ", ".join(ips)))
        else:
            miss_list.append(i)
            reason = "候选IP均解析到其他地区(数据源精度)" if has_candidate[i] else "无候选IP(数据源无该省)"
            print("   ..  %-20s 未命中 —— %s" % (i, reason))

    print("\n== ip-api 正向校验统计（以 ip-api 为准）==")
    print("SVG 干净 id 中可用 ip-api 解析命中: %d / %d  命中率: %.1f%%" % (
        hit, len(clean), 100.0 * hit / max(1, len(clean))))
    if miss_list:
        print("未命中的 SVG id：")
        for i2 in miss_list:
            print("   %s" % i2)
    if id_extra:
        print("\nip-api 能拼出但 SVG 中不存在的 id（可能的命名缺口）：")
        for got, ips in sorted(id_extra.items()):
            print("   %-20s (例IP: %s)" % (got, ips[0]))


if __name__ == "__main__":
    main()