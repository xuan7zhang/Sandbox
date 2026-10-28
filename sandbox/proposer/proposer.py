"""Task proposers.

A proposer sees the *full* world (including hidden tools) and the archive's
summary of existing tasks, and emits candidate tasks with hidden verifiers and
a reference solution. Candidates then go through `filters.TaskFilter`.

LLMProposer  : prompts a model for N tasks at a target difficulty, with
               diversity pressure from a summary of existing tasks and the
               current agent's per-tag solve rate (so it proposes at the
               frontier, OMNI-style "interesting = learnable but not solved").
MockProposer : grammar-based generator for offline tests. Produces the same
               task format with hand-written verifiers.
"""
from __future__ import annotations

import json
import random
import re
import textwrap
from typing import Any, Dict, List, Optional, Protocol

from ..llm import LLM
from ..tasks import new_task
from ..world.base import World


class Proposer(Protocol):
    name: str

    def propose(self, world: World, n: int, *, generation: int, existing: List[Dict[str, Any]],
                frontier: Optional[Dict[str, float]] = None, difficulty: int = 2) -> List[Dict[str, Any]]: ...


# --------------------------------------------------------------------------- LLM proposer
PROPOSER_SYSTEM = """You design tasks for an AI agent that operates a company's software through tools.
You will write (1) a natural-language instruction, (2) a hidden Python checker, (3) a reference
solution as a list of tool calls. Rules for the checker:
- signature exactly: def verify(initial, final, trajectory, answer) -> dict(passed: bool, score: float, evidence: str)
- `initial` / `final` are the full world state dicts before and after; `trajectory` is the list of
  tool calls made ({"tool","args","ok","error"}); `answer` is the agent's final report string.
- Check the FINAL STATE, not the trajectory, wherever possible (the agent may reach the goal in any order).
- The checker must FAIL on the initial state (a do-nothing agent must not pass).
- Penalise collateral damage: records outside the task's scope must be unchanged.
- Only use: json, math, re, collections, itertools. No file/network access.
- Never reference keys starting with "_" (hidden state).
Tasks must be fully specified by the instruction (ids, quantities, exact strings) so success is unambiguous,
and should require several dependent steps (inspect, reason, then change) at the requested difficulty."""


def _proposer_user_prompt(world: World, n: int, difficulty: int, existing: List[Dict[str, Any]],
                          frontier: Optional[Dict[str, float]]) -> str:
    state = world.public_state()
    tools = world.tool_schemas(include_hidden=False)
    recent = [t["instruction"] for t in existing[-40:]]
    frontier_txt = json.dumps(frontier or {}, indent=0)
    return textwrap.dedent(f"""
    WORLD: {world.describe()}

    TOOLS (JSON schemas):
    {json.dumps(tools, ensure_ascii=False)}

    CURRENT PUBLIC STATE (seed {world.seed}):
    {json.dumps(state, ensure_ascii=False)[:12000]}

    EXISTING TASKS (avoid duplicates; vary the tables, the kind of reasoning and the length):
    {json.dumps(recent, ensure_ascii=False)}

    AGENT SOLVE RATE BY TAG (propose where it is between 0.2 and 0.8; avoid tags near 1.0):
    {frontier_txt}

    Produce {n} tasks at difficulty {difficulty} (1 = one obvious action, 5 = 15+ dependent actions with
    constraints to reconcile). Difficulty-{difficulty} tasks here should need roughly {3 * difficulty} tool calls.

    Output ONLY a JSON list; each element:
    {{"instruction": str, "difficulty": int, "scope_tables": [str], "tags": [str],
      "reference_actions": [{{"tool": str, "args": {{}}}}], "verifier_code": str}}
    """).strip()


def _extract_json_list(text: str) -> List[Dict[str, Any]]:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if m:
        text = m.group(1)
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("no JSON list in proposer output")
    return json.loads(text[start:end + 1])


class LLMProposer:
    def __init__(self, llm: LLM, max_steps_per_difficulty: int = 12):
        self.llm = llm
        self.name = f"llm:{llm.model}"
        self.max_steps_per_difficulty = max_steps_per_difficulty

    def propose(self, world, n, *, generation, existing, frontier=None, difficulty=2):
        prompt = _proposer_user_prompt(world, n, difficulty, existing, frontier)
        text = self.llm.text(prompt, system=PROPOSER_SYSTEM, max_tokens=8000, temperature=0.7)
        try:
            items = _extract_json_list(text)
        except (ValueError, json.JSONDecodeError):
            return []
        tasks = []
        for i, it in enumerate(items):
            if not isinstance(it, dict) or "instruction" not in it or "verifier_code" not in it:
                continue
            d = int(it.get("difficulty", difficulty) or difficulty)
            tasks.append(new_task(
                world.name, world.seed, it["instruction"], it["verifier_code"], generation=generation,
                proposer=self.name, scope_tables=it.get("scope_tables", []),
                max_steps=max(10, min(120, self.max_steps_per_difficulty * d)), difficulty=max(1, min(5, d)),
                reference_actions=it.get("reference_actions", []), tags=it.get("tags", []),
                ordinal=len(existing) + i))
        return tasks


# --------------------------------------------------------------------------- mock proposer
_ID_RE = re.compile(r"\b[a-zA-Z]{1,2}\d+\b")


def _record_key(text: str) -> str:
    m = _ID_RE.search(text)
    return m.group(0) if m else text


class MockProposer:
    """Grammar-based tasks over BizOps, composable to arbitrary length.

    Each atom is (sentence, scope_table, reference_action, verifier_clause).
    Difficulty d => d atoms chained into one instruction with one verifier.
    """

    name = "mock"

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def _atoms(self, world: World) -> List[Dict[str, Any]]:
        if world.name == "tickets":
            return self._atoms_tickets(world)
        return self._atoms_bizops(world)

    def _atoms_tickets(self, world: World) -> List[Dict[str, Any]]:
        s = world.state()
        atoms: List[Dict[str, Any]] = []
        for t in s["tickets"]:
            lab = self.rng.choice(["urgent", "docs", "tech-debt"])
            if lab not in t["labels"]:
                atoms.append({
                    "text": f"Add label {lab} to ticket {t['id']}.", "table": "tickets", "tag": "labels",
                    "ref": {"tool": "add_label", "args": {"ticket_id": t["id"], "label": lab}},
                    "clause": f"{lab!r} in _row(final, 'tickets', {t['id']!r})['labels']",
                })
            atoms.append({
                "text": f"Comment 'reviewed' on ticket {t['id']}.", "table": "tickets", "tag": "comments",
                "ref": {"tool": "comment", "args": {"ticket_id": t["id"], "text": "reviewed"}},
                "clause": f"any(c['text'] == 'reviewed' for c in _row(final, 'tickets', {t['id']!r})['comments'])",
            })
            if t["status"] == "backlog" and t["assignee"] is None and t["sprint"] is None:
                k = self.rng.choice([1, 2, 3, 5])
                atoms.append({
                    "text": f"Set points of {t['id']} to {k}.", "table": "tickets", "tag": "estimation",
                    "ref": {"tool": "set_points", "args": {"ticket_id": t["id"], "points": k}},
                    "clause": f"_row(final, 'tickets', {t['id']!r})['points'] == {k}",
                })
            if t["status"] == "todo":
                atoms.append({
                    "text": f"Move ticket {t['id']} to backlog.", "table": "tickets", "tag": "workflow",
                    "ref": {"tool": "transition", "args": {"ticket_id": t["id"], "status": "backlog"}},
                    "clause": f"_row(final, 'tickets', {t['id']!r})['status'] == 'backlog'",
                })
        for i in range(3):
            name, cap = f"Sprint Q{i+3}", self.rng.choice([10, 15, 20])
            atoms.append({
                "text": f"Create sprint '{name}' with capacity {cap}.", "table": "sprints", "tag": "sprints",
                "ref": {"tool": "create_sprint", "args": {"name": name, "capacity_points": cap}},
                "clause": f"any(x['name'] == {name!r} and x['capacity_points'] == {cap} for x in final['sprints'])",
            })
        return atoms

    def _atoms_bizops(self, world: World) -> List[Dict[str, Any]]:
        s = world.state()
        atoms: List[Dict[str, Any]] = []
        for o in s["orders"]:
            if o["status"] in ("draft", "confirmed"):
                atoms.append({
                    "text": f"Cancel order {o['id']}.", "table": "orders", "tag": "orders",
                    "ref": {"tool": "set_order_status", "args": {"order_id": o["id"], "status": "cancelled"}},
                    "clause": f"_order(final, {o['id']!r})['status'] == 'cancelled'",
                })
            if o["status"] == "draft":
                atoms.append({
                    "text": f"Confirm order {o['id']}.", "table": "orders", "tag": "orders",
                    "ref": {"tool": "set_order_status", "args": {"order_id": o["id"], "status": "confirmed"}},
                    "clause": f"_order(final, {o['id']!r})['status'] == 'confirmed'",
                })
            atoms.append({
                "text": f"Annotate order {o['id']} with 'reviewed'.", "table": "orders", "tag": "orders",
                "ref": {"tool": "annotate_order", "args": {"order_id": o["id"], "note": "reviewed"}},
                "clause": f"_order(final, {o['id']!r})['note'] == 'reviewed'",
            })
        for p in s["products"]:
            q = self.rng.randint(2, 9)
            atoms.append({
                "text": f"Restock {p['id']} by {q}.", "table": "products", "tag": "inventory",
                "ref": {"tool": "restock", "args": {"product_id": p["id"], "qty": q}},
                "clause": f"_prod(final, {p['id']!r})['stock'] == _prod(initial, {p['id']!r})['stock'] + {q}",
            })
            pr = round(self.rng.uniform(1, 60), 2)
            atoms.append({
                "text": f"Set price of {p['id']} to {pr}.", "table": "products", "tag": "pricing",
                "ref": {"tool": "set_price", "args": {"product_id": p["id"], "price": pr}},
                "clause": f"abs(_prod(final, {p['id']!r})['price'] - {pr}) < 1e-6",
            })
        for c in s["contacts"]:
            tag = self.rng.choice(["vip", "partner", "lead"])
            if tag not in c["tags"]:
                atoms.append({
                    "text": f"Tag contact {c['id']} as {tag}.", "table": "contacts", "tag": "contacts",
                    "ref": None,  # multi-step: get then update; reference built below
                    "ref_multi": [{"tool": "get_contact", "args": {"contact_id": c["id"]}},
                                  {"tool": "update_contact", "args": {"contact_id": c["id"],
                                                                      "fields": {"tags": c["tags"] + [tag]}}}],
                    "clause": f"{tag!r} in _contact(final, {c['id']!r})['tags']",
                })
            atoms.append({
                "text": f"Email contact {c['id']} with subject 'Follow-up'.", "table": "outbox", "tag": "email",
                "ref": {"tool": "send_email", "args": {"contact_id": c["id"], "subject": "Follow-up", "body": "Hello."}},
                "clause": f"any(m['contact_id'] == {c['id']!r} and m['subject'] == 'Follow-up' for m in final['outbox'])",
            })
        return atoms

    def propose(self, world, n, *, generation, existing, frontier=None, difficulty=2):
        atoms = self._atoms(world)
        tasks = []
        for i in range(n):
            d = max(1, min(5, difficulty + self.rng.choice([-1, 0, 0, 1])))
            chosen, used_tables, used_text = [], [], set()
            for a in self.rng.sample(atoms, k=len(atoms)):
                if a["text"] in used_text:
                    continue
                # avoid two atoms acting on the same record (keeps verifier clauses consistent)
                key = _record_key(a["text"])
                if any(key == _record_key(c["text"]) for c in chosen):
                    continue
                chosen.append(a)
                used_text.add(a["text"])
                if len(chosen) == d:
                    break
            instruction = " ".join(a["text"] for a in chosen)
            clauses = " and ".join(f"({a['clause']})" for a in chosen)
            tables = sorted({a["table"] for a in chosen})
            ref: List[Dict[str, Any]] = []
            for a in chosen:
                ref.extend(a.get("ref_multi") or [a["ref"]])
            code = textwrap.dedent(f"""
                def _row(s, table, i):
                    return next(r for r in s[table] if r['id'] == i)
                def _order(s, i):
                    return _row(s, 'orders', i)
                def _prod(s, i):
                    return _row(s, 'products', i)
                def _contact(s, i):
                    return _row(s, 'contacts', i)
                def verify(initial, final, trajectory, answer):
                    try:
                        ok = {clauses}
                    except StopIteration:
                        return {{"passed": False, "score": 0.0, "evidence": "record missing"}}
                    return {{"passed": bool(ok), "score": 1.0 if ok else 0.0, "evidence": "final-state check"}}
            """).strip()
            tasks.append(new_task(world.name, world.seed, instruction, code, generation=generation, proposer=self.name,
                                  scope_tables=tables, max_steps=10 + 6 * d, difficulty=d, reference_actions=ref,
                                  tags=sorted({a["tag"] for a in chosen}), ordinal=len(existing) + i))
        return tasks
