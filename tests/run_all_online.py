#!/usr/bin/env python3
"""分批刷新 ip-api 反查缓存，并输出该国校验结果。

新数据模型下，`tests/data/ipapi_lookup.csv` 是全局反查缓存（ip,cc,region,city），
`tests/data/maxmind_samples.csv` 是 maxmind 采样缓存。默认测试完全离线读缓存；
`run_all_online.py` 只在需要时按国家分批联网刷新 ip-api 缓存（受免费限流，分批排队），
可中途打断续跑。

用法：
  python tests/run_all_online.py --refresh-ipapi --vote 2     # 全国家分批联网刷新缓存
  python tests/run_all_online.py --refresh-ipapi --countries br,mx
  python tests/run_all_online.py --refresh-maxmind           # 只重新采样 maxmind（一次性）
  python tests/run_all_online.py --outdir tmp                # 指定结果/log 目录
"""

import argparse
import csv
import os
import re
import subprocess
import sys
import time

TESTS = os.path.join(os.path.dirname(__file__), "ip_naming_test.py")
DEFAULT_OUT = os.path.join(os.path.dirname(__file__), "results")


def get_clean_countries():
    src = os.path.join(os.path.dirname(__file__), "..", "src", "world-states-provinces.svg")
    raw = open(src, encoding="utf-8").read()
    ids = re.findall(r'\bid="([^"]+)"', raw)
    ccs = set()
    for i in ids:
        m = re.fullmatch(r"([A-Z]{2})-([A-Z]{2})", i)
        if m:
            ccs.add(m.group(1))
    return sorted(ccs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", default="")
    ap.add_argument("--vote", type=int, default=2)
    ap.add_argument("--inter", type=int, default=40, help="每批之间等待秒数")
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    ap.add_argument("--key", default=None)
    ap.add_argument("--refresh-ipapi", action="store_true", help="联网刷新 ip-api 缓存")
    ap.add_argument("--refresh-maxmind", action="store_true", help="重新采样 maxmind")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    if not countries:
        countries = get_clean_countries()

    done_file = os.path.join(args.outdir, "done_ctry.csv")
    done = set()
    if os.path.exists(done_file):
        with open(done_file, newline="", encoding="utf-8") as f:
            for row in csv.reader(f):
                if row:
                    done.add(row[0])

    total = len(countries)
    for idx, cc in enumerate(countries, 1):
        if cc in done:
            print("[skip] %s 本批已完成（缓存已刷新）" % cc)
            continue
        print("\n===== [%d/%d] 国家 %s =====" % (idx, total, cc))
        cmd = [sys.executable, TESTS, "--countries", cc, "--vote", str(args.vote)]
        if args.refresh_ipapi:
            cmd.append("--refresh-ipapi")
        if args.refresh_maxmind:
            cmd.append("--refresh-maxmind")
        if args.key:
            cmd += ["--key", args.key]
        logfile = os.path.join(args.outdir, "%s.log" % cc)
        with open(logfile, "w", encoding="utf-8") as fh:
            p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
        tail = ""
        if os.path.exists(logfile):
            with open(logfile, encoding="utf-8") as fh:
                tail = fh.read()[-600:]
        if "== ip-api 严格反向校验统计 ==" in tail or "== 离线覆盖校验" in tail:
            with open(done_file, "a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow([cc])
            print("[done] %s" % cc)
        else:
            print("[warn] %s 未见完整校验输出（可能限流/异常），未标记完成" % cc)
        if idx < total:
            print("等待 %d 秒避开限流..." % args.inter)
            time.sleep(args.inter)

    # maxmind 一次性刷新：只需跑一个国家即可写全量采样缓存（采样是全库的）
    if args.refresh_maxmind:
        print("\n[提示] maxmind 采样是全库的，仅需一次。可手动运行:\n"
              "  python tests/ip_naming_test.py --refresh-maxmind")
    print("\n全部批次结束。日志目录: %s" % args.outdir)


if __name__ == "__main__":
    main()