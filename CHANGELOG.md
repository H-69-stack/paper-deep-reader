# Changelog

版本号只记在 README 和本文件：DSH 的 SKILL.md frontmatter 目前没有 `version` 字段的通用约定，
写进 frontmatter 不会被读取，反而会让人误以为它生效。

## v0.3.0 — 2026-11-17

这一版按用户的实际使用习惯改造：支持"讲算法"而不只是"讲论文"，篇幅下调约 12%，术语库扩到约 300 条，
并补上 Word / LaTeX 导出。方向从"液压电磁阀耦合故障"扩写为 **PHM 中的故障诊断（带电摩擦副：导电滚环 RCC、
电机、液压电磁阀等；模块：信号处理 / 机器学习与深度学习 / 大模型与 Agent）**。

### Added

- **三种模式**：论文精讲（第0～9节）/ 算法详解（章结构）/ 速览（约800字）。判定规则写在 SKILL.md「先判模式」
  与模板第十一节；`check_output.py` 用 `--profile auto|paper|algorithm|brief` 支持，`auto` 按标记风格自动判定。
- **算法详解校验 A0–A8**：章数≥6 且编号连续、符号/地图章、≥3 章含公式、公式章合计≥2600 字、占比≥55%、
  ≥3 章有手算、≥2 章有通俗解释、有总结章。三段式改为**按内容实质**判定（`> **通俗解释**：`、`【数字例子】`、
  "举个例子/算一下/代入"等都可以），不再死抠 `#### 【…】` 标题。
- `scripts/export_docx.py`：Markdown → `.docx`（python-docx；标题层级、表格、代码块、独立公式用 matplotlib
  渲成 PNG 插入；含中文的公式退回 LaTeX 文本并提示核对）。
- `scripts/export_tex.py`：Markdown → `.tex`（`ctexart`，XeLaTeX / Overleaf 直接编译；行内 `$...$`、独立
  `$$...$$`、表格、代码块原样保留）。
- 术语库从 9 册 254 行扩到 **9 册约 300 条**：`signal` / `ml` / `dl` / `llm-agent` / `phm` / `objects` /
  `metrics` / `translation` / `symbols`。新增 PHM 全链路册、研究对象与故障机理册、深度学习册、大模型与 Agent 册；
  每册带 2–4 列术语表与"数字例子模板"。

### Changed

- 篇幅下限下调：全文 5000 → **4500 字**，方法部分 3000 → **2600 字**，占比 60% → **55%**。
  `lint_skill.py` 的 `EXPECT`、`check_output.py` 的 `BUDGET`、模板预算表、桌面端 JSON 四处同步。
- 术语库由"单文件全量读"改为"索引 + 按方向挑 2–3 册"。
- `assets/deepseek-desktop-agent.json` 重写：`system_prompt` 2834 字符，自包含 PHM 背景、三模式、10 节、
  10 条硬性要求、16 项自检、降级 5 条、式(n)、4500/2600/55 预算、算法详解章结构、导出命令、技能边界。
- README 重写：加三种模式表、导出说明、脚本用法四组命令；技能边界与已知限制同步。

### Fixed

- `check_output.py` S9 的 `式(n)` 解析：先修 lookbehind（避免把 `论文式(7)` 的 7 当自编号），再改为**只解析
  速查表第一列**（第8节"论文式号"列里的 `式(5)` 会被误算成自编号）。
- `check_output.py --profile brief` 不再因为缺 10 节而直接 FAIL。
- `export_docx.py` 的 `$$...$$` 单行公式解析（原先只认独占一行的 `$$`，样例里 27 个公式一个都没识别）。
- `export_tex.py` 的 `PREAMBLE % {...}` 格式化与 `%` 注释冲突（`ValueError: unsupported format character`）。

### Verified

- 用户的 2 份旧精讲（`算法详解1.md` 11 章 / `算法详解2.md` 14 章）在 `--profile algorithm` 下 A0–A8 全过；
  仅命中真实的禁用词「同理」共 3 处（是脚本在起作用，不是假阳性）。
- `lint_skill.py` 35 项全过；`evals/run_evals.py` 全绿。

## v0.2.0 — 2026-11-17

这一版的目标不是"多写几条规则"，而是把原来靠自觉执行的 31 条约束（10 条硬性要求 +
16 项自检 + 5 条降级）变成**可执行、可校验**。

### Added

- `scripts/lint_skill.py`：技能自洽性检查。frontmatter、资源路径存在性、模板结构（10 节/10 条/16 项/5 行降级）、
  三份副本的关键数字一致性、术语库索引与分册同步、仓库配套文件。15 项失败起步，现在 0 失败。
- `scripts/check_output.py`：精讲成品机械校验 S1–S12（节完整性、标题层级、三段式、公式↔例子、禁用词、
  篇幅与每节预算、FAQ、中英对照、`式(n)` 与速查表对齐、出处标注、推测标注、占位符残留）。
  支持 `--profile brief`（速览）、`--min-total` / `--min-method` / `--skip-share`、`--json`。
- `scripts/extract_pdf.py`：PDF → markdown 提取链路（pypdf → pdfplumber → PyMuPDF 依次降级），
  并诊断三类"读不出来"：扫描件无文本层、公式疑似丢失、双栏错序。
- `evals/`：`check_output.py` 的回归测试。骨架样本必须放行，五种故意做坏的样本必须拦住，
  另有一条"默认阈值下骨架必须失败"的反向断言，防止自检脚本退化成永远通过。
- `references/glossary/`：术语库按领域拆成 9 册（signal / ml / transfer / fault / edge-agent /
  translation / training / metrics / symbols）。
- 模板新增四节：七、论文类型路由（方法/综述/理论/数据集/应用）；八、标题层级映射与公式编号约定；
  九、每节字数预算；十、速览模式。
- `LICENSE`（MIT）。

### Changed

- `references/field-glossary.md` 从 254 行单体改为约 30 行的索引 + 路由表，术语内容迁入 9 个分册。
  目的是按需只读 2–3 册，而不是每篇论文都把整库读进上下文。
- 自检清单重写为 16 项，新增 `式(n)` 与速查表对齐、标题层级、每节字数预算三项可机械判定的检查。
- 第8节公式速查表改为 5 列：自编号 / 论文式号 / 模块 / 公式 / 一句话含义。
- 第5节新增"逐图逐表解读"四问：轴或表头是什么、基线是谁、趋势说明什么、作者想证明哪一句。
- 硬性要求第 8 条补充"第3节≥3000字且占比≥60%、每节落在预算内"。
- `assets/deepseek-desktop-agent.json` 按当前规则整体重写（system_prompt 3019 字符，自包含，
  含论文类型路由、字数预算、`式(n)` 约定、降级规则、自检浓缩、速览、技能边界与维护说明）。
- `SKILL.md` 重写：资源索引前置、Step 1 接上 `extract_pdf.py`、Step 2 先判论文类型、Step 5 接上
  `check_output.py`、新增技能边界与维护章节。

### Fixed

- 桌面端 JSON 与 SKILL.md 的实质漂移：硬性要求写成 11 条、丢了"第3节≥3000字"、没有 16 项自检、
  没有 Step 1 取全文链路、降级规则缺"扫描件无文本层"、维护说明写"两份副本"（实际三份）。
- `式(n)` 正则会把"论文式(7)"里的 7 误当成自编号，导致速查表比对出现假失败。
- 速查表编号现在只看"自编号"列的第一个单元格，避免"论文式号"列污染比对结果。

### Known limitations

- 脚本只能查结构与数字，查不住"讲得对不对"；内容质量仍取决于模型。
- 扫描件不会自动 OCR，只做诊断并给出如实说明。
- 每节字数预算是启发式区间，来自对同类精讲的估计，不是实测统计。

## v0.1.0 — 2026-10-12

首个版本，单提交：`SKILL.md` + `references/deep-reading-template.md` + `references/field-glossary.md`
+ `assets/deepseek-desktop-agent.json` + `.gitattributes`。零依赖、零脚本，全部规则靠模型自觉执行。
