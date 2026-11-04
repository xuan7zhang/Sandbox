#!/usr/bin/env python3
"""Idea 1 — post-hoc verifier audit of a finished run (the real-model version of toy/toy.py's re-judge).

Copies <run_dir> to <run_dir>_posthoc (the original is never touched), hardens every active and held-out
task of the copy with the deterministic guards the in-loop condition uses (scope guard + minimality guard),
then re-judges every stored episode under the full rule-based stack. For each generation it reports the
champion's latest verdict per task, as the loop recorded it and after the audit:

  reported   : clean pass rate the loop reported (same episodes, stored verdicts)
  posthoc    : same episodes, hardened verifier + rule-based integrity checks; a stored hack flag
               (e.g. from the LLM rubric judge, which is not re-run) is kept
  illusory   : reported - posthoc  (share of reported progress that is a verifier loophole)

    python scripts/posthoc_audit.py runs/vllm_noguard_matrix/best/seed0
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sandbox.archive import Archive  # noqa: E402
from sandbox.metrics.rejudge import rejudge  # noqa: E402
from sandbox.verifier import VerifierStack  # noqa: E402
from sandbox.verifier.adversary import add_minimality_guard, add_scope_guard  # noqa: E402


def _rate(rows, key):
    return round(sum(int(r[key]) for r in rows) / len(rows), 3) if rows else None


def champion_curve(rows, gens, *, purpose_rows):
    """Per generation: champion's latest verdict per task (episodes up to that generation)."""
    out = []
    for s in gens:
        g, ch = int(s["gen"]), s.get("champion")
        latest = {}
        for r in sorted((r for r in purpose_rows if r["agent_version"] == ch and r["generation"] <= g),
                        key=lambda r: (r["generation"], r["episode"])):
            latest[r["task_id"]] = r
        L = list(latest.values())
        out.append({"gen": g, "champion": ch, "n": len(L), "reported": _rate(L, "old_clean"),
                    "posthoc": _rate(L, "posthoc_clean"),
                    "flipped": sum(int(r["old_clean"] and not r["posthoc_clean"]) for r in L)})
        if out[-1]["reported"] is not None and out[-1]["posthoc"] is not None:
            out[-1]["illusory"] = round(out[-1]["reported"] - out[-1]["posthoc"], 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", default=None, help="copy to audit (default <run_dir>_posthoc)")
    a = ap.parse_args()
    src = a.run_dir.rstrip("/")
    dst = a.out or src + "_posthoc"
    if not os.path.exists(os.path.join(src, "generations.jsonl")):
        sys.exit(f"{src}: no generations.jsonl")
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("report", "*-journal"))

    arch = Archive(dst)
    hardened = {"scope_guard": 0, "minimality_guard": 0, "tasks": 0, "unguardable": 0}
    for status in ("active", "heldout"):
        for t in arch.tasks(status):
            hardened["tasks"] += 1
            s, m = add_scope_guard(t), add_minimality_guard(t)
            hardened["scope_guard"] += int(s)
            hardened["minimality_guard"] += int(m)
            if not t.get("meta", {}).get("minimality_guard"):
                hardened["unguardable"] += 1  # no reference / reference fails to replay: guard cannot be derived
            if s or m:
                arch.update_task(t, reason="post-hoc audit: scope + minimality guard")

    gens = [json.loads(l) for l in open(os.path.join(src, "generations.jsonl"))]
    cfg = json.load(open(os.path.join(src, "config.json"))) if os.path.exists(os.path.join(src, "config.json")) else {}
    out = {"run_dir": src, "audit_dir": dst, "condition": cfg.get("condition"), "world": cfg.get("world"),
           "minimality_guard_in_loop": cfg.get("minimality_guard"), "adversary_in_loop": cfg.get("adversary"),
           "hardened_posthoc": hardened,
           "loop_reported": [{"gen": s["gen"], "champion": s.get("champion"),
                              "champion_pass_rate": s.get("champion_pass_rate"),
                              "champion_heldout_pass_rate": s.get("champion_heldout_pass_rate"),
                              "annecs": s.get("annecs"),
                              "hacking_rate_of_passes": (s.get("hacking") or {}).get("hacking_rate_of_passes"),
                              "accepted_child": s.get("accepted_child")} for s in gens]}
    for purpose in ("eval", "heldout"):
        rj = rejudge(arch, purpose=purpose, stack=VerifierStack())
        rows = rj["rows"]
        for r in rows:
            r["posthoc_clean"] = bool(r["new_pass"] and not r["new_hacking"] and not r["hacking"])
        key = "active" if purpose == "eval" else "heldout"
        out[key] = {"episodes": rj["episodes"], "flipped_total": sum(int(r["old_clean"] and not r["posthoc_clean"]) for r in rows),
                    "champion_curve": champion_curve(rows, gens, purpose_rows=rows)}
        if purpose == "eval":
            out["annecs_posthoc"] = rj["annecs"]
            # every archived agent (incl. rejected children): reported vs post-hoc clean rate
            by_agent = {}
            for r in rows:
                d = by_agent.setdefault(r["agent_version"], {"n": 0, "reported": 0, "posthoc": 0})
                d["n"] += 1
                d["reported"] += int(r["old_clean"])
                d["posthoc"] += int(r["posthoc_clean"])
            out["by_agent"] = by_agent
    with open(os.path.join(dst, "posthoc.json"), "w") as f:
        json.dump(out, f, indent=1)
    last = out["active"]["champion_curve"][-1]
    print(json.dumps({"run": src, "hardened": hardened, "final_gen": last,
                      "annecs_loop": gens[-1].get("annecs"), "annecs_posthoc": out["annecs_posthoc"]}))


if __name__ == "__main__":
    main()
