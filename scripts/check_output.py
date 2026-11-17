#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""精讲成品机械自检（check_output.py）。

背景：references/deep-reading-template.md 里的交付前自检，人工"逐项核对"在写完
四五千字之后基本等于自我盖章。本脚本把其中**可机械判定**的部分变成真检查，
交付前跑一遍，结论可以直接附在交付说明里。

三种模式（对应模板第十一节的模式路由）：

    paper      论文精讲：第0～9节固定结构（默认，适合"精讲这篇论文"）
    algorithm  算法详解：章结构不限数目（适合"把这个项目的算法讲透"）
    brief      速览：约 800 字，只要总览 + 要点表 + 值不值得读

检查项：

    S1/S1b  结构完整性（paper 10 节齐全 / brief 三件套齐全）
    S2      标题层级；A1 算法模式的章结构与连续性
    S3      三段式：每个模块要有"通俗解释 + 公式 + 手算例子"的实质内容
    S4      有公式却没有数字例子，逐个点名（降级规则豁免的不算）
    S5      禁用词：显然/易知/同理可得/化简得/整理得/不言而喻/众所周知
    S6      篇幅：全文≥4500 字、方法部分≥2600 字且≥55%、每节落在预算内
    S7      FAQ：第9节至少 5 个问题
    S8      术语中英对照：至少 5 处"中文（English）"
    S9      公式编号：正文 式(n) 集合与第8节速查表一致
    S10     出处标注：第5节的数字旁边要有 式/图/表 出处
    S11     推测标注：写了"推测"就必须同时写"论文未涉及"
    S12     无占位符（TODO/待补充）

用法：
    python scripts/check_output.py 某某论文-精讲.md                    # 自动判模式
    python scripts/check_output.py 某某论文-精讲.md --profile algorithm
    python scripts/check_output.py 某某论文-精讲.md --profile brief
    python scripts/check_output.py 某某论文-精讲.md --min-total 3000 --min-method 1800
    python scripts/check_output.py 某某论文-精讲.md --json --quiet

退出码：0 = 无 FAIL；1 = 存在 FAIL。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 常量与阈值
CJK = re.compile(r"[\u4e00-\u9fff]")

FORBIDDEN = ["显然", "易知", "同理可得", "同理", "化简得", "整理得", "不言而喻", "众所周知"]
# 规则本身在讲"禁止写 X"时会出现这些词，属于合法引用
EXEMPT_CTX = ("禁止", "不许", "不准", "不得", "不要写", "禁词", "算不合格", "违规")

# 每节字数预算（中文字符）—— 与模板"字数预算"表保持一致
BUDGET = {
    "0": (50, 240),
    "1": (450, 1200),
    "2": (450, 1400),
    "3": (2600, 12000),
    "4": (270, 1000),
    "5": (540, 1600),
    "6": (220, 800),
    "7": (300, 900),
    "8": (50, 900),
    "9": (300, 1000),
}
MIN_TOTAL = 4500
MIN_METHOD = 2600
MIN_SHARE = 55
MIN_FAQ = 5
MIN_TERMS = 5
MIN_CITATIONS = 3
MIN_BRIEF = 600

# 节标题：## 第 3 节 … / ## 第3章 … / ## 3. …
SECTION_RE = re.compile(r"^#{2,3}[ \t]*第[ \t]*(\d+)[ \t]*[节章][ \t]*[:：、.]?[ \t]*(.*)$", re.M)
NUMBERED_RE = re.compile(r"^#{2,3}[ \t]*(\d+)[ \t]*[.、](?!\d)[ \t]*(.*)$", re.M)
STEP_RE = re.compile(r"^#{3,5}[ \t]*步骤[ \t]*[0-9一二三四五六七八九十]+[ \t]*[:：][ \t]*(.+)$", re.M)

# 三段式的"实质"标记：不要求用固定小标题，只要有对应内容
PLAIN_MARK = ("通俗理解", "通俗解释", "通俗地说", "打个比方", "比喻", "就像", "好比", "可以理解为", "大白话")
EXAMPLE_MARK = ("数字例子", "举个例子", "举例", "算一下", "代入", "手算", "演示", "数值例子", "小例子", "走一遍")
FORMULA_RE = re.compile(r"\$\$|\\\[|\\begin\{(?:equation|aligned|array|cases)\}|式\s*[（(]\s*\d")

RESULTS = []  # (level, code, name, detail)


def add(level, code, name, detail=""):
    RESULTS.append((level, code, name, detail))


def ok(code, name, detail=""):
    add("OK", code, name, detail)


def warn(code, name, detail=""):
    add("WARN", code, name, detail)


def fail(code, name, detail=""):
    add("FAIL", code, name, detail)


def cjk_len(text):
    return len(CJK.findall(text))


def has_formula(text):
    if FORMULA_RE.search(text):
        return True
    # 行内公式且不止一个 $，避免把货币/占位符当公式
    return len(re.findall(r"\$[^$\n]{2,80}\$", text)) >= 1


def has_example(text):
    return any(k in text for k in EXAMPLE_MARK)


def has_plain(text):
    return any(k in text for k in PLAIN_MARK)


# ---------------------------------------------------------------- 结构解析
class Doc:
    def __init__(self, text):
        self.text = text
        self.title = ""
        m = re.search(r"^#\s+(.+)$", text, re.M)
        if m:
            self.title = m.group(1).strip()

        marks = []
        for regex in (SECTION_RE, NUMBERED_RE):
            for m in regex.finditer(text):
                style = "章" if "章" in m.group(0) else ("节" if "节" in m.group(0) else "num")
                marks.append((int(m.group(1)), (m.group(2) or "").strip(), m.start(), m.end(), style))
        # 两个正则可能命中同一行，按位置去重
        marks.sort(key=lambda x: x[2])
        dedup, seen = [], set()
        for mk in marks:
            if mk[2] in seen:
                continue
            seen.add(mk[2])
            dedup.append(mk)
        marks = dedup

        self.sections = []
        for i, (num, title, start, end, style) in enumerate(marks):
            stop = marks[i + 1][2] if i + 1 < len(marks) else len(text)
            self.sections.append({"num": num, "title": title, "style": style,
                                  "body": text[end:stop], "text": text[start:stop]})

    def get(self, n):
        for s in self.sections:
            if s["num"] == n:
                return s
        return None

    def body(self, n):
        s = self.get(n)
        return s["body"] if s else ""

    def step_blocks(self):
        """第3节（方法节）里每个"步骤X"的 (标题, 正文)。"""
        body = self.body(3)
        ms = list(STEP_RE.finditer(body))
        out = []
        for i, m in enumerate(ms):
            stop = ms[i + 1].start() if i + 1 < len(ms) else len(body)
            out.append((m.group(1).strip(), body[m.end():stop]))
        return out


def detect_profile(doc):
    """按标题风格判模式：出现『第N节』就是论文精讲；否则章数≥6 视为算法详解。"""
    styles = {s["style"] for s in doc.sections}
    if "节" in styles:
        return "paper"
    if len(doc.sections) >= 6:
        return "algorithm"
    if doc.sections:
        return "paper"
    return "brief"


# ---------------------------------------------------------------- 通用检查
def check_forbidden(doc):
    hits = []
    for i, line in enumerate(doc.text.splitlines(), 1):
        if any(w in line for w in EXEMPT_CTX):
            continue
        for w in FORBIDDEN:
            if w in line:
                hits.append((i, w, line.strip()[:40]))
                break
    if hits:
        detail = "；".join(f"L{n}『{w}』{snip}" for n, w, snip in hits[:6])
        fail("S5", f"命中禁用词 {len(hits)} 处", detail)
    else:
        ok("S5", "禁用词零命中")


def check_terms(doc):
    n = len(re.findall(r"[（(]\s*[A-Za-z][A-Za-z0-9\s\-/&.]{1,40}\s*[)）]", doc.text))
    if n < MIN_TERMS:
        warn("S8", f"中英对照仅 {n} 处 < {MIN_TERMS} 处", "术语首现要写『中文（English）』")
    else:
        ok("S8", f"中英对照 {n} 处")


def check_speculation(doc):
    if "推测" in doc.text and "论文未涉及" not in doc.text:
        fail("S11", "写了『推测』但没有『论文未涉及』标注", "读者无法分辨哪些是论文说的")
    elif "推测" in doc.text:
        ok("S11", "推测内容已标注")
    else:
        ok("S11", "无推测内容")


def check_placeholders(doc):
    hits = re.findall(r"TODO|待补充|待填|【待|\(待", doc.text)
    if hits:
        fail("S12", f"残留占位符 {len(hits)} 处", "交付前必须清空")
    else:
        ok("S12", "无占位符残留")


# ---------------------------------------------------------------- paper 模式
def check_sections(doc):
    nums = [s["num"] for s in doc.sections]
    if nums == list(range(10)):
        ok("S1", "第0～9节齐全且顺序正确")
    else:
        missing = [n for n in range(10) if n not in nums]
        extra = [n for n in nums if n not in range(10)]
        detail = []
        if missing:
            detail.append("缺少第" + "、".join(map(str, missing)) + "节")
        if extra:
            detail.append("异常节号" + "、".join(map(str, extra)))
        if nums != sorted(nums) and not detail:
            detail.append("节顺序错乱：" + "→".join(map(str, nums)))
        fail("S1", "第0～9节不完整", "；".join(detail) or "顺序不正确")

    if doc.title:
        ok("S2a", "有一级标题（# 论文精讲：…）")
    else:
        fail("S2a", "缺少一级标题", "文档应以 `# 论文精讲：<论文标题>` 开头")


def check_heading_levels(doc):
    sec_hashes = {}
    for s in doc.sections:
        m = re.match(r"^(#+)", s["text"])
        sec_hashes[s["num"]] = len(m.group(1)) if m else 0
    bad_sec = {n: h for n, h in sec_hashes.items() if h != 2}
    if bad_sec:
        detail = "；".join(f"第{n}节用了 {h} 个 #" for n, h in sorted(bad_sec.items()))
        warn("S2b", "节标题层级不是统一的二级（##）", detail)
    else:
        ok("S2b", "节标题统一为二级（##）")

    step_hashes = {len(m.group(1)) for m in re.finditer(r"^(#+)\s*步骤", doc.text, re.M)}
    if not step_hashes:
        warn("S2c", "未使用『步骤X』结构", "论文没有可拆模块时可忽略；方法类论文应使用")
    elif step_hashes == {3}:
        ok("S2c", "步骤标题统一为三级（###）")
    else:
        warn("S2c", "步骤标题层级不统一", f"出现 {sorted(step_hashes)} 个 #")

    part_hashes = {len(m.group(1)) for m in re.finditer(r"^(#+)\s*【", doc.text, re.M)}
    if not part_hashes:
        warn("S2d", "未使用【…】三段式小标题", "只要内容里有比喻/公式/例子也能过 S3")
    elif part_hashes == {4}:
        ok("S2d", "三段式标题统一为四级（####）")
    else:
        warn("S2d", "三段式标题层级不统一", f"出现 {sorted(part_hashes)} 个 #")


def _units_for_parts(doc):
    """判定三段式的单位：优先『步骤X』块；没有就按第3节整体。"""
    blocks = doc.step_blocks()
    if blocks:
        return blocks
    body = doc.body(3)
    return [("第3节", body)] if body.strip() else []


def check_three_parts(doc):
    units = _units_for_parts(doc)
    if not units:
        fail("S3", "第3节为空，无法判定三段式", "方法节是核心")
        return
    bad = []
    for title, body in units:
        missing = []
        if not has_plain(body):
            missing.append("通俗解释")
        if not has_formula(body):
            missing.append("公式")
        if not has_example(body):
            missing.append("手算例子")
        if missing:
            bad.append(f"『{title}』缺 " + "、".join(missing))
    if bad:
        fail("S3", f"{len(bad)}/{len(units)} 个模块三段式不全", "；".join(bad[:6]) + ("…" if len(bad) > 6 else ""))
    else:
        ok("S3", f"{len(units)} 个模块三段式齐全（通俗+公式+手算）")


def check_formula_example(doc):
    units = _units_for_parts(doc)
    bad, exempt = [], []
    for title, body in units:
        if not has_formula(body) or has_example(body):
            continue
        if any(k in body for k in ("无法手算", "演示用简化", "论文未涉及", "只解释各项作用")):
            exempt.append(title)
        else:
            bad.append(title)
    if bad:
        fail("S4", f"{len(bad)} 个模块有公式但没有手算例子", "、".join(bad[:8]))
    elif exempt:
        warn("S4", f"{len(exempt)} 个模块按降级规则豁免了手算例子", "、".join(exempt[:8]))
    else:
        ok("S4", "每个有公式的模块都配了手算例子")


def check_length(doc, min_total, min_method, skip_share, profile):
    total = cjk_len(doc.text)
    if profile == "algorithm":
        method = sum(cjk_len(s["body"]) for s in doc.sections if has_formula(s["body"]))
        share = (method / total * 100) if total else 0
    elif profile == "brief":
        if total < MIN_BRIEF:
            fail("S6a", f"速览模式字数不足（{total} < {MIN_BRIEF}）", "速览版约 800 字")
        else:
            ok("S6a", f"速览模式字数合格（{total} 字）")
        ok("S6b", "速览模式不检查方法部分占比")
        return total, 0, 0.0
    else:
        method = cjk_len(doc.body(3))
        share = (method / total * 100) if total else 0

    if total < min_total:
        fail("S6a", f"全文 {total} 字 < {min_total} 字", "不足就补内容，不要靠拉长句子凑")
    else:
        ok("S6a", f"全文 {total} 字（≥{min_total}）")

    label = "公式所在章" if profile == "algorithm" else "第3节"
    if method < min_method:
        fail("S6b", f"{label} {method} 字 < {min_method} 字", "方法核心部分必须写透")
    else:
        ok("S6b", f"{label} {method} 字（≥{min_method}）")

    if not skip_share:
        if share < MIN_SHARE:
            fail("S6c", f"{label}占比 {share:.0f}% < {MIN_SHARE}%", f"{method}/{total} 字")
        else:
            ok("S6c", f"{label}占比 {share:.0f}%（≥{MIN_SHARE}%）")

    if profile == "paper":
        out = []
        for s in doc.sections:
            lo, hi = BUDGET.get(str(s["num"]), (0, 10**9))
            n = cjk_len(s["body"])
            if n < lo or n > hi:
                out.append(f"第{s['num']}节 {n} 字（预算 {lo}-{hi}）")
        if out:
            warn("S6d", "部分节字数偏离预算", "；".join(out))
        else:
            ok("S6d", "每节字数都在预算区间内")
    return total, method, share


def check_faq(doc):
    body = doc.body(9)
    if not body.strip():
        fail("S7", "第9节缺失", "FAQ 至少 5 个问题")
        return
    items = len(re.findall(r"^\s*(?:\d+[.、)]|[-*])\s+", body, re.M))
    qmarks = body.count("？") + body.count("?")
    est = max(items, qmarks)
    if est < MIN_FAQ:
        fail("S7", f"FAQ 约 {est} 个 < {MIN_FAQ} 个", "把小白真会问的问题补齐")
    else:
        ok("S7", f"FAQ 约 {est} 个问题")


def _table_self_nums(body):
    """从速查表『自编号』列（每行第一个单元格）取编号。

    只认第一列：『论文式号』列也写着 式(7) 这样的原文编号，整段扫会把原文编号
    误当自编号，虚构出"速查表多出式(5)"这种假失败。没有 式(n) 时返回 None。
    """
    nums = set()
    for line in body.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0]
        if not first or set(first) <= set("-: "):
            continue
        for m in re.finditer(r"(?<!论文)式\s*[（(]\s*(\d+)\s*[)）]", first):
            nums.add(int(m.group(1)))
    return nums or None


def check_formula_index(doc):
    sec8 = doc.get(8)
    if not sec8:
        warn("S9", "第8节缺失，跳过编号一致性检查", "")
        return
    others = [s["body"] for s in doc.sections if s["num"] != 8]
    body_nums = {int(x) for x in re.findall(r"(?<!论文)式\s*[（(]\s*(\d+)\s*[)）]", "\n".join(others))}
    table_nums = _table_self_nums(sec8["body"])
    if table_nums is None:
        table_nums = {int(x) for x in re.findall(r"(?<!论文)式\s*[（(]\s*(\d+)\s*[)）]", sec8["body"])}

    if not body_nums:
        warn("S9", "正文没有出现 式(n) 自编号", "速查表无法与正文对齐，建议统一编号")
        return
    missing = sorted(body_nums - table_nums)
    extra = sorted(table_nums - body_nums)
    if missing or extra:
        detail = []
        if missing:
            detail.append("速查表缺 " + "、".join(f"式({n})" for n in missing[:10]))
        if extra:
            detail.append("速查表多 " + "、".join(f"式({n})" for n in extra[:10]))
        fail("S9", "速查表与正文公式编号不一致", "；".join(detail))
    else:
        ok("S9", f"速查表与正文编号一致（{len(body_nums)} 条公式）")


def check_citations(doc):
    body = doc.body(5)
    if not body.strip():
        warn("S10", "第5节缺失，跳过出处检查", "")
        return
    n = len(re.findall(r"式\s*[（(]\s*\d+|图\s*\d+|表\s*\d+|\[图|\[表|§\s*\d", body))
    if n < MIN_CITATIONS:
        warn("S10", f"第5节出处标注仅 {n} 处 < {MIN_CITATIONS} 处", "结论要能回查原文图表")
    else:
        ok("S10", f"第5节出处标注 {n} 处")


# ---------------------------------------------------------------- algorithm 模式
def check_algorithm(doc, min_total, min_method):
    nums = [s["num"] for s in doc.sections]
    if doc.title:
        ok("A0", "有一级标题")
    else:
        fail("A0", "缺少一级标题", "文档应以 `# …` 开头")

    if not nums:
        fail("A1", "没有任何章节标题", "算法详解需要 `## 第N章 …` 或 `## N. …` 的分章结构")
        return
    seq_ok = nums == list(range(nums[0], nums[0] + len(nums)))
    if len(nums) < 6:
        fail("A1", f"只有 {len(nums)} 章 < 6 章", "算法详解至少要有 符号/背景/数学基础/模块×N/训练/评估")
    elif not seq_ok:
        fail("A1", "章号不连续或顺序错乱", "章号：" + "→".join(map(str, nums)))
    else:
        ok("A1", f"{len(nums)} 章，编号连续（{nums[0]}～{nums[-1]}）")

    titles = "\n".join(s["title"] for s in doc.sections)
    if re.search(r"符号|记号|约定|地图|全景|总览", titles):
        ok("A2", "有符号约定/整体地图章")
    else:
        warn("A2", "没有符号约定或整体地图章", "公式多的算法建议加一章先统一记号")

    module_like = sum(1 for s in doc.sections if has_formula(s["body"]))
    if module_like >= 3:
        ok("A3", f"{module_like} 章含公式（相当于模块章）")
    else:
        fail("A3", f"只有 {module_like} 章含公式 < 3", "算法详解要把每个模块的公式摆出来")

    formula_chars = sum(cjk_len(s["body"]) for s in doc.sections if has_formula(s["body"]))
    total = cjk_len(doc.text)
    if formula_chars < min_method:
        fail("A4", f"公式所在章合计 {formula_chars} 字 < {min_method} 字", "模块部分要占大头")
    else:
        ok("A4", f"公式所在章合计 {formula_chars} 字（≥{min_method}）")
    if total and not args_skip_share:
        share = formula_chars / total * 100
        if share < MIN_SHARE:
            warn("A5", f"公式所在章占比 {share:.0f}% < {MIN_SHARE}%", f"{formula_chars}/{total} 字")
        else:
            ok("A5", f"公式所在章占比 {share:.0f}%（≥{MIN_SHARE}%）")

    example_units = sum(1 for s in doc.sections if has_example(s["body"]))
    if example_units >= 3:
        ok("A6", f"{example_units} 章有手算/举例")
    else:
        warn("A6", f"只有 {example_units} 章有手算/举例", "至少 3 章配数字例子，读者才能跟上")

    plain_units = sum(1 for s in doc.sections if has_plain(s["body"]))
    if plain_units >= 2:
        ok("A7", f"{plain_units} 章有通俗解释/比喻")
    else:
        warn("A7", f"只有 {plain_units} 章有通俗解释", "每 1–2 章至少要有一个比喻")

    if re.search(r"总结|小结|一图|全景|串讲|回顾", titles):
        ok("A8", "有总结/串讲章")
    else:
        warn("A8", "没有总结章", "建议加一章『设计思想一图流』收尾")


# ---------------------------------------------------------------- brief 模式
def check_brief(doc):
    text = doc.text
    missing = []
    if "一句话" not in text and "第0节" not in text:
        missing.append("一句话总览")
    if "要点" not in text and "|---" not in text:
        missing.append("要点表")
    if not re.search(r"值得|适合|不适合|细读", text):
        missing.append("值不值得细读的判断")
    if missing:
        fail("S1b", "速览版缺少：" + "、".join(missing), "见模板的速览模式规格")
    else:
        ok("S1b", "速览版结构齐全（总览/要点表/是否值得细读）")


# ---------------------------------------------------------------- 入口
args_skip_share = False


def main():
    global args_skip_share
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="精讲成品机械自检")
    ap.add_argument("path", help="精讲 markdown 文件路径")
    ap.add_argument("--profile", choices=["auto", "paper", "algorithm", "brief", "full"], default="auto",
                    help="auto=按标题自动判断（默认）；full 等同 paper")
    ap.add_argument("--min-total", type=int, default=MIN_TOTAL, help=f"全文最低中文字数（默认 {MIN_TOTAL}）")
    ap.add_argument("--min-method", type=int, default=MIN_METHOD, help=f"方法部分最低中文字数（默认 {MIN_METHOD}）")
    ap.add_argument("--skip-share", action="store_true", help="不检查方法部分占比")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--quiet", action="store_true", help="只打印未通过项")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"文件不存在：{path}")
        return 1
    text = path.read_text(encoding="utf-8")

    doc = Doc(text)
    profile = detect_profile(doc) if args.profile == "auto" else args.profile
    if profile == "full":
        profile = "paper"
    args_skip_share = args.skip_share

    if profile == "brief":
        check_brief(doc)
        check_forbidden(doc)
        total, method, share = check_length(doc, args.min_total, args.min_method, args.skip_share, profile)
        check_placeholders(doc)
    elif profile == "algorithm":
        check_algorithm(doc, args.min_total, args.min_method)
        check_forbidden(doc)
        total, method, share = check_length(doc, args.min_total, args.min_method, args.skip_share, profile)
        check_terms(doc)
        check_placeholders(doc)
    else:
        check_sections(doc)
        check_heading_levels(doc)
        check_three_parts(doc)
        check_formula_example(doc)
        check_forbidden(doc)
        total, method, share = check_length(doc, args.min_total, args.min_method, args.skip_share, profile)
        check_faq(doc)
        check_terms(doc)
        check_formula_index(doc)
        check_citations(doc)
        check_speculation(doc)
        check_placeholders(doc)

    fails = [r for r in RESULTS if r[0] == "FAIL"]
    warns = [r for r in RESULTS if r[0] == "WARN"]
    oks = [r for r in RESULTS if r[0] == "OK"]

    if args.json:
        print(json.dumps(
            {
                "file": str(path),
                "profile": profile,
                "metrics": {"cjk_total": total, "cjk_method": method, "method_share": round(share, 1)},
                "summary": {"ok": len(oks), "warn": len(warns), "fail": len(fails)},
                "results": [{"level": lv, "code": c, "name": n, "detail": d} for lv, c, n, d in RESULTS],
            },
            ensure_ascii=False,
            indent=2,
        ))
        return 1 if fails else 0

    icon = {"FAIL": "[FAIL]", "WARN": "[WARN]", "OK": "[ OK ]"}
    for lv, code, name, detail in RESULTS:
        if args.quiet and lv == "OK":
            continue
        line = f"{icon[lv]} {code} {name}"
        if detail:
            line += f" — {detail}"
        print(line)

    print()
    print(f"模式：{profile}｜机械校验：通过 {len(oks)} 项，警告 {len(warns)} 项，失败 {len(fails)} 项")
    print(f"篇幅：全文 {total} 字，方法部分 {method} 字（{share:.0f}%）")
    if fails:
        print("结论：未达交付标准，先修上方 FAIL 项。")
        return 1
    if warns:
        print("结论：可交付，但建议处理上方 WARN 项。")
        return 0
    print("结论：全部机械校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
