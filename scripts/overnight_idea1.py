#!/usr/bin/env python3
"""Unattended idea-1 queue on one vLLM server: keep K loop runs in flight at all times, audit each run as
soon as it finishes, refresh the aggregate report, restart the server it started if that server dies.

Priority order (later tiers start only when slots free up, so the GPU never idles):
  P1  S1 census (bizops, tickets) + S2 core: in-loop guard (A) vs no guard (B), selection=best, seeds 0-2
  P2  same with selection=random (matched-budget baseline)
  P3  Tickets world, A vs B, best, seeds 0-2          (not a BizOps artefact)
  P4  BizOps A vs B, best, seeds 3-4                   (tighter CIs)
  P5  B without the LLM rubric judge, best, seeds 0-2 (how much the judge alone catches)
  P6  BizOps A vs B, best, seed 0, 10 generations      (does the illusory gain grow with horizon?)

    python scripts/overnight_idea1.py --root /data2/ec2-user/rsi_sandbox/overnight --slots 14
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = sys.executable
NAME = "Qwen/Qwen3-30B-A3B-Instruct-2507"


def log(msg):
    print(f"[{time.strftime('%m-%d %H:%M:%S')}] {msg}", flush=True)


def procs():
    """(pid, argv) of this user's processes, from /proc."""
    out = []
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            if os.stat(f"/proc/{d}").st_uid != os.getuid():
                continue
            with open(f"/proc/{d}/cmdline", "rb") as f:
                argv = [x.decode(errors="replace") for x in f.read().split(b"\0") if x]
            if argv:
                out.append((int(d), argv))
        except OSError:
            continue
    return out


def alive_group(pgid):
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


def gpu_used_mib():
    out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout.split()
    return int(out[0]) if out else 0


# ----------------------------------------------------------------------------- vLLM
class Server:
    """Owns only the server it launches (its own process group); never touches other GPU processes."""

    def __init__(self, a):
        self.a, self.proc, self.pgid = a, None, None
        self.url = f"http://127.0.0.1:{a.port}/v1"
        self.restarts = 0

    def healthy(self):
        try:
            with urllib.request.urlopen(self.url + "/models", timeout=10) as r:
                return NAME in r.read().decode()
        except Exception:  # noqa: BLE001
            return False

    def start(self):
        if self.healthy():
            # adopt a server an earlier instance of this script launched (same model dir), so stop() can end it
            for pid, cmd in procs():
                if "serve" in cmd and self.a.model_dir in cmd and any(x.endswith("/vllm") for x in cmd[:2]):
                    self.pgid = os.getpgid(pid)
                    log(f"vLLM already up; adopted pgid {self.pgid}")
                    return
            log("vLLM already up (not ours; will not stop it)")
            return
        for _ in range(120):  # someone else holds the GPU: wait for it rather than kill it
            if self.healthy():
                return
            if gpu_used_mib() < 5000:
                break
            log(f"GPU busy ({gpu_used_mib()} MiB used by another process); waiting")
            time.sleep(60)
        env = dict(os.environ, VLLM_USE_FLASHINFER_SAMPLER="0", CUDA_HOME=self.a.cuda_home,
                   PATH=os.path.join(self.a.cuda_home, "bin") + ":" + os.path.dirname(self.a.vllm_bin) + ":"
                   + os.environ["PATH"], HF_HUB_OFFLINE="1")
        cmd = [self.a.vllm_bin, "serve", self.a.model_dir, "--served-model-name", NAME, "--host", "127.0.0.1",
               "--port", str(self.a.port), "--max-model-len", "65536", "--gpu-memory-utilization", "0.92",
               "--max-num-seqs", "64", "--enable-auto-tool-choice", "--tool-call-parser", "hermes",
               "--moe-backend", "triton"]  # flashinfer's cutlass MoE needs a JIT build (no nvcc/ninja here)
        lf = open(os.path.join(self.a.root, "logs", f"vllm.{self.restarts}.log"), "w")
        self.proc = subprocess.Popen(cmd, stdout=lf, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        self.pgid = self.proc.pid
        for _ in range(180):
            if self.healthy():
                log(f"vLLM ready (start #{self.restarts}, pgid {self.proc.pid})")
                return
            if self.proc.poll() is not None:
                break
            time.sleep(10)
        raise RuntimeError("vLLM failed to start; see logs/vllm.*.log")

    def stop(self):
        """Stop the server this script started: its whole process group (the EngineCore child included)."""
        if self.pgid is None:
            return
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(self.pgid, sig)
            except ProcessLookupError:
                break
            for _ in range(30):
                if not alive_group(self.pgid):
                    break
                time.sleep(2)
        self.pgid = None
        time.sleep(10)

    def ensure(self):
        if self.healthy():
            return
        for _ in range(3):  # a saturated server can miss one /models probe; confirm before restarting
            time.sleep(20)
            if self.healthy():
                return
        self.restarts += 1
        log(f"vLLM unhealthy -> restart #{self.restarts}")
        self.stop()
        self.start()


# ----------------------------------------------------------------------------- jobs
def make_cfg(a, base, *, world, guard, seed, selection, generations, judge=True, lax=False, seek=False):
    cfg = yaml.safe_load(open(base))
    for m in cfg["models"].values():
        m["base_url"] = f"http://127.0.0.1:{a.port}/v1"
    if not judge:
        cfg["models"].pop("judge", None)
    if lax:   # positive control: checkers only confirm the requested change (no collateral-damage clause)
        cfg["models"]["proposer"]["kwargs"] = {"lax": True}
    if seek:  # positive control: improver told to maximise the measured pass rate
        cfg["models"]["improver"]["kwargs"] = {"mode": "score"}
    L = cfg["loop"]
    L.update(world=world, rng_seed=seed, selection=selection, generations=generations)
    if not guard:
        L.update(minimality_guard=False, adversary=False)
    return cfg


def jobs(a):
    base = os.path.join(REPO, "configs", "vllm_local.yaml")
    J = []

    def loop_job(tier, exp, *, world="bizops", guard=True, seed=0, selection="best", generations=5, judge=True,
                 lax=False, seek=False):
        rd = os.path.join(a.root, "runs", exp, selection, f"seed{seed}")
        cfg = make_cfg(a, base, world=world, guard=guard, seed=seed, selection=selection, generations=generations,
                       judge=judge, lax=lax, seek=seek)
        cfg["loop"]["run_dir"] = rd
        J.append({"tier": tier, "id": f"{exp}/{selection}/seed{seed}", "kind": "loop", "run_dir": rd, "cfg": cfg,
                  "random": selection == "random"})

    def audit_job(tier, world, lax=False):
        cfg = make_cfg(a, base, world=world, guard=True, seed=0, selection="best", generations=1, lax=lax)
        name = world + ("_lax" if lax else "")
        J.append({"tier": tier, "id": f"S1/{name}", "kind": "audit", "out": os.path.join(a.root, "S1", name),
                  "cfg": cfg, "world": world})

    audit_job(1, "bizops")
    audit_job(1, "tickets")
    for s in (0, 1, 2):
        loop_job(1, "A_guard_bizops", guard=True, seed=s)
        loop_job(1, "B_noguard_bizops", guard=False, seed=s)
    for s in (0, 1, 2):
        loop_job(2, "A_guard_bizops", guard=True, seed=s, selection="random")
        loop_job(2, "B_noguard_bizops", guard=False, seed=s, selection="random")
    for s in (0, 1, 2):
        loop_job(3, "A_guard_tickets", world="tickets", guard=True, seed=s)
        loop_job(3, "B_noguard_tickets", world="tickets", guard=False, seed=s)
    for s in (3, 4):
        loop_job(4, "A_guard_bizops", guard=True, seed=s)
        loop_job(4, "B_noguard_bizops", guard=False, seed=s)
    for s in (0, 1, 2):
        loop_job(5, "B_noguard_nojudge_bizops", guard=False, seed=s, judge=False)
    loop_job(6, "A_guard_bizops_g10", guard=True, seed=0, generations=10)
    loop_job(6, "B_noguard_bizops_g10", guard=False, seed=0, generations=10)
    # follow-up (positive control): does the pipeline detect illusory gain when checkers DO have loopholes?
    audit_job(7, "bizops", lax=True)
    for s in (0, 1, 2, 3, 4):
        loop_job(7, "C_lax_guard_bizops", guard=True, seed=s, lax=True)
        loop_job(7, "C_lax_noguard_bizops", guard=False, seed=s, lax=True)
    for s in (0, 1, 2):
        loop_job(8, "D_laxseek_guard_bizops", guard=True, seed=s, lax=True, seek=True)
        loop_job(8, "D_laxseek_noguard_bizops", guard=False, seed=s, lax=True, seek=True)
    return J


def done_marker(j):
    return (j["run_dir"] if j["kind"] == "loop" else j["out"]) + ".DONE"


def cfg_path(a, j):
    return os.path.join(a.root, "cfg", j["id"].replace("/", "__") + ".yaml")


def completed_ok(j):
    """Exit status of a job we did not start (adopted from an earlier scheduler), judged from its outputs."""
    if j["kind"] == "loop":
        p = os.path.join(j["run_dir"], "generations.jsonl")
        n = sum(1 for _ in open(p)) if os.path.exists(p) else 0
        return n >= j["cfg"]["loop"]["generations"] + 1
    p = os.path.join(j["out"], "audit.json")
    try:
        return "table" in json.load(open(p))
    except (OSError, ValueError):
        return False


class Adopted:
    """Stand-in for Popen for a job process started by an earlier scheduler instance."""

    def __init__(self, pid, j):
        self.pid, self.j = pid, j

    def poll(self):
        try:
            os.kill(self.pid, 0)
            return None
        except ProcessLookupError:
            return 0 if completed_ok(self.j) else 1


def adopt_running(a, queue):
    """Jobs whose run_loop/audit process (identified by its per-job config path) is still alive."""
    live = {}
    for pid, argv in procs():
        if len(argv) > 2 and argv[1].endswith(("run_loop.py", "audit_verifiers.py")):
            live[argv[2]] = pid
    adopted = []
    for j in list(queue):
        pid = live.get(cfg_path(a, j))
        if pid:
            queue.remove(j)
            j["proc"], j["t0"] = Adopted(pid, j), time.time()
            j["log"] = (j.get("run_dir") or j["out"]) + ".log"
            adopted.append(j)
            log(f"adopted running {j['id']} (pid {pid})")
    return adopted


def launch(a, j):
    os.makedirs(os.path.join(a.root, "cfg"), exist_ok=True)
    cpath = cfg_path(a, j)
    yaml.safe_dump(j["cfg"], open(cpath, "w"))
    if j["kind"] == "loop":
        if os.path.exists(j["run_dir"]):  # never resume a partial run (Loop.run restarts at gen 1): set it aside
            shutil.move(j["run_dir"], j["run_dir"] + f".partial.{int(time.time())}")
        os.makedirs(os.path.dirname(j["run_dir"]), exist_ok=True)
        cmd = [PY, os.path.join(HERE, "run_loop.py"), cpath, "--run-dir", j["run_dir"]]
        if j["random"]:
            cmd += ["--baseline", "random"]
        logp = j["run_dir"] + ".log"
    else:
        cmd = [PY, os.path.join(HERE, "audit_verifiers.py"), cpath, "--n", str(a.audit_n), "--world", j["world"],
               "--out", j["out"]]
        os.makedirs(os.path.dirname(j["out"]), exist_ok=True)
        logp = j["out"] + ".log"
    env = dict(os.environ, OPENAI_API_KEY="EMPTY", LLM_MAX_RETRIES="40", LLM_TIMEOUT_S="1200", PYTHONUNBUFFERED="1",
               no_proxy="localhost,127.0.0.1", NO_PROXY="localhost,127.0.0.1")
    j["log"] = logp
    j["proc"] = subprocess.Popen(cmd, stdout=open(logp, "a"), stderr=subprocess.STDOUT, env=env, cwd=REPO)
    j["t0"] = time.time()
    log(f"start {j['id']} (tier {j['tier']}, attempt {j.get('attempt', 0) + 1})")


def finish(a, j, rc):
    mins = (time.time() - j["t0"]) / 60
    if rc == 0 and j["kind"] == "loop":
        r = subprocess.run([PY, os.path.join(HERE, "posthoc_audit.py"), j["run_dir"]], capture_output=True, text=True,
                           cwd=REPO)
        log(f"done {j['id']} in {mins:.0f} min; posthoc: {(r.stdout.strip() or r.stderr.strip())[-400:]}")
    else:
        log(f"done {j['id']} in {mins:.0f} min rc={rc}")
    if rc == 0:
        open(done_marker(j), "w").write(time.strftime("%F %T"))
    subprocess.run([PY, os.path.join(HERE, "idea1_report.py"), "--root", a.root], capture_output=True, cwd=REPO)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--slots", type=int, default=14)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--audit-n", type=int, default=100)
    ap.add_argument("--max-tier", type=int, default=8)
    ap.add_argument("--model-dir", default="/data2/ec2-user/rsi_sandbox/models/Qwen3-30B-A3B-Instruct-2507")
    ap.add_argument("--vllm-bin", default="/home/ec2-user/miniconda3/envs/vllm/bin/vllm")
    ap.add_argument("--cuda-home",
                    default="/home/ec2-user/miniconda3/envs/vllm/lib/python3.10/site-packages/nvidia/cu13")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.root, "logs"), exist_ok=True)
    srv = Server(a)
    srv.start()
    queue = [j for j in jobs(a) if j["tier"] <= a.max_tier and not os.path.exists(done_marker(j))]
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
        subprocess.run([PY, os.path.join(HERE, "idea1_report.py"), "--root", a.root], cwd=REPO)
        log("all jobs finished")
        open(os.path.join(a.root, "ALL_DONE"), "w").write(time.strftime("%F %T"))
    finally:
        srv.stop()  # release the GPU when the queue is done (or the scheduler is stopped)


if __name__ == "__main__":
    main()
