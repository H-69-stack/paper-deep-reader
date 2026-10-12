# paper-deep-reader · 论文深度精讲

一个给 **DSH（DeepSeek Harness）** 用的 Agent Skill：把一篇学术论文讲成"零基础也能读懂"的长文。

面向数学基础薄弱的工科读者（默认研究方向：液压电磁阀耦合故障诊断），每个复杂概念都走三层穿透：

1. **生活化比喻** → 讲清"它在干什么"
2. **学术公式逐符号解释** → 讲清"公式在算什么"
3. **极小数字例子手算** → 讲清"具体怎么算"

## 输出结构

固定 **第0～9节共10节**：一句话总览 → 问题背景 → 概念扫盲 → **方法逐模块精讲（占全文≥60%）** → 训练与优化 → 实验结果怎么看 → 创新点 → 局限性与迁移性 → 公式速查表 → 小白FAQ。

配套规则：**10条硬性要求**（禁止跳步、禁止黑话、公式必配手算例子、不编造…）、**16项交付前自检清单**、以及"公式确实无法手算时"的降级规则（显式说明，不许编数字）。

## 仓库结构

```
SKILL.md                             # 技能本体（含 YAML frontmatter，入口）
references/deep-reading-template.md  # 10节结构 + 硬性要求 + 公式三段式规范 + 16项自检清单
references/field-glossary.md         # 术语表（信号处理/ML/迁移学习/耦合故障/边缘计算/Agent）+ 领域翻译表 + 电磁阀比喻库 + 数学符号速查
assets/deepseek-desktop-agent.json   # DeepSeek 桌面客户端"智能体"配置，可手动复制字段导入
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

DSH 会在新会话的技能列表中加载它（技能根目录必须是被加载的**真实目录**，不要用符号链接/junction 指向别处）。

**方式二：在 DSH 技能管理器里添加本仓库**：填 `https://github.com/H-69-stack/paper-deep-reader`，它会扫描根目录的 `SKILL.md` 识别为一个技能。注意：这种方式会把技能**复制**进技能目录，是一份独立副本，更新需重新安装。

## 触发方式

提到"精讲/精读/详解/讲透这篇论文""小白视角解读""把公式逐符号讲清楚"等，或直接上传论文 PDF/文本/DOCX 即可。也可以显式调用：`/paper-deep-reader`。

论文可以来自：粘贴的文本、本地 PDF、Zotero 文库（走 `zotero_search` → `zotero_get_attachments` → `zotero_get_fulltext`）。

## 已知限制

- 需要能拿到**论文全文**；扫描件没有文本层时无法读取，需要先 OCR 或提供文本。
- 定位是"教学型长文"，输出较长（单篇一般 ≥5000 字），不适合只要一句话结论的场景。
- 术语库与比喻库偏**故障诊断/信号处理**方向；其他领域论文走"领域翻译"，但相距过远时只做迁移性分析，不硬套比喻。

## License

暂未指定。如需开源授权，请补充 `LICENSE` 文件。
