"""Fixed task pool for idea 2 (static-benchmark protocol): every condition and seed trains and is
tested on the SAME tasks, so pass rates are comparable across runs.

Sources: post-hoc-audited archives (<run>_posthoc) of loop runs that had NO in-loop hardening, so every
verifier carries only the validated post-hoc scope + minimality guards. Each candidate is re-validated
(reference passes, do-nothing fails), deduplicated by instruction, and labelled with v0's clean-pass rate
in its source run. The split is stratified by (difficulty, v0 solved) so train and test have equal headroom.
Usage: python scripts/build_task_pool.py --out pool.json run_posthoc_dir [...]
"""
from __future__ import annotations

import argparse, json, os, random, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sandbox.archive import Archive  # noqa: E402
from sandbox.verifier.sandboxed import run_verifier_code  # noqa: E402
from sandbox.world import get_world  # noqa: E402


def valid(t):
    w = get_world(t["world"], seed=t["seed"])
    init = w.state()
    if run_verifier_code(t["verifier"]["code"], init, init, [], "").passed:
        return False
    traj = []
    for i, a in enumerate(t.get("reference_actions") or []):
        r = w.call(a.get("tool", ""), a.get("args") or {}, allow_hidden=True)
        traj.append({"step": i + 1, "tool": a.get("tool"), "args": a.get("args"), "ok": r.ok, "error": r.error})
        if not r.ok:
            return False
    return bool(traj) and run_verifier_code(t["verifier"]["code"], init, w.state(), traj, "reference").passed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runs", nargs="+")
    ap.add_argument("--out", required=True)
    ap.add_argument("--n-train", type=int, default=40)
    ap.add_argument("--n-test", type=int, default=40)
    ap.add_argument("--min-difficulty", type=int, default=2)
    ap.add_argument("--solved-frac", type=float, default=0.5, help="share of pool tasks v0 solved in its source run")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    cands, seen = [], set()
    for rd in a.runs:
        arch = Archive(rd)
        v0 = defaultdict(list)
        for e in arch.episodes(agent_version="v0"):
            v0[e["task_id"]].append(int(e["passed"] and not e["hacking"]))
        for t in arch.tasks("active") + arch.tasks("heldout"):
            key = re.sub(r"\W+", " ", t["instruction"].lower()).strip()
            if key in seen or t["id"] not in v0 or t["difficulty"] < a.min_difficulty:
                continue
            if not (t.get("meta", {}).get("minimality_guard") or t.get("meta", {}).get("scope_guard")):
                continue  # keep only tasks the audit could harden
            if not valid(t):
                continue
            seen.add(key)
            t = json.loads(json.dumps(t))
            t["meta"]["pool_source"] = {"run": rd, "id": t["id"], "v0_clean_rate": sum(v0[t["id"]]) / len(v0[t["id"]])}
            t["id"] = f"P{len(cands):04d}"
            cands.append(t)
    rng = random.Random(a.seed)
    solved = [t for t in cands if t["meta"]["pool_source"]["v0_clean_rate"] >= 0.5]
    unsolved = [t for t in cands if t["meta"]["pool_source"]["v0_clean_rate"] < 0.5]
    n = a.n_train + a.n_test
    k_u = min(len(unsolved), n - round(n * a.solved_frac))
    k_s = min(len(solved), round(k_u * a.solved_frac / (1 - a.solved_frac)))  # keep the solved share when unsolved run short
    pick = rng.sample(solved, k_s) + rng.sample(unsolved, k_u)
    strata = defaultdict(list)
    for t in pick:
        strata[(t["difficulty"], t["meta"]["pool_source"]["v0_clean_rate"] >= 0.5)].append(t)
    train, test = [], []
    flip = 0
    for k in sorted(strata):
        L = strata[k]
        rng.shuffle(L)
        h = len(L) // 2
        train += L[:h]
        test += L[h:2 * h]
        if len(L) % 2:  # odd stratum: the spare task alternates between the two sides
            (train if flip == 0 else test).append(L[-1])
            flip ^= 1
    def desc(L):
        d = defaultdict(int)
        for t in L:
            d[t["difficulty"]] += 1
        return {"n": len(L), "v0_solved": sum(t["meta"]["pool_source"]["v0_clean_rate"] >= 0.5 for t in L),
                "by_difficulty": dict(sorted(d.items()))}
    out = {"candidates": len(cands), "candidates_solved": len(solved), "candidates_unsolved": len(unsolved),
           "train": train, "test": test, "summary": {"train": desc(train), "test": desc(test)}}
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("train", "test")}))


if __name__ == "__main__":
    main()
