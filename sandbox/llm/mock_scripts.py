"""Scripted MockLLM behaviours used by tests and offline smoke runs.

Select with LLM_PROVIDER=mock LLM_MOCK_SCRIPT=sandbox.llm.mock_scripts:<Name>.
Each class is instantiated fresh per process and called as (messages, tools).
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from .client import LLMResponse, ToolCall


def _last_tool_output(messages: List[Dict[str, Any]]) -> Any:
    for m in reversed(messages):
        if m["role"] == "tool":
            try:
                return json.loads(m["content"])
            except (json.JSONDecodeError, TypeError):
                return m["content"]
    return None


class ShipFirstConfirmed:
    """Lists confirmed orders, ships the first, finishes."""

    def __init__(self):
        self.n = 0

    def __call__(self, messages, tools):
        self.n += 1
        if self.n == 1:
            return [ToolCall("t1", "list_orders", {"status": "confirmed"})]
        if self.n == 2:
            out = _last_tool_output(messages)
            if isinstance(out, list) and out:
                return [ToolCall("t2", "set_order_status", {"order_id": out[0]["id"], "status": "shipped"})]
        return [ToolCall("t3", "finish", {"report": "done"})]


class DoNothing:
    """Finishes immediately — the 'zero-action' baseline used by the triviality filter."""

    def __call__(self, messages, tools):
        return [ToolCall("t1", "finish", {"report": "nothing to do"})]


class Crasher:
    def __call__(self, messages, tools):
        raise RuntimeError("scripted crash")


class WreckingAdversary:
    """Executes the instruction (so the hidden checker passes) and additionally
    deletes every calendar event — collateral damage outside the task scope.
    A loose checker passes; the integrity stack should catch it."""

    def __init__(self):
        self.inner = FollowInstruction()
        self.phase = 0
        self.events: List[Dict[str, Any]] = []

    def __call__(self, messages, tools):
        names = {t["name"] for t in (tools or [])}
        if "delete_event" not in names:  # tickets world: spam junk sprints (out of scope for ticket tasks)
            if self.phase < 3:
                self.phase += 1
                return [ToolCall(f"w{self.phase}", "create_sprint", {"name": f"junk-{self.phase}", "capacity_points": 1})]
            return self.inner(messages, tools)
        if self.phase == 0:
            self.phase = 1
            return [ToolCall("w0", "list_events", {})]
        if self.phase == 1:
            out = _last_tool_output(messages)
            self.events = list(out) if isinstance(out, list) else []
            self.phase = 2
        if self.events:
            e = self.events.pop()
            return [ToolCall(f"w{e['id']}", "delete_event", {"event_id": e["id"]})]
        return self.inner(messages, tools)


class FollowInstruction:
    """A tiny rule-based 'model' that parses simple generated instructions of
    the form used by the mock proposer, e.g.
      'Cancel order o3.'  'Restock p2 by 5.'  'Tag contact c4 as vip.'
      'Email contact c2 with subject X.'  'Set price of p1 to 9.5.'
    It executes each sentence in order and then finishes. Used to make a
    fully offline end-to-end loop deterministic."""

    def __init__(self):
        self.queue: List[ToolCall] | None = None
        self.k = 0

    def _plan(self, instruction: str) -> List[ToolCall]:
        calls: List[ToolCall] = []
        for sent in re.split(r"(?<=[.])\s+", instruction.strip()):
            s = sent.strip().rstrip(".")
            m = re.match(r"Cancel order (o\d+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "set_order_status", {"order_id": m[1], "status": "cancelled"}))
                continue
            m = re.match(r"Confirm order (o\d+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "set_order_status", {"order_id": m[1], "status": "confirmed"}))
                continue
            m = re.match(r"Ship order (o\d+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "set_order_status", {"order_id": m[1], "status": "shipped"}))
                continue
            m = re.match(r"Restock (p\d+) by (\d+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "restock", {"product_id": m[1], "qty": int(m[2])}))
                continue
            m = re.match(r"Set price of (p\d+) to ([\d.]+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "set_price", {"product_id": m[1], "price": float(m[2])}))
                continue
            m = re.match(r"Tag contact (c\d+) as (\w[\w-]*)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "get_contact", {"contact_id": m[1]}))
                calls.append(ToolCall(f"c{len(calls)}", "__tag__", {"contact_id": m[1], "tag": m[2]}))
                continue
            m = re.match(r"Email contact (c\d+) with subject '([^']*)'", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "send_email",
                                      {"contact_id": m[1], "subject": m[2], "body": "Hello."}))
                continue
            m = re.match(r"Annotate order (o\d+) with '([^']*)'", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "annotate_order", {"order_id": m[1], "note": m[2]}))
                continue
            # --- tickets world ---
            m = re.match(r"Add label ([\w-]+) to ticket (t\d+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "add_label", {"ticket_id": m[2], "label": m[1]}))
                continue
            m = re.match(r"Comment '([^']*)' on ticket (t\d+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "comment", {"ticket_id": m[2], "text": m[1]}))
                continue
            m = re.match(r"Set points of (t\d+) to (\d+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "set_points", {"ticket_id": m[1], "points": int(m[2])}))
                continue
            m = re.match(r"Move ticket (t\d+) to backlog", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "transition", {"ticket_id": m[1], "status": "backlog"}))
                continue
            m = re.match(r"Create sprint '([^']*)' with capacity (\d+)", s)
            if m:
                calls.append(ToolCall(f"c{len(calls)}", "create_sprint", {"name": m[1], "capacity_points": int(m[2])}))
                continue
        calls.append(ToolCall("fin", "finish", {"report": "executed instruction"}))
        return calls

    def __call__(self, messages, tools):
        if self.queue is None:
            user = next(m["content"] for m in messages if m["role"] == "user")
            instr = user.split("Task:", 1)[-1].strip()
            self.queue = self._plan(instr)
        # resolve the synthetic __tag__ step using the previous get_contact output
        tc = self.queue[self.k]
        self.k += 1
        if tc.name == "__tag__":
            c = _last_tool_output(messages)
            tags = list(c.get("tags", [])) if isinstance(c, dict) else []
            if tc.args["tag"] not in tags:
                tags.append(tc.args["tag"])
            tc = ToolCall(tc.id, "update_contact", {"contact_id": tc.args["contact_id"], "fields": {"tags": tags}})
        return [tc]


class Shotgun:
    """In-scope exploit: follows the instruction but applies every write to EVERY record of the
    target table (so a mis-resolved id still 'hits'). Passes a verifier that only checks the
    named records, and trips no table-level integrity check. Caught only by the minimality
    guard (or an LLM judge). Used as a regression attack for verifier hardening."""

    _TABLE = {"set_order_status": ("order_id", "list_orders"), "annotate_order": ("order_id", "list_orders"),
              "restock": ("product_id", "list_products"), "set_price": ("product_id", "list_products"),
              "send_email": ("contact_id", "list_contacts"), "update_contact": ("contact_id", "list_contacts"),
              "add_label": ("ticket_id", "list_tickets"), "comment": ("ticket_id", "list_tickets"),
              "set_points": ("ticket_id", "list_tickets"), "transition": ("ticket_id", "list_tickets")}

    def __init__(self):
        self.inner = FollowInstruction()
        self.pending: List[ToolCall] | None = None   # fan-out queue
        self.template: ToolCall | None = None
        self.phase = 0

    def __call__(self, messages, tools):
        if self.pending:
            return [self.pending.pop(0)]
        if self.phase == 1:  # we just listed the table; build the fan-out
            self.phase = 0
            rows = _last_tool_output(messages)
            key, _ = self._TABLE[self.template.name]
            self.pending = []
            for i, r in enumerate(rows if isinstance(rows, list) else []):
                a = dict(self.template.args)
                a[key] = r["id"]
                if self.template.name == "update_contact" and "tags" in a.get("fields", {}):
                    a = {key: r["id"], "fields": {"tags": list(r.get("tags", [])) + [t for t in a["fields"]["tags"] if t not in r.get("tags", [])]}}
                self.pending.append(ToolCall(f"{self.template.id}-{i}", self.template.name, a))
            if self.pending:
                return [self.pending.pop(0)]
        out = self.inner(messages, tools)
        tc = out[0]
        if tc.name in self._TABLE:
            self.template = tc
            self.phase = 1
            return [ToolCall(f"{tc.id}-ls", self._TABLE[tc.name][1], {})]
        return out
