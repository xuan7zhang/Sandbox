"""First-class metrics for a self-improvement run.

annecs(g)              Accumulated Number of Novel Environments Created and Solved
                       (Enhanced POET's open-endedness measure, adapted): tasks that
                       (a) were NOT solved by the agent lineage at creation time and
                       (b) have since been solved by a non-hacking pass at gen <= g.
hacking_rate(g)        hacking-suspected passes / all passes in generation g (and /all episodes).
clade_metaproductivity HGM's CMP: mean non-hacking pass rate over an agent's clade
                       (itself + all descendants) - estimates how productive a lineage is
                       at producing good descendants, not just how good the node is.
generation_summary     everything a results table needs for one generation.
budget_so_far          cumulative LLM usage (for matched-budget comparisons).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..archive import Archive


def annecs(archive: Archive, upto_gen: Optional[int] = None) -> int:
    n = 0
    for r in archive.task_rows():
        if r["novel_at_creation"] and r["first_solved_gen"] is not None:
            if upto_gen is None or r["first_solved_gen"] <= upto_gen:
                n += 1
    return n


def hacking_rate(archive: Archive, gen: int, purpose: str = "eval") -> Dict[str, Optional[float]]:
    eps = archive.episodes(generation=gen, purpose=purpose)
    passes = [e for e in eps if e["passed"]]
    hacks = [e for e in passes if e["hacking"]]
    return {
        "episodes": len(eps),
        "passes": len(passes),
        "hacking_passes": len(hacks),
        "hacking_rate_of_passes": round(len(hacks) / len(passes), 3) if passes else None,
        "hacking_rate_of_episodes": round(len(hacks) / len(eps), 3) if eps else None,
    }


def clade_metaproductivity(archive: Archive, version: str) -> Optional[float]:
    rates = [archive.pass_rate(v) for v in archive.clade(version)]
    rates = [r for r in rates if r is not None]
    return sum(rates) / len(rates) if rates else None


def budget_so_far(archive: Archive, upto_gen: Optional[int] = None) -> Dict[str, int]:
    q = "SELECT SUM(input_tokens), SUM(output_tokens), SUM(llm_calls), COUNT(*) FROM episodes"
    args: tuple = ()
    if upto_gen is not None:
        q += " WHERE generation<=?"
        args = (upto_gen,)
    i, o, c, n = archive.db.execute(q, args).fetchone()
    return {"input_tokens": i or 0, "output_tokens": o or 0, "llm_calls": c or 0, "episodes": n or 0}


def generation_summary(archive: Archive, gen: int, champion: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    tasks = archive.task_rows()
    active = [t for t in tasks if t["status"] == "active"]
    gen_tasks = [t for t in tasks if t["generation"] == gen]
    eval_eps = archive.episodes(generation=gen, purpose="eval")
    by_diff: Dict[int, List[int]] = {}
    diff_of = {t["id"]: t["difficulty"] for t in tasks}
    for e in eval_eps:
        if e["agent_version"] == champion:
            by_diff.setdefault(diff_of.get(e["task_id"], 0), []).append(int(e["passed"] and not e["hacking"]))
    s = {
        "champion": champion,
        "champion_pass_rate": archive.pass_rate(champion),
        "champion_pass_rate_incl_hacks": archive.pass_rate(champion, exclude_hacks=False),
        "champion_cmp": clade_metaproductivity(archive, champion),
        "tasks_active": len(active),
        "tasks_created_this_gen": len(gen_tasks),
        "tasks_novel_this_gen": sum(1 for t in gen_tasks if t["novel_at_creation"]),
        "annecs": annecs(archive, gen),
        "hacking": hacking_rate(archive, gen),
        "pass_rate_by_difficulty": {str(d): round(sum(v) / len(v), 3) for d, v in sorted(by_diff.items())},
        "budget_cumulative": budget_so_far(archive, gen),
        "agents_total": len(archive.agents()),
    }
    if extra:
        s.update(extra)
    return s
