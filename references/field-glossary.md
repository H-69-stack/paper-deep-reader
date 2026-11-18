# 术语库索引

术语库共 **13 个分册、约 470 条**，按领域拆分。**不要一次全读**——按论文方向挑 2–3 册即可，全量读进来会稀释注意力。

> **RCC 在用户语境里指「导电滚环」（Conductive Rolling Ring）**，见 `rcc.md`。它与滑环（slip ring，滑动接触）不是同一种部件，读到"滑环""集电环"时要看原文的接触方式再决定用哪册。

## 一、按论文方向选册

| 论文方向 | 必读 | 可选 |
|---|---|---|
| 振动/声学信号处理、时频分析 | `signal.md` | `symbols.md` |
| **滚动轴承**诊断、特征频率、包络谱 | `bearing.md` | `signal.md`、`metrics.md` |
| **导电滚环 RCC / 电接触 / 打火电蚀** | `rcc.md` | `objects.md`、`signal.md` |
| **液压电磁阀**、卡滞、内泄漏、线圈 | `valve.md` | `signal.md`、`phm.md` |
| **电机**断条/偏心/匝间短路/轴电流 | `motor.md` | `signal.md`、`metrics.md` |
| 轴承本体 / 复合故障机理 / 跨对象类比 | `objects.md` | `bearing.md`、`motor.md` |
| 传统机器学习分类/回归 | `ml.md` | `metrics.md` |
| 深度学习 / 注意力 / 图网络 | `dl.md` | `ml.md` |
| 迁移学习 / 变工况 / 域适应 | `dl.md` | `ml.md`、`phm.md` |
| PHM 全链路、RUL、维护决策 | `phm.md` | `metrics.md`、`bearing.md` |
| 大模型 / Agent / RAG / 提示工程 | `llm-agent.md` | `ml.md` |
| 综述类论文（跨多个子领域） | `translation.md` | 按主题再选 1–2 册 |
| 只有指标表格、要看懂实验 | `metrics.md` | `ml.md` |
| 公式符号看不懂 | `symbols.md` | 对应主题册 |
| 论文离本行业很远（NLP/CV/推荐） | `translation.md` | `dl.md` |

## 二、分册清单

- `references/glossary/signal.md` — 采样、FFT/STFT/小波/EMD/VMD、包络与解调、循环平稳、时域统计指标（33 条）
- `references/glossary/bearing.md` — **滚动轴承专项**：特征频率 BPFO/BPFI/BSF/FTF、故障四阶段、包络解调、谱峭度、阶次分析、寿命 L10、Hi/RUL（34 条）
- `references/glossary/rcc.md` — **导电滚环 RCC 专项**：接触电阻（收缩/膜）、压降与温升、电弧与电蚀、磨屑桥接、四线法、通道串扰、FMEA 故障模式（34 条）
- `references/glossary/valve.md` — **液压电磁阀专项**：阀芯间隙与内泄漏、卡滞与滞环、线圈电流与吸合力、阀口流量、空化、污染度（34 条）
- `references/glossary/motor.md` — **电机专项**：极对数/转差率、断条边带、匝间短路、偏心、MCSA/Park 矢量、VFD 谐波与轴电流（33 条）
- `references/glossary/objects.md` — 带电摩擦副总览、RCC/滑环/电刷、电机定转子、轴承本体、复合故障机理（32 条）
- `references/glossary/phm.md` — 状态监测、HI、退化建模、RUL、CBM、跨域诊断、边缘部署（34 条）
- `references/glossary/ml.md` — 样本划分、过拟合、损失与优化、SVM/树模型/PCA/聚类/异常检测、小样本（38 条）
- `references/glossary/dl.md` — 卷积/感受野/残差/BN/RNN/注意力/Transformer/GNN/自编码器/域适应/蒸馏（37 条）
- `references/glossary/llm-agent.md` — LLM、token、RAG、embedding、工具调用、ReAct、多智能体、微调与评测（21 条）
- `references/glossary/metrics.md` — 混淆矩阵、Precision/Recall/F1、AUC、RUL 评分、参数量/FLOPs、消融（28 条）
- `references/glossary/translation.md` — 领域翻译表（14 组）+ 电磁阀/轴承比喻库（20 条）+ 使用规则
- `references/glossary/symbols.md` — 常用数学符号读法/含义（44 条）+ 希腊字母表（24 个）+ 单位量纲提醒

## 三、使用规则

1. **术语首现**：精讲里任何术语第一次出现，必须给"中文（English）"对照，并能在分册里查到。
2. **一册够用就别翻第二册**：优先读索引路由表指定的"必读"册；对象类论文通常是「对象专项册 + `signal.md`」两本。
3. **对象类分册优先于总览册**：写轴承查 `bearing.md`，写电机查 `motor.md`，写滚环查 `rcc.md`，写阀查 `valve.md`；`objects.md` 只在需要"带电摩擦副"整体框架或跨对象类比时才读。
4. **比喻必须可映射**：`translation.md` 第二节的比喻库可以用，但每个比喻都要能指出它对应公式里的哪一项；答不上来就换。
5. **例子是模板不是数据**：每册末尾的"数字例子"是手算示范，实际精讲要换成论文里的真实规模，并注明"此处为演示用简化"。
6. **查不到就明说**：分册里没有的术语，按 SKILL.md 的降级规则处理，不要编一个定义。
