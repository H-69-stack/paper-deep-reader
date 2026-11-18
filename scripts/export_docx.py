# -*- coding: utf-8 -*-
"""把论文精讲 / 算法详解的 Markdown 导出成 .docx。

- 标题按 # 层级映射到 Word 标题样式
- 公式：行内 `$...$` 转普通文本（去掉 $ 记号）；独立 `$$...$$` 用 matplotlib 渲成 PNG 插入
- 表格：Markdown 表格 → Word 表格
- 代码块：等宽字体段落
- 不联网、不调用 pandoc / Word，只依赖 python-docx 与 matplotlib

用法：
    python scripts/export_docx.py 精讲.md                 # 输出同名 .docx
    python scripts/export_docx.py 精讲.md -o 输出.docx
    python scripts/export_docx.py 精讲.md --keep-images    # 保留渲染出的公式图片目录
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^```")
FORMULA_BLOCK_RE = re.compile(r"^\$\$\s*$")
TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
BULLET_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+(.*)$")
QUOTE_RE = re.compile(r"^>\s?(.*)$")
INLINE_MATH_RE = re.compile(r"\$([^$\n]+)\$")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
CODE_SPAN_RE = re.compile(r"`([^`]+)`")
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
# ![图 1 xxx](figs/fig1.png) 或带可选标题的写法
IMAGE_RE = re.compile(r"^!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+\"[^\"]*\")?\s*\)$")


# ---------------------------------------------------------------- markdown 解析
def parse_blocks(text: str):
    """把 markdown 切成 [(kind, payload), ...]，kind ∈ h/p/code/math/table/list/quote/hr。"""
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
            i += 1  # 跳过结束围栏
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

        m = IMAGE_RE.match(stripped)
        if m:
            flush_para()
            blocks.append(("img", (m.group(1).strip(), m.group(2).strip())))
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

        m = BULLET_RE.match(line)
        if m:
            flush_para()
            items = []
            while i < len(lines):
                cur = lines[i]
                mm = BULLET_RE.match(cur)
                if mm:
                    items.append(mm.group(2).strip())
                    i += 1
                elif cur.strip() and cur.startswith(("  ", "\t")) and items:
                    items[-1] += " " + cur.strip()  # 续行
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
        cells = [c.strip() for c in raw.strip().strip("|").split("|")]
        rows.append(cells)
    return rows


def plain(text: str) -> str:
    """去掉行内 markdown 记号，供 Word 普通文本使用。"""
    text = INLINE_MATH_RE.sub(lambda m: m.group(1).strip(), text)
    text = CODE_SPAN_RE.sub(lambda m: m.group(1), text)
    text = BOLD_RE.sub(lambda m: m.group(1), text)
    text = text.replace("\\(", "(").replace("\\)", ")")
    return text


# ---------------------------------------------------------------- 公式渲图
def sanitize_for_mathtext(expr: str) -> str:
    """把 mathtext 不支持的常见命令降级成它能渲染的形式（只用于画图，不改原文）。"""
    # \underbrace{X}_{Y} → X\ (Y)，\overbrace 同理
    for cmd in ("underbrace", "overbrace"):
        pattern = re.compile(r"\\" + cmd + r"\{")
        while True:
            m = pattern.search(expr)
            if not m:
                break
            start = m.start()
            depth = 0
            j = m.end() - 1
            while j < len(expr):
                if expr[j] == "{":
                    depth += 1
                elif expr[j] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            inner = expr[m.end():j]
            rest = expr[j + 1:]
            sub = re.match(r"_\{\}", rest)
            note = ""
            if sub:
                start2 = sub.start()
                depth = 0
                k = start2
                while k < len(rest):
                    if rest[k] == "{":
                        depth += 1
                    elif rest[k] == "}":
                        depth -= 1
                        if depth == 0:
                            break
                    k += 1
                note = rest[start2 + 2:k]
                rest = rest[k + 1:]
            expr = expr[:start] + inner + (r"\ \left(" + note + r"\right)" if note else "") + rest
    # \boxed{X} → X
    expr = re.sub(r"\\boxed\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}", r"\1", expr)
    # \text{纯英文} → \mathrm{...}；含中文的 \text 直接删掉外层
    expr = re.sub(r"\\text\{([A-Za-z0-9\s\-_/]+)\}", r"\\mathrm{\1}", expr)
    expr = re.sub(r"\\text\{([^{}]*)\}", r"\\mathrm{\1}", expr)
    expr = expr.replace(r"\qquad", r"\ \ \ ").replace(r"\quad", r"\ \ ")
    expr = expr.replace(r"\left", "").replace(r"\right", "")
    expr = expr.replace(r"\big", "").replace(r"\Big", "")
    expr = re.sub(r"\\(operatorname|mathrm|mathbf|mathit|mathcal)\{([^{}]*)\}", lambda m: "\\" + m.group(1) + "{" + m.group(2) + "}", expr)
    return expr


def render_formula(tex: str, out_png: Path) -> bool:
    """把独立公式渲成 PNG。成功返回 True；mathtext 不支持（如含中文）时返回 False。"""
    import logging

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        logging.getLogger("matplotlib").setLevel(logging.ERROR)
        logging.getLogger("matplotlib.mathtext").setLevel(logging.ERROR)
    except Exception:  # noqa: BLE001
        return False

    body = tex.strip()
    if body.startswith("\\[") and body.endswith("\\]"):
        body = body[2:-2].strip()
    body = body.replace("$$", "").strip()
    if not body:
        return False

    # mathtext 只认 $...$；把 latex 环境包裹成普通数学文本
    expr = body
    if "\\begin{" in expr:  # align / cases 等环境 mathtext 不一定支持，退回原文
        return False
    expr = expr.replace("\n", " ")

    candidates = [expr]
    cleaned = sanitize_for_mathtext(expr)
    # 清洗后若还剩中文，mathtext 会渲染成方框，不如老实退回文本
    if cleaned != expr and not CJK_RE.search(cleaned):
        candidates.append(cleaned)

    n_lines = max(1, body.count("\\\\") + 1)
    width = 8.0
    height = 0.9 + 0.55 * n_lines
    for cand in candidates:
        text = cand if cand.startswith("$") else f"${cand}$"
        try:
            fig = plt.figure(figsize=(width, height), dpi=200)
            fig.text(0.5, 0.5, text, ha="center", va="center", fontsize=12)
            fig.savefig(out_png, bbox_inches="tight", pad_inches=0.08, transparent=False, facecolor="white")
            plt.close(fig)
            if out_png.stat().st_size > 0:
                return True
        except Exception:  # noqa: BLE001
            try:
                plt.close("all")
            except Exception:  # noqa: BLE001
                pass
    return False


# ---------------------------------------------------------------- docx 组装
def build_docx(md_path: Path, out_path: Path, img_dir: Path, keep_images: bool) -> None:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm, Pt, RGBColor

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(10.5)

    blocks = parse_blocks(md_path.read_text(encoding="utf-8"))
    img_dir.mkdir(parents=True, exist_ok=True)
    img_no = 0
    stats = {"formula_img": 0, "formula_text": 0, "table": 0, "code": 0, "figure": 0, "figure_missing": 0}

    def add_text_runs(par, text: str) -> None:
        """把一段文本按 **粗体** / `代码` 拆成 run。"""
        pos = 0
        for m in re.finditer(r"\*\*([^*]+)\*\*|`([^`]+)`", text):
            if m.start() > pos:
                par.add_run(plain(text[pos:m.start()]))
            if m.group(1) is not None:
                run = par.add_run(plain(m.group(1)))
                run.bold = True
            else:
                run = par.add_run(m.group(2))
                run.font.name = "Consolas"
                run.font.size = Pt(9.5)
            pos = m.end()
        if pos < len(text):
            par.add_run(plain(text[pos:]))

    for kind, payload in blocks:
        if kind == "h":
            level, title = payload
            heading = doc.add_heading(level=min(level, 4))
            run = heading.add_run(plain(title))
            run.font.color.rgb = RGBColor(0x1F, 0x3A, 0x5F)
        elif kind == "p":
            par = doc.add_paragraph()
            par.paragraph_format.space_after = Pt(6)
            add_text_runs(par, payload)
        elif kind == "list":
            for item in payload:
                par = doc.add_paragraph(style="List Bullet")
                add_text_runs(par, item)
        elif kind == "quote":
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Cm(0.6)
            run = par.add_run(plain(payload))
            run.italic = True
            run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
        elif kind == "code":
            lang, body = payload
            par = doc.add_paragraph()
            par.paragraph_format.left_indent = Cm(0.4)
            par.paragraph_format.space_before = Pt(4)
            par.paragraph_format.space_after = Pt(6)
            run = par.add_run(body)
            run.font.name = "Consolas"
            run.font.size = Pt(8.5)
            if lang:
                cap = doc.add_paragraph()
                cap.paragraph_format.space_after = Pt(2)
                cap_run = cap.add_run(f"[代码块 {lang}]")
                cap_run.font.size = Pt(8)
                cap_run.font.color.rgb = RGBColor(0x88, 0x88, 0x88)
            stats["code"] += 1
        elif kind == "math":
            img_no += 1
            png = img_dir / f"formula_{img_no:03d}.png"
            if render_formula(payload, png):
                par = doc.add_paragraph()
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = par.add_run()
                run.add_picture(str(png), width=Cm(15.5))
                stats["formula_img"] += 1
            else:
                par = doc.add_paragraph()
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = par.add_run(payload)
                run.font.name = "Cambria Math"
                run.font.size = Pt(10)
                stats["formula_text"] += 1
        elif kind == "table":
            rows = table_rows(payload)
            if not rows:
                continue
            ncol = max(len(r) for r in rows)
            table = doc.add_table(rows=0, cols=ncol)
            table.style = "Table Grid"
            for r_idx, row in enumerate(rows):
                cells = table.add_row().cells
                for c_idx in range(ncol):
                    text = row[c_idx] if c_idx < len(row) else ""
                    par = cells[c_idx].paragraphs[0]
                    add_text_runs(par, text)
                    if r_idx == 0:
                        for run in par.runs:
                            run.bold = True
            stats["table"] += 1
        elif kind == "img":
            alt, rel = payload
            src = (md_path.parent / rel).resolve()
            if src.is_file():
                par = doc.add_paragraph()
                par.alignment = WD_ALIGN_PARAGRAPH.CENTER
                par.paragraph_format.space_before = Pt(6)
                par.paragraph_format.space_after = Pt(2)
                par.add_run().add_picture(str(src), width=Cm(15.0))
                if alt:
                    cap = doc.add_paragraph()
                    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    cap.paragraph_format.space_after = Pt(8)
                    cap_run = cap.add_run(plain(alt))
                    cap_run.font.size = Pt(9)
                    cap_run.italic = True
                    cap_run.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
                stats["figure"] += 1
            else:
                par = doc.add_paragraph()
                run = par.add_run(f"[缺图] {alt or rel}（找不到文件 {rel}）")
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(0xB0, 0x30, 0x30)
                stats["figure_missing"] += 1
        elif kind == "hr":
            par = doc.add_paragraph()
            par.paragraph_format.space_before = Pt(2)
            par.paragraph_format.space_after = Pt(2)
            run = par.add_run("—" * 28)
            run.font.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
            run.font.size = Pt(8)

    doc.save(str(out_path))

    if not keep_images:
        try:
            for png in img_dir.glob("*.png"):
                png.unlink()
            img_dir.rmdir()
        except OSError:
            pass

    print(f"已生成 {out_path}")
    print(
        "  公式渲成图片 {formula_img} 个 / 退回文本 {formula_text} 个；"
        "表格 {table} 个；代码块 {code} 个；插图 {figure} 张".format(**stats)
    )
    if stats["figure_missing"]:
        print(f"  警告：有 {stats['figure_missing']} 张插图找不到文件，已在文档中标红占位。")
    if stats["formula_text"]:
        print("  提示：含中文或 mathtext 不支持环境的公式保留了原始 LaTeX 文本，请在 Word 里用公式编辑器核对。")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Markdown 精讲 → .docx")
    ap.add_argument("md", help="要导出的 markdown 文件")
    ap.add_argument("-o", "--out", help="输出 .docx 路径（默认同名）")
    ap.add_argument("--keep-images", action="store_true", help="保留下载… 保留渲染出的公式图片")
    args = ap.parse_args(argv)

    md_path = Path(args.md)
    if not md_path.is_file():
        print(f"找不到文件：{md_path}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else md_path.with_suffix(".docx")
    img_dir = Path(tempfile.mkdtemp(prefix="pdr_formula_")) if not args.keep_images else md_path.with_name(
        md_path.stem + "_formulas"
    )
    try:
        build_docx(md_path, out, img_dir, args.keep_images)
    except ImportError as exc:
        print(f"缺少依赖：{exc}。请先 pip install python-docx matplotlib", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
