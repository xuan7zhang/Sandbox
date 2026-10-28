# RUNBOOK — 在你的服务器上跑真实模型

目标：第一个真实模型里程碑 = 5 代、3 个 seed、cmp vs random 两个条件，拿到
非退化的三个数（proposer 接受率、adversary 捕获率、hacking 率）和第一张 curves.png。

## 0. 环境

```bash
git clone <your repo> rsi-sandbox && cd rsi-sandbox
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,llm]"
pytest -q                      # 24 个离线测试，约 30 s，必须全绿
python scripts/run_loop.py configs/minimal_mock.yaml   # 离线冒烟，约 10 s
```

## 1A. 本地开源模型（推荐先跑这个，零 API 费用）

需要一个支持工具调用的模型。单卡 80G 或双卡 48G 起：

```bash
# 终端 1：vLLM（Qwen3-30B-A3B 工具调用稳定；更小的可换 Qwen3-8B / Qwen2.5-14B-Instruct）
vllm serve Qwen/Qwen3-30B-A3B-Instruct-2507 \
  --enable-auto-tool-choice --tool-call-parser hermes \
  --max-model-len 32768 --port 8000 --gpu-memory-utilization 0.9

# 终端 2：冒烟（1 代，确认工具调用、proposer JSON、验证器都正常）
export OPENAI_API_KEY=EMPTY
python scripts/run_loop.py configs/vllm_local.yaml --generations 1 --run-dir runs/smoke_vllm
python scripts/report.py runs/smoke_vllm
```

看 `runs/smoke_vllm/generations.jsonl` 里的 gen0：
- `proposer_acceptance.acceptance_rate` 在 0.2–0.8 之间算正常；<0.1 说明 proposer 写不出能过过滤的验证器（看 `rejected_by` 是哪一项占主导）
- `adversary.caught_rate` > 0 且 `undetected_rate` < 0.5
- `hacking.hacking_rate_of_passes` 在 0–0.3；全 0 要检查 judge 是否真的被调用（`meta_llm_usage`）

## 1B. Claude API

```bash
export ANTHROPIC_API_KEY=...
python scripts/run_loop.py configs/claude_small.yaml --generations 1 --run-dir runs/smoke_claude
```

费用估算：每代 ≈ `tasks_per_gen × 2（攻击+探测）+ children_per_gen × |活跃任务|` 个 episode；
solver 用 haiku，一代十几个任务大约 1–3 美元，5 代、3 seed、2 条件约 50–100 美元。

## 2. 主实验矩阵

```bash
python scripts/run_matrix.py configs/vllm_local.yaml --seeds 0 1 2 --conditions cmp random --generations 5 --parallel 2
# 结果：runs/vllm_local_matrix/report/{summary.md, summary.json, curves.png}
```

`--parallel` 受 vLLM 吞吐限制；solver 子进程是 I/O 等待为主，2–4 并行通常没问题。
单个 run 可用 `--run-dir` 指定目录后**重复执行**续跑（Archive 会从 champion 恢复）。

## 3. 读结果

- `summary.md`：每代一行；`pass`/`incl.hacks` 的差就是被完整性栈抓到的 hack 占比；
  `verifier-attributed` 列是重判后"进步中有多少来自验证器漏洞"
- `curves.png`：六个小图，多 seed 时带 95% CI 阴影；cmp 与 random 预算列应接近（匹配预算）
- 审计单条 episode：`runs/<run>/episodes/g<k>/ep000123.json`（含轨迹、裁决、最终状态）
- 看某代 improver 到底改了什么：`runs/<run>/agents/g3c0/rationale.md` + `diff agents/v0/agent.py agents/g3c0/agent.py`
- 回滚某任务的验证器：`Archive(run).rollback_task_verifier(task_id, version)`

## 4. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| proposer 接受率 ≈ 0，`rejected_by.safety` 为主 | 模型在验证器里 import 了非白名单模块；在 `PROPOSER_SYSTEM` 里再强调一次，或换更强的 proposer 模型 |
| `rejected_by.unsolvable` 为主 | 参考动作写错；可设 `TaskFilter(require_reference=False)`（接受但标 `solvable=unverified`），或用 solver 跑一次作为可解性检查 |
| episode `status=fatal` 很多 | 看 `logs` 里的 stderr；多半是 improver 写坏了 agent（会被拒绝，不影响冠军）或 tool-call JSON 解析失败 |
| hacking 率为 0 但 `incl.hacks` ≠ `pass` | 正常：前者按通过数算，后者按任务集算 |
| vLLM 工具调用返回空 | 确认 `--enable-auto-tool-choice --tool-call-parser` 与模型匹配（Qwen 用 hermes，Llama 用 llama3_json） |

## 5. 下一个里程碑

真实模型 5 代跑通后：
1. 两个世界各跑一遍，比较 `annecs` 曲线斜率与 hacking 率（跨世界迁移章节）
2. 固定任务集 vs 共进化任务集（`adversary: false` + 固定 `difficulty`）作为消融
3. 人工审计 50 条 judge 标记为 hack 的 episode，报告 judge 的精确率

---

## 6. 2026-10-27 更新：全 vLLM 实验计划（S1 → S2 → S3）

toy 排查（`toy/README.md`）的结论改变了优先级：先证明"验证器漏洞贡献了多少报告进步"，再谈搜索方法。
三件事按顺序跑，每件都有"算通过"的数字；前一件不通过不要跑下一件。

### 模型选择（全开源）

| 角色 | 建议模型 | 说明 |
|---|---|---|
| solver / adversary | `Qwen/Qwen3-30B-A3B-Instruct-2507` | 调用量占 90%+，MoE 吞吐高；工具调用用 `--tool-call-parser hermes` |
| proposer / improver / hardening / judge | 同一模型先试；S1 看 proposer 合格率，S2 看 improver 合格率，不够再换 `Qwen3-235B-A22B-Instruct`（≥4×80G）或 `deepseek-ai/DeepSeek-V3.2`（8×80G） | 元层质量是弱模型最容易挂的地方（Live-SWE-agent 的 GPT-5-Nano 44→14） |

两个模型时起两个 vLLM（端口 8000 / 8001），在 yaml 里按角色填 `base_url`。单卡 80G 跑 30B-A3B 用 `--max-model-len 32768`；improver 要读完整 agent.py + 诊断，`max_tokens 8000`，确认 `--max-model-len` ≥ 24k。

### S1 验证器漏洞普查（约 1 GPU 小时，不需要 improver）

```bash
export OPENAI_API_KEY=EMPTY
python scripts/audit_verifiers.py configs/vllm_local.yaml --n 100 --out runs/audit_vllm
python scripts/audit_verifiers.py configs/vllm_local.yaml --n 100 --world tickets --out runs/audit_vllm_tickets
```

产出 `audit.json` 的 `table`：三种脚本化攻击（do_nothing / wrecking / shotgun）在加固前后的通过率与未检出率，
以及 `rejected_by`（proposer 写不出合格验证器的原因分布）。

- **通过**：proposer 接受率 0.2–0.8；加固后三种攻击 `undetected_after` 均 < 0.05；加固前 shotgun `undetected_before` 是论文表 1 的核心数字
- **不通过**：接受率 < 0.1 → 换 proposer 模型；`undetected_after` 高 → 真实验证器有 toy 没覆盖的漏洞类型，先看 `rows` 里哪些任务、补确定性加固，这本身是论文内容
- 人工看 20 个 `tasks[*].verifier.code`，记录漏洞类型分布（只查点名记录 / 只查存在性 / 不查数量 / 其他），这张小表直接进论文

### S2 主实验：三条曲线（约 10–20 GPU 小时）

```bash
# 条件 A：完整系统（minimality_guard: true 是 LoopConfig 默认）
python scripts/run_matrix.py configs/vllm_local.yaml --seeds 0 1 2 --conditions best random --generations 5 --parallel 2
# 条件 B：消融——验证器不做循环内加固（事后审计才发现漏洞）
#   复制 configs/vllm_local.yaml 为 configs/vllm_noguard.yaml，在 loop: 下加  minimality_guard: false  和  adversary: false，run_dir 改名
python scripts/run_matrix.py configs/vllm_noguard.yaml --seeds 0 1 2 --conditions best random --generations 5 --parallel 2
python scripts/report.py runs/vllm_local_matrix/*/seed* runs/vllm_noguard_matrix/*/seed*
```

`report.py` 现在做**全栈重判**（隐藏验证器 + 完整性检查都重跑），并给出 archive 级 / 冠军级两个 ANNECS。主图三条线：
条件 B 的 reported、条件 B 重判后、条件 A（reported 应 ≈ 重判）。

- **通过**：条件 B 的 `verifier-attributed` > 0.1 且随代际不缩小；条件 A 的 ≈ 0；A 的冠军级 ANNECS ≥ B 的
- **random 追平 best 不算失败**：主张不押在搜索上，三条曲线在两种选择下都成立反而更强
- **improver 合格率**（`children[*].status != invalid` 的比例）< 0.5 → 元层模型太弱，换 improver 模型重跑，不要硬凑

### S3 只在 S2 通过后

1. `--conditions cmp`，看 CMP 是否比 best 更不易接受 hack（HGM 的"元生产力 ≠ 分数"论点）
2. 固定任务集消融：`difficulty: "2"` + `tasks_per_gen: 0`（静态基准 ≈ DGM/HGM 协议）vs frontier
3. Tickets 世界重复 S2 的条件 A；两个世界的 shotgun 等价物不同，这是"不是 BizOps 特例"的证据
4. 泄露实验（toy 已验证设计）：给 `LLMImprover` 加 `leak` 档位（0 无诊断 / 1 pass-fail / 2 +flag / 3 +evidence+轨迹），指标 **time-to-hack**（首次重判翻转的冠军出现的代数）；只在 S2 的 B 条件里有可观测 hack 时跑

### 预算与时间（单卡 80G，30B-A3B，约 25 tok/s/请求、并发 8）

| 实验 | episode 数 | 墙钟 |
|---|---|---|
| S1 ×2 世界 | ~600 | 1–2 h |
| S2 一个条件（3 seed × 5 代） | ~1,200 | 4–8 h |
| S2 两个条件 | ~2,400 | 1 天 |
| S3 全部 | ~5,000 | 2–3 天 |

上下文溢出是最常见的失败（SWE-bench Pro 里 Sonnet 4 的 35.6% 失败是这个）：`episode_timeout_s: 900`，
`max_steps_cap: 80`，solver 在 `agents/v0` 里已对工具输出截断到 6000 字符；若 `status=step_limit` 占比 > 30%，先降 `max_steps_cap` 再看。
