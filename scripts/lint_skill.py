#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paper-deep-reader 技能仓库自检（lint_skill.py）。

解决的问题：本技能的规则同时存在于 SKILL.md、references/deep-reading-template.md
和 assets/deepseek-desktop-agent.json 三处。历史上已经发生过多副本漂移
（JSON 少 3000 字、少一条降级规则、不引用 references/）。本脚本把这些
"必须一致的关键数字"变成可执行断言，漂移会立刻报 FAIL。

检查项：
  1. SKILL.md frontmatter 完整性（name / description / license）
  2. 所有被引用的资源路径真实存在（防改名/删文件后留下死链）
  3. 模板自身的结构自洽（10节 / 10条硬性要求 / 16项自检 / 5条降级）
  4. 三份规则副本的关键数字一致（防漂移）
  5. references/glossary 分册与 field-glossary.md 索引同步
  6. README 是否覆盖新增目录（脚本、评测、许可证、更新日志）

用法：
    python scripts/lint_skill.py             # 只报问题
    python scripts/lint_skill.py --verbose   # 同时打印通过的检查项
    python scripts/lint_skill.py --quiet     # 只打印 FAIL

退出码：0 = 无 FAIL（允许有 WARN）；1 = 存在 FAIL。
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "SKILL.md"
TEMPLATE = ROOT / "references" / "deep-reading-template.md"
GLOSSARY_INDEX = ROOT / "references" / "field-glossary.md"
GLOSSARY_DIR = ROOT / "references" / "glossary"
AGENT_JSON = ROOT / "assets" / "deepseek-desktop-agent.json"
README = ROOT / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
LICENSE = ROOT / "LICENSE"

# 单一事实源：这些数字必须同时出现在三份副本里
EXPECT = {
    "sections": 10,
    "hard_rules": 10,
    "checklist": 16,
    "degradations": 5,
    "min_total": 4500,
    "min_method": 2600,
    "method_share": 55,
}

RESULTS = []  # (level, name, detail)


def record(level, name, detail=""):
    RESULTS.append((level, name, detail))


def ok(name, detail=""):
    record("OK", name, detail)


def warn(name, detail=""):
    record("WARN", name, detail)


def fail(name, detail=""):
    record("FAIL", name, detail)


def read(path):
    if not path.exists():
        fail(f"缺少文件 {path.relative_to(ROOT)}", "请确认文件未被删除或改名")
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail(f"{path.relative_to(ROOT)} 不是 UTF-8 编码", "统一用 UTF-8 存储")
        return ""


def parse_frontmatter(text):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    body = text[3:end].strip("\n")
    data = {}
    for line in body.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", line)
        if m:
            data[m.group(1)] = m.group(2).strip()
    return data


def block(text, start_pat, stop_pats):
    """取从 start_pat 匹配行开始、遇到任一 stop_pat 之前的文本块。"""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if re.search(start_pat, line):
            start = i
            break
    if start is None:
        return ""
    out = [lines[start]]
    for line in lines[start + 1:]:
        if any(re.search(p, line) for p in stop_pats):
            break
        out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- 1. frontmatter
def check_frontmatter():
    text = read(SKILL)
    if not text:
        return
    fm = parse_frontmatter(text)
    if fm is None:
        fail("SKILL.md 缺少 YAML frontmatter", "文件首行必须是 ---")
        return
    if fm.get("name") != "paper-deep-reader":
        fail("frontmatter.name 不是 paper-deep-reader", f"实际值：{fm.get('name')!r}")
    else:
        ok("frontmatter.name")
    desc = fm.get("description", "")
    if len(desc) < 40:
        fail("frontmatter.description 过短", "过短会导致技能路由不准，需包含触发词与适用领域")
    elif "精讲" not in desc or "公式" not in desc:
        warn("description 未包含核心触发词（精讲/公式）", "可能降低被正确触发的概率")
    else:
        ok("frontmatter.description（含触发词）")
    if not fm.get("license"):
        fail("frontmatter 缺少 license 字段", "仓库有 LICENSE 时应在 frontmatter 声明")
    else:
        ok("frontmatter.license")


# ------------------------------------------------------------- 2. 资源路径存在
PATH_RE = re.compile(r"(?<![\w/.-])((?:references|assets|scripts|evals)/[A-Za-z0-9_./-]+)")


def check_links():
    sources = {
        "SKILL.md": SKILL,
        "README.md": README,
        "references/deep-reading-template.md": TEMPLATE,
    }
    checked = set()
    missing = []
    for label, path in sources.items():
        text = read(path)
        for m in PATH_RE.finditer(text):
            rel = m.group(1).rstrip(".,);`")
            if rel in checked:
                continue
            checked.add(rel)
            if not (ROOT / rel).exists():
                missing.append(f"{label} → {rel}")
    if missing:
        fail(f"存在 {len(missing)} 个失效引用", "; ".join(missing))
    else:
        ok(f"资源路径引用全部存在（{len(checked)} 个）")

    # JSON 里的路径引用同样检查
    text = read(AGENT_JSON)
    bad = []
    for m in PATH_RE.finditer(text):
        rel = m.group(1)
        if not (ROOT / rel).exists():
            bad.append(rel)
    if bad:
        fail("agent JSON 引用了不存在的资源", "; ".join(sorted(set(bad))))


# ------------------------------------------------------- 3. 模板结构自洽性
def check_template():
    text = read(TEMPLATE)
    if not text:
        return

    nums = sorted({int(n) for n in re.findall(r"^###\s*第(\d+)节", text, re.M)})
    if nums != list(range(EXPECT["sections"])):
        fail("模板的节标题不是完整的第0～9节", f"实际找到：{nums}")
    else:
        ok(f"模板节标题完整（{EXPECT['sections']} 节）")

    rules_block = block(text, r"^##\s*二、", [r"^##\s"])
    rules = re.findall(r"^(\d+)\.\s+\*\*", rules_block, re.M)
    if len(rules) != EXPECT["hard_rules"]:
        fail(
            "硬性要求条数与预期不符",
            f"模板 {len(rules)} 条，预期 {EXPECT['hard_rules']} 条（改条数须同步 SKILL.md/JSON/自检清单）",
        )
    else:
        ok(f"硬性要求 {len(rules)} 条")

    checks = re.findall(r"^-\s*\[\s*\]\s*(.+)$", text, re.M)
    if len(checks) != EXPECT["checklist"]:
        fail("自检清单项数与预期不符", f"模板 {len(checks)} 项，预期 {EXPECT['checklist']} 项")
    else:
        ok(f"自检清单 {len(checks)} 项")

    deg_block = block(text, r"^###\s*降级规则", [r"^###\s", r"^##\s"])
    rows = [ln for ln in deg_block.splitlines() if ln.strip().startswith("|")]
    rows = [ln for ln in rows if not re.match(r"^\|[\s:|-]+\|$", ln.strip())]
    deg_rows = max(0, len(rows) - 1)  # 去掉表头
    if deg_rows != EXPECT["degradations"]:
        fail(
            "降级规则行数与预期不符",
            f"模板 {deg_rows} 行，预期 {EXPECT['degradations']} 行",
        )
    else:
        ok(f"降级规则 {deg_rows} 行")

    for anchor, label in [
        (str(EXPECT["min_total"]), "全文最低字数"),
        (str(EXPECT["min_method"]), "方法节最低字数"),
        (f"{EXPECT['method_share']}%", "方法节占比"),
    ]:
        if anchor in text:
            ok(f"模板包含{label}（{anchor}）")
        else:
            fail(f"模板缺少{label}（{anchor}）", "关键阈值必须在模板中写明")

    for anchor, label in [
        ("字数预算", "每节字数预算表"),
        ("标题层级", "标题层级映射"),
        ("式(1)", "正文公式自编号约定"),
        ("论文类型", "论文类型路由"),
        ("速览", "速览模式规格"),
    ]:
        if anchor in text:
            ok(f"模板包含{label}")
        else:
            fail(f"模板缺少{label}", "该规则是 check_output.py 的判定依据，必须写进模板")


# ------------------------------------------- 4. 三份副本的关键数字一致性
def check_copies():
    skill = read(SKILL)
    template = read(TEMPLATE)
    agent = read(AGENT_JSON)

    if not (skill and template and agent):
        return

    try:
        data = json.loads(agent)
    except json.JSONDecodeError as exc:
        fail("agent JSON 不是合法 JSON", str(exc))
        return
    for key in ("agent_name", "agent_description", "system_prompt", "opening_message"):
        if not data.get(key):
            fail(f"agent JSON 缺少字段 {key}")
    sp = data.get("system_prompt", "")
    if not sp:
        fail("agent JSON 的 system_prompt 为空")
        return
    ok(f"agent JSON 结构完整（system_prompt {len(sp)} 字符）")

    pairs = [
        (r"第\s*0\s*[～~-]\s*9\s*节|共\s*10\s*节", "10 节结构"),
        (rf"{EXPECT['min_total']}\s*字", f"全文 ≥{EXPECT['min_total']} 字"),
        (rf"{EXPECT['min_method']}\s*字", f"方法节 ≥{EXPECT['min_method']} 字"),
        (rf"{EXPECT['checklist']}\s*项", f"自检 {EXPECT['checklist']} 项"),
    ]
    for pat, label in pairs:
        miss = [
            name
            for name, text in (("SKILL.md", skill), ("template", template), ("agent JSON", sp))
            if not re.search(pat, text)
        ]
        if miss:
            fail(f"『{label}』在以下副本中缺失", "、".join(miss))
        else:
            ok(f"『{label}』三副本一致")

    if not re.search(r"降级", sp):
        fail("agent JSON 未包含降级规则", "用户按桌面端使用时会被迫沉默违规")
    else:
        ok("agent JSON 包含降级规则")

    if not re.search(r"式\(|式号", sp):
        warn("agent JSON 未提到公式出处标注", "建议保留，便于回查原文")

    note = json.dumps(data, ensure_ascii=False)
    if "lint_skill.py" not in note:
        warn(
            "agent JSON 未提示由 lint_skill.py 守护一致性",
            "建议在 maintenance_note 中写明，避免维护者误以为需要手工逐字同步",
        )
    else:
        ok("agent JSON 标注了自动化校验方式")

    # 副本份数声明必须与实际一致
    if re.search(r"两份副本|两个副本", note):
        fail("agent JSON 仍写『两份副本』", "实际是三份：SKILL.md / template / 本 JSON")


# ------------------------------------------------- 5. 术语库分册与索引同步
def check_glossary():
    text = read(GLOSSARY_INDEX)
    if not text:
        return
    files = sorted(p.name for p in GLOSSARY_DIR.glob("*.md")) if GLOSSARY_DIR.is_dir() else []
    if not files:
        fail("references/glossary/ 下没有分册文件", "术语库应按领域拆分以降低上下文占用")
        return
    ok(f"术语库分册 {len(files)} 个")
    missing = [f for f in files if f not in text]
    if missing:
        fail("field-glossary.md 索引未列全分册", "、".join(missing))
    else:
        ok("术语库索引与分册同步")
    empty = []
    for name in files:
        p = GLOSSARY_DIR / name
        body = p.read_text(encoding="utf-8")
        if not body.startswith("#"):
            empty.append(name)
        elif len(body) < 200:
            empty.append(f"{name}(过短)")
    if empty:
        fail("分册内容异常", "、".join(empty))
    else:
        ok("分册内容均以标题开头且非空")


# --------------------------------------------------------- 6. 仓库配套文件
def check_repo():
    for path, label in [
        (LICENSE, "LICENSE"),
        (CHANGELOG, "CHANGELOG.md"),
        (ROOT / "scripts" / "check_output.py", "scripts/check_output.py"),
        (ROOT / "scripts" / "extract_pdf.py", "scripts/extract_pdf.py"),
        (ROOT / "evals" / "README.md", "evals/README.md"),
    ]:
        if path.exists():
            ok(f"存在 {label}")
        else:
            fail(f"缺少 {label}")

    text = read(README)
    if not text:
        return
    if "暂未指定" in text and LICENSE.exists():
        fail("README 仍写『License 暂未指定』", "已补 LICENSE，需同步 README")
    for anchor in ("scripts/", "evals/", "CHANGELOG"):
        if anchor in text:
            ok(f"README 覆盖 {anchor}")
        else:
            warn(f"README 未提及 {anchor}", "新增目录需在 README 中说明")
    if "技能边界" in text or "边界" in text:
        ok("README 说明了技能边界")


def main():
    # Windows 控制台默认不是 UTF-8，输出中文会乱码
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="paper-deep-reader 技能仓库自检")
    ap.add_argument("--verbose", action="store_true", help="同时打印通过的检查项")
    ap.add_argument("--quiet", action="store_true", help="只打印 FAIL")
    args = ap.parse_args()

    for fn in (
        check_frontmatter,
        check_links,
        check_template,
        check_copies,
        check_glossary,
        check_repo,
    ):
        fn()

    fails = [r for r in RESULTS if r[0] == "FAIL"]
    warns = [r for r in RESULTS if r[0] == "WARN"]
    oks = [r for r in RESULTS if r[0] == "OK"]

    icon = {"FAIL": "[FAIL]", "WARN": "[WARN]", "OK": "[ OK ]"}
    for level, name, detail in RESULTS:
        if args.quiet and level != "FAIL":
            continue
        if level == "OK" and not args.verbose and not args.quiet:
            continue
        line = f"{icon[level]} {name}"
        if detail:
            line += f" — {detail}"
        print(line)

    print()
    print(f"通过 {len(oks)} 项，警告 {len(warns)} 项，失败 {len(fails)} 项")
    if fails:
        print("结论：存在必须修复的一致性问题（见上方 FAIL）。")
        return 1
    print("结论：三份副本一致，资源引用完整。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
