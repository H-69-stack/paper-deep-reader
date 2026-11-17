# 术语库索引

术语库共 **9 个分册、约 300 条**，按领域拆分。**不要一次全读**——按论文方向挑 2–3 册即可，全量读进来会稀释注意力。

## 一、按论文方向选册

| 论文方向 | 必读 | 可选 |
|---|---|---|
| 振动/声学信号处理、时频分析 | `signal.md` | `symbols.md` |
| 传统机器学习分类/回归 | `ml.md` | `metrics.md` |
| 深度学习 / 注意力 / 图网络 | `dl.md` | `ml.md` |
| 迁移学习 / 变工况 / 域适应 | `dl.md` | `ml.md`、`phm.md` |
| 复合故障 / 耦合机理 | `phm.md` | `objects.md` |
| 导电滚环 / 电机 / 电磁阀 / 轴承本体 | `objects.md` | `signal.md` |
| PHM 全链路、RUL、维护决策 | `phm.md` | `metrics.md` |
| 大模型 / Agent / RAG / 提示工程 | `llm-agent.md` | `ml.md` |
| 综述类论文（跨多个子领域） | `translation.md` | 按主题再选 1–2 册 |
| 只有指标表格、要看懂实验 | `metrics.md` | `ml.md` |
| 公式符号看不懂 | `symbols.md` | 对应主题册 |
| 论文离本行业很远（NLP/CV/推荐） | `translation.md` | `dl.md` |

## 二、分册清单

- `references/glossary/signal.md` — 采样、FFT/STFT/小波/EMD/VMD、包络与解调、循环平稳、时域统计指标（36 条）
- `references/glossary/ml.md` — 样本划分、过拟合、损失与优化、SVM/树模型/PCA/聚类/异常检测、小样本（36 条）
- `references/glossary/dl.md` — 卷积/感受野/残差/BN/RNN/注意力/Transformer/GNN/自编码器/域适应/蒸馏（36 条）
- `references/glossary/llm-agent.md` — LLM、token、RAG、embedding、工具调用、ReAct、多智能体、微调与评测（20 条）
- `references/glossary/phm.md` — 状态监测、HI、退化建模、RUL、CBM、复合故障、跨域诊断、边缘部署（36 条）
- `references/glossary/objects.md` — 带电摩擦副、RCC/滑环/电刷、电机、轴承、液压电磁阀、故障机理（32 条）
- `references/glossary/metrics.md` — 混淆矩阵、Precision/Recall/F1、AUC、RUL 评分、参数量/FLOPs、消融（28 条）
- `references/glossary/translation.md` — 领域翻译表（14 组）+ 电磁阀/轴承比喻库（20 条）+ 使用规则
- `references/glossary/symbols.md` — 常用数学符号读法/含义（44 条）+ 希腊字母表（24 个）+ 单位量纲提醒

## 三、使用规则

1. **术语首现**：精讲里任何术语第一次出现，必须给"中文（English）"对照，并能在分册里查到。
2. **一册够用就别翻第二册**：优先读索引路由表指定的"必读"册。
3. **比喻必须可映射**：`translation.md` 第二节的比喻库可以用，但每个比喻都要能指出它对应公式里的哪一项；答不上来就换。
4. **例子是模板不是数据**：每册末尾的"数字例子"是手算示范，实际精讲要换成论文里的真实规模，并注明"此处为演示用简化"。
5. **查不到就明说**：分册里没有的术语，按 SKILL.md 的降级规则处理，不要编一个定义。
