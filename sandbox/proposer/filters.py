"""Task filters: a candidate task must survive all of these before entering
the archive. Each gate corresponds to a documented failure mode in the
literature (trivial tasks, unsolvable tasks, duplicate tasks, unsafe or buggy
verifiers). Results are written into task["meta"]["filter"] so acceptance
rates can be reported per generation.

  safety        : verifier passes static screen (imports/names)
  nontrivial    : verifier FAILS on (initial, initial, [], "")   — the do-nothing agent
  solvable      : replaying reference_actions on a fresh world makes the verifier PASS
  dedup         : fingerprint + token-Jaccard against existing tasks
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..tasks import task_fingerprint
from ..verifier.sandboxed import check_verifier_code_safety, run_verifier_code
from ..world import get_world


@dataclass
class FilterReport:
    accepted: List[Dict[str, Any]] = field(default_factory=list)
    rejected: List[Tuple[Dict[str, Any], str]] = field(default_factory=list)

    def summary(self) -> Dict[str, Any]:
        reasons: Dict[str, int] = {}
        for _, r in self.rejected:
            reasons[r.split(":")[0]] = reasons.get(r.split(":")[0], 0) + 1
        n = len(self.accepted) + len(self.rejected)
        return {"candidates": n, "accepted": len(self.accepted), "rejected_by": reasons,
                "acceptance_rate": round(len(self.accepted) / n, 3) if n else None}


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


class TaskFilter:
    def __init__(self, jaccard_threshold: float = 0.85, require_reference: bool = True):
        self.jaccard_threshold = jaccard_threshold
        self.require_reference = require_reference

    def run(self, candidates: List[Dict[str, Any]], existing: List[Dict[str, Any]]) -> FilterReport:
        rep = FilterReport()
        seen_fp = {task_fingerprint(t) for t in existing}
        seen_tok = [_tokens(t["instruction"]) for t in existing]
        for t in candidates:
            why = self._check(t, seen_fp, seen_tok)
            t.setdefault("meta", {})["filter"] = why or "ok"
            if why:
                rep.rejected.append((t, why))
            else:
                rep.accepted.append(t)
                seen_fp.add(task_fingerprint(t))
                seen_tok.append(_tokens(t["instruction"]))
        return rep

    def _check(self, t: Dict[str, Any], seen_fp: set, seen_tok: List[set]) -> Optional[str]:
        code = t["verifier"]["code"]
        ok, why = check_verifier_code_safety(code)
        if not ok:
            return f"safety: {why}"
        if not t["instruction"].strip():
            return "empty: no instruction"
        # dedup
        fp = task_fingerprint(t)
        if fp in seen_fp:
            return "dedup: identical fingerprint"
        tk = _tokens(t["instruction"])
        for s in seen_tok:
            if tk and s and len(tk & s) / len(tk | s) >= self.jaccard_threshold:
                return "dedup: near-duplicate instruction"
        # nontrivial
        world = get_world(t["world"], seed=t["seed"])
        init = world.state()
        o = run_verifier_code(code, init, init, [], "")
        if o.error:
            return f"verifier_error: {o.error}"
        if o.passed:
            return "trivial: verifier passes on untouched state"
        # solvable (replay reference)
        ref = t.get("reference_actions") or []
        if not ref:
            if self.require_reference:
                return "unsolvable: no reference_actions"
            t["meta"]["solvable"] = "unverified"
            return None
        traj = []
        for i, a in enumerate(ref):
            r = world.call(a.get("tool", ""), a.get("args") or {}, allow_hidden=True)
            traj.append({"step": i + 1, "tool": a.get("tool"), "args": a.get("args"), "ok": r.ok, "error": r.error})
            if not r.ok:
                return f"unsolvable: reference step {i+1} ({a.get('tool')}) failed: {r.error}"
        o2 = run_verifier_code(code, init, world.state(), traj, "reference")
        if o2.error:
            return f"verifier_error: on reference run: {o2.error}"
        if not o2.passed:
            return "unsolvable: reference solution does not pass verifier"
        t["meta"]["solvable"] = "reference"
        t["meta"]["reference_steps"] = len(ref)
        return None
