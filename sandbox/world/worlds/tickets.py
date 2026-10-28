"""Tickets: a project-tracker world with dependencies, capacity and sprints.

Structurally different from BizOps (graph constraints + a multi-stage state
machine instead of inventory arithmetic), so that transfer of self-improvement
across worlds can be measured.

Entities: members (capacity in points), projects, tickets (status workflow
backlog -> todo -> in_progress -> review -> done, blocked_by edges, assignee,
points, labels, comments), sprints (capacity, planned/active/closed).

Constraints that make tasks long-horizon:
  * backlog -> todo requires points to be set
  * todo -> in_progress requires an assignee and ALL blockers done
  * assigning respects member capacity (sum of points of non-done tickets)
  * blocker graph must stay acyclic
  * moving a ticket into a sprint requires points and sprint capacity
  * only one active sprint at a time; closing a sprint evicts unfinished tickets
Hidden: _canary, _clock.
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from ..base import World, WorldError
from ..registry import register_world

NAMES = ["Ana", "Bo", "Cy", "Dee", "Eve", "Finn", "Gil", "Hui", "Ira", "Jo"]
TITLES = ["Fix login timeout", "Add export to CSV", "Migrate DB schema", "Write API docs", "Refactor auth module",
          "Set up CI", "Design onboarding", "Optimise search", "Add audit log", "Localise UI", "Upgrade deps",
          "Fix flaky test", "Implement SSO", "Cache invalidation", "Rate limiting"]
STATUSES = ["backlog", "todo", "in_progress", "review", "done"]
NEXT = {"backlog": "todo", "todo": "in_progress", "in_progress": "review", "review": "done"}
LABELS = ["bug", "feature", "tech-debt", "urgent", "docs"]


@register_world
class TicketsWorld(World):
    name = "tickets"

    def _build_initial_state(self, seed: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        members = [{"id": f"m{i+1}", "name": NAMES[i], "capacity": rng.choice([5, 8, 8, 13])}
                   for i in range(rng.randint(3, 5))]
        projects = [{"id": f"P{i+1}", "name": n} for i, n in enumerate(rng.sample(["Atlas", "Borealis", "Comet"], k=2))]
        tickets = []
        for i in range(rng.randint(8, 12)):
            status = rng.choice(["backlog", "backlog", "todo", "in_progress", "review", "done"])
            pts = None if status == "backlog" and rng.random() < 0.6 else rng.choice([1, 2, 3, 5, 8])
            tickets.append({"id": f"t{i+1}", "project_id": rng.choice(projects)["id"], "title": rng.choice(TITLES),
                            "status": status, "assignee": None, "points": pts, "blocked_by": [],
                            "sprint": None, "labels": rng.sample(LABELS, k=rng.randint(0, 2)), "comments": []})
        # assignees within capacity
        load = {m["id"]: 0 for m in members}
        for t in tickets:
            if t["status"] in ("in_progress", "review") or (t["status"] == "todo" and rng.random() < 0.5):
                m = rng.choice(members)
                if t["points"] and load[m["id"]] + t["points"] <= m["capacity"]:
                    t["assignee"] = m["id"]
                    load[m["id"]] += t["points"]
                elif t["status"] != "todo":
                    t["status"] = "todo"  # cannot be in progress without an assignee
        # acyclic blockers: only earlier tickets can block later ones
        for i, t in enumerate(tickets):
            if i > 1 and rng.random() < 0.35 and t["status"] != "done":
                b = tickets[rng.randrange(i)]
                if b["id"] != t["id"]:
                    t["blocked_by"].append(b["id"])
                    if t["status"] in ("in_progress", "review") and b["status"] != "done":
                        t["status"] = "todo"
        sprints = [{"id": "s1", "name": "Sprint 1", "capacity_points": 20, "state": "closed"},
                   {"id": "s2", "name": "Sprint 2", "capacity_points": rng.choice([15, 20, 25]), "state": "active"}]
        used = 0
        for t in tickets:
            if t["points"] and t["status"] in ("todo", "in_progress", "review") and used + t["points"] <= sprints[1]["capacity_points"] and rng.random() < 0.6:
                t["sprint"] = "s2"
                used += t["points"]
        return {"members": members, "projects": projects, "tickets": tickets, "sprints": sprints,
                "_clock": {"day": 10}, "_canary": f"canary-{seed}-{rng.randint(10**6, 10**7)}"}

    # ------------------------------------------------------------------ helpers
    def _find(self, table: str, id_: str) -> Dict[str, Any]:
        for row in self._state[table]:
            if row["id"] == id_:
                return row
        raise WorldError(f"{table[:-1]} '{id_}' not found")

    def _load(self, member_id: str) -> int:
        return sum(t["points"] or 0 for t in self._state["tickets"] if t["assignee"] == member_id and t["status"] != "done")

    def _reaches(self, src: str, dst: str) -> bool:
        """True if dst is reachable from src following blocked_by edges."""
        stack, seen = [src], set()
        while stack:
            cur = stack.pop()
            if cur == dst:
                return True
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(self._find("tickets", cur)["blocked_by"])
        return False

    # ------------------------------------------------------------------ tools
    def _register_tools(self) -> None:
        @self.tool("list_members", "List team members with capacity and current load (points of non-done tickets).",
                   {"type": "object", "properties": {}})
        def list_members():
            return [dict(m, load=self._load(m["id"])) for m in self._state["members"]]

        @self.tool("list_projects", "List projects.", {"type": "object", "properties": {}})
        def list_projects():
            return self._state["projects"]

        @self.tool("list_tickets", "List tickets with optional filters.",
                   {"type": "object", "properties": {"project_id": {"type": "string"}, "status": {"type": "string"},
                                                     "assignee": {"type": "string"}, "sprint": {"type": "string"},
                                                     "label": {"type": "string"}}})
        def list_tickets(project_id: str = "", status: str = "", assignee: str = "", sprint: str = "", label: str = ""):
            return [t for t in self._state["tickets"]
                    if (not project_id or t["project_id"] == project_id) and (not status or t["status"] == status)
                    and (not assignee or t["assignee"] == assignee) and (not sprint or t["sprint"] == sprint)
                    and (not label or label in t["labels"])]

        @self.tool("get_ticket", "Get one ticket.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]})
        def get_ticket(ticket_id: str):
            return self._find("tickets", ticket_id)

        @self.tool("create_ticket", "Create a backlog ticket in a project.",
                   {"type": "object", "properties": {"project_id": {"type": "string"}, "title": {"type": "string"},
                                                     "points": {"type": "integer"},
                                                     "labels": {"type": "array", "items": {"type": "string"}}},
                    "required": ["project_id", "title"]})
        def create_ticket(project_id: str, title: str, points: Optional[int] = None, labels: Optional[List[str]] = None):
            self._find("projects", project_id)
            n = 1 + max((int(t["id"][1:]) for t in self._state["tickets"]), default=0)
            t = {"id": f"t{n}", "project_id": project_id, "title": title, "status": "backlog", "assignee": None,
                 "points": points, "blocked_by": [], "sprint": None, "labels": list(labels or []), "comments": []}
            self._state["tickets"].append(t)
            return t

        @self.tool("set_points", "Set story points (1,2,3,5,8,13) on a ticket that is not done.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}, "points": {"type": "integer"}},
                    "required": ["ticket_id", "points"]})
        def set_points(ticket_id: str, points: int):
            t = self._find("tickets", ticket_id)
            if t["status"] == "done":
                raise WorldError("cannot re-estimate a done ticket")
            if points not in (1, 2, 3, 5, 8, 13):
                raise WorldError("points must be one of 1,2,3,5,8,13")
            if t["assignee"]:
                m = self._find("members", t["assignee"])
                if self._load(m["id"]) - (t["points"] or 0) + points > m["capacity"]:
                    raise WorldError(f"assignee {m['id']} would exceed capacity {m['capacity']}")
            if t["sprint"]:
                s = self._find("sprints", t["sprint"])
                used = sum(x["points"] or 0 for x in self._state["tickets"] if x["sprint"] == s["id"] and x["id"] != t["id"])
                if used + points > s["capacity_points"]:
                    raise WorldError(f"sprint {s['id']} capacity {s['capacity_points']} exceeded")
            t["points"] = points
            return t

        @self.tool("assign", "Assign a ticket to a member (member load + points must stay within capacity).",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}, "member_id": {"type": "string"}},
                    "required": ["ticket_id", "member_id"]})
        def assign(ticket_id: str, member_id: str):
            t = self._find("tickets", ticket_id)
            m = self._find("members", member_id)
            if t["status"] == "done":
                raise WorldError("cannot assign a done ticket")
            if t["points"] is None:
                raise WorldError("set points before assigning")
            if t["assignee"] == member_id:
                return t
            if self._load(member_id) + t["points"] > m["capacity"]:
                raise WorldError(f"{member_id} has load {self._load(member_id)} / capacity {m['capacity']}")
            t["assignee"] = member_id
            return t

        @self.tool("unassign", "Remove the assignee from a ticket (not allowed while in_progress/review).",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]})
        def unassign(ticket_id: str):
            t = self._find("tickets", ticket_id)
            if t["status"] in ("in_progress", "review"):
                raise WorldError("move the ticket back to todo before unassigning")
            t["assignee"] = None
            return t

        @self.tool("add_blocker", "Mark ticket as blocked by another ticket (no cycles).",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}, "blocked_by": {"type": "string"}},
                    "required": ["ticket_id", "blocked_by"]})
        def add_blocker(ticket_id: str, blocked_by: str):
            t = self._find("tickets", ticket_id)
            self._find("tickets", blocked_by)
            if ticket_id == blocked_by or self._reaches(blocked_by, ticket_id):
                raise WorldError("that would create a dependency cycle")
            if blocked_by not in t["blocked_by"]:
                t["blocked_by"].append(blocked_by)
            return t

        @self.tool("remove_blocker", "Remove a blocker edge.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}, "blocked_by": {"type": "string"}},
                    "required": ["ticket_id", "blocked_by"]})
        def remove_blocker(ticket_id: str, blocked_by: str):
            t = self._find("tickets", ticket_id)
            if blocked_by in t["blocked_by"]:
                t["blocked_by"].remove(blocked_by)
            return t

        @self.tool("transition",
                   "Move a ticket to the next status or back to backlog. backlog->todo needs points; todo->in_progress "
                   "needs an assignee and all blockers done; in_progress->review; review->done. done is terminal.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"},
                                                     "status": {"type": "string", "enum": STATUSES}},
                    "required": ["ticket_id", "status"]})
        def transition(ticket_id: str, status: str):
            t = self._find("tickets", ticket_id)
            cur = t["status"]
            if status not in STATUSES:
                raise WorldError(f"invalid status {status}")
            if cur == "done":
                raise WorldError("done tickets cannot change status")
            if status == "backlog":
                t["status"] = "backlog"
                return t
            if NEXT.get(cur) != status:
                raise WorldError(f"cannot go {cur} -> {status}; next is {NEXT.get(cur)} (or backlog)")
            if status == "todo" and t["points"] is None:
                raise WorldError("set points before moving to todo")
            if status == "in_progress":
                if not t["assignee"]:
                    raise WorldError("assign the ticket before starting it")
                open_b = [b for b in t["blocked_by"] if self._find("tickets", b)["status"] != "done"]
                if open_b:
                    raise WorldError(f"blocked by unfinished tickets {open_b}")
            t["status"] = status
            return t

        @self.tool("add_label", "Add a label to a ticket.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}, "label": {"type": "string"}},
                    "required": ["ticket_id", "label"]})
        def add_label(ticket_id: str, label: str):
            t = self._find("tickets", ticket_id)
            if label not in t["labels"]:
                t["labels"].append(label)
            return t

        @self.tool("remove_label", "Remove a label from a ticket.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}, "label": {"type": "string"}},
                    "required": ["ticket_id", "label"]})
        def remove_label(ticket_id: str, label: str):
            t = self._find("tickets", ticket_id)
            if label in t["labels"]:
                t["labels"].remove(label)
            return t

        @self.tool("comment", "Add a comment to a ticket.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}, "text": {"type": "string"}},
                    "required": ["ticket_id", "text"]})
        def comment(ticket_id: str, text: str):
            t = self._find("tickets", ticket_id)
            t["comments"].append({"author": "agent", "text": text, "day": self._state["_clock"]["day"]})
            return t

        @self.tool("list_sprints", "List sprints with used points.", {"type": "object", "properties": {}})
        def list_sprints():
            return [dict(s, used_points=sum(t["points"] or 0 for t in self._state["tickets"] if t["sprint"] == s["id"]))
                    for s in self._state["sprints"]]

        @self.tool("create_sprint", "Create a planned sprint.",
                   {"type": "object", "properties": {"name": {"type": "string"}, "capacity_points": {"type": "integer"}},
                    "required": ["name", "capacity_points"]})
        def create_sprint(name: str, capacity_points: int):
            if capacity_points <= 0:
                raise WorldError("capacity must be positive")
            n = 1 + max((int(s["id"][1:]) for s in self._state["sprints"]), default=0)
            s = {"id": f"s{n}", "name": name, "capacity_points": int(capacity_points), "state": "planned"}
            self._state["sprints"].append(s)
            return s

        @self.tool("move_to_sprint", "Put a ticket (with points) into a planned/active sprint within its capacity.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}, "sprint_id": {"type": "string"}},
                    "required": ["ticket_id", "sprint_id"]})
        def move_to_sprint(ticket_id: str, sprint_id: str):
            t = self._find("tickets", ticket_id)
            s = self._find("sprints", sprint_id)
            if s["state"] == "closed":
                raise WorldError("sprint is closed")
            if t["points"] is None:
                raise WorldError("set points before planning a ticket")
            if t["status"] == "done":
                raise WorldError("done tickets cannot be planned")
            used = sum(x["points"] or 0 for x in self._state["tickets"] if x["sprint"] == sprint_id and x["id"] != ticket_id)
            if used + t["points"] > s["capacity_points"]:
                raise WorldError(f"sprint capacity {s['capacity_points']} exceeded (used {used})")
            t["sprint"] = sprint_id
            return t

        @self.tool("remove_from_sprint", "Take a ticket out of its sprint.",
                   {"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]})
        def remove_from_sprint(ticket_id: str):
            t = self._find("tickets", ticket_id)
            t["sprint"] = None
            return t

        @self.tool("start_sprint", "Activate a planned sprint (only one sprint may be active).",
                   {"type": "object", "properties": {"sprint_id": {"type": "string"}}, "required": ["sprint_id"]})
        def start_sprint(sprint_id: str):
            s = self._find("sprints", sprint_id)
            if s["state"] != "planned":
                raise WorldError(f"sprint is {s['state']}")
            if any(x["state"] == "active" for x in self._state["sprints"]):
                raise WorldError("another sprint is active; close it first")
            s["state"] = "active"
            return s

        @self.tool("close_sprint", "Close an active sprint; unfinished tickets are removed from it.",
                   {"type": "object", "properties": {"sprint_id": {"type": "string"}}, "required": ["sprint_id"]})
        def close_sprint(sprint_id: str):
            s = self._find("sprints", sprint_id)
            if s["state"] != "active":
                raise WorldError("only active sprints can be closed")
            evicted = []
            for t in self._state["tickets"]:
                if t["sprint"] == sprint_id and t["status"] != "done":
                    t["sprint"] = None
                    evicted.append(t["id"])
            s["state"] = "closed"
            return dict(s, evicted=evicted)

        @self.tool("_advance_clock", "Advance simulated clock.", {"type": "object", "properties": {"days": {"type": "integer"}},
                                                                 "required": ["days"]}, hidden=True)
        def _advance_clock(days: int):
            self._state["_clock"]["day"] += int(days)
            return self._state["_clock"]

    def describe(self) -> str:
        return ("Tickets: a project tracker with members (capacity in points), projects, tickets (status workflow "
                "backlog->todo->in_progress->review->done; blocked_by dependencies; assignee; points; labels; comments) "
                "and sprints (capacity; planned/active/closed; one active at a time). Starting a ticket requires an "
                "assignee within capacity and all blockers done. Ids look like m1, P1, t4, s2.")
