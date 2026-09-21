#!/usr/bin/env python3
"""应用一份人工确认的 id 映射表（old_id -> new_id），仅替换 id 属性并校验。

用于：自动化 propose 之后的人工修正 / 逐条复核定案。映射表两列 CSV（无表头）：
  old_id,new_id

用法：
  python tools/apply.py batch26.csv --commit "batch 26: ST KW"
"""
import argparse
import csv
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src", "world-states-provinces.svg")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mapping", help="old_id,new_id 两列 CSV")
    ap.add_argument("--file", default=SRC, help="目标 SVG（默认 provinces）")
    ap.add_argument("--commit", default=None)
    args = ap.parse_args()

    rows = []
    with open(args.mapping, newline="", encoding="utf-8") as f:
        for r in csv.reader(f):
            r = [x.strip() for x in r if x.strip()]
            if not r or r[0].startswith("#"):
                continue
            if len(r) != 2:
                print("跳过非法行: %r" % r)
                continue
            rows.append((r[0], r[1]))

    raw = open(args.file, encoding="utf-8").read()
    new = raw
    seen = set()
    problems = []
    for old, newid in rows:
        if newid in seen:
            problems.append((old, newid, "重复"))
            continue
        if not all(ord(ch) < 128 for ch in newid):
            problems.append((old, newid, "非 ASCII"))
            continue
        pat = 'id="%s"' % old
        if new.count(pat) != 1:
            problems.append((old, newid, "未找到/不唯一(%d)" % new.count(pat)))
            continue
        new = new.replace(pat, 'id="%s"' % newid, 1)
        seen.add(newid)

    if problems:
        print("异常，未写回：")
        for p in problems:
            print("  ", p)
        return
    try:
        ET.fromstring(new)
    except Exception as e:
        print("XML 解析失败: %s" % e)
        return
    open(args.file, "w", encoding="utf-8").write(new)
    ids = [e.get("id") for e in ET.parse(args.file).getroot().iter() if e.get("id")]
    print("应用 %d 个 id；全局唯一性 %s (共 %d)" % (
        len(seen), "OK" if len(ids) == len(set(ids)) else "FAIL", len(ids)))

    if args.commit:
        subprocess.run(["git", "add", args.file], check=True)
        subprocess.run(["git", "commit", "-m", args.commit], check=True)
        print("已提交: %s" % args.commit)


if __name__ == "__main__":
    main()