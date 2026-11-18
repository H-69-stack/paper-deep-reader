#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跑一遍 evals，确认 scripts/check_output.py 既不会放过坏输出，也不会误杀好输出。

为什么要有它：
    一个自检脚本最大的风险是"永远说通过"。改完 check_output.py 之后，如果不验证，
    很容易出现阈值写错、正则匹配不到、检查项被跳过而无人发现的情况。
    这里用三份样本 + 多组故意做坏的变体来钉死行为：
        - 合格骨架必须给 0
        - 五种坏样本必须给 1（分别命中 S1 / S5 / S3 / S9 / S12）
        - 同一份骨架在默认阈值（4500 字）下必须失败，证明阈值真的在起作用
        - 算法详解骨架在 algorithm 模式下必须给 0；删到 4 章后必须给 1（A1）

用法：
    python evals/run_evals.py            # 跑全部
    python evals/run_evals.py --verbose  # 连子进程输出一起打

退出码：0 = 全部符合预期；1 = 有案例不符合预期。
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CHECK = ROOT / "scripts" / "check_output.py"
FIXTURES = HERE / "fixtures"

# 骨架样本只有几百字，用放宽的阈值来单独验证"结构"判定
SKELETON_FLAGS = ["--min-total", "300", "--min-method", "100", "--skip-share"]


def read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


# ------------------------------------------------------------------ 变体构造
def drop_section(text, num):
    """删掉指定的整节（用于制造 S1 节缺失）。"""
    lines = text.split("\n")
    out, skipping = [], False
    for ln in lines:
        if ln.startswith("## 第") and ln.startswith(f"## 第{num}节"):
            skipping = True
            continue
        if skipping and ln.startswith("## 第"):
            skipping = False
        if not skipping:
            out.append(ln)
    return "\n".join(out)


def append_to_section(text, num, extra):
    """在某节末尾插入一行（用于制造禁用词、占位符）。"""
    marker = f"## 第{num}节"
    idx = text.find(marker)
    if idx < 0:
        raise SystemExit(f"样本里没有 {marker}")
    nxt = text.find("\n## 第", idx + len(marker))
    cut = nxt if nxt > 0 else len(text)
    return text[:cut] + "\n" + extra + "\n" + text[cut:]


def strip_part(text, part="数字例子"):
    """删掉第一个【数字例子】小节（用于制造 S3 三段式缺失）。

    注意边界要取"下一个【】小节 / 下一个步骤标题 / 下一节"三者的最小值，
    否则会把后面那个步骤的标题一起吃掉，S3 就退化成"只剩一个步骤"而不再报三段式缺失。
    """
    head = f"#### 【{part}】"
    start = text.find(head)
    if start < 0:
        raise SystemExit(f"样本里没有 {head}")
    after = start + len(head)
    candidates = [i for i in (
        text.find("#### 【", after),
        text.find("\n### 步骤", after),
        text.find("\n## 第", after),
    ) if i >= 0]
    nxt = min(candidates) if candidates else len(text)
    return text[:start] + text[nxt:]


def break_formula_index(text):
    """删掉速查表里 式(2) 那一行（用于制造 S9 编号不一致）。"""
    return "\n".join(ln for ln in text.split("\n") if "| 式(2) |" not in ln)


def strip_tables(text):
    """删掉所有表格行和表注（用于制造 S13 表格不足）。"""
    keep = []
    for ln in text.split("\n"):
        s = ln.strip()
        if s.startswith("|") or s.startswith("**表 "):
            continue
        keep.append(ln)
    return "\n".join(keep)


def strip_images(text):
    """删掉所有插图行（用于制造 S14 没有插图）。"""
    return "\n".join(ln for ln in text.split("\n") if not ln.startswith("!["))


def drop_chapter(text, num):
    """删掉算法模式的整章（`## 第N章 …`），用于制造 A1 章数不足。"""
    lines = text.split("\n")
    out, skipping = [], False
    start = f"## 第{num}章"
    for ln in lines:
        if ln.startswith(start):
            skipping = True
            continue
        if skipping and ln.startswith("## 第"):
            skipping = False
        if not skipping:
            out.append(ln)
    return "\n".join(out)


CASES = [
    dict(name="骨架样本在放宽阈值下通过",
         source="good-minimal.md", mutate=None, flags=SKELETON_FLAGS, expect=0),
    dict(name="骨架样本在默认 4500 字阈值下必须失败",
         source="good-minimal.md", mutate=None, flags=[], expect=1),
    dict(name="速览样本通过 brief 判定",
         source="brief.md", mutate=None, flags=["--profile", "brief"], expect=0),
    dict(name="算法详解骨架在 algorithm 模式下通过",
         source="algorithm-minimal.md", mutate=None,
         flags=["--profile", "algorithm"] + SKELETON_FLAGS, expect=0),
    dict(name="坏样本：算法详解只剩 4 章 → A1 失败",
         source="algorithm-minimal.md",
         flags=["--profile", "algorithm"] + SKELETON_FLAGS, expect=1,
         mutate=lambda t: drop_chapter(drop_chapter(drop_chapter(
             drop_chapter(drop_chapter(drop_chapter(t, 3), 4), 5), 6), 7), 8)),
    dict(name="坏样本：算法详解写成因果关系混乱的禁用词 → S5 失败",
         source="algorithm-minimal.md",
         flags=["--profile", "algorithm"] + SKELETON_FLAGS, expect=1,
         mutate=lambda t: t.replace("这一步的好处是", "同理，这一步的好处是")),
    dict(name="坏样本：删掉第4节 → S1 失败",
         source="good-minimal.md", flags=SKELETON_FLAGS, expect=1,
         mutate=lambda t: drop_section(t, 4)),
    dict(name="坏样本：插入禁用词『显然』 → S5 失败",
         source="good-minimal.md", flags=SKELETON_FLAGS, expect=1,
         mutate=lambda t: append_to_section(t, 5, "显然这个结论成立，不需要额外验证。")),
    dict(name="坏样本：删掉数字例子 → S3/S4 失败",
         source="good-minimal.md", flags=SKELETON_FLAGS, expect=1,
         mutate=lambda t: strip_part(t, "数字例子")),
    dict(name="坏样本：速查表缺 式(2) → S9 失败",
         source="good-minimal.md", flags=SKELETON_FLAGS, expect=1,
         mutate=break_formula_index),
    dict(name="坏样本：删光表格 → S13 失败",
         source="good-minimal.md", flags=SKELETON_FLAGS, expect=1,
         mutate=strip_tables),
    dict(name="坏样本：删掉插图 → S14 失败",
         source="good-minimal.md", flags=SKELETON_FLAGS, expect=1,
         mutate=strip_images),
    dict(name="坏样本：留 TODO → S12 失败",
         source="good-minimal.md", flags=SKELETON_FLAGS, expect=1,
         mutate=lambda t: append_to_section(t, 6, "TODO: 补实验数据。")),
]


def run_case(case, tmpdir, verbose):
    text = read_fixture(case["source"])
    if case.get("mutate"):
        text = case["mutate"](text)
    path = Path(tmpdir) / f"{abs(hash(case['name']))}.md"
    path.write_text(text, encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, str(CHECK), str(path)] + case["flags"],
        capture_output=True, text=True, encoding="utf-8",
    )
    passed = proc.returncode == case["expect"]
    icon = "PASS" if passed else "FAIL"
    print(f"[{icon}] {case['name']}（期望 exit={case['expect']}，实际 exit={proc.returncode}）")
    if verbose or not passed:
        for line in (proc.stdout or "").splitlines():
            if line.startswith(("[FAIL]", "[WARN]", "结论")):
                print("       " + line)
    return passed


def main():
    ap = argparse.ArgumentParser(description="验证 check_output.py 的判定行为")
    ap.add_argument("--verbose", action="store_true", help="打印每个案例的检查明细")
    args = ap.parse_args()

    if not CHECK.exists():
        print(f"[ERROR] 找不到 {CHECK}")
        return 1

    print(f"待测脚本：{CHECK}")
    print(f"案例数：{len(CASES)}")
    print("-" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        results = [run_case(c, tmpdir, args.verbose) for c in CASES]

    ok_n = sum(results)
    print("-" * 60)
    print(f"结果：{ok_n}/{len(results)} 个案例符合预期")
    if ok_n != len(results):
        print("有案例不符合预期 —— check_output.py 的判定逻辑被改坏了，或有阈值/正则写错。")
        return 1
    print("全部符合预期。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
