# 实验结果（2026-10-28 – 10-31）

这里只放各轮实验的报告和小体积汇总文件（md / json / png）。原始运行数据（archive、episodes、日志）体积太大，没有放进 repo，仍在实验机的 `/data2/ec2-user/rsi_sandbox/<实验>/` 下。报告里出现的 `runs/...`、`overnight/...` 等路径都是指那台机器上的位置。

所有实验的设置相同：solver、proposer 和 improver 都是 Qwen3-30B-A3B-Instruct-2507（bf16，本地 vLLM），世界为 BizOps 或 Tickets。

| 目录 | 问题 | 结论 | 驱动脚本 |
|---|---|---|---|
| [idea1_illusory/](idea1_illusory/) | **虚假进步**：自改进循环报告的进步里，有多少是钻验证器漏洞（verifier loophole）？ | 24/27 个 run 完成（tier 1–6，5 代）。A（有 guard）和 B（无 guard）两种条件下，虚假进步都约为 0。漏洞存在：hardening 前 shotgun 攻击能骗过 bizops_lax 77%、tickets 62% 的任务，但 improver 从来没有利用它。 | `scripts/overnight_idea1.py`、`posthoc_audit.py`、`s1_reference_attacks.py`、`idea1_report.py` |
| [idea2_search/](idea2_search/) | 在静态任务池（36 train / 35 test）上比较 best / cmp / random / best_nodiag 四种搜索方式 | 带诊断信息的 improver 反而让 test 变差：best − nodiag = −0.099，p = 0.027。机制见 `MECHANISM.md`：improver 把 false_claim flag 当成根因，加了一堆先验证再结束的代码；不看诊断的 improver 写的是通用修复，反而修好了 v0 的过度操作问题。 | `build_task_pool.py`、`overnight_idea2.py`、`reeval_champions.py`、`idea2_mechanism.py`、`idea2_report.py` |
| [idea3_leak/](idea3_leak/) | 给 improver 泄露的信息越多（leak 0–3），是否越快学会作弊？ | 零结果（null）。episode 作弊率 v0 为 1.4–2.1%，children 为 2.0–2.8%，与泄露级别无关；65% 的翻转来自同一个多步任务的副作用。 | `build_lax_pool.py`、`overnight_idea3.py`、`idea3_report.py` |
| [night_p2/](night_p2/) | 夜间计划 P0–P2：A 与 B 的完整对比 | P2 主线失败：B 的事后审计 VA = 0，没有可以归因的进步。LLM rubric judge 给出的 97 个作弊标记全部是误报。发现一个未修复的核心 bug，见下文。 | `configs/night_{A,B}.yaml`、`night_p2.py`、`night_extract.py` |
| [overfit/](overfit/) | 改设置专门诱导过拟合，共三轮：leak 4 给出 checker 源码，naive improver 去掉完整性规则 | 三轮的 VA 都约为 0。正向对照证明漏洞存在：手写的 fan-out agent 在 raw verifier 上得 0.396，hardened 后只有 0.021；而且循环会接受这种 agent。但 improver 每次修的都是真 bug，从没写过 fan-out 代码。 | `build_overfit_pool.py`、`overfit_probe.py`、`overnight_overfit.py`、`overfit_posthoc.py`、`overfit_report.py` |

## 总体结论

在这两个合成工具世界里，验证器漏洞是存在的，但 Qwen3-30B 做 improver 时不会主动去利用。所以虚假进步测不出来，原因是这里的作弊上限太低，不是没有作弊的可能。下一步正在评估把沙盒迁移到 SWE-smith 任务上的可行性，该实验单独存放，不在本 repo 里。

## 已知未修复问题

- `sandbox/verifier/adversary.py` 里的 `add_minimality_guard` 用空轨迹做验证，导致带 `len(trajectory)==0` 检查的 verifier 会跳过这个 guard，影响约 13–28% 的任务。tickets 在 hardening 之后剩下的 19% shotgun 泄漏全部来自这个 bug，详见 `night_p2/MORNING_REPORT.md`。overfit 实验在构建任务池的脚本里绕开了这个问题，`sandbox/` 本身没有修。
- `Loop.run()` 恢复运行时会从第 1 代重新开始，导致代数重复。所以失败的 run 都是重命名后从头重跑。
- `report.py` 按 config 里的 condition 分组，会把 A 和 B 的 `best` 合并到一起。需要按 matrix 分别运行。
