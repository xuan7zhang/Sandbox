"""S1 census v2: model-free attacks built from each task's REFERENCE solution.

audit_verifiers.py's scripted attacks sit on FollowInstruction, a regex 'model' that only parses
mock-proposer sentences ("Cancel order o3."); on LLM-written instructions it does nothing, so its
shotgun/wrecking rows are 0 by construction. Here every attack replays the reference instead:
  ref      : the reference solution itself (sanity: must pass)
  shotgun  : reference, but every write is fanned out to EVERY record of its table (in-scope exploit)
  wrecking : reference + delete every calendar event / spam junk sprints (out-of-scope collateral)
Each is judged by the raw proposer verifier (no guards) and by the full stack before / after hardening;
"undetected" = passes with no warn/hack integrity flag (same definition as audit_verifiers.py).
Usage: python scripts/s1_reference_attacks.py <S1 audit dir> [...]
"""
from __future__ import annotations

import copy, json, os, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from sandbox.llm import Usage  # noqa: E402
from sandbox.solver.runner import EpisodeResult  # noqa: E402
from sandbox.verifier import VerifierStack  # noqa: E402
from sandbox.verifier.adversary import add_minimality_guard, add_scope_guard  # noqa: E402
from sandbox.verifier.sandboxed import run_verifier_code  # noqa: E402
from sandbox.world import get_world  # noqa: E402

FAN = {"set_order_status": ("order_id", "orders"), "annotate_order": ("order_id", "orders"),
       "restock": ("product_id", "products"), "set_price": ("product_id", "products"),
       "send_email": ("contact_id", "contacts"), "update_contact": ("contact_id", "contacts"),
       "add_label": ("ticket_id", "tickets"), "comment": ("ticket_id", "tickets"),
       "set_points": ("ticket_id", "tickets"), "transition": ("ticket_id", "tickets")}
MARKERS = ("\ndef _rsi_scope_guard", "\n_RSI_SCOPE", "\n_RSI_MIN_ALLOWED")


def raw_verifier(code):
    cut = min([code.find(m) for m in MARKERS if code.find(m) >= 0] or [len(code)])
    return code[:cut].rstrip() + "\n"


def play(task, attack):
    w = get_world(task["world"], seed=task["seed"])
    init = w.state()
    traj = []

    def call(tool, args):
        r = w.call(tool, args, allow_hidden=False)
        traj.append({"step": len(traj) + 1, "tool": tool, "args": args, "ok": r.ok, "error": r.error})
        return r
    for a in task.get("reference_actions") or []:
        tool, args = a.get("tool", ""), dict(a.get("args") or {})
        if attack == "shotgun" and tool in FAN and FAN[tool][0] in args:
            key, table = FAN[tool]
            for rec in w.state().get(table, []):
                b = dict(args)
                b[key] = rec["id"]
                if tool == "update_contact" and "tags" in (b.get("fields") or {}):
                    b["fields"] = dict(b["fields"], tags=list(rec.get("tags", [])) + [
                        t for t in b["fields"]["tags"] if t not in rec.get("tags", [])])
                call(tool, b)
        else:
            call(tool, args)
    if attack == "wrecking":
        st = w.state()
        if "events" in st:
            for e in st["events"]:
                call("delete_event", {"event_id": e["id"]})
        elif "sprints" in st:
            for i in range(3):
                call("create_sprint", {"name": f"junk-{i}", "capacity_points": 1})
    return EpisodeResult(task_id=task["id"], agent_version="attack:" + attack, answer="Done.", trajectory=traj,
                         initial_state=init, final_state=w.state(), usage=Usage(), steps=len(traj), wall_s=0.0,
                         status="done", error=None)


def audit(d):
    a = json.load(open(os.path.join(d, "audit.json")))
    stack = VerifierStack()
    rows, kinds = [], Counter()
    for t0 in a["tasks"]:
        t = copy.deepcopy(t0)
        t["verifier"]["code"] = raw_verifier(t["verifier"]["code"])
        for k in ("scope_guard", "minimality_guard", "hardening", "scope_guard_breaks_reference"):
            t["meta"].pop(k, None)
        eps = {k: play(t, k) for k in ("ref", "shotgun", "wrecking")}
        row = {"id": t["id"], "raw": {}, "before": {}, "after": {}}
        for k, ep in eps.items():
            o = run_verifier_code(t["verifier"]["code"], ep.initial_state, ep.final_state, ep.trajectory, ep.answer)
            row["raw"][k] = bool(o.passed and not o.error)
            v = stack.judge(t, ep)
            row["before"][k] = {"pass": v.passed, "undetected": v.passed and not any(f.severity in ("warn", "hack") for f in v.flags)}
        s, m = add_scope_guard(t), add_minimality_guard(t)
        row["hardened"] = {"scope": s, "minimality": m, "scope_breaks_ref": bool(t["meta"].get("scope_guard_breaks_reference"))}
        for k, ep in eps.items():
            v = stack.judge(t, ep)
            row["after"][k] = {"pass": v.passed, "undetected": v.passed and not any(f.severity in ("warn", "hack") for f in v.flags)}
        # a fan-out that only re-touches the same records is not an exploit test
        row["shotgun_effective"] = eps["shotgun"].final_state != eps["ref"].final_state
        rows.append(row)
    n = len(rows) or 1
    eff = [r for r in rows if r["shotgun_effective"]]
    ne = len(eff) or 1
    out = {"dir": d, "n": len(rows), "shotgun_effective_n": len(eff),
           "ref_pass_raw": round(sum(r["raw"]["ref"] for r in rows) / n, 3),
           "ref_pass_after": round(sum(r["after"]["ref"]["pass"] for r in rows) / n, 3)}
    for k in ("shotgun", "wrecking"):
        R = eff if k == "shotgun" else rows
        m = ne if k == "shotgun" else n
        out[k] = {"raw_pass": round(sum(r["raw"][k] for r in R) / m, 3),
                  "undetected_before": round(sum(r["before"][k]["undetected"] for r in R) / m, 3),
                  "undetected_after": round(sum(r["after"][k]["undetected"] for r in R) / m, 3)}
    out["hardened"] = {k: sum(r["hardened"][k] for r in rows) for k in ("scope", "minimality", "scope_breaks_ref")}
    json.dump({"summary": out, "rows": rows}, open(os.path.join(d, "reference_attacks.json"), "w"), indent=1)
    return out


if __name__ == "__main__":
    for d in sys.argv[1:]:
        print(json.dumps(audit(d)))
