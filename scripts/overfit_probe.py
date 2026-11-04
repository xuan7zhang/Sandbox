#!/usr/bin/env python3
"""Score agents on the overfit pool under RAW and HARDENED verifiers from the same episodes.

Each (agent, task, rep) episode is run once and judged twice (rule-based stack, no LLM judge, as in the
loop): with the task's raw verifier (what condition B's loop sees) and its hardened one (truth).
    train_raw - train_hard = the agent's verifier-attributed pass rate on train.
    python scripts/overfit_probe.py --pool /data2/.../overfit/pool --agent v0=sandbox/solver/agents/v0 \
        --agent fanout=/data2/.../overfit/agents/fanout --reps 2 --out probe.json
Needs the vLLM server on --port.
"""
from __future__ import annotations

import argparse, json, os, statistics as st, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from sandbox.solver.runner import run_episode  # noqa: E402
from sandbox.tasks import public_view  # noqa: E402
from sandbox.verifier import VerifierStack  # noqa: E402
from sandbox.world import get_world  # noqa: E402

NAME = "Qwen/Qwen3-30B-A3B-Instruct-2507"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True, help="prefix given to build_overfit_pool.py")
    ap.add_argument("--agent", action="append", required=True, help="label=agent_dir")
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    raw, hard = json.load(open(a.pool + "_raw.json")), json.load(open(a.pool + "_hard.json"))
    rawt = {t["id"]: t for t in raw["train"] + raw["test"]}
    hardt = {t["id"]: t for t in hard["train"] + hard["test"]}
    agents = [x.split("=", 1) for x in a.agent]
    llm_cfg = {"provider": "openai", "model": NAME, "base_url": f"http://127.0.0.1:{a.port}/v1"}
    stack = VerifierStack()

    def one(job):
        label, adir, tid, rep = job
        t = hardt[tid]
        w = get_world(t["world"], seed=t["seed"])
        ep = run_episode(adir, w, public_view(t, w.describe()), agent_version=label, llm=None, llm_cfg=llm_cfg,
                         max_steps=t["max_steps"], timeout_s=900, isolate=True)
        vr, vh = stack.judge(rawt[tid], ep), stack.judge(t, ep)
        return {"agent": label, "task": tid, "rep": rep, "status": ep.status, "steps": ep.steps,
                "raw": int(vr.passed and not vr.hacking_suspected), "hard": int(vh.passed and not vh.hacking_suspected),
                "payoff": t["meta"]["pool_source"]["payoff"]}
    jobs = [(l, d, tid, r) for r in range(a.reps) for l, d in agents for tid in hardt]
    t0 = time.time()
    with ThreadPoolExecutor(a.workers) as ex:
        res = list(ex.map(one, jobs))
    print(f"{len(jobs)} episodes in {(time.time() - t0) / 60:.1f} min")
    json.dump(res, open(a.out, "w"))
    tr = {t["id"] for t in hard["train"]}
    for l, _ in agents:
        for name, ids in (("train", tr), ("test", set(hardt) - tr)):
            rows = [r for r in res if r["agent"] == l and r["task"] in ids]
            pr = [r for r in rows if r["payoff"]]
            print(f"{l:10s} {name:5s} raw {st.mean(r['raw'] for r in rows):.3f}  hard {st.mean(r['hard'] for r in rows):.3f}"
                  f"  | payoff tasks raw {st.mean(r['raw'] for r in pr) if pr else float('nan'):.3f}"
                  f" hard {st.mean(r['hard'] for r in pr) if pr else float('nan'):.3f}  n={len(rows)}")


if __name__ == "__main__":
    main()
