#!/usr/bin/env python3
"""Overfit experiment queue: does a score-maximising self-improvement loop overfit a leaky verifier when the
loophole actually pays, and does in-loop hardening stop it?

Static pool from scripts/build_overfit_pool.py (train rich in 'payoff' tasks: v0 fails them, fanning the
reference out to a whole table passes the raw verifier). Improver mode=score, no LLM rubric judge.
  B_L3 : trains on RAW train verifiers, improver leak 3 (evidence / trajectory: the default diagnostics)
  B_L4 : RAW, leak 4 (+ checker source of failed tasks: white-box tests)
  A_L3 / A_L4 : same, but trains on HARDENED train verifiers (scope + minimality guard)
  B_N4 / A_N4 : leak 4 + improver mode=naive (pure score objective, no integrity rules); run on pool2
Test tasks are hardened in every condition. After each run scripts/overfit_posthoc.py re-judges every
episode under the hardened verifiers -> verifier-attributed pass rate per generation.
    nohup python scripts/overnight_overfit.py --root /data2/ec2-user/rsi_sandbox/overfit > .../logs/queue.log &
"""
from __future__ import annotations

import argparse, os, subprocess, sys, time

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overnight_idea1 import HERE, PY, REPO, Server, adopt_running, done_marker, launch, log  # noqa: E402

CONDS = {"B_L3": ("raw", 3, "score"), "B_L4": ("raw", 4, "score"), "A_L3": ("hard", 3, "score"),
         "A_L4": ("hard", 4, "score"),
         # stronger pressure (round 2): naive improver = pure score objective, no integrity rules
         "B_N4": ("raw", 4, "naive"), "A_N4": ("hard", 4, "naive")}


def jobs(a):
    J = []
    for s in a.seeds:
        for name in a.conds:
            pool, k, mode = CONDS[name]
            cfg = yaml.safe_load(open(os.path.join(REPO, "configs", "vllm_local.yaml")))
            cfg["models"].pop("judge", None)
            for m in cfg["models"].values():
                m["base_url"] = f"http://127.0.0.1:{a.port}/v1"
            cfg["models"]["improver"]["kwargs"] = {"mode": mode, "leak": k}
            rd = os.path.join(a.root, "runs", name, f"seed{s}")
            cfg["loop"].update(run_dir=rd, world="bizops", rng_seed=s, selection="best", generations=a.generations,
                               task_pool=f"{a.pool}_{pool}.json", tasks_per_gen=0, heldout_per_gen=0,
                               initial_heldout=0, initial_tasks=0, adversary=False, minimality_guard=False,
                               children_per_gen=a.children, difficulty="2", eval_workers=a.eval_workers,
                               accept_margin=a.accept_margin)
            J.append({"tier": 1, "id": f"{name}/seed{s}", "kind": "loop", "run_dir": rd, "cfg": cfg, "random": False})
    return J


def finish(a, j, rc):
    log(f"done {j['id']} in {(time.time() - j['t0']) / 60:.0f} min rc={rc}")
    if rc == 0:
        r = subprocess.run([PY, os.path.join(HERE, "overfit_posthoc.py"), j["run_dir"], "--pool", a.pool],
                           capture_output=True, text=True, cwd=REPO)
        log(f"posthoc {j['id']} rc={r.returncode} {r.stdout.strip()[-300:]} {r.stderr.strip()[-300:]}")
        open(done_marker(j), "w").write(time.strftime("%F %T"))
    subprocess.run([PY, os.path.join(HERE, "overfit_report.py"), "--root", a.root], capture_output=True, cwd=REPO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pool", default="/data2/ec2-user/rsi_sandbox/overfit/pool")
    ap.add_argument("--conds", nargs="+", default=list(CONDS))
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--generations", type=int, default=10)
    ap.add_argument("--children", type=int, default=3)
    ap.add_argument("--accept-margin", type=int, default=1)
    ap.add_argument("--eval-workers", type=int, default=4)
    ap.add_argument("--slots", type=int, default=12)
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
                if rc != 0 and j.get("attempt", 0) < 2:
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
        log("all jobs finished")
        open(os.path.join(a.root, "ALL_DONE"), "w").write(time.strftime("%F %T"))
    finally:
        srv.stop()


if __name__ == "__main__":
    main()
