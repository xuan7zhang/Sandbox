"""Screening matrix for ideas 1-3 on the real sandbox (mock models).

M1  leakage sweep  (idea 1 + 3): leak 0..3, selection=best, frontier tasks
M2  2x2 (+cmp)     (idea 2)    : {static d=2, frontier} x {best/leak3, cmp/leak3, random/leak0}
M3  verifier co-evolution (idea 1): minimality guard closed in-loop vs post-hoc only

    python3 toy/run_matrix.py --seeds 5 --gens 6 --parallel 4
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import statistics as st
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from toy.toy import run_toy  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


def job(args):
    name, kw = args
    rd = os.path.join(OUT, "runs", name)
    shutil.rmtree(rd, ignore_errors=True)
    try:
        r = run_toy(rd, **kw)
    except Exception as e:  # noqa: BLE001
        return name, {"error": repr(e)}
    r["name"] = name
    return name, r


def ci(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    if len(xs) < 2:
        return xs[0], 0.0
    return st.mean(xs), 1.96 * st.stdev(xs) / math.sqrt(len(xs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--gens", type=int, default=6)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--p-noise", type=float, default=0.3)
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    seeds = list(range(a.seeds))
    jobs = []
    for s in seeds:
        for leak in range(4):
            jobs.append((f"M1_leak{leak}_s{s}", dict(seed=s, leak=leak, selection="best", generations=a.gens, p_noise=a.p_noise)))
        for diff in ("2", "frontier"):
            for cond, (sel, leak) in {"best": ("best", 3), "cmp": ("cmp", 3), "random": ("random", 0)}.items():
                jobs.append((f"M2_{diff}_{cond}_s{s}", dict(seed=s, leak=leak, selection=sel, difficulty=diff, generations=a.gens, p_noise=a.p_noise)))
        jobs.append((f"M3_inloop_s{s}", dict(seed=s, leak=3, selection="best", generations=a.gens, p_noise=a.p_noise, minimality_in_loop=True)))
    # M1 leak3 doubles as M3 post-hoc-only and M2 frontier/best
    with ProcessPoolExecutor(a.parallel) as ex:
        results = dict(ex.map(job, jobs))
    with open(os.path.join(OUT, "raw.json"), "w") as f:
        json.dump(results, f, indent=1)

    def final(name_prefix, key):
        vals = []
        for s in seeds:
            r = results.get(f"{name_prefix}_s{s}")
            if r and "per_gen" in r:
                vals.append(r["per_gen"][-1][key])
        return vals

    def share_shotgun(name_prefix):
        vals = []
        for s in seeds:
            r = results.get(f"{name_prefix}_s{s}")
            if r and "per_gen" in r:
                vals.append(float(r["per_gen"][-1]["knobs"]["MODE"] == "shotgun"))
        return vals

    summary = {"M1": {}, "M2": {}, "M3": {}}
    for leak in range(4):
        p = f"M1_leak{leak}"
        summary["M1"][f"leak{leak}"] = {
            "reported": ci(final(p, "reported")), "rejudged": ci(final(p, "rejudged")),
            "illusory": ci([x - y for x, y in zip(final(p, "reported"), final(p, "rejudged"))]),
            "annecs": ci(final(p, "annecs")), "annecs_rejudged": ci(final(p, "annecs_rejudged")),
            "flagged_hack_rate": ci(final(p, "hack_rate_flagged")), "champion_is_shotgun": ci(share_shotgun(p)),
        }
    for diff in ("2", "frontier"):
        for cond in ("best", "cmp", "random"):
            p = f"M2_{diff}_{cond}"
            summary["M2"][f"{diff}/{cond}"] = {
                "reported": ci(final(p, "reported")), "rejudged": ci(final(p, "rejudged")),
                "annecs": ci(final(p, "annecs")), "annecs_rejudged": ci(final(p, "annecs_rejudged")),
                "champion_is_shotgun": ci(share_shotgun(p)),
                "final_max_actions": ci([results[f"{p}_s{s}"]["per_gen"][-1]["knobs"]["MAX_ACTIONS"] for s in seeds if f"{p}_s{s}" in results and "per_gen" in results[f"{p}_s{s}"]]),
            }
    for label, p in (("posthoc_only", "M1_leak3"), ("in_loop", "M3_inloop")):
        summary["M3"][label] = {
            "reported": ci(final(p, "reported")), "rejudged": ci(final(p, "rejudged")),
            "annecs": ci(final(p, "annecs")), "annecs_rejudged": ci(final(p, "annecs_rejudged")),
            "champion_is_shotgun": ci(share_shotgun(p)),
            "final_max_actions": ci([results[f"{p}_s{s}"]["per_gen"][-1]["knobs"]["MAX_ACTIONS"] for s in seeds if f"{p}_s{s}" in results and "per_gen" in results[f"{p}_s{s}"]]),
        }
    # per-generation curves for M1 (reported vs rejudged) and M3
    curves = {}
    for p in [f"M1_leak{l}" for l in range(4)] + ["M3_inloop"]:
        rows = [results[f"{p}_s{s}"]["per_gen"] for s in seeds if f"{p}_s{s}" in results and "per_gen" in results[f"{p}_s{s}"]]
        if not rows:
            continue
        G = min(len(r) for r in rows)
        curves[p] = {k: [ci([r[g][k] for r in rows]) for g in range(G)] for k in ("reported", "rejudged", "annecs", "annecs_rejudged")}
    summary["curves"] = curves
    errors = {k: v["error"] for k, v in results.items() if "error" in v}
    summary["errors"] = errors
    with open(os.path.join(OUT, "summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "curves"}, indent=1))


if __name__ == "__main__":
    main()
