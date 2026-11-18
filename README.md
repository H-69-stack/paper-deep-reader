# paper-deep-reader · 论文深度精讲

一个给 **DSH（DeepSeek Harness）** 用的 Agent Skill：把一篇学术论文讲成"零基础也能读懂"的长文。

面向数学基础薄弱的工科读者，方向是 **PHM（设备智能维护）中的故障诊断**：技术模块分信号处理、机器学习与深度学习、大模型与 Agent；研究对象是带电摩擦副类部件（导电滚环 RCC、电机、液压电磁阀、滑环、轴承等）。每个复杂概念都走三层穿透：

1. **生活化比喻** → 讲清"它在干什么"
2. **学术公式逐符号解释** → 讲清"公式在算什么"
3. **极小数字例子手算** → 讲清"具体怎么算"

## 三种模式

| 模式 | 什么时候用 | 输出结构 | 校验参数 |
|---|---|---|---|
| **论文精讲** | 给的是论文（PDF / 文本 / 标题） | 第0～9节，共10节 | 默认（自动判定） |
| **算法详解** | 给的是代码仓库 / 项目 / 自己的实验，"把算法讲透" | 章结构：符号与地图 → 背景 → 数学地基 → 模块章（≥3）→ 训练 → 指标 → 全流程小例子 → 总结 | `--profile algorithm` |
| **速览** | "速览 / 值不值得读 / 只要结论" | 约 800 字四件套 | `--profile brief` |

## 输出结构

论文精讲固定 **第0～9节共10节**：一句话总览 → 问题背景 → 概念扫盲 → **方法逐模块精讲（占全文≥55%）** → 训练与优化 → 实验结果怎么看 → 创新点 → 局限性与迁移性 → 公式速查表 → 小白FAQ。

配套规则：**10条硬性要求**（禁止跳步、禁止黑话、公式必配手算例子、不编造…）、**18项交付前自检清单**、"公式确实无法手算时"的降级规则（显式说明，不许编数字），以及**论文类型路由**（方法类 / 综述类 / 理论证明类 / 数据集类 / 应用工程类走不同变体结构）、**每节字数预算**、**速览模式**。

篇幅下限：全文 **≥4500字**，方法部分 **≥2600字 且 ≥全文55%**（下限不是目标，禁止灌水）。

**图表是硬指标**：表格 ≥3 张、插图 ≥1 张，都要编号并在正文被引用（`S13`–`S15` 会查）；插图用 `scripts/make_figures.py` 按 JSON 生成，避免从 PDF 截图。

结构不是靠自觉守的：交付前跑一遍机械校验，`FAIL` 不许宣布完成。

## 仓库结构

```
SKILL.md                             # 技能本体（YAML frontmatter，入口）
README.md                            # 本文件
CHANGELOG.md                         # 版本与变更记录
LICENSE                              # MIT

SKILL.md 旁边的三个目录：
references/
  deep-reading-template.md           # 必修：10节结构 + 10条硬性要求 + 三段式 + 18项自检 + 类型路由/层级/预算/速览/模式路由/图表规范
  field-glossary.md                  # 术语库索引（按方向挑分册，约560条 / 16册）
  glossary-index.html                # 上面16册编译成的单文件检索页（浏览器打开可搜索）
  glossary/                          # 16个分册：对象7册（bearing/motor/rcc/valve/gearbox/pump/cylinder）+ 方法9册（objects/phm/signal/ml/dl/llm-agent/metrics/translation/symbols）
assets/
  deepseek-desktop-agent.json        # DeepSeek 桌面客户端"智能体"配置，可手动复制字段导入
scripts/
  lint_skill.py                      # 技能自洽性：三副本一致、资源路径存在、术语库索引同步
  check_output.py                    # 成品机械校验：论文精讲 / 算法详解 / 速览三种模式
  extract_pdf.py                     # PDF→markdown + 三项诊断（扫描件/公式丢失/双栏错序）
  make_figures.py                    # 按 JSON 生成结构图/条形图/折线图/热图（diagram/bar/line/heat）
  export_docx.py                     # Markdown → .docx（公式渲成图片、插图自动嵌入）
  export_tex.py                      # Markdown → .tex（XeLaTeX / Overleaf 可直接编译，插图复制进 figs/）
  build_glossary_html.py             # references/glossary/*.md → 单文件检索页 glossary-index.html
evals/
  README.md                          # 回归测试说明
  run_evals.py                       # 跑全部案例：合格骨架放行、坏样本拦住
  fixtures/                          # good-minimal.md、brief.md、algorithm-minimal.md、fig-sample.png 等
```

## 安装

**方式一：克隆到 DSH 技能目录**（也是本仓库作者的使用方式）

```bash
git clone https://github.com/H-69-stack/paper-deep-reader.git \
  "$DSH_HOME/skills/paper-deep-reader"
```

Windows PowerShell：

```powershell
git clone https://github.com/H-69-stack/paper-deep-reader.git "$env:DSH_HOME\skills\paper-deep-reader"
```

DSH 会在新会话的技能列表中加载它（技能根目录必须是被加载的**真实目录**，不要用符号链接/junction 指向别处；符号链接只适合作为进入该目录的快捷入口）。

**方式二：在 DSH 技能管理器里添加本仓库**：填 `https://github.com/H-69-stack/paper-deep-reader`，它会扫描根目录的 `SKILL.md` 识别为一个技能。注意：这种方式会把技能**复制**进技能目录，是一份独立副本，更新需重新安装。

## 触发方式

提到"精讲/精读/详解/讲透这篇论文""小白视角解读""把公式逐符号讲清楚"等，或直接上传论文 PDF/文本/DOCX 即可。也可以显式调用：`/paper-deep-reader`。

论文可以来自：粘贴的文本、本地 PDF、Zotero 文库（走 `zotero_search` → `zotero_get_attachments` → `zotero_get_fulltext`）。

- 给论文 → **论文精讲**（第0～9节）。
- 贴代码/项目说"把这个算法讲透" → **算法详解**（章结构）。
- 只要结论、不想读 4500 字 → 说"速览"或"值不值得读"，走约 800 字的速览模式。

## 脚本用法

只依赖 Python 标准库 + `python-docx` / `matplotlib`（后两个仅导出时用）；PDF 提取按 `pypdf` → `pdfplumber` → `PyMuPDF` 依次降级，本机装了哪个用哪个，不联网装包。

```bash
# 1. 取全文前先诊断（扫描件/公式丢失/双栏错序）
python scripts/extract_pdf.py paper.pdf --report
python scripts/extract_pdf.py paper.pdf --out paper.md --pages 1-6

# 2. 出图（写正文前/后都可以，图放精讲同目录的 figs/）
python scripts/make_figures.py diagram spec.json -o figs/fig1.png --title "整体结构"
python scripts/make_figures.py bar     bleu.json -o figs/fig5.png --title "BLEU 对比" --ylabel BLEU
python scripts/make_figures.py line    curve.json -o figs/fig6.png --title "学习率曲线"
python scripts/make_figures.py heat    attn.json  -o figs/fig4.png --title "注意力权重" --cmap Blues --vmin 0 --vmax 1

# 3. 写完后机械校验（FAIL 必须修）
python scripts/check_output.py 某某论文-精讲.md
python scripts/check_output.py 某某算法-详解.md --profile algorithm
python scripts/check_output.py 某某一页纸.md --profile brief
python scripts/check_output.py 短论文-精讲.md --min-total 3000 --skip-share

# 4. 导出（先有 .md 再导出）
python scripts/export_docx.py 某某论文-精讲.md
python scripts/export_tex.py  某某论文-精讲.md

# 5. 改了术语分册后，重新生成检索页
python scripts/build_glossary_html.py

# 6. 改过规则或脚本后自检
python scripts/lint_skill.py
python evals/run_evals.py
```

导出说明：`.docx` 里独立公式会被 matplotlib 渲成图片插入，`![图 N …](figs/x.png)` 形式的插图会以 15 cm 宽嵌入并带斜体图注；`.tex` 会把插图复制进 `figs/` 并生成 `\includegraphics` + `\caption`。（含中文的公式退回原始 LaTeX 文本，需在 Word 里核对）；`.tex` 用 `ctexart`，**用 XeLaTeX 编译**（Overleaf 里把 Compiler 设为 XeLaTeX），公式与表格原样保留。

退出码统一为：0 = 无失败项，1 = 有失败项。

## 技能边界（什么场合别用它）

- **不是摘要器**：只要 200 字总结时用速览模式，不要硬走 10 节流程。
- **不是翻译器**：只做术语级中英对照，整篇翻译另找工具。
- **不是代写**：不代写论文正文、审稿意见、回复信。
- **不替代方法学审稿**：能指出"论文没写清"，但不判定实验是否造假、统计是否合适。
- **不给没有的全文**：扫描件、付费墙后只有摘要、只有标题且检索不到 → 如实说明，不猜内容。
- **不硬扯领域**：论文离故障诊断很远时，用论文自身领域比喻，迁移讨论放第7节并讲代价。

## 已知限制

- 需要能拿到**论文全文**；扫描件没有文本层时无法读取，需要先 OCR 或提供文本（`extract_pdf.py` 会诊断出来并说明，不会硬编内容）。
- 定位是"教学型长文"，输出较长（单篇论文精讲一般 ≥4500 字），不适合只要一句话结论的场景。
- 术语库偏向 **PHM / 故障诊断 / 信号处理**（约 560 条，16 个分册），其中 7 册是对象专项册（滚动轴承 / 电机 / 导电滚环 RCC / 液压电磁阀 / 齿轮箱 / 泵 / 液压缸）；其他领域论文走"领域翻译"，但相距过远时只做迁移性分析。想快速查词可打开 `references/glossary-index.html`。
- `check_output.py` 查得住结构与数字（节完整性、三段式、编号对齐、字数、禁用词、算法模式的章结构），**查不住内容对不对**；那部分仍靠模型判断。
- 每节字数预算是启发式区间，不是实测统计。
- 图表检查只数数量和编号，**判断不了图好不好看、表有没有信息量**；图是脚本生成的，复杂示意图仍可能需要手工微调 JSON。
- 导出不依赖 pandoc/Word：`.docx` 的公式是渲染图（不可再编辑），`.tex` 需要本地或 Overleaf 的 XeLaTeX 才能编译出 PDF。

## 版本

当前 v0.6.0（2026-11-18）。变更明细见 [CHANGELOG.md](CHANGELOG.md)。

## License

MIT，见 `LICENSE`。
