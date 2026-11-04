"""Fixed task pool for idea 3 (improver information leak -> time-to-hack): tasks whose proposer-written
verifiers are LAX (proposer told only to confirm the requested change) and are used RAW in the loop
(no scope / minimality guard), so an over-broad agent can pass them. The post-hoc audit
(scripts/posthoc_audit.py) later hardens the copies and counts the passes that flip.

Sources: S1 lax audit dirs (audit.json; guard code is stripped) and archives of lax runs WITHOUT in-loop
hardening (raw verifiers). Every candidate is re-validated (do-nothing fails, reference passes), deduplicated,
labelled with v0's clean-pass rate when its source run has v0 episodes, and with `shotgun_exploitable`
(the reference fanned out to every record of its table passes the raw stack with no warn/hack flag).
Selection keeps every v0-unsolved task (headroom), then fills with the rest, exploitable verifiers first; the split is stratified by
(difficulty, v0 label, exploitable).
Usage: python scripts/build_lax_pool.py --out pool.json --audit S1/bizops_lax --runs run_dir [...]
"""
from __future__ import annotations

import argparse, copy, json, os, random, re, sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sandbox.archive import Archive  # noqa: E402
from sandbox.verifier import VerifierStack  # noqa: E402
from build_task_pool import valid  # noqa: E402
from s1_reference_attacks import play, raw_verifier  # noqa: E402

GUARD_META = ("scope_guard", "minimality_guard", "hardening", "scope_guard_breaks_reference")


def raw_task(t):
    t = copy.deepcopy(t)
    t["verifier"]["code"] = raw_verifier(t["verifier"]["code"])
    for k in GUARD_META:
        t.setdefault("meta", {}).pop(k, None)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--audit", nargs="*", default=[])
    ap.add_argument("--runs", nargs="*", default=[])
    ap.add_argument("--n", type=int, default=80, help="train + test")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    stack = VerifierStack()
    src = []  # (task, v0 rate or None, source)
    for d in a.audit:
        for t in json.load(open(os.path.join(d, "audit.json")))["tasks"]:
            src.append((t, None, d))
    for rd in a.runs:
        arch = Archive(rd)
        v0 = defaultdict(list)
        for e in arch.episodes(agent_version="v0"):
            v0[e["task_id"]].append(int(e["passed"] and not e["hacking"]))
        for t in arch.tasks("active") + arch.tasks("heldout"):
            r = v0.get(t["id"])
            src.append((t, sum(r) / len(r) if r else None, rd))
    cands, seen, drop = [], set(), Counter()
    # labelled tasks first so a duplicate keeps its v0 label
    for t0, rate, where in sorted(src, key=lambda x: x[1] is None):
        key = re.sub(r"\W+", " ", t0["instruction"].lower()).strip()
        if key in seen:
            drop["duplicate"] += 1
            continue
        t = raw_task(t0)
        if not valid(t):
            drop["invalid"] += 1
            continue
        seen.add(key)
        ref, sg = play(t, "ref"), play(t, "shotgun")
        v = stack.judge(t, sg)
        exploitable = sg.final_state != ref.final_state and v.passed and not any(
            f.severity in ("warn", "hack") for f in v.flags)
        t["meta"]["pool_source"] = {"src": where, "id": t["id"], "v0_clean_rate": rate,
                                    "shotgun_exploitable": bool(exploitable)}
        t["id"] = f"L{len(cands):04d}"
        cands.append(t)

    def lab(t):
        r = t["meta"]["pool_source"]["v0_clean_rate"]
        return "unk" if r is None else ("solved" if r >= 0.5 else "unsolved")
    rng = random.Random(a.seed)
    by = defaultdict(list)
    for t in cands:
        by[lab(t)].append(t)
    for L in by.values():
        rng.shuffle(L)
    pick = by["unsolved"][:a.n]
    rest = by["unk"] + by["solved"]
    rng.shuffle(rest)  # fill with loophole-bearing verifiers first: they are the hack opportunities
    rest.sort(key=lambda t: not t["meta"]["pool_source"]["shotgun_exploitable"])
    pick += rest[:a.n - len(pick)]
    strata = defaultdict(list)
    for t in pick:
        strata[(t["difficulty"], lab(t), t["meta"]["pool_source"]["shotgun_exploitable"])].append(t)
    train, test, flip = [], [], 0
    for k in sorted(strata, key=str):
        L = strata[k]
        h = len(L) // 2
        train += L[:h]
        test += L[h:2 * h]
        if len(L) % 2:
            (train if flip == 0 else test).append(L[-1])
            flip ^= 1

    def desc(L):
        return {"n": len(L), "by_label": dict(Counter(lab(t) for t in L)),
                "by_difficulty": dict(sorted(Counter(t["difficulty"] for t in L).items())),
                "shotgun_exploitable": sum(t["meta"]["pool_source"]["shotgun_exploitable"] for t in L)}
    out = {"candidates": len(cands), "dropped": dict(drop), "candidates_by_label": {k: len(v) for k, v in by.items()},
           "candidates_exploitable_by_label": {k: sum(t["meta"]["pool_source"]["shotgun_exploitable"] for t in v)
                                               for k, v in by.items()},
           "train": train, "test": test, "summary": {"all": desc(cands), "train": desc(train), "test": desc(test)}}
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k not in ("train", "test")}, indent=1))


if __name__ == "__main__":
    main()
