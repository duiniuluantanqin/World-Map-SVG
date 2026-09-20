#!/usr/bin/env python3
"""分批远程 ip-api 全量在线校验驱动。

由于 ip-api 免费版有速率限制（~15 次/分钟，批量接口共享配额），全量 804 个干净 id
拆成若干批、按国家分组，逐步跑完；批次间等待以避开限流，可中途打断续跑。

用法：
  python tests/run_all_online.py                    # 全部国家分批
  python tests/run_all_online.py --countries br,mx  # 仅这些国家
  python tests/run_all_online.py --vote 2
  python tests/run_all_online.py --inter 60         # 每批间隔秒数
  python tests/run_all_online.py --outdir tmp       # 结果输出目录（默认脚本同目录结果）
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
    """读取 SVG，返回有干净 id 的国家列表（与 ip_naming_test 同口径）。"""
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
    ap.add_argument("--inter", type=int, default=45, help="每批之间等待秒数")
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    ap.add_argument("--key", default=None)
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    countries = [c.strip().upper() for c in args.countries.split(",") if c.strip()]
    if not countries:
        countries = get_clean_countries()

    # 已完成的记录文件（续跑依据）
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
            print("[skip] %s 已完成" % cc)
            continue
        print("\n===== [%d/%d] 国家 %s =====" % (idx, total, cc))
        cmd = [sys.executable, TESTS,
               "--countries", cc,
               "--vote", str(args.vote)]
        logfile = os.path.join(args.outdir, "%s.log" % cc)
        with open(logfile, "w", encoding="utf-8") as fh:
            p = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT)
        # 读取日志末尾看是否有命中统计
        tail = ""
        if os.path.exists(logfile):
            with open(logfile, encoding="utf-8") as fh:
                tail = fh.read()[-800:]
        if "== ip-api 严格反向校验统计 ==" in tail:
            # 无论命中与否都视为已跑完（严格校验完成）
            with open(done_file, "a", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow([cc])
            print("[done] %s" % cc)
        else:
            print("[warn] %s 未见完整校验输出（可能限流/异常），未标记完成" % cc)
        if idx < total:
            print("等待 %d 秒避开限流..." % args.inter)
            time.sleep(args.inter)

    print("\n全部批次结束。日志目录: %s" % args.outdir)


if __name__ == "__main__":
    main()