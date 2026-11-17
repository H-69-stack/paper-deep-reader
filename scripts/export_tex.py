# -*- coding: utf-8 -*-
"""把论文精讲 / 算法详解的 Markdown 导出成可 Overleaf / XeLaTeX 编译的 .tex。

- 文档类 ctexart（中文直接可编译），不依赖 pandoc / 本地 TeX 安装
- 行内 `$...$`、独立 `$$...$$` 原样保留为数学环境（`$$...$$` → `\\[...\\]`）
- 表格 → tabular（包在 \\resizebox 里防溢出），代码块 → verbatim
- 只做语法层转换，不重排你的公式

用法：
    python scripts/export_tex.py 精讲.md                # 输出同名 .tex
    python scripts/export_tex.py 精讲.md -o 输出.tex
    python scripts/export_tex.py 精讲.md --standalone   # 输出完整文档（默认就是完整文档）
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^```")
FORMULA_BLOCK_RE = re.compile(r"^\$\$\s*$")
TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
BULLET_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+(.*)$")
QUOTE_RE = re.compile(r"^>\s?(.*)$")

PREAMBLE = r"""% !TEX program = xelatex
% 由 paper-deep-reader/scripts/export_tex.py 生成；请用 XeLaTeX 编译（Overleaf 里把 Compiler 设为 XeLaTeX）。
\documentclass[UTF8,zihao=-4]{ctexart}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{bm}
\usepackage{graphicx}
\usepackage{booktabs}
\usepackage{listings}
\usepackage{xcolor}
\usepackage[margin=2.4cm]{geometry}
\usepackage[hidelinks]{hyperref}
\setlength{\parskip}{0.35em}
\setlength{\parindent}{0pt}
\lstset{
  basicstyle=\ttfamily\small,
  breaklines=true,
  columns=fullflexible,
  frame=single,
  rulecolor=\color{gray!40},
  showstringspaces=false
}
\title{@@TITLE@@}
\author{@@AUTHOR@@}
\date{}
\begin{document}
\maketitle
"""

POSTAMBLE = "\n\\end{document}\n"


def esc(text: str) -> str:
    """转义 LaTeX 特殊字符（只用于非数学片段）。"""
    table = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "<": r"\ensuremath{<}",
        ">": r"\ensuremath{>}",
    }
    return "".join(table.get(ch, ch) for ch in text)


INLINE_SPLIT_RE = re.compile(r"(\$[^$\n]+\$|`[^`]+`)")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def inline(text: str) -> str:
    """处理行内：保留 $数学$，`代码` → \\texttt，**粗体** → \\textbf。"""
    out = []
    for piece in INLINE_SPLIT_RE.split(text):
        if not piece:
            continue
        if piece.startswith("$") and piece.endswith("$") and len(piece) > 2:
            out.append(piece)  # 数学原样
        elif piece.startswith("`") and piece.endswith("`") and len(piece) > 2:
            out.append(r"\texttt{" + esc(piece[1:-1]) + "}")
        else:
            # 先处理粗体，再逐段转义
            pos = 0
            for m in BOLD_RE.finditer(piece):
                if m.start() > pos:
                    out.append(esc(piece[pos:m.start()]))
                out.append(r"\textbf{" + esc(m.group(1)) + "}")
                pos = m.end()
            if pos < len(piece):
                out.append(esc(piece[pos:]))
    return "".join(out)


def parse_blocks(text: str):
    blocks = []
    lines = text.splitlines()
    i = 0
    buf: list[str] = []

    def flush_para():
        nonlocal buf
        if buf:
            blocks.append(("p", "\n".join(buf).strip()))
            buf = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush_para()
            i += 1
            continue

        if FENCE_RE.match(stripped):
            flush_para()
            lang = stripped.strip("`").strip()
            i += 1
            body = []
            while i < len(lines) and not FENCE_RE.match(lines[i].strip()):
                body.append(lines[i])
                i += 1
            i += 1
            blocks.append(("code", (lang, "\n".join(body))))
            continue

        if stripped.startswith("$$"):
            flush_para()
            body_lines: list[str] = []
            first = stripped[2:]
            if first.rstrip().endswith("$$") and first.rstrip()[:-2].strip():
                body_lines.append(first.rstrip()[:-2].strip())
                i += 1
            else:
                if first.strip():
                    body_lines.append(first.strip())
                i += 1
                while i < len(lines):
                    cur = lines[i].strip()
                    if cur.endswith("$$"):
                        tail = cur[:-2].strip()
                        if tail:
                            body_lines.append(tail)
                        i += 1
                        break
                    body_lines.append(cur)
                    i += 1
            blocks.append(("math", "\n".join(body_lines).strip()))
            continue

        m = HEADING_RE.match(stripped)
        if m:
            flush_para()
            blocks.append(("h", (len(m.group(1)), m.group(2).strip())))
            i += 1
            continue

        if stripped in {"---", "***", "___"}:
            flush_para()
            blocks.append(("hr", None))
            i += 1
            continue

        if stripped.startswith("|") and "|" in stripped[1:]:
            flush_para()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            blocks.append(("table", rows))
            continue

        if BULLET_RE.match(line):
            flush_para()
            items = []
            while i < len(lines):
                cur = lines[i]
                mm = BULLET_RE.match(cur)
                if mm:
                    items.append(mm.group(2).strip())
                    i += 1
                elif cur.strip() and cur.startswith(("  ", "\t")) and items:
                    items[-1] += " " + cur.strip()
                    i += 1
                else:
                    break
            blocks.append(("list", items))
            continue

        if QUOTE_RE.match(line):
            flush_para()
            quotes = []
            while i < len(lines) and QUOTE_RE.match(lines[i]):
                quotes.append(QUOTE_RE.match(lines[i]).group(1).strip())
                i += 1
            blocks.append(("quote", " ".join(quotes)))
            continue

        buf.append(stripped)
        i += 1

    flush_para()
    return blocks


def table_rows(raw_rows: list[str]) -> list[list[str]]:
    rows = []
    for raw in raw_rows:
        if TABLE_SEP_RE.match(raw):
            continue
        rows.append([c.strip() for c in raw.strip().strip("|").split("|")])
    return rows


def convert(md_text: str) -> tuple[str, dict]:
    blocks = parse_blocks(md_text)
    out: list[str] = []
    stats = {"h1": 0, "table": 0, "code": 0, "math": 0}

    for kind, payload in blocks:
        if kind == "h":
            level, title = payload
            if level == 1 and stats["h1"] == 0:
                stats["h1"] += 1
                continue  # 一级标题当文档标题，正文里不再重复
            cmd = {1: "section", 2: "section", 3: "subsection", 4: "subsubsection"}.get(level, "paragraph")
            if level >= 5:
                cmd = "subsubsection"
            out.append(f"\\{cmd}{{{inline(title)}}}\n")
        elif kind == "p":
            out.append(inline(payload) + "\n")
        elif kind == "list":
            out.append("\\begin{itemize}\n")
            for item in payload:
                out.append("  \\item " + inline(item) + "\n")
            out.append("\\end{itemize}\n")
        elif kind == "quote":
            out.append("\\begin{quote}\n" + inline(payload) + "\n\\end{quote}\n")
        elif kind == "code":
            lang, body = payload
            if FENCE_RE.search(body):
                body = body.replace("```", "'''")
            out.append("\\begin{lstlisting}" + (f"[language={lang}]" if lang and lang.isalpha() else "") + "\n")
            out.append(body + "\n")
            out.append("\\end{lstlisting}\n")
            stats["code"] += 1
        elif kind == "math":
            body = payload.strip()
            if body.startswith("\\[") and body.endswith("\\]"):
                body = body[2:-2].strip()
            out.append("\\[\n" + body + "\n\\]\n")
            stats["math"] += 1
        elif kind == "table":
            rows = table_rows(payload)
            if not rows:
                continue
            ncol = max(len(r) for r in rows)
            spec = "l" * ncol
            out.append("\\begin{table}[htbp]\n\\centering\n\\small\n")
            out.append("\\resizebox{\\linewidth}{!}{%\n")
            out.append(f"\\begin{{tabular}}{{{spec}}}\n\\toprule\n")
            for r_idx, row in enumerate(rows):
                cells = [inline(row[c]) if c < len(row) else "" for c in range(ncol)]
                out.append(" & ".join(cells) + r" \\" + "\n")
                if r_idx == 0:
                    out.append("\\midrule\n")
            out.append("\\bottomrule\n\\end{tabular}}\n\\end{table}\n")
            stats["table"] += 1
        elif kind == "hr":
            out.append("\\bigskip\\hrule\\bigskip\n")

    return "\n".join(out), stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Markdown 精讲 → .tex（XeLaTeX / Overleaf）")
    ap.add_argument("md", help="要导出的 markdown 文件")
    ap.add_argument("-o", "--out", help="输出 .tex 路径（默认同名）")
    ap.add_argument("--title", help="文档标题（默认取第一个一级标题）")
    ap.add_argument("--author", default="", help="作者署名（默认留空）")
    args = ap.parse_args(argv)

    md_path = Path(args.md)
    if not md_path.is_file():
        print(f"找不到文件：{md_path}", file=sys.stderr)
        return 2

    text = md_path.read_text(encoding="utf-8")
    first_h1 = ""
    for line in text.splitlines():
        m = re.match(r"^#\s+(.*)$", line.strip())
        if m:
            first_h1 = m.group(1).strip()
            break

    body, stats = convert(text)
    title = args.title or first_h1 or md_path.stem
    doc = (
        PREAMBLE.replace("@@TITLE@@", esc(title)).replace("@@AUTHOR@@", esc(args.author))
        + body
        + POSTAMBLE
    )
    out = Path(args.out) if args.out else md_path.with_suffix(".tex")
    out.write_text(doc, encoding="utf-8")
    print(f"已生成 {out}")
    print(f"  公式 {stats['math']} 个；表格 {stats['table']} 个；代码块 {stats['code']} 个")
    print("  编译方式：xelatex 文件名.tex（Overleaf 里把 Compiler 设为 XeLaTeX；ctexart 自带中文字体配置）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
