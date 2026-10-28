#!/usr/bin/env python3
"""Run the main experiment matrix: conditions x seeds, then aggregate.

    python scripts/run_matrix.py configs/minimal_mock.yaml --seeds 0 1 2 --conditions cmp best random
    python scripts/run_matrix.py configs/vllm_local.yaml  --seeds 0 1 2 3 4 --conditions cmp random --parallel 2

Conditions:
  cmp     HGM-style clade-metaproductivity parent selection, diagnostics-conditioned improver
  best    greedy champion-as-parent, diagnostics-conditioned improver
  random  uniform parent selection + diagnostics-free improver  (matched-budget baseline)
Each (condition, seed) is one `run_loop.py` invocation with its own run_dir under
<run_dir>_matrix/<condition>/seed<k>. All runs share base_seed so that the task
worlds are identical across conditions; rng_seed differs per seed. After all runs
finish, scripts/report.py is called on the matrix directory.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--conditions", nargs="+", default=["cmp", "best", "random"])
    ap.add_argument("--generations", type=int, default=None)
    ap.add_argument("--parallel", type=int, default=1)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    base = yaml.safe_load(open(a.config))
    matrix_dir = base["loop"]["run_dir"].rstrip("/") + "_matrix"
    os.makedirs(matrix_dir, exist_ok=True)

    jobs = []
    for cond in a.conditions:
        for seed in a.seeds:
            cfg = yaml.safe_load(open(a.config))
            cfg["loop"]["run_dir"] = os.path.join(matrix_dir, cond, f"seed{seed}")
            cfg["loop"]["rng_seed"] = seed
            cfg["loop"]["selection"] = "random" if cond == "random" else cond
            if a.generations is not None:
                cfg["loop"]["generations"] = a.generations
            os.makedirs(os.path.dirname(cfg["loop"]["run_dir"]), exist_ok=True)
            cpath = os.path.join(matrix_dir, cond, f"seed{seed}.yaml")
            with open(cpath, "w") as f:
                yaml.safe_dump(cfg, f)
            cmd = [sys.executable, os.path.join(HERE, "run_loop.py"), cpath]
            if cond == "random":
                cmd += ["--baseline", "random", "--run-dir", cfg["loop"]["run_dir"]]
            jobs.append((cond, seed, cmd, cfg["loop"]["run_dir"]))

    for cond, seed, cmd, rd in jobs:
        print(f"[{cond} seed{seed}] {' '.join(cmd)}")
    if a.dry_run:
        return

    def run(job):
        cond, seed, cmd, rd = job
        log = open(rd + ".log", "w")
        p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
        print(f"[{cond} seed{seed}] exit={p.returncode}")
        return p.returncode

    with ThreadPoolExecutor(max_workers=a.parallel) as ex:
        codes = list(ex.map(run, jobs))
    run_dirs = [rd for (_, _, _, rd), c in zip(jobs, codes) if c == 0 and os.path.exists(os.path.join(rd, "generations.jsonl"))]
    if run_dirs:
        r = subprocess.run([sys.executable, os.path.join(HERE, "report.py"), *run_dirs, "--out", os.path.join(matrix_dir, "report")])
        codes.append(r.returncode)
    failed = [f"{cond}/seed{seed}" for (cond, seed, _, _), c in zip(jobs, codes) if c != 0]
    if failed or not run_dirs:
        sys.exit(f"failed runs: {failed or 'all'} (see <run_dir>.log)")


if __name__ == "__main__":
    main()
