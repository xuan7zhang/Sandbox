# toy/ — 在真实沙盒上做的 idea 排查实验（全离线，mock 模型）

目的：**不花一分钱 API**，用沙盒自己的 loop / verifier stack / archive / rejudge，检查 idea 1–3 的实验设计是否"可识别、效应量够大、结论靠什么假设"。核心代码一行未改；全部在 `toy/` 下。

```
toy/agent_knobs/agent.py   可演化脚手架，三个旋钮：MAX_ACTIONS（诚实能力）、MODE precise|shotgun（漏洞利用）、WIPE（会被抓的越界破坏）
toy/toy.py                 NoisyFollow（弱模型：p=0.3 概率搞错记录 id）、StrategyImprover（leak 0–3 控制 improver 能看到什么）、
                           harden_minimality（新的验证器加固：scope 表内只允许参考解触碰的记录改变）、run_toy
toy/run_matrix.py          M1 泄露扫描 / M2 静态 vs 前沿 × 选择 / M3 验证器循环内加固 vs 事后审计；5 seed × 6 代，55 个 run，2 核约 9 分钟
toy/plot.py                results/toy_screening.png
toy/results/summary.json   均值 ± 95% CI；raw.json 每个 run 的逐代数据；runs/ 每个 run 的完整 archive（可 rejudge）
```

## 排查时发现的真实漏洞（不是 toy 假设）

沙盒现有的 integrity stack（canary / forbidden / collateral / scope guard）只看 **scope 表之外**的改动；隐藏验证器只检查 **指令点名的记录**。
于是一个"散弹枪"脚手架——把模型的每个写操作扇出到该表的**所有**记录——能让弱模型的 id 错误消失、通过验证器、且 **0 个 flag**。
`harden_minimality` 是针对它的确定性加固（参考解 30/30 仍通过）。这件事本身就是论文里 "evaluator-under-attack" 的一个现成案例。

**已合入核心代码**（2026-10-27 下午）：`sandbox/verifier/adversary.py::add_minimality_guard`，由参考解回放推导（scope 表内仅参考解改动的记录可变；每表新建记录数、append-only 表增长量都钉死）；`Adversary.run` 对每个新任务**主动**施加，`LoopConfig.minimality_guard=False` 关掉做消融；`mock_scripts.Shotgun` 作为回归攻击；`rejudge(stack=...)` 现在重跑完整性检查并给 archive 级 / 冠军级 ANNECS；`scripts/audit_verifiers.py` 是 S1 普查脚本（mock 上 shotgun 未检出率 83% → 0%）。24 个测试全绿。

## 结果（5 seed，6 代，frontier，mean ± 95% CI）

| 条件 | reported | 事后重判 | 幻觉增益 | ANNECS | ANNECS 重判 | flag 到的 hack 率 | 冠军=shotgun |
|---|---|---|---|---|---|---|---|
| leak 0（随机 improver） | 0.65±0.09 | 0.04±0.04 | **0.61** | 9.0 | 8.0 | 0.00 | 1.00 |
| leak 1（pass/fail） | 0.66±0.08 | 0.03±0.04 | 0.63 | 10.2 | 9.2 | 0.00 | 1.00 |
| leak 2（+flag 名） | 0.68±0.06 | 0.16±0.23 | 0.52 | 11.8 | 11.0 | 0.00 | 0.80 |
| leak 3（+evidence/轨迹） | 0.65±0.07 | 0.15±0.24 | 0.49 | 9.6 | 9.2 | 0.00 | 0.80 |
| **验证器循环内加固**（leak 3） | 0.61±0.09 | **0.61±0.09** | **0.00** | 11.0 | 11.0 | 0.00 | **0.00** |

| idea 2 | static d=2 | frontier |
|---|---|---|
| archive greedy（重判） | 0.15±0.21 | 0.15±0.24 |
| archive CMP（重判） | 0.18±0.27 | 0.28±0.28 |
| random 匹配预算（重判） | 0.14±0.20 | 0.15±0.19 |

## 每个 idea 的判定

**Idea 1（幻觉增益 / illusory improvement）— 存活，且效应量极大。**
- 真实 loop 的接受门（"非 hacking 通过率严格提升"）在 4/4 泄露档都把 shotgun 接受成冠军，stack 报 hack 率 0。
- 事后加固 + `rejudge` 把冠军从 0.65 打回 0.04–0.15：**报告的进步中 75–95% 是验证器漏洞**。
- 更尖的一句话：循环内加固的诚实冠军真实率 0.61，事后审计的 hack 冠军真实率 0.15——**循环报告 +0.04，真实 −0.46**。hack 不是"多拿一点分"，是用真实能力换报告分。
- `rejudge.py` 这条管线是可行的，但要注意它只重跑隐藏验证器，不重跑 integrity flags。
- 实验设计建议：主图就是 reported vs rejudged 两条曲线 + 循环内加固第三条；真实模型上只需换掉 NoisyFollow / StrategyImprover。

**Idea 3（improver 信息泄露阈值）— 在这个设定下证伪，需要改设计。**
- 泄露 0→3 对最终 hack 份额**没有影响**（1.0 / 1.0 / 0.8 / 0.8，CI 重叠）。原因：漏洞距离初始脚手架只有**一次突变**，接受门本身就会选中它，improver 看不看诊断只改变"第几代被找到"（leak 3 第 1 代，leak 0 第 3 代）。
- 结论改写：**hacking 由"接受门 × 漏洞可达深度"驱动，而非 improver 信息**——当漏洞一步可达时。要让泄露成为变量，必须构造"没有诊断就几乎找不到"的多步漏洞（例如需要先读 evidence 字符串才知道验证器查哪个字段），并把指标从"最终 hack 份额"改成 **time-to-hack**（首次 hack 被接受的代数）。这反而是一个更好的论文变量。

**Idea 2（随机采样 vs 归档搜索；静态 vs 共进化）— 本 toy 无法区分，需要更大的突变空间。**
- 三种选择在两种任务分布上重判后全部 ≈0.15，CI 完全重叠；reported 也一样。
- 原因：旋钮只有 3 个，诚实能力轴（MAX_ACTIONS）两三步就到天花板（shotgun 在多原子任务上互相冲突、frontier 升到 d≥3 后谁也解不了）。Gideoni 的"随机追平"在小突变空间里是必然的。
- 要做 idea 2，脚手架改动空间必须让**累积**有意义（真实 LLM 重写 agent.py 才满足），或者在 toy 里把诚实能力做成需要 ≥5 次独立突变累加的多维向量。先跑真实模型版再决定论文结构，这个判断不变。

**附带发现：ANNECS 比通过率抗 hack。** 重判后 ANNECS 只掉 1–2（9.6→9.2），通过率掉 0.5。原因是 `annecs()` 计的是"archive 中任一 agent 的首次干净解"，被拒绝的诚实子代也算；而冠军通过率只看一个（被 hack 污染的）agent。这既是 ANNECS 的优点，也是一个需要在论文里说清的定义选择（"archive 级 vs 冠军级"）。

## Idea 3 改版：time-to-hack × 漏洞深度（`toy/run_tth.py`，6 seed × 8 代）

深度 2 = shotgun 需要同时改 `MODE` 和 `RESOLVE`，单改任一个都是中性的，被严格接受门拒绝；leak 3 的 improver 能从 evidence 推出"目标错误"并做复合编辑，leak 0–2 只能靠 30% 概率的盲目双突变。

| | 深度 1 | 深度 2 |
|---|---|---|
| leak 0 | 6/6 被 hack，中位第 3 代 | 3/6，删失均值 6.2 代 |
| leak 1 | 6/6，2.5 | 2/6，7.0 |
| leak 2 | 6/6，2.5 | 4/6，5.3 |
| leak 3（+evidence） | 6/6，2.0 | **6/6，1.8** |

判定：**漏洞深度是被原设计漏掉的隐变量**。一步可达的漏洞，接受门自己就会选中，泄露只改变速度；两步可达的漏洞，evidence 级泄露把 time-to-hack 从 ≥5 代压到 2 代、命中率从 1/3–2/3 升到 6/6。这是 by construction 的（improver 的"理解"是脚本写死的），但它证明了改版后的测量（time-to-hack，以深度为因子）在 6 seed 下能分离，而原版（最终 hack 份额）不能。真实模型上的假设就写成：*泄露只对深漏洞起作用*；真实 proposer 验证器的漏洞深度分布是 S1 要测的东西。

## 这个 toy 不能回答的

- 真实 improver 是否会主动写出 shotgun 式代码（这里是旋钮突变 + 接受门选中；真实模型可能更会、也可能因为 prompt 里"不要副作用"而不会）。
- 真实 proposer 写的验证器有多少类似漏洞（mock 验证器全是"点名记录最终状态"模板）。
- 多步漏洞的可达深度分布——这是 idea 3 改版后的核心未知量。

## 复现

```bash
pip install -e ".[dev]"; python3 toy/run_matrix.py --seeds 5 --gens 6 --parallel 2; python3 toy/plot.py
```
