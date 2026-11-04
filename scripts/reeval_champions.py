"""Idea-2 follow-up: re-evaluate every run's final champion (and v0) on the pool's TEST tasks several times.

In the loop each champion is scored on the test set once, and a single re-run of the same agent flips 1-5
train tasks (parent_eval.retest_flips), so one-shot test numbers carry about +-0.03 of sampling noise per run.
Here each agent gets --reps fresh passes over the test set under the same stack as the loop (rule-based
integrity checks + LLM rubric judge), and the condition means are compared on these averaged rates.
    python scripts/reeval_champions.py --root /data2/ec2-user/rsi_sandbox/idea2 --pool .../pool.json
Writes <root>/report/REEVAL.md and reeval.json. Starts (or adopts) the vLLM server like the overnight queues.
"""
from __future__ import annotations

import argparse, glob, json, os, re, statistics as st, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
from sandbox.llm import get_llm  # noqa: E402
from sandbox.solver.runner import run_episode  # noqa: E402
from sandbox.tasks import public_view  # noqa: E402
from sandbox.verifier import VerifierStack  # noqa: E402
from sandbox.verifier.judge import RubricJudge  # noqa: E402
from sandbox.world import get_world  # noqa: E402
from overnight_idea1 import NAME, Server, log  # noqa: E402

CONDS = ["S_best", "S_cmp", "S_random", "S_best_nodiag"]


def ci(xs):
    from _tstat import ci95_half
    return f"{ci95_half(xs):.3f}" if len(xs) > 1 else "—"


def welch(x, y):
    from _tstat import welch_p
    return round(st.mean(x) - st.mean(y), 3), round(welch_p(x, y), 4)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--pool", required=True)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-server", action="store_true", help="use an already-running server; never start/stop one")
    ap.add_argument("--limit", type=int, default=0, help="smoke test: only the first N test tasks and agents")
    ap.add_argument("--model-dir", default="/data2/ec2-user/rsi_sandbox/models/Qwen3-30B-A3B-Instruct-2507")
    ap.add_argument("--vllm-bin", default="/home/ec2-user/miniconda3/envs/vllm/bin/vllm")
    ap.add_argument("--cuda-home",
                    default="/home/ec2-user/miniconda3/envs/vllm/lib/python3.10/site-packages/nvidia/cu13")
    a = ap.parse_args()
    os.makedirs(os.path.join(a.root, "logs"), exist_ok=True)
    os.makedirs(os.path.join(a.root, "report"), exist_ok=True)
    tasks = json.load(open(a.pool))["test"]
    url = f"http://127.0.0.1:{a.port}/v1"
    llm_cfg = {"provider": "openai", "model": NAME, "base_url": url}
    agents = []  # (label, condition, agent_dir)
    conds = [c for c in CONDS] + sorted(
        os.path.basename(d) for d in glob.glob(os.path.join(a.root, "runs", "*_m*")) if os.path.isdir(d))
    for c in conds:
        for rd in sorted(glob.glob(os.path.join(a.root, "runs", c, "seed?"))):
            if not os.path.exists(rd + ".DONE"):
                continue
            gens = [json.loads(l) for l in open(os.path.join(rd, "generations.jsonl"))]
            ch = gens[-1]["champion"]
            agents.append((f"{c}/{os.path.basename(rd)}:{ch}", c, os.path.join(rd, "agents", ch)))
    first = sorted(glob.glob(os.path.join(a.root, "runs", CONDS[0], "seed?")))[0]
    agents.append(("v0", "v0", os.path.join(first, "agents", "v0")))
    if a.limit:
        tasks, agents = tasks[:a.limit], agents[:a.limit] + [agents[-1]]
    srv = None if a.no_server else Server(a)
    if srv:
        srv.start()
    try:
        stack = VerifierStack()
        stack.add(RubricJudge(get_llm("openai", NAME, base_url=url)))

        def one(job):
            label, cond, adir, t, rep = job
            w = get_world(t["world"], seed=t["seed"])
            ep = run_episode(adir, w, public_view(t, w.describe()), agent_version=label, llm=None, llm_cfg=llm_cfg,
                             max_steps=t["max_steps"], timeout_s=900, isolate=True)
            v = stack.judge(t, ep)
            return label, t["id"], rep, int(v.passed and not v.hacking_suspected)
        # reuse earlier re-evaluations of the same (agent, task, rep) so adding runs only costs the new agents
        raw_p = os.path.join(a.root, "report", "reeval_raw.json")
        cache = {} if a.limit or not os.path.exists(raw_p) else {
            (l, tid, rep): ok for l, tid, rep, ok in json.load(open(raw_p))}
        jobs = [(l, c, d, t, r) for r in range(a.reps) for (l, c, d) in agents for t in tasks
                if (l, t["id"], r) not in cache]
        log(f"re-eval: {len(agents)} agents x {len(tasks)} test tasks x {a.reps} reps = {len(jobs)} episodes")
        t0 = time.time()
        with ThreadPoolExecutor(a.workers) as ex:
            res = [(l, tid, rep, ok) for (l, tid, rep), ok in cache.items()] + list(ex.map(one, jobs))
        log(f"re-eval episodes done in {(time.time() - t0) / 60:.0f} min")
    finally:
        if srv:
            srv.stop()
    json.dump(res, open(os.path.join(a.root, "report", "reeval_raw.json"), "w"))
    per = {}
    for label, tid, rep, ok in res:
        per.setdefault(label, {}).setdefault(rep, []).append(ok)
    rows = {}
    for label, cond, _ in agents:
        reps = [st.mean(v) for _, v in sorted(per[label].items())]
        rows[label] = {"condition": cond, "reps": [round(x, 3) for x in reps], "mean": round(st.mean(reps), 3)}
    by = {c: [r["mean"] for r in rows.values() if r["condition"] == c] for c in conds + ["v0"]}
    v0 = rows["v0"]["mean"]
    md = ["# Idea 2 — final champions re-evaluated on the test set", "",
          f"{len(tasks)} test tasks x {a.reps} reps per agent, same stack as the loop (rule-based + LLM judge). "
          f"v0 = {v0:.3f} (reps {rows['v0']['reps']}).", "",
          "| run : champion | reps | mean | − v0 |", "|---|---|---|---|"]
    for label, r in rows.items():
        md.append(f"| {label} | {r['reps']} | {r['mean']:.3f} | {r['mean'] - v0:+.3f} |")
    md += ["", "| condition | runs | mean test (95% CI) | − v0 |", "|---|---|---|---|"]
    if a.limit:
        print("\n".join(md))
        return
    for c in conds:
        if by.get(c):
            md.append(f"| {c} | {len(by[c])} | {st.mean(by[c]):.3f} ± {ci(by[c])} | {st.mean(by[c]) - v0:+.3f} |")
    md += ["", "Welch t-tests on per-run means (diag = best, cmp; diag-free = random, best_nodiag):", ""]
    tests = {}
    for sfx in sorted({(re.search(r"_m\d+$", c) or [""])[0] for c in conds}):
        g = {k: by.get(k + sfx, []) for k in CONDS}
        tag = f"[accept_margin {sfx[2:] or 1}] "
        pairs = {"best - best_nodiag": (g["S_best"], g["S_best_nodiag"]), "best - random": (g["S_best"], g["S_random"]),
                 "cmp - best": (g["S_cmp"], g["S_best"]),
                 "(best+cmp) - (random+nodiag)": (g["S_best"] + g["S_cmp"], g["S_random"] + g["S_best_nodiag"])}
        for k, (x, y) in pairs.items():
            if len(x) >= 2 and len(y) >= 2:
                tests[tag + k] = welch(x, y)
    for k, (d, p) in tests.items():
        md.append(f"- {k}: {d:+.3f} (p={p})")
    open(os.path.join(a.root, "report", "REEVAL.md"), "w").write("\n".join(md) + "\n")
    json.dump({"rows": rows, "by_condition": by, "tests": tests}, open(os.path.join(a.root, "report", "reeval.json"), "w"),
              indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    main()
