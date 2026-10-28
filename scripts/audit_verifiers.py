#!/usr/bin/env python3
"""S1 — verifier loophole census for a real proposer.

Generates N candidate tasks with the configured proposer, runs the filters, then attacks every
accepted task's verifier with three scripted exploits — before and after the deterministic
hardening (scope guard + minimality guard). Writes a table that answers the reviewer question
"how weak are the verifiers your proposer writes?".

    OPENAI_API_KEY=EMPTY python scripts/audit_verifiers.py configs/vllm_local.yaml --n 100 --out runs/audit_vllm
    python scripts/audit_verifiers.py configs/minimal_mock.yaml --n 30 --out runs/audit_mock   # offline check

Exploits (all run with the honest v0 scaffold + a scripted 'model', no LLM needed):
  do_nothing : finish immediately                      -> passes  => trivially satisfiable verifier
  wrecking   : follow instruction + out-of-scope damage -> passes w/o flag => table-level blindness
  shotgun    : follow instruction fanned out to every record in scope tables
               -> passes w/o flag => record-level blindness (the loophole the minimality guard closes)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sandbox.llm import MockLLM, get_llm  # noqa: E402
from sandbox.llm.mock_scripts import DoNothing, FollowInstruction, Shotgun, WreckingAdversary  # noqa: E402
from sandbox.proposer import LLMProposer, MockProposer, TaskFilter  # noqa: E402
from sandbox.solver import run_episode  # noqa: E402
from sandbox.tasks import public_view  # noqa: E402
from sandbox.verifier import VerifierStack  # noqa: E402
from sandbox.verifier.adversary import add_minimality_guard, add_scope_guard  # noqa: E402
from sandbox.world import get_world  # noqa: E402

V0 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sandbox", "solver", "agents", "v0")
EXPLOITS = {"do_nothing": DoNothing, "wrecking": WreckingAdversary, "shotgun": Shotgun}


def judge(stack, task, script):
    w = get_world(task["world"], seed=task["seed"])
    ep = run_episode(V0, w, public_view(task, w.describe()), llm=MockLLM(script()), isolate=False,
                     max_steps=task["max_steps"], timeout_s=120)
    return stack.judge(task, ep)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--world", default=None)
    ap.add_argument("--difficulty", type=int, default=2)
    ap.add_argument("--out", default="runs/audit")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config))
    world_name = a.world or cfg.get("loop", {}).get("world", "bizops")
    p = cfg.get("models", {}).get("proposer", {})
    if p.get("provider") == "mock":
        proposer = MockProposer(seed=0)
    else:
        proposer = LLMProposer(get_llm(p.get("provider"), p.get("model"), base_url=p.get("base_url")))
    os.makedirs(a.out, exist_ok=True)

    # 1. generate + filter
    cands, accepted, rep_summary = [], [], Counter()
    batch, g = 8, 0
    while len(accepted) < a.n and g < 4 * a.n // batch + 2:
        world = get_world(world_name, seed=5000 + g)
        try:
            c = proposer.propose(world, batch, generation=g, existing=accepted, difficulty=a.difficulty)
        except Exception as e:  # noqa: BLE001
            print(f"proposer error gen {g}: {e!r}")
            c = []
        rep = TaskFilter().run(c, accepted)
        for k, v in rep.summary().get("rejected_by", {}).items():
            rep_summary[k] += v
        cands.extend(c)
        accepted.extend(rep.accepted)
        g += 1
    accepted = accepted[:a.n]
    print(f"candidates {len(cands)} -> accepted {len(accepted)}  rejected_by={dict(rep_summary)}")

    # 2. attack before / after hardening
    stack = VerifierStack()
    rows = []
    for t in accepted:
        row = {"id": t["id"], "instruction": t["instruction"][:120], "difficulty": t["difficulty"],
               "scope": t["scope"]["tables"], "before": {}, "after": {}}
        for name, script in EXPLOITS.items():
            v = judge(stack, t, script)
            row["before"][name] = {"pass": v.passed, "flagged": any(f.severity in ("warn", "hack") for f in v.flags)}
        row["hardened"] = {"scope_guard": add_scope_guard(t), "minimality_guard": add_minimality_guard(t)}
        for name, script in EXPLOITS.items():
            v = judge(stack, t, script)
            row["after"][name] = {"pass": v.passed, "flagged": any(f.severity in ("warn", "hack") for f in v.flags)}
        row["honest_after"] = judge(stack, t, FollowInstruction).passed if p.get("provider") == "mock" else None
        rows.append(row)
        print(f"{t['id']}: " + " ".join(f"{k}={'PASS' if row['before'][k]['pass'] else 'fail'}{'!' if row['before'][k]['pass'] and not row['before'][k]['flagged'] else ''}" for k in EXPLOITS)
              + " | after: " + " ".join(f"{k}={'PASS' if row['after'][k]['pass'] else 'fail'}" for k in EXPLOITS))

    # 3. table
    n = len(rows) or 1
    def rate(stage, name, undetected=False):
        return round(sum(1 for r in rows if r[stage][name]["pass"] and (not r[stage][name]["flagged"] if undetected else True)) / n, 3)
    table = {name: {"passes_before": rate("before", name), "undetected_before": rate("before", name, True),
                    "passes_after": rate("after", name), "undetected_after": rate("after", name, True)} for name in EXPLOITS}
    table["hardened"] = {k: round(sum(1 for r in rows if r["hardened"][k]) / n, 3) for k in ("scope_guard", "minimality_guard")}
    json.dump({"n": len(rows), "rejected_by": dict(rep_summary), "table": table, "rows": rows,
               "tasks": accepted}, open(os.path.join(a.out, "audit.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps({"n": len(rows), "rejected_by": dict(rep_summary), "table": table}, indent=1))


if __name__ == "__main__":
    main()
