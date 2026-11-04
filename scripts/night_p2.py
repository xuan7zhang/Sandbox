#!/usr/bin/env python3
"""Unattended P2 queue for the night plan: A (configs/night_A.yaml) vs B (configs/night_B.yaml).

Jobs run in priority order through --slots concurrent run_matrix.py invocations (one condition x seed each):
  batch 1: A,B seed 0 best   batch 2: A,B seeds 1 2 best   batch 3: A,B seeds 0 1 2 random
A failed run is renamed <run>.failed<k> (never deleted; Loop resume re-runs gens 1..N, so no in-place resume)
and restarted, at most 3 attempts. Before every launch: /data2 free >= 20 GB, vLLM answers (restarted via tmux
otherwise). After every finished batch: posthoc_audit.py on its runs, report.py (per matrix + combined),
night_extract.py, and the table is appended to runs/MORNING_REPORT.md.
    nohup python scripts/night_p2.py --slots 12 > runs/logs/p2_driver.log 2>&1 &
"""
from __future__ import annotations

import argparse, glob, os, shutil, subprocess, sys, time, urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
RUNS = os.path.join(REPO, "runs")
LOG = os.path.join(RUNS, "logs")


def log(msg):
    print(time.strftime("[%m-%d %H:%M:%S] ") + msg, flush=True)


def vllm_ok():
    try:
        return b"Qwen" in urllib.request.urlopen("http://127.0.0.1:8000/v1/models", timeout=20).read()
    except Exception:  # noqa: BLE001
        return False


def ensure_vllm():
    if vllm_ok():
        return
    log("vLLM not answering; restarting tmux session 'vllm'")
    subprocess.run(["tmux", "kill-session", "-t", "vllm"], capture_output=True)
    time.sleep(10)
    subprocess.run(["tmux", "new", "-d", "-s", "vllm", os.path.join(LOG, "start_vllm.sh")])
    for _ in range(90):
        if vllm_ok():
            log("vLLM back")
            return
        time.sleep(10)
    log("vLLM did not come back within 15 min")


def free_gb():
    st = os.statvfs(os.path.realpath(RUNS))
    return st.f_bavail * st.f_frsize / 2**30


def run_dir(j):
    return os.path.join(RUNS, f"night_{j['sys']}_matrix", j["cond"], f"seed{j['seed']}")


def launch(j):
    cmd = [PY, os.path.join(REPO, "scripts", "run_matrix.py"), os.path.join(REPO, "configs", f"night_{j['sys']}.yaml"),
           "--seeds", str(j["seed"]), "--conditions", j["cond"], "--generations", "5", "--parallel", "1"]
    lp = os.path.join(LOG, f"p2_{j['sys']}_{j['cond']}_seed{j['seed']}.log")
    j["proc"] = subprocess.Popen(cmd, stdout=open(lp, "a"), stderr=subprocess.STDOUT, cwd=REPO,
                                 env=dict(os.environ, OPENAI_API_KEY="EMPTY"))
    j["t0"], j["log"] = time.time(), lp
    j["attempt"] = j.get("attempt", 0) + 1
    log(f"start {j['sys']}/{j['cond']}/seed{j['seed']} attempt {j['attempt']}")


def after_batch(b, jobs):
    for j in jobs:
        rd = run_dir(j)
        if j.get("ok") and not os.path.exists(rd + "_posthoc"):
            r = subprocess.run([PY, os.path.join(REPO, "scripts", "posthoc_audit.py"), rd], capture_output=True,
                               text=True, cwd=REPO)
            log(f"posthoc {rd} rc={r.returncode} {r.stdout.strip()[-200:]} {r.stderr.strip()[-300:]}")
    for S in ("A", "B"):
        ds = sorted(glob.glob(os.path.join(RUNS, f"night_{S}_matrix", "*", "seed?")))
        if ds:
            r = subprocess.run([PY, os.path.join(REPO, "scripts", "report.py"), *ds, "--out",
                                os.path.join(RUNS, f"night_{S}_matrix", "report")], capture_output=True, text=True,
                               cwd=REPO)
            log(f"report {S} rc={r.returncode} {r.stderr.strip()[-300:]}")
    ds = sorted(glob.glob(os.path.join(RUNS, "night_[AB]_matrix", "*", "seed?")))
    r = subprocess.run([PY, os.path.join(REPO, "scripts", "report.py"), *ds, "--out",
                        os.path.join(RUNS, "report_night", "combined")], capture_output=True, text=True, cwd=REPO)
    log(f"report combined rc={r.returncode} {r.stderr.strip()[-300:]}")
    r = subprocess.run([PY, os.path.join(REPO, "scripts", "night_extract.py"), "--root", RUNS, "--out",
                        os.path.join(RUNS, "report_night", "P2_TABLE.md")], capture_output=True, text=True, cwd=REPO)
    log(f"extract rc={r.returncode} {r.stderr.strip()[-300:]}")
    status = ", ".join(f"{j['sys']}/{j['cond']}/seed{j['seed']}:{'ok' if j.get('ok') else 'FAILED'}"
                       f"({(j.get('t1', time.time()) - j['t0']) / 60:.0f} min, {j.get('attempt', 0)} attempt)"
                       for j in jobs)
    with open(os.path.join(RUNS, "MORNING_REPORT.md"), "a") as f:
        f.write(f"\n### P2 批次 {b} 完成（自动追加 {time.strftime('%F %T')}）\n\n{status}\n\n"
                f"完整表：`runs/report_night/P2_TABLE.md`；report.py 输出：`runs/night_A_matrix/report/`、"
                f"`runs/night_B_matrix/report/`、`runs/report_night/combined/`（含 curves.png）。\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slots", type=int, default=12)
    ap.add_argument("--deadline-h", type=float, default=11.0, help="no new launch after this many hours")
    a = ap.parse_args()
    t_start = time.time()
    batches = [[(S, 0, "best") for S in "AB"], [(S, s, "best") for s in (1, 2) for S in "AB"],
               [(S, s, "random") for s in (0, 1, 2) for S in "AB"]]
    jobs = [{"sys": S, "seed": s, "cond": c, "batch": b + 1} for b, B in enumerate(batches) for S, s, c in B]
    queue, running, done_b = list(jobs), [], set()
    while queue or running:
        for j in list(running):
            rc = j["proc"].poll()
            if rc is None:
                continue
            running.remove(j)
            j["t1"] = time.time()
            rd = run_dir(j)
            if rc == 0:
                j["ok"] = True
                log(f"done {j['sys']}/{j['cond']}/seed{j['seed']} in {(j['t1'] - j['t0']) / 60:.0f} min")
            else:
                tail = open(j["log"]).read()[-3000:]
                log(f"FAILED {j['sys']}/{j['cond']}/seed{j['seed']} rc={rc} attempt {j['attempt']}; tail:\n{tail[-1500:]}")
                if os.path.exists(rd):
                    shutil.move(rd, f"{rd}.failed{j['attempt']}")
                if j["attempt"] < 3:
                    ensure_vllm()
                    queue.insert(0, j)
                else:
                    j["ok"] = False
                    open(os.path.join(LOG, f"p2_SKIPPED_{j['sys']}_{j['cond']}_seed{j['seed']}.tail50"), "w").write(
                        "\n".join(open(j["log"]).read().splitlines()[-50:]))
        for b in sorted({j["batch"] for j in jobs} - done_b):
            bj = [j for j in jobs if j["batch"] == b]
            if all("ok" in j for j in bj):
                done_b.add(b)
                log(f"batch {b} finished")
                after_batch(b, bj)
        while queue and len(running) < a.slots:
            if time.time() - t_start > a.deadline_h * 3600:
                log(f"deadline reached; not starting {len(queue)} queued job(s)")
                for j in queue:
                    j["ok"] = False
                    j.setdefault("t0", time.time())
                queue = []
                break
            if free_gb() < 20:
                log(f"disk free {free_gb():.0f} GB < 20 GB: not starting new runs")
                for j in queue:
                    j["ok"] = False
                    j.setdefault("t0", time.time())
                queue = []
                break
            ensure_vllm()
            j = queue.pop(0)
            launch(j)
            running.append(j)
            time.sleep(5)
        time.sleep(30)
    log("all P2 jobs finished")
    open(os.path.join(LOG, "P2_ALL_DONE"), "w").write(time.strftime("%F %T"))


if __name__ == "__main__":
    main()
