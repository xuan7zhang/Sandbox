#!/usr/bin/env python3
"""Run a self-improvement loop from a YAML config.

    python scripts/run_loop.py configs/minimal_mock.yaml          # fully offline smoke run
    python scripts/run_loop.py configs/claude_small.yaml           # real models (needs ANTHROPIC_API_KEY)
    python scripts/run_loop.py configs/claude_small.yaml --baseline random   # matched-budget baseline

Config keys (see configs/*.yaml): loop.*, models.{solver,proposer,improver,adversary,hardening}.
Each model entry is {provider, model, base_url?}; provider "mock" with "script" for offline runs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sandbox.llm import get_llm  # noqa: E402
from sandbox.loop import Loop, LoopConfig  # noqa: E402
from sandbox.loop.improver import LLMImprover, MockImprover, RandomImprover  # noqa: E402
from sandbox.proposer import LLMProposer, MockProposer  # noqa: E402
from sandbox.verifier import VerifierStack  # noqa: E402
from sandbox.verifier.judge import RubricJudge  # noqa: E402


def _llm(entry):
    if entry is None:
        return None
    if entry.get("provider") == "mock":
        import importlib

        mod, _, attr = entry["script"].partition(":")
        cls = getattr(importlib.import_module(mod), attr)
        return lambda: get_llm("mock", script=cls())
    return lambda: get_llm(entry.get("provider"), entry.get("model"), base_url=entry.get("base_url"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--generations", type=int, default=None)
    ap.add_argument("--baseline", choices=["none", "random"], default="none",
                    help="random = uniform parent selection + diagnostics-free improver (matched budget)")
    a = ap.parse_args()
    with open(a.config) as f:
        cfg = yaml.safe_load(f)

    loop_kw = dict(cfg.get("loop", {}))
    if a.run_dir:
        loop_kw["run_dir"] = a.run_dir
    if a.generations is not None:
        loop_kw["generations"] = a.generations
    if a.baseline == "random":
        loop_kw["selection"] = "random"
        if not a.run_dir:
            loop_kw["run_dir"] = loop_kw["run_dir"].rstrip("/") + "_baseline_random"
    models = cfg.get("models", {})
    solver = models.get("solver", {})
    if solver.get("provider") == "mock":
        loop_kw["isolate"] = False
    else:
        loop_kw["solver_llm_cfg"] = {k: solver.get(k) for k in ("provider", "model", "base_url") if solver.get(k)}
    lc = LoopConfig(**loop_kw)
    os.makedirs(lc.run_dir, exist_ok=True)

    # proposer
    p = models.get("proposer", {})
    proposer = MockProposer(seed=lc.rng_seed) if p.get("provider") == "mock" else LLMProposer(_llm(p)())
    # improver
    im = models.get("improver", {})
    if im.get("provider") == "mock":
        improver = MockImprover(**im.get("kwargs", {}))
    else:
        improver = RandomImprover(_llm(im)()) if a.baseline == "random" else LLMImprover(_llm(im)())
    solver_factory = _llm(solver) if solver.get("provider") == "mock" else None
    adversary_factory = _llm(models.get("adversary"))
    hardening_llm = _llm(models.get("hardening"))
    stack = VerifierStack()
    judge = _llm(models.get("judge"))
    if judge:
        stack.add(RubricJudge(judge(), **models["judge"].get("kwargs", {})))
    loop = Loop(lc, proposer=proposer, improver=improver, stack=stack, solver_llm_factory=solver_factory,
                adversary_llm_factory=adversary_factory, hardening_llm=hardening_llm() if hardening_llm else None)
    sums = loop.run()
    print(json.dumps({"run_dir": lc.run_dir, "final": {k: sums[-1][k] for k in
                      ("champion", "champion_pass_rate", "annecs", "tasks_active", "hacking", "budget_cumulative")}},
                     indent=1))


if __name__ == "__main__":
    main()
