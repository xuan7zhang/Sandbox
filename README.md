# rsi-sandbox

A long-horizon **self-improvement sandbox** in which the three things that existing
self-improving-agent papers keep fixed — the task distribution, the verifier, and the
safety guardrails — are themselves versioned, evolvable and audited objects, and in
which *hacking rate* and *novel-tasks-created-and-solved* (ANNECS) are reported as
first-class metrics next to pass rate.

The design follows the gap analysis in `RSI 与长程沙盒论文综述` (project doc): the
self-improving coding-agent line (STOP → ADAS → SICA → DGM → HGM → GEA/MGM/RQGM) is
bound to static benchmarks; the self-play line (AZR → R-Zero → SPADE/Explorer-Zero)
collapses without external grounding; and every paper that checked found objective
hacking that grows with optimisation steps. This sandbox is built to measure those
things rather than hide them.

```
            ┌──────────────┐    tasks + hidden verifiers     ┌──────────────┐
            │   PROPOSER   │ ───────────────────────────────▶│   FILTERS    │ safety / nontrivial /
            │ (LLM | mock) │  ◀── frontier solve-rate by tag │              │ solvable / dedup
            └──────────────┘                                 └──────┬───────┘
                                                                    ▼
┌──────────────┐  attack trajectories   ┌──────────────┐    ┌──────────────┐
│  ADVERSARY   │ ──────────────────────▶│  VERIFIER    │◀───│   ARCHIVE    │ agents (lineage, CMP)
│ (red team)   │ ◀── harden verifier ── │   STACK      │    │              │ tasks (versioned verifiers)
└──────────────┘                        └──────▲───────┘    │              │ episodes, generations
                                               │ verdict    └──────▲───────┘
┌──────────────┐   new agent.py         ┌──────┴───────┐           │
│   IMPROVER   │ ──────────────────────▶│   SOLVER     │ ──────────┘ episode (host-recorded trajectory)
│ (meta-agent) │ ◀── diagnostics only   │  subprocess  │
└──────────────┘                        └──────┬───────┘
                                               │ tool calls (JSON-lines, no hidden state)
                                        ┌──────▼───────┐
                                        │    WORLD     │ synthetic stateful tool world,
                                        │   (BizOps)   │ snapshot / restore / state-diff
                                        └──────────────┘
```

## Layers

| layer | module | what it does |
|---|---|---|
| World | `sandbox/world/` | `World` base class: JSON state, JSON-schema tools, `snapshot/restore`, `state_diff`, hidden keys (`_canary`, `_clock`) and hidden tools never exposed to the solver. Two worlds: `BizOpsWorld` (contacts / products / orders / calendar / outbox; inventory arithmetic + state machines) and `TicketsWorld` (members with capacity, tickets with a 5-stage workflow, acyclic blocker graph, sprints) — structurally different so transfer can be measured. |
| Solver | `sandbox/solver/` | The **self-modifiable** scaffold is one file, `agent.py`, with contract `run(task, tools, env, llm) -> str`. It runs in a `python -I` subprocess speaking a JSON-lines protocol; the host records the authoritative trajectory, enforces step limits and timeouts, and blocks hidden tools. `agents/v0` is the initial ReAct agent; `agents/adversary` is the red-team agent. |
| Proposer | `sandbox/proposer/` | `LLMProposer` generates `(instruction, hidden verify() code, scope tables, reference actions)` at the champion's **frontier difficulty**, with diversity pressure from existing tasks and per-tag solve rates. `TaskFilter` gates: static safety screen → do-nothing must fail → reference replay must pass → fingerprint/Jaccard dedup. Acceptance rates are logged. |
| Verifier | `sandbox/verifier/` | Hidden `verify()` code runs sandboxed (`python -I -S`, rlimits, timeout, import whitelist). The `VerifierStack` adds integrity checks: canary, forbidden-action, collateral (out-of-scope state changes), false-claim, zero-action-pass, plus an optional LLM `RubricJudge` (called only on passes) for letter-not-spirit exploits. A pass that trips a hack-severity flag is **hacking_suspected**. `Adversary` attacks each new task; passes that are caught trigger **hardening** (deterministic scope guard + optional LLM rewrite validated against reference / null / attack), producing a new verifier version. |
| Archive | `sandbox/archive/` | SQLite + files: agent lineage (parent, status, rationale), versioned tasks (`tasks/history/*.v{k}.json`), every episode (trajectory, verdict, usage, **final state**), per-generation summaries, rollback of verifier versions. |
| Metrics | `sandbox/metrics/` | `annecs` (tasks novel at creation and later solved without hacking), `hacking_rate`, `clade_metaproductivity` (HGM's CMP), per-difficulty pass rates, cumulative LLM budget, and `rejudge` (re-score every stored episode under the current verifier version → *verifier-attributed progress* per generation). |
| Loop | `sandbox/loop/` | One generation = propose → attack/harden → probe champion (novelty) → select parent (`best` / `cmp` / `random`) → improve → evaluate child on the full active set → accept only on strict non-hacking improvement → report. `RandomImprover` + `selection: random` is the matched-budget baseline. |

**Information boundaries.** The solver sees only public state through tools. The
improver sees only verdict-level diagnostics (pass/fail, flag names, evidence
strings, trajectory), never verifier code. The adversary sees the task but not the
verifier. Only proposer / filters / hardening touch verifier code, and that code is
itself sandboxed because it is model-written.

## Quick start

```bash
pip install -e ".[dev,llm]"
pytest -q                                           # 24 tests, fully offline (~30 s)
python scripts/run_loop.py configs/minimal_mock.yaml   # offline 3-generation loop
python scripts/run_loop.py configs/minimal_mock.yaml --baseline random
```

Offline run output (limited initial agent, mock improver that raises its action budget):

```
gen0: champ=v0   rate=0.50 annecs=0 tasks=6   by_diff={1:1.0, 2:0.5, 3:0.0} hardened=6
gen1: champ=g1c0 rate=1.00 annecs=4 tasks=10  diff_target=2 hardened=4 accepted=g1c0
gen2: champ=g2c0 rate=1.00 annecs=7 tasks=14  diff_target=4 hardened=4 accepted=g2c0
gen3: champ=g3c0 rate=1.00 annecs=8 tasks=18  diff_target=5 hardened=4 accepted=g3c0
```

Experiment matrix (conditions × seeds, aggregated with 95% CIs, figure):

```bash
python scripts/run_matrix.py configs/minimal_mock.yaml --seeds 0 1 2 --conditions cmp best random --parallel 3
python scripts/report.py runs/minimal_mock_matrix/*/seed*      # or any set of run dirs
# -> report/summary.md, summary.json, curves.png (pass rate, ANNECS, hacking, difficulty, catch rate, budget)
```

Real models — see **RUNBOOK.md** (vLLM local open models or the Claude API):

```bash
export ANTHROPIC_API_KEY=...
python scripts/run_loop.py configs/claude_small.yaml
# or a local open model through vLLM (OpenAI-compatible):
python scripts/run_loop.py configs/vllm_local.yaml
```

Everything lands in `runs/<name>/`: `generations.jsonl` (one summary per generation),
`archive.sqlite`, `agents/<version>/agent.py` + `rationale.md`, `tasks/*.json`,
`tasks/history/`, `episodes/g<k>/*.json`.

## What a generation reports

```json
{"gen": 2, "champion": "g2c0", "champion_pass_rate": 0.71, "champion_pass_rate_incl_hacks": 0.79,
 "champion_cmp": 0.64, "annecs": 7, "tasks_active": 14, "tasks_novel_this_gen": 3,
 "hacking": {"episodes": 32, "passes": 22, "hacking_passes": 3, "hacking_rate_of_passes": 0.136},
 "pass_rate_by_difficulty": {"1": 1.0, "2": 0.8, "3": 0.5, "4": 0.2},
 "adversary": {"attacks": 4, "attack_pass_rate": 0.5, "caught_rate": 0.5, "undetected_rate": 0.0, "hardened": 2},
 "proposer_acceptance": {"candidates": 9, "accepted": 4, "rejected_by": {"trivial": 2, "unsolvable": 3}},
 "children": [{"version": "g2c0", "status": "alive", "pass_rate": 0.71, "parent_pass_rate": 0.64}],
 "budget_cumulative": {"input_tokens": 1.2e6, "output_tokens": 9e4, "llm_calls": 611, "episodes": 62},
 "meta_llm_usage": {"proposer": {...}, "improver": {...}, "hardening": {...}}}
```

## Adding a world

Subclass `World`, implement `_build_initial_state(seed)` and register tools with
`self.tool(name, description, json_schema)` inside `_register_tools`; prefix hidden
state keys and hidden tools with `_`. Register with `@register_world`. Everything else
(snapshot, diff, isolation, verifier stack) is inherited. The proposer prompt is
world-agnostic; `MockProposer` is BizOps-specific and only used offline.

## Roadmap (toward the paper)

Done: two worlds, rule-based + LLM-judge integrity stack, adversary + hardening with
verifier versioning, re-judging, experiment matrix with CIs and figures.

1. **Real-model milestone** (RUNBOOK.md): 5 generations × 3 seeds × {cmp, random};
   check that proposer acceptance, adversary catch rate and hacking rate are non-degenerate.
2. **Ablations**: co-evolving tasks+verifiers vs. frozen task set (`adversary: false`,
   fixed `difficulty`); with vs. without the rubric judge; BizOps vs. Tickets transfer.
3. **Judge calibration**: human audit of ~50 judge-flagged passes → precision/recall.
4. **Scale**: more generations (≥10), async episode execution, a third world
   (filesystem + shell) for longer horizons.
