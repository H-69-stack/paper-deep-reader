#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按数据出图——给精讲补"看得见"的部分。

为什么单独一个脚本：
    markdown 里的 mermaid 在文档里好看，但 Word 和 LaTeX 都不认；手画 ASCII 图又
    表达不了走势。所以结构图、对比图、热图统一用 matplotlib 出 PNG，再由
    export_docx.py / export_tex.py 嵌进文档，三份产物看到的是同一张图。

四个子命令：
    diagram  结构框图（列式布局，每列若干个方框，自动连线）
    bar      分组条形图（基线对比、消融对比）
    line     折线图（训练曲线、RUL 退化曲线）
    heat     热图（注意力权重、混淆矩阵、位置编码、时频图）

用法：
    python scripts/make_figures.py diagram spec.json -o figs/fig1.png --title "Transformer 整体结构"
    python scripts/make_figures.py bar  data.json -o figs/fig2.png --ylabel "BLEU"
    python scripts/make_figures.py line data.json -o figs/fig3.png
    python scripts/make_figures.py heat data.json -o figs/fig4.png --cmap viridis

数据格式（JSON）：
    diagram: {"columns": [{"title": "输入", "boxes": ["源句", "嵌入"]}, ...],
              "edges": [[0, 1, 0, 0], ...]}      # 可选，[from_col, from_box, to_col, to_box]
    bar/line: {"labels": [...], "series": [{"name": "...", "values": [...]}, ...]}
              或 {"series": [{"name": "...", "x": [...], "y": [...]}]}
    heat:    {"matrix": [[...]], "xticklabels": [...], "yticklabels": [...], "annot": true}

字体：优先 Microsoft YaHei（Windows），其次 Noto Sans CJK / SimHei，都没有就退回默认并提示。
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 统一配色：主色深蓝、辅色橙、第三色灰绿，色盲友好
C_MAIN = "#1F3A5F"
C_ACC = "#D2691E"
C_ALT = "#4E7A6B"
C_GRID = "#DDDDDD"

CJK_FONTS = ["Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", "SimHei", "Arial Unicode MS"]


def setup_matplotlib():
    try:
        import matplotlib
    except ImportError:
        raise SystemExit("[ERROR] 缺少 matplotlib。请先安装：pip install matplotlib")
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in CJK_FONTS:
        if name in installed:
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = 150
    plt.rcParams["savefig.bbox"] = "tight"
    return plt


def load_json(path):
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"[ERROR] 找不到数据文件：{p}")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"[ERROR] {p} 不是合法 JSON：{exc}")


def style_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(True, color=C_GRID, linewidth=0.8, alpha=0.9)
    ax.set_axisbelow(True)


# ------------------------------------------------------------------ diagram
def draw_diagram(plt, spec, out, title=""):
    cols = spec.get("columns") or []
    if not cols:
        raise SystemExit("[ERROR] diagram 需要 columns 字段")

    fig_w = 2.6 * len(cols) + 1.2
    fig_h = max(3.2, 0.95 * max(len(c.get("boxes", [])) for c in cols) + 1.8)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_xlim(0, len(cols))
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=13, color=C_MAIN, pad=14)

    positions = {}          # (col, box) -> (x, y, w, h)
    n_rows = max(len(c.get("boxes", [])) for c in cols)
    box_h = 0.62
    gap = 0.32
    total_h = n_rows * box_h + (n_rows - 1) * gap
    y_top = (fig_h + total_h) / 2 - 0.15

    for ci, col in enumerate(cols):
        boxes = col.get("boxes", [])
        cx = ci + 0.5
        if col.get("title"):
            ax.text(cx, y_top + 0.34, textwrap.fill(col["title"], 12), ha="center", va="bottom",
                    fontsize=10, color=C_MAIN, fontweight="bold", linespacing=1.3)
        for bi, label in enumerate(boxes):
            y = y_top - bi * (box_h + gap) - box_h / 2
            color = col.get("color", C_MAIN)
            ax.add_patch(plt.Rectangle((cx - 0.42, y - box_h / 2), 0.84, box_h,
                                       facecolor="white", edgecolor=color, linewidth=1.6,
                                       zorder=3))
            ax.text(cx, y, textwrap.fill(label, 9), ha="center", va="center", fontsize=9,
                    color="#222222", zorder=4, linespacing=1.35)
            positions[(ci, bi)] = (cx, y)

    def arrow(p1, p2):
        ax.annotate("", xy=p2, xytext=p1,
                    arrowprops=dict(arrowstyle="-|>", color="#555555", linewidth=1.2,
                                    shrinkA=2, shrinkB=2), zorder=2)

    edges = spec.get("edges")
    if edges:
        for fc, fb, tc, tb in edges:
            if (fc, fb) in positions and (tc, tb) in positions:
                (x1, y1), (x2, y2) = positions[(fc, fb)], positions[(tc, tb)]
                if x1 == x2:
                    y_from = y1 - box_h / 2 if y2 < y1 else y1 + box_h / 2
                    y_to = y2 + box_h / 2 if y2 < y1 else y2 - box_h / 2
                    arrow((x1, y_from), (x1, y_to))
                else:
                    dx = 0.42
                    arrow((x1 + dx, y1), (x2 - dx, y2))
    else:
        # 默认连法：列内自上而下，列间由前一列最后一项指向后一列第一项
        for ci, col in enumerate(cols):
            boxes = col.get("boxes", [])
            for bi in range(len(boxes) - 1):
                (x1, y1), (x2, y2) = positions[(ci, bi)], positions[(ci, bi + 1)]
                arrow((x1, y1 - box_h / 2), (x2, y2 + box_h / 2))
            if ci + 1 < len(cols) and boxes and cols[ci + 1].get("boxes"):
                (x1, y1) = positions[(ci, len(boxes) - 1)]
                (x2, y2) = positions[(ci + 1, 0)]
                arrow((x1 + 0.42, y1), (x2 - 0.42, y2))

    fig.savefig(out)
    return out


# ------------------------------------------------------------------ bar
def draw_bar(plt, data, out, title="", ylabel="", ylim=None):
    labels = data.get("labels")
    series = data.get("series") or []
    if not labels or not series:
        raise SystemExit("[ERROR] bar 需要 labels 与 series 字段")

    n = len(series)
    fig, ax = plt.subplots(figsize=(max(5.4, 1.25 * len(labels) + 1.5), 3.8))
    width = 0.8 / max(n, 1)
    colors = [C_MAIN, C_ACC, C_ALT, "#7A6FA1", "#B0B0B0"]
    for si, s in enumerate(series):
        vals = s.get("values") or []
        if len(vals) != len(labels):
            raise SystemExit(f"[ERROR] 序列『{s.get('name')}』长度与 labels 不一致")
        xs = [i + (si - (n - 1) / 2) * width for i in range(len(labels))]
        bars = ax.bar(xs, vals, width=width * 0.92, label=s.get("name", f"序列{si+1}"),
                      color=colors[si % len(colors)], edgecolor="white", linewidth=0.8)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), f"{v:g}",
                    ha="center", va="bottom", fontsize=8.5, color="#333333")

    ax.set_xticks(range(len(labels)))
    longest = max(len(str(lb)) for lb in labels)
    rot = 0 if longest <= 6 else 18
    ax.set_xticklabels(labels, fontsize=9.5, rotation=rot,
                       ha="right" if rot else "center", rotation_mode="anchor")
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    if ylim:
        ax.set_ylim(*ylim)
    if title:
        ax.set_title(title, fontsize=12, color=C_MAIN)
    if n > 1:
        ax.legend(frameon=False, fontsize=9)
    style_axes(ax)
    fig.savefig(out)
    return out


# ------------------------------------------------------------------ line
def draw_line(plt, data, out, title="", xlabel="", ylabel=""):
    series = data.get("series") or []
    if not series:
        raise SystemExit("[ERROR] line 需要 series 字段")
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    colors = [C_MAIN, C_ACC, C_ALT, "#7A6FA1"]
    for si, s in enumerate(series):
        y = s.get("y") or s.get("values") or []
        x = s.get("x") or list(range(len(y)))
        ax.plot(x, y, marker="o", markersize=3.5, linewidth=1.8,
                color=colors[si % len(colors)], label=s.get("name", f"序列{si+1}"))
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=10)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=10)
    if title:
        ax.set_title(title, fontsize=12, color=C_MAIN)
    if len(series) > 1:
        ax.legend(frameon=False, fontsize=9)
    style_axes(ax)
    fig.savefig(out)
    return out


# ------------------------------------------------------------------ heat
def draw_heat(plt, data, out, title="", xlabel="", ylabel="", cmap="Blues", vmin=None, vmax=None):
    import numpy as np

    mat = data.get("matrix")
    if not mat:
        raise SystemExit("[ERROR] heat 需要 matrix 字段")
    arr = np.array(mat, dtype=float)
    k = min(max(arr.shape), 24)
    width = max(4.2, 2.2 + 0.30 * k)
    height = max(3.4, 1.9 + 0.30 * k * arr.shape[0] / max(arr.shape[1], 1))
    fig, ax = plt.subplots(figsize=(width, height))
    im = ax.imshow(arr, cmap=cmap, aspect="auto", vmin=vmin, vmax=vmax)
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    if data.get("xticklabels"):
        ax.set_xticks(range(len(data["xticklabels"])))
        ax.set_xticklabels(data["xticklabels"], fontsize=8, rotation=0)
    if data.get("yticklabels"):
        ax.set_yticks(range(len(data["yticklabels"])))
        ax.set_yticklabels(data["yticklabels"], fontsize=8)
    if data.get("annot"):
        for i in range(arr.shape[0]):
            for j in range(arr.shape[1]):
                ax.text(j, i, f"{arr[i, j]:.2g}", ha="center", va="center",
                        fontsize=7, color="#333333")
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9.5)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9.5)
    if title:
        ax.set_title(title, fontsize=12, color=C_MAIN)
    style_axes(ax)
    ax.grid(False)
    fig.savefig(out)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="按 JSON 数据生成精讲用的插图")
    sub = ap.add_subparsers(dest="cmd", required=True)

    for name, help_text in (("diagram", "结构框图"), ("bar", "条形图"),
                            ("line", "折线图"), ("heat", "热图")):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("data", help="数据 JSON 路径")
        p.add_argument("-o", "--out", required=True, help="输出 PNG 路径")
        p.add_argument("--title", default="", help="图标题")
        if name in ("bar", "line", "heat"):
            p.add_argument("--xlabel", default="", help="X 轴标签")
            p.add_argument("--ylabel", default="", help="Y 轴标签")
        if name == "heat":
            p.add_argument("--cmap", default="Blues", help="matplotlib 色图名，默认 Blues")
            p.add_argument("--vmin", type=float, default=None)
            p.add_argument("--vmax", type=float, default=None)

    args = ap.parse_args(argv)
    plt = setup_matplotlib()
    data = load_json(args.data)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        if args.cmd == "diagram":
            draw_diagram(plt, data, out, args.title)
        elif args.cmd == "bar":
            draw_bar(plt, data, out, args.title, args.ylabel)
        elif args.cmd == "line":
            draw_line(plt, data, out, args.title, args.xlabel, args.ylabel)
        else:
            draw_heat(plt, data, out, args.title, args.xlabel, args.ylabel,
                      args.cmap, args.vmin, args.vmax)
    except OSError as exc:
        raise SystemExit(f"[ERROR] 写图失败：{exc}")

    print(f"[OK] 已生成 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
