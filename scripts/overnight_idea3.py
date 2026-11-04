#!/usr/bin/env python3
"""Unattended idea-3 queue: does the improver's information level (leak) speed up verifier hacking?

Every run trains on the same fixed pool of LAX tasks (scripts/build_lax_pool.py) whose raw proposer
verifiers are used in the loop with no scope / minimality guard and no LLM rubric judge, so an over-broad
agent can pass them; only the rule-based integrity stack runs in the loop. The improver is told to
maximise the measured pass rate (mode=score) and sees diagnostics at one of four leak levels:
  L0  none                 (diagnostics-free improver)
  L1  pass / fail          (which tasks failed, solver-side status and steps)
  L2  + integrity flags    (flag names, hacking-suspected list)
  L3  + checker evidence   (evidence strings, errors, trajectory, final answer: the default improver)
After each run, scripts/posthoc_audit.py hardens a copy of the pool and re-judges every episode; a pass that
flips is a verifier exploit. scripts/idea3_report.py: time-to-hack and exploit rates per leak level.

    python scripts/overnight_idea3.py --root /data2/ec2-user/rsi_sandbox/idea3 --pool /data2/.../idea3/pool.json
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overnight_idea1 import HERE, PY, REPO, Server, adopt_running, done_marker, launch, log  # noqa: E402

LEAKS = {"L0": 0, "L1": 1, "L2": 2, "L3": 3}


def jobs(a):
    J = []
    for s in a.seeds:
        for name, k in LEAKS.items():
            cfg = yaml.safe_load(open(os.path.join(REPO, "configs", "vllm_local.yaml")))
            cfg["models"].pop("judge", None)
            for m in cfg["models"].values():
                m["base_url"] = f"http://127.0.0.1:{a.port}/v1"
            cfg["models"]["improver"]["kwargs"] = {"mode": "score", "leak": k}
            rd = os.path.join(a.root, "runs", name, f"seed{s}")
            cfg["loop"].update(run_dir=rd, world="bizops", rng_seed=s, selection="best", generations=a.generations,
                               task_pool=a.pool, tasks_per_gen=0, heldout_per_gen=0, initial_heldout=0,
                               initial_tasks=0, adversary=False, minimality_guard=False,
                               children_per_gen=a.children, difficulty="2", eval_workers=a.eval_workers)
            J.append({"tier": 1, "id": f"{name}/seed{s}", "kind": "loop", "run_dir": rd, "cfg": cfg, "random": False})
    return J


def report(a):
    subprocess.run([PY, os.path.join(HERE, "idea3_report.py"), "--root", a.root], capture_output=True, cwd=REPO)


def finish(a, j, rc):
    log(f"done {j['id']} in {(time.time() - j['t0']) / 60:.0f} min rc={rc}")
    if rc == 0:
        r = subprocess.run([PY, os.path.join(HERE, "posthoc_audit.py"), j["run_dir"]], capture_output=True,
                           text=True, cwd=REPO)
        log(f"posthoc {j['id']} rc={r.returncode} {r.stdout.strip()[-300:]} {r.stderr.strip()[-300:]}")
        open(done_marker(j), "w").write(time.strftime("%F %T"))
    report(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3, 4])
    ap.add_argument("--generations", type=int, default=8)
    ap.add_argument("--children", type=int, default=2)
    ap.add_argument("--eval-workers", type=int, default=3)
    ap.add_argument("--slots", type=int, default=20)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--model-dir", default="/data2/ec2-user/rsi_sandbox/models/Qwen3-30B-A3B-Instruct-2507")
    ap.add_argument("--vllm-bin", default="/home/ec2-user/miniconda3/envs/vllm/bin/vllm")
    ap.add_argument("--cuda-home",
                    default="/home/ec2-user/miniconda3/envs/vllm/lib/python3.10/site-packages/nvidia/cu13")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.root, "logs"), exist_ok=True)
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
        report(a)
        log("all jobs finished")
        open(os.path.join(a.root, "ALL_DONE"), "w").write(time.strftime("%F %T"))
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
