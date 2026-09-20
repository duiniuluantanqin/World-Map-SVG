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
    ap.add_argument("--offline", action="store_true")
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
        m = re.fullmatch(r"([A-Z]{2})-([A-Z]{2})", i)
        if m:
            clean.append((m.group(1), m.group(2), i))
    print("其中后缀为 2 位字母的干净 id: %d 条" % len(clean))

    # 过滤国家
    if args.countries:
        ccs = set(c.upper() for c in args.countries.split(",") if c.strip())
        clean = [(c, r, i) for (c, r, i) in clean if c in ccs]
        print("过滤后国家: %s  -> 干净 id: %d 条" % (",".join(sorted(ccs)), len(clean)))

    desired = {(c, r) for (c, r, i) in clean}
    sample, names, mult, country_ips = scan_maxmind(object(), desired=desired)
    print("maxmind 抽得 (cc, region) 样本: %d 条" % len(sample))

    # 对每个干净 id，能否从 maxmind 找到该 (cc, region) 的个人真实 IP
    if args.vote >= 2:
        # 投票模式：使用 mult 候选
        prov = [(c, r, i) for (c, r, i) in clean if (c, r) in mult and len(mult[(c, r)]) >= 2]
    else:
        prov = [(c, r, i) for (c, r, i) in clean if (c, r) in sample]
    missing = [(c, r, i) for (c, r, i) in clean if (c, r) not in sample]
    print("能在 maxmind 找到该省 IP 的: %d 条；缺失: %d 条" % (len(prov), len(missing)))

    if args.limit:
        prov = prov[:args.limit]

    if args.offline:
        print("\n== 离线校验（干净 id 是否有对应 maxmind IP 样本）==")
        print("有样本: %d / %d" % (len(prov), len(clean)))
        print("覆盖的国家数: %d" % len({c for (c, r, i) in clean}))
        missing_by_country = {}
        for (c, r, i) in missing:
            missing_by_country.setdefault(c, []).append(r)
        print("缺失省份涉及的国家数: %d" % len(missing_by_country))
        print("缺失明细（前 60 条）：")
        for (c, r, i) in missing[:60]:
            print("   %s  (SVG 命名后缀 %s 在 maxmind 中无该 ISO region)" % (i, r))
        return

    # ---- 在线：ip-api 批量反查，验证 ip-api 返回是否 == 该 id ----
    if not prov:
        print("没有可验证的样本，结束。")
        return
    if args.vote >= 2:
        # 收集每个省份要查询的所有候选 IP
        ip_to_key = {}
        for (c, r, i) in prov:
            for ip in mult[(c, r)]:
                ip_to_key[ip] = (c, r, i)
        all_ips = list(ip_to_key)
    else:
        ip_to_key = {}
        for (c, r, i) in prov:
            ip = sample[(c, r)]
            ip_to_key[ip] = (c, r, i)
        all_ips = [sample[(c, r)] for (c, r, i) in prov]
    # 若缺失省份较多，追加使用该国兜底 IP（country_ips）参与反查，扩大覆盖
    fallback_ips = []
    fallback_names = {}
    missing_cc = {c for (c, r, i) in missing}
    for c in missing_cc:
        for ip in country_ips.get(c, [])[:6]:
            if ip not in ip_to_key:
                ip_to_key[ip] = None  # None 表示国家级兜底
                fallback_ips.append(ip)
                fallback_names[ip] = c
    all_ips = list(ip_to_key)
    resmap = ipapi_batch(all_ips, pause=1.5, key=args.key)

    hit = miss = 0
    miss_list = []
    # 国家兜底命中：统计该国家 ip-api 返回已经覆盖到 SVG 中哪些省
    covered_by_fallback = {}
    for ip in fallback_ips:
        res = resmap.get(ip)
        if res is None:
            continue
        cc = fallback_names[ip]
        got = res[0] + "-" + res[1]
        covered_by_fallback.setdefault(got, cc)
    if covered_by_fallback:
        print("\n国家兜底（无省样本国家）ip-api 返回的省（与 SVG 命名比对）：")
        for got, cc in sorted(covered_by_fallback.items()):
            in_svg = got in named
            print("   -> %-20s 在SVG中=%s" % (got, "是" if in_svg else "否"))
    for (c, r, i) in prov:
        if args.vote >= 2:
            votes = {}
            qfail = 0
            for ip in mult[(c, r)]:
                res = resmap.get(ip)
                if res is None:
                    qfail += 1
                    continue
                got = res[0] + "-" + res[1]
                votes[got] = votes.get(got, 0) + 1
            if not votes:
                miss += 1
                miss_list.append((i, "/".join(mult[(c, r)]), "(全部查询失败)"))
                print("   ..  %-20s 查询失败" % (i,))
                continue
            top = max(votes, key=votes.get)
            win = top == i
            # 打印投票
            vote_txt = ", ".join("%s(%d)" % (k, v) for k, v in sorted(votes.items(), key=lambda x: -x[1]))
            if win:
                hit += 1
                print("   OK  %-20s votes={%s}" % (i, vote_txt))
            else:
                miss += 1
                miss_list.append((i, "/".join(mult[(c, r)]), "投票=%s" % vote_txt))
                print("   !!  %-20s 期望=%s votes={%s} (ip-api竞销票=%s)" % (i, i, vote_txt, top))
        else:
            ip = sample[(c, r)]
            res = resmap.get(ip)
            if res is None:
                miss += 1
                miss_list.append((i, ip, "(查询失败)"))
                print("   %-20s ip=%s -> 查询失败" % (i, ip))
                continue
            rcc, rrg, rcity = res
            got = rcc + "-" + rrg
            if got == i:
                hit += 1
                print("   OK  %-20s ip=%s city=%s -> ip-api=%s" % (i, ip, rcity, got))
            else:
                miss += 1
                miss_list.append((i, ip, "%s(≠) ip-api=%s city=%s" % (got, rcc, rcity)))
                print("   !!  %-20s 期望=%s ip=%s -> ip-api=%s" % (i, i, ip, got))

    print("\n== ip-api 严格反向校验统计 ==")
    print("命中: %d  未命中: %d  命中率: %.1f%%" % (hit, miss, 100.0 * hit / max(1, hit + miss)))
    if miss_list:
        print("未命中明细：")
        for (i, ip, why) in miss_list:
            print("   %-20s ip=%s  %s" % (i, ip, why))


if __name__ == "__main__":
    main()