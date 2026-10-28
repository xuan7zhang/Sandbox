"""Re-judge stored episodes under the *current* verifier version of each task.

Why: when the adversary hardens a verifier at generation g, every pass recorded
under the older verifier might have been a pass only because the checker was
loose. Re-scoring all stored final states under the latest verifier gives

    verifier_attributed_progress(g) = pass_rate_old(g) - pass_rate_rejudged(g)

i.e. how much of the apparent progress at each generation evaporates once the
checker is fixed. Reported per generation and per agent version.

Episodes store `final_state`; the initial state is rebuilt from (world, seed).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..archive import Archive
from ..llm import Usage
from ..solver.runner import EpisodeResult
from ..verifier.sandboxed import run_verifier_code
from ..verifier.stack import VerifierStack
from ..world import get_world


def rejudge(archive: Archive, purpose: str = "eval", timeout_s: float = 10.0,
            stack: Optional[VerifierStack] = None) -> Dict[str, Any]:
    """Re-score every stored episode under each task's *current* verifier. With `stack`, the full
    verdict (hidden verifier + integrity checks) is recomputed, so `new_hacking` is also fresh;
    without it only the hidden verifier is re-run and the stored hacking flag is kept."""
    tasks = {t["id"]: t for t in archive.tasks("active") + archive.tasks("heldout")}
    init_cache: Dict[tuple, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    for e in archive.episodes(purpose=purpose):
        t = tasks.get(e["task_id"])
        if t is None:
            continue
        cur_v = int(t.get("meta", {}).get("verifier_version", 1))
        f = archive.episode_file(e["id"], e["generation"])
        fs = f.get("final_state")
        if fs is None:
            continue
        key = (t["world"], t["seed"])
        if key not in init_cache:
            init_cache[key] = get_world(t["world"], seed=t["seed"]).state()
        ej = f["episode"]
        new_hack = bool(e["hacking"])
        if stack is not None:
            ep = EpisodeResult(task_id=e["task_id"], agent_version=e["agent_version"], answer=ej.get("answer", "") or "",
                               trajectory=ej.get("trajectory", []), initial_state=init_cache[key], final_state=fs,
                               usage=Usage(), steps=int(ej.get("steps", 0)), wall_s=0.0,
                               status=ej.get("status", "done"), error=ej.get("error"))
            v = stack.judge(t, ep)
            new_pass, new_hack = bool(v.passed), bool(v.hacking_suspected)
        elif e["verifier_version"] == cur_v:
            new_pass = bool(e["passed"])
        else:
            o = run_verifier_code(t["verifier"]["code"], init_cache[key], fs, ej.get("trajectory", []),
                                  ej.get("answer", ""), timeout_s=timeout_s)
            new_pass = bool(o.passed and not o.error)
        rows.append({"episode": e["id"], "generation": e["generation"], "agent_version": e["agent_version"],
                     "task_id": e["task_id"], "old_verifier_version": e["verifier_version"],
                     "current_verifier_version": cur_v, "old_pass": bool(e["passed"]),
                     "hacking": bool(e["hacking"]), "new_pass": new_pass, "new_hacking": new_hack,
                     "old_clean": bool(e["passed"]) and not bool(e["hacking"]),
                     "new_clean": new_pass and not new_hack})

    def _agg(group_key: str) -> Dict[str, Dict[str, Any]]:
        out: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            g = out.setdefault(str(r[group_key]), {"n": 0, "old_pass": 0, "new_pass": 0, "flipped": 0,
                                                    "old_clean": 0, "new_clean": 0})
            g["n"] += 1
            g["old_pass"] += r["old_pass"]
            g["new_pass"] += r["new_pass"]
            g["old_clean"] += r["old_clean"]
            g["new_clean"] += r["new_clean"]
            g["flipped"] += int(r["old_clean"] and not r["new_clean"])
        for g in out.values():
            g["old_rate"] = round(g["old_clean"] / g["n"], 3)   # non-hacking pass rate, as the loop reports it
            g["new_rate"] = round(g["new_clean"] / g["n"], 3)   # same episodes under the current verifier + stack
            g["verifier_attributed"] = round(g["old_rate"] - g["new_rate"], 3)
        return dict(sorted(out.items(), key=lambda kv: (len(kv[0]), kv[0])))

    return {"episodes": len(rows), "rejudged": sum(1 for r in rows if r["old_verifier_version"] != r["current_verifier_version"]),
            "flipped_total": sum(1 for r in rows if r["old_clean"] and not r["new_clean"]),
            "annecs": annecs_rejudged(archive, rows),
            "by_generation": _agg("generation"), "by_agent": _agg("agent_version"), "rows": rows}


def annecs_rejudged(archive: Archive, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """ANNECS recomputed from re-judged episodes, at two granularities:
      archive  : a novel task counts once any archived agent (incl. rejected children) solves it cleanly
      champion : a novel task counts only if the agent that was champion at that generation solved it cleanly
    The loop's live `annecs()` is the archive-level definition."""
    novel = {r["id"] for r in archive.task_rows() if r["novel_at_creation"]}
    champ_at = {int(g["gen"]): (g.get("summary") or {}).get("champion") for g in archive.generations()}
    arch, champ = set(), set()
    for r in rows:
        if r["task_id"] not in novel or not r["new_clean"]:
            continue
        arch.add(r["task_id"])
        if champ_at.get(int(r["generation"])) == r["agent_version"]:
            champ.add(r["task_id"])
    return {"archive": len(arch), "champion": len(champ) if champ_at else None}
