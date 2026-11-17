#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把论文 PDF 转成可精讲的 markdown，并诊断三类最常见的"读不出来"。

为什么需要它：
    SKILL.md 说"本地 PDF 用 pypdf / pdfplumber / PyMuPDF 提取"，但每次让模型现写提取代码，
    结果不稳定：有时只提到前两页、有时静默丢公式、有时扫描件提到空字符串还继续编。
    这个脚本把提取链路固定下来，并把"提不出来"变成显式诊断，而不是让模型猜。

三类诊断（对应 SKILL.md 的降级规则）：
    1. 扫描件无文本层  → 每页字符数中位数 < 50，必须如实告知用户，不要编内容
    2. 公式疑似丢失    → 出现大量孤立数字/符号行，提示对照原文核对公式
    3. 双栏/表格错序   → 行过短且行数过多，提示右边栏可能被拼到左边

用法：
    python scripts/extract_pdf.py paper.pdf                 # markdown 打到 stdout
    python scripts/extract_pdf.py paper.pdf --out paper.md  # 写文件
    python scripts/extract_pdf.py paper.pdf --report        # 只看诊断，不输出正文
    python scripts/extract_pdf.py paper.pdf --pages 1-3,7   # 只取部分页（1 起）
    python scripts/extract_pdf.py paper.pdf --json          # 机器可读

只使用本机已装的库，不联网安装。pypdf → pdfplumber → PyMuPDF 依次降级。
"""

import argparse
import json
import logging
import re
import statistics
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PAGE_HEADER = "## 第 {n} 页"

# 诊断阈值（调这里即可改变严格程度）
SCAN_MEDIAN_CHARS = 50   # 每页字符数中位数低于此值 → 疑似扫描件
FORMULA_SHORT_LINES = 0.18  # 长度<=3 且含数字的行占比超过此值 → 公式疑似丢失
TWOCOL_MEDIAN_LINE = 28  # 行长度中位数低于此值且行数很多 → 疑似双栏错序
TWOCOL_MIN_LINES = 35


# ------------------------------------------------------------------ 提取后端
def _extract_pypdf(path):
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def _extract_pdfplumber(path):
    import pdfplumber

    out = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return out


def _extract_fitz(path):
    import fitz  # PyMuPDF

    doc = fitz.open(str(path))
    try:
        return [page.get_text() or "" for page in doc]
    finally:
        doc.close()


BACKENDS = [
    ("pypdf", _extract_pypdf, "pip install pypdf"),
    ("pdfplumber", _extract_pdfplumber, "pip install pdfplumber"),
    ("PyMuPDF", _extract_fitz, "pip install pymupdf"),
]


def extract(path):
    """按 pypdf → pdfplumber → PyMuPDF 依次尝试，返回 (pages, backend, notes)。"""
    notes = []
    # pypdf 遇到轻微损坏的 PDF 会往 stderr 刷 "Ignoring wrong pointing object N 0 (offset 0)"，
    # 这些是底层警告、不影响取文，但会淹没我们自己的诊断输出，所以只留 ERROR。
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    for name, fn, hint in BACKENDS:
        try:
            pages = fn(path)
        except ImportError:
            notes.append(f"{name} 未安装（{hint}），跳过")
            continue
        except Exception as exc:  # 加密、损坏、版本不兼容
            notes.append(f"{name} 提取失败：{type(exc).__name__}: {exc}")
            continue
        text_chars = sum(len(p) for p in pages)
        if not pages:
            notes.append(f"{name} 返回 0 页，跳过")
            continue
        if text_chars == 0:
            notes.append(f"{name} 全部页面无文字（可能是扫描件），继续尝试下一个后端")
            # 保留这份结果，作为"确实没有文本层"的证据
            return pages, name, notes
        return pages, name, notes
    raise RuntimeError("没有可用的 PDF 提取后端。请安装其中之一：\n" +
                       "\n".join(f"  - {hint}" for _, _, hint in BACKENDS))


# ------------------------------------------------------------------ 文本规整
def clean_page(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in text.split("\n")]
    # 去掉页眉页脚重复行留出的超长空段，但保留段落间距
    out, blank = [], 0
    for ln in lines:
        if not ln:
            blank += 1
            if blank <= 2:
                out.append("")
        else:
            blank = 0
            out.append(ln)
    return "\n".join(out).strip("\n")


def to_markdown(pages):
    blocks = [f"{PAGE_HEADER.format(n=i)}\n\n{p}" for i, p in enumerate(pages, 1)]
    return "\n\n---\n\n".join(blocks) + "\n"


# ------------------------------------------------------------------ 诊断
def _line_stats(text):
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return {"chars": len(text), "lines": 0, "median_line": 0.0,
                "short_ratio": 0.0, "formula_ratio": 0.0}
    lengths = [len(ln) for ln in lines]
    short = sum(1 for ln in lines if len(ln) <= 3)
    formula_like = sum(1 for ln in lines if len(ln) <= 3 and re.search(r"\d", ln))
    return {
        "chars": len(text),
        "lines": len(lines),
        "median_line": round(statistics.median(lengths), 1),
        "short_ratio": round(short / len(lines), 3),
        "formula_ratio": round(formula_like / len(lines), 3),
    }


def diagnose(pages):
    """返回 {页统计, 问题列表}。问题包含 level: fail/warn 与建议。"""
    per_page = [_line_stats(p) for p in pages]
    char_counts = [s["chars"] for s in per_page] or [0]
    median_chars = statistics.median(char_counts)
    total_chars = sum(char_counts)
    issues = []

    if total_chars == 0:
        issues.append({
            "level": "fail", "kind": "no-text-layer",
            "message": "整份 PDF 没有任何文本层字符。",
            "advice": "按 SKILL.md 降级规则如实告知用户：这是扫描件、无文本层，当前位置无法提取正文；"
                      "可选：让用户提供 OCR 后的文本，或改用 Zotero 已索引全文。不要凭标题编造内容。",
        })
        return {"pages": per_page, "median_chars": median_chars,
                "total_chars": total_chars, "issues": issues}

    if median_chars < SCAN_MEDIAN_CHARS:
        issues.append({
            "level": "fail", "kind": "likely-scan",
            "message": f"每页字符数中位数仅 {median_chars:.0f}（阈值 {SCAN_MEDIAN_CHARS}），疑似扫描件或纯图片 PDF。",
            "advice": "不要继续写精讲。先告诉用户提取到的字数，请其确认是否提供 OCR 文本。",
        })

    # 公式丢失：孤立数字/符号行很多
    mean_formula = statistics.mean([s["formula_ratio"] for s in per_page])
    if mean_formula > FORMULA_SHORT_LINES:
        issues.append({
            "level": "warn", "kind": "formula-loss",
            "message": f"孤立数字/符号行占比 {mean_formula:.0%}，公式排版可能已丢失（尤其 PDF 里公式是图片或特殊字体的）。",
            "advice": "讲到公式时必须对照原文页面核对；无法确认时标注「论文未涉及 / 公式无法完整提取」，不要自行补全。",
        })

    # 双栏错序
    bad_pages = [i for i, s in enumerate(per_page, 1)
                 if s["lines"] >= TWOCOL_MIN_LINES and 0 < s["median_line"] < TWOCOL_MEDIAN_LINE]
    if bad_pages:
        issues.append({
            "level": "warn", "kind": "column-misorder",
            "message": f"第 {', '.join(map(str, bad_pages[:8]))} 页行长度中位数过短且行数多，可能是双栏/表格错序（右栏被拼到左栏后）。",
            "advice": "读这些页时按语义重排，不要逐行照抄；必要时用 --pages 单独取该页人工核对。",
        })

    return {"pages": per_page, "median_chars": median_chars,
            "total_chars": total_chars, "issues": issues}


def format_report(diag, backend, path):
    lines = [f"# PDF 提取报告：{path.name}", "",
             f"- 后端：{backend}", f"- 页数：{len(diag['pages'])}",
             f"- 总字符数：{diag['total_chars']}",
             f"- 每页字符数中位数：{diag['median_chars']:.0f}",
             f"- 预计可写精讲：{'可以' if diag['total_chars'] >= 3000 else '内容偏少，可能需要向用户要全文'}", ""]
    if not diag["issues"]:
        lines.append("诊断结果：未发现明显问题。")
    else:
        lines.append("## 诊断结果")
        for it in diag["issues"]:
            lines.append(f"- [{it['level'].upper()}] {it['kind']}：{it['message']}")
            lines.append(f"  - 处理：{it['advice']}")
    lines += ["", "## 逐页统计", "", "| 页 | 字符数 | 行数 | 行长中位数 | 孤行占比 |", "|---|---|---|---|---|"]
    for i, s in enumerate(diag["pages"], 1):
        lines.append(f"| {i} | {s['chars']} | {s['lines']} | {s['median_line']} | {s['short_ratio']:.0%} |")
    return "\n".join(lines)


# ------------------------------------------------------------------ 命令行
def parse_page_spec(spec, total):
    """支持 '1-3,7' / '2' / '1-' 形式，返回 0 基索引列表。"""
    if not spec:
        return list(range(total))
    picked = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            a, _, b = chunk.partition("-")
            start = int(a) if a.strip() else 1
            end = int(b) if b.strip() else total
        else:
            start = end = int(chunk)
        for n in range(start, end + 1):
            if 1 <= n <= total:
                picked.append(n - 1)
    return sorted(set(picked))


def main(argv=None):
    ap = argparse.ArgumentParser(description="PDF → markdown，并诊断扫描件/公式丢失/双栏错序")
    ap.add_argument("pdf", help="PDF 文件路径")
    ap.add_argument("--out", help="输出 markdown 文件（默认 stdout）")
    ap.add_argument("--pages", help="只取这些页，如 1-3,7（1 起，默认全部）")
    ap.add_argument("--report", action="store_true", help="只打印诊断报告，不输出正文")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出（诊断 + 正文）")
    args = ap.parse_args(argv)

    path = Path(args.pdf)
    if not path.is_file():
        print(f"[ERROR] 文件不存在：{path}", file=sys.stderr)
        return 2

    try:
        pages, backend, notes = extract(path)
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    picked = parse_page_spec(args.pages, len(pages))
    pages = [clean_page(pages[i]) for i in picked]
    diag = diagnose(pages)
    markdown = to_markdown(pages)
    report = format_report(diag, backend, path)
    if notes:
        report += "\n\n## 后端尝试记录\n" + "\n".join(f"- {n}" for n in notes)

    if args.json:
        print(json.dumps({"report": report, "diagnostics": diag,
                          "backend": backend, "notes": notes, "markdown": markdown},
                         ensure_ascii=False, indent=2))
        return 0

    print(report, file=sys.stderr)
    has_fail = any(i["level"] == "fail" for i in diag["issues"])
    if args.report:
        return 1 if has_fail else 0

    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
        print(f"[OK] 已写入 {args.out}（{len(markdown)} 字符）", file=sys.stderr)
    else:
        print(markdown)

    return 1 if has_fail else 0


if __name__ == "__main__":
    sys.exit(main())
