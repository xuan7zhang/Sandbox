#!/usr/bin/env python3
"""Unattended idea-2 queue (search method under a static-benchmark protocol) on one vLLM server.

Every run trains on the same fixed task pool (scripts/build_task_pool.py: 'train' = active tasks used for
selection / acceptance / improver diagnostics, 'test' = held-out tasks only used to report the champion),
so champions are comparable across conditions and seeds. Conditions (matched budget: same generations,
children per generation and task set):
  S_best         greedy: parent = champion, improver sees diagnostics            (DGM-lite)
  S_cmp          parent = highest clade metaproductivity                          (HGM-style)
  S_random       uniform random parent + diagnostics-free improver               (Gideoni random sampling)
  S_best_nodiag  parent = champion, diagnostics-free improver  (separates selection from improver information)

    python scripts/overnight_idea2.py --root /data2/ec2-user/rsi_sandbox/idea2 --pool /data2/.../pool.json
Reuses the server / adoption / launch machinery of overnight_idea1.py.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import overnight_idea1 as base  # noqa: E402
from overnight_idea1 import HERE, PY, REPO, Server, adopt_running, done_marker, launch, log  # noqa: E402

CONDITIONS = {  # name -> (selection, improver kwargs, random baseline flag)
    "S_best": ("best", {}, False),
    "S_cmp": ("cmp", {}, False),
    "S_random": ("random", {}, True),
    "S_best_nodiag": ("best", {"use_diagnostics": False}, False),
}


def jobs(a):
    J = []
    plan = [(s, 1) for s in a.seeds] + [(s, m) for m in a.extra_margins for s in a.extra_seeds]
    for s, margin in plan:
        for base_name, (sel, ikw, rnd) in CONDITIONS.items():
            name = base_name if margin == 1 else f"{base_name}_m{margin}"
            cfg = yaml.safe_load(open(os.path.join(REPO, "configs", "vllm_local.yaml")))
            for m in cfg["models"].values():
                m["base_url"] = f"http://127.0.0.1:{a.port}/v1"
            if ikw:
                cfg["models"]["improver"]["kwargs"] = ikw
            rd = os.path.join(a.root, "runs", name, f"seed{s}")
            cfg["loop"].update(run_dir=rd, world="bizops", rng_seed=s, selection=sel, generations=a.generations,
                               task_pool=a.pool, tasks_per_gen=0, heldout_per_gen=0, initial_heldout=0,
                               initial_tasks=0, adversary=False, children_per_gen=a.children, difficulty="2",
                               eval_workers=a.eval_workers, accept_margin=margin)
            J.append({"tier": 1, "id": f"{name}/seed{s}", "kind": "loop", "run_dir": rd, "cfg": cfg, "random": rnd})
    return J


def finish(a, j, rc):
    log(f"done {j['id']} in {(time.time() - j['t0']) / 60:.0f} min rc={rc}")
    if rc == 0:
        open(done_marker(j), "w").write(time.strftime("%F %T"))
    subprocess.run([PY, os.path.join(HERE, "idea2_report.py"), "--root", a.root], capture_output=True, cwd=REPO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--extra-margins", type=int, nargs="*", default=[],
                    help="also run every condition with accept_margin=m (named <cond>_m<m>) on --extra-seeds")
    ap.add_argument("--extra-seeds", type=int, nargs="*", default=[0, 1, 2])
    ap.add_argument("--generations", type=int, default=8)
    ap.add_argument("--children", type=int, default=2)
    ap.add_argument("--eval-workers", type=int, default=5)
    ap.add_argument("--slots", type=int, default=12)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--model-dir", default="/data2/ec2-user/rsi_sandbox/models/Qwen3-30B-A3B-Instruct-2507")
    ap.add_argument("--vllm-bin", default="/home/ec2-user/miniconda3/envs/vllm/bin/vllm")
    ap.add_argument("--cuda-home",
                    default="/home/ec2-user/miniconda3/envs/vllm/lib/python3.10/site-packages/nvidia/cu13")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.root, "logs"), exist_ok=True)
    if os.path.exists(os.path.join(a.root, "ALL_DONE")):
        os.remove(os.path.join(a.root, "ALL_DONE"))
    srv = Server(a)
    srv.start()
    queue = [j for j in jobs(a) if not os.path.exists(done_marker(j))]
    running = adopt_running(a, queue)
    log(f"{len(queue)} jobs queued, {len(running)} adopted, {a.slots} slots")
    last_check = 0.0
    try:
        while queue or running:
            if time.time() - last_check > 60:
                srv.ensure()
                last_check = time.time()
            for j in list(running):
                rc = j["proc"].poll()
                if rc is None:
                    continue
                running.remove(j)
                if rc != 0 and j.get("attempt", 0) < 1:
                    j["attempt"] = j.get("attempt", 0) + 1
                    log(f"FAILED {j['id']} rc={rc}; requeue (log tail: {open(j['log']).read()[-300:]!r})")
                    srv.ensure()
                    queue.insert(0, j)
                else:
                    finish(a, j, rc)
            while queue and len(running) < a.slots:
                j = queue.pop(0)
                launch(a, j)
                running.append(j)
                time.sleep(2)
            time.sleep(15)
        subprocess.run([PY, os.path.join(HERE, "idea2_report.py"), "--root", a.root], cwd=REPO)
        log("all jobs finished")
        open(os.path.join(a.root, "ALL_DONE"), "w").write(time.strftime("%F %T"))
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
