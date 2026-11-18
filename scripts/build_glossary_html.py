#!/usr/bin/env python3
"""把 references/glossary/ 下的术语分册编译成一张可检索的单页 HTML。

用法：
    python scripts/build_glossary_html.py
    python scripts/build_glossary_html.py -o 自定义路径.html

产物：references/glossary-index.html（单文件、无外部依赖、可离线打开、可打印）
改了任何术语分册或索引后都要重跑一次，否则页面里的条目数会落后。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "references" / "glossary"
INDEX = ROOT / "references" / "field-glossary.md"
DEFAULT_OUT = ROOT / "references" / "glossary-index.html"

# 分册 → (展示名, 分组)；分组的顺序决定页面顺序
VOLUME_META = {
    "bearing": ("滚动轴承", "对象"),
    "motor": ("电机", "对象"),
    "rcc": ("导电滚环 RCC", "对象"),
    "valve": ("液压电磁阀", "对象"),
    "gearbox": ("齿轮箱", "对象"),
    "pump": ("泵", "对象"),
    "cylinder": ("液压缸", "对象"),
    "objects": ("研究对象总览", "对象"),
    "phm": ("PHM 全链路", "方法"),
    "signal": ("信号处理", "方法"),
    "ml": ("机器学习", "方法"),
    "dl": ("深度学习", "方法"),
    "llm-agent": ("大模型与 Agent", "方法"),
    "metrics": ("评价指标", "方法"),
    "translation": ("领域翻译与比喻", "基础"),
    "symbols": ("数学符号", "基础"),
}

TABLE_ROW = re.compile(r"^\|(.+)\|\s*$")
SEP_ROW = re.compile(r"^\|[\s:|-]+\|\s*$")


def parse_volume(path: Path) -> dict:
    """解析一个分册：标题、导语、若干张表格（表头可不同）、数字例子。"""
    text = path.read_text(encoding="utf-8")
    title = ""
    intro: list[str] = []
    tables: list[dict] = []
    examples: list[dict] = []
    cur_example: dict | None = None
    cur_table: dict | None = None
    section = ""

    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            name = line[3:].strip()
            cur_table = None
            section = name
            if "例子" in name:
                cur_example = {"title": name, "body": []}
                examples.append(cur_example)
            else:
                cur_example = None
            continue
        if line.startswith(">"):
            if cur_example is None and not tables:
                intro.append(line.lstrip("> ").strip())
            continue
        if TABLE_ROW.match(line):
            if SEP_ROW.match(line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not cells:
                continue
            if cur_table is None:
                cur_table = {"headers": cells, "rows": [], "caption": section}
                tables.append(cur_table)
                continue
            if len(cells) == len(cur_table["headers"]):
                cur_table["rows"].append(cells)
            continue
        if line.strip():
            cur_table = None
        if cur_example is not None and line.strip():
            cur_example["body"].append(line.strip())

    tables = [t for t in tables if t["rows"]]
    return {
        "file": path.stem,
        "title": title or path.stem,
        "intro": [p for p in intro if p],
        "tables": tables,
        "examples": [{"title": e["title"], "body": "\n".join(e["body"])} for e in examples],
    }


def parse_index() -> dict:
    """从 field-glossary.md 里取路由表。"""
    if not INDEX.exists():
        return {"routes": []}
    routes = []
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        if line.startswith("|") and "`" in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 3 and "论文方向" not in cells[0] and not SEP_ROW.match(line):
                routes.append({"direction": cells[0], "must": cells[1], "optional": cells[2]})
    return {"routes": routes}


PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>论文精讲 · 术语库速查（__TOTAL__ 条 / __VOLUMES__ 册）</title>
<style>
  :root {
    --ink: #1f2933; --muted: #5f6b76; --line: #dfe3e8; --bg: #f7f8fa;
    --accent: #1f3a5f; --accent2: #b4560f; --chip: #eef1f5;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--ink);
    font-family: "Microsoft YaHei", "Noto Sans CJK SC", "Source Han Sans SC", -apple-system, sans-serif;
    line-height: 1.6;
  }
  header {
    position: sticky; top: 0; z-index: 20; background: #fff;
    border-bottom: 1px solid var(--line); padding: 14px 20px 10px;
  }
  h1 { margin: 0 0 4px; font-size: 19px; color: var(--accent); }
  .sub { color: var(--muted); font-size: 13px; margin-bottom: 10px; }
  .searchrow { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
  #q {
    flex: 1 1 320px; min-width: 200px; padding: 9px 12px; font-size: 15px;
    border: 1px solid var(--line); border-radius: 8px; outline: none; background: #fff;
  }
  #q:focus { border-color: var(--accent); box-shadow: 0 0 0 3px rgba(31,58,95,.12); }
  #count { color: var(--muted); font-size: 13px; white-space: nowrap; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
  .chip {
    border: 1px solid var(--line); background: var(--chip); color: var(--ink);
    border-radius: 999px; padding: 3px 11px; font-size: 13px; cursor: pointer;
  }
  .chip[aria-pressed="true"] { background: var(--accent); color: #fff; border-color: var(--accent); }
  main { padding: 18px 20px 60px; max-width: 1180px; margin: 0 auto; }
  .vol { margin: 0 0 22px; }
  .vol h2 { font-size: 16px; margin: 0 0 2px; color: var(--accent); display: flex; align-items: baseline; gap: 8px; }
  .vol h2 small { color: var(--muted); font-weight: normal; font-size: 12px; }
  .intro { color: var(--muted); font-size: 13px; margin: 0 0 8px; }
  table { width: 100%; border-collapse: collapse; background: #fff; font-size: 13.5px; }
  th, td { border: 1px solid var(--line); padding: 7px 9px; vertical-align: top; text-align: left; }
  th { background: #f0f3f7; font-weight: 600; }
  td:first-child { width: 15%; font-weight: 600; }
  tr.hit td { background: #fff7ea; }
  mark { background: #ffe08a; padding: 0 1px; border-radius: 2px; }
  details { margin: 6px 0 0; font-size: 13px; color: var(--muted); }
  details summary { cursor: pointer; color: var(--accent2); }
  pre { white-space: pre-wrap; background: #fbfbfd; border: 1px dashed var(--line); padding: 8px 10px; border-radius: 6px; }
  .empty { color: var(--muted); padding: 30px 4px; }
  footer { color: var(--muted); font-size: 12px; text-align: center; padding: 0 0 30px; }
  @media print {
    header { position: static; } .chips, #q { display: none; }
    main { max-width: none; } tr.hit td { background: none; }
  }
</style>
</head>
<body>
<header>
  <h1>论文精讲 · 术语库速查</h1>
  <div class="sub">__VOLUMES__ 册 · __TOTAL__ 条术语 · 支持中文 / 英文 / 比喻 / 信号表现模糊搜索（快捷键 <b>/</b>，Esc 清空）</div>
  <div class="searchrow">
    <input id="q" type="search" placeholder="如：BPFO / 接触电阻 / 汽蚀 / 边带 / 爬行" autocomplete="off">
    <span id="count"></span>
  </div>
  <div class="chips" id="chips"></div>
</header>
<main>
  <section id="routes"></section>
  <div id="list"></div>
</main>
<footer>由 <code>scripts/build_glossary_html.py</code> 从 <code>references/glossary/*.md</code> 自动生成；改完分册要重跑。</footer>

<script>
const DATA = __DATA__;
const volumes = DATA.volumes;
const chipsEl = document.getElementById("chips");
const listEl = document.getElementById("list");
const qEl = document.getElementById("q");
const countEl = document.getElementById("count");
let active = null;

function esc(s) {
  return String(s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}
function hl(text, terms) {
  let out = esc(text);
  terms.forEach(function (t) {
    if (!t) return;
    const safe = t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(safe, "gi"), function (m) { return "<mark>" + m + "</mark>"; });
  });
  return out;
}

// 路由表（默认收起，打印时展开）
(function () {
  const el = document.getElementById("routes");
  if (!DATA.routes.length) return;
  const rows = DATA.routes.map(function (r) {
    return "<tr><td>" + esc(r.direction) + "</td><td>" + esc(r.must) + "</td><td>" + esc(r.optional) + "</td></tr>";
  }).join("");
  el.innerHTML = "<details><summary>按论文方向选册（" + DATA.routes.length +
    " 行，来自 field-glossary.md）</summary><table><thead><tr><th>论文方向</th><th>必读</th><th>可选</th></tr></thead><tbody>" +
    rows + "</tbody></table></details>";
})();

// 分册筛选
const allChip = document.createElement("button");
allChip.className = "chip";
allChip.textContent = "全部";
allChip.dataset.file = "";
chipsEl.appendChild(allChip);
volumes.forEach(function (v) {
  const b = document.createElement("button");
  b.className = "chip";
  b.textContent = v.title + " " + v.count;
  b.dataset.file = v.file;
  chipsEl.appendChild(b);
});
chipsEl.addEventListener("click", function (e) {
  const b = e.target.closest(".chip");
  if (!b) return;
  active = b.dataset.file || null;
  Array.prototype.forEach.call(chipsEl.children, function (c) {
    c.setAttribute("aria-pressed", String((c.dataset.file || "") === (active || "")));
  });
  render();
});
allChip.setAttribute("aria-pressed", "true");

function render() {
  const raw = qEl.value.trim();
  const terms = raw ? raw.split(/\s+/).filter(Boolean) : [];
  let total = 0;
  const parts = [];

  volumes.forEach(function (v) {
    if (active && v.file !== active) return;
    const blocks = [];
    let volHits = 0;
    v.tables.forEach(function (t, ti) {
      const hits = t.rows.filter(function (r) {
        const hay = (r.join(" ") + " " + v.title).toLowerCase();
        return terms.every(function (x) { return hay.indexOf(x.toLowerCase()) >= 0; });
      });
      if (!hits.length) return;
      volHits += hits.length;
      const head = t.headers.map(function (h) { return "<th>" + esc(h) + "</th>"; }).join("");
      const body = hits.map(function (r) {
        return '<tr class="' + (terms.length ? "hit" : "") + '">' + r.map(function (c) {
          return "<td>" + hl(c, terms) + "</td>";
        }).join("") + "</tr>";
      }).join("");
      const cap = (ti > 0 && t.caption) ? "<p class=\"intro\">" + esc(t.caption) + "</p>" : "";
      blocks.push(cap + "<table><thead><tr>" + head + "</tr></thead><tbody>" + body + "</tbody></table>");
    });
    if (!volHits) return;
    total += volHits;
    const ex = (!terms.length || !v.examples.length) ? "" :
      "<details><summary>本册数字例子（" + v.examples.length + " 个）</summary>" +
      v.examples.map(function (e) {
        return "<p><b>" + esc(e.title) + "</b></p><pre>" + esc(e.body) + "</pre>";
      }).join("") + "</details>";
    parts.push('<section class="vol"><h2>' + esc(v.title) + " <small>" + esc(v.group) + " · " +
      volHits + ' 条</small></h2>' +
      (v.intro.length ? '<p class="intro">' + esc(v.intro.join(" ")) + "</p>" : "") +
      blocks.join("") + ex + "</section>");
  });

  listEl.innerHTML = parts.join("") || '<div class="empty">没有匹配的条目。换个关键词，或点"全部"。</div>';
  countEl.textContent = "命中 " + total + " 条";
}

qEl.addEventListener("input", render);
document.addEventListener("keydown", function (e) {
  if (e.key === "/" && document.activeElement !== qEl) { e.preventDefault(); qEl.focus(); }
  if (e.key === "Escape") { qEl.value = ""; render(); qEl.blur(); }
});
render();
</script>
</body>
</html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description="生成术语库单页检索 HTML")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    if not GLOSSARY.is_dir():
        print(f"[FAIL] 找不到术语分册目录：{GLOSSARY}", file=sys.stderr)
        return 1

    volumes = []
    for path in sorted(GLOSSARY.glob("*.md")):
        vol = parse_volume(path)
        vol["count"] = sum(len(tb["rows"]) for tb in vol["tables"])
        if not vol["count"]:
            continue
        name, group = VOLUME_META.get(vol["file"], (vol["title"], "其他"))
        vol["title"] = name
        vol["group"] = group
        volumes.append(vol)

    order = {"对象": 0, "方法": 1, "基础": 2, "其他": 3}
    volumes.sort(key=lambda v: (order.get(v["group"], 9), v["file"]))

    idx = parse_index()
    total = sum(v["count"] for v in volumes)
    data = {"volumes": volumes, "routes": idx["routes"]}

    page = (
        PAGE.replace("__TOTAL__", str(total))
        .replace("__VOLUMES__", str(len(volumes)))
        .replace("__DATA__", json.dumps(data, ensure_ascii=False))
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8", newline="\n")

    print(f"[OK] {out}")
    print(f"  分册 {len(volumes)} 册，术语 {total} 条，路由 {len(idx['routes'])} 行，{len(page) / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
