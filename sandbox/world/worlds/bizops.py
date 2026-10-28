"""BizOps: a small-business operations world.

A deterministic, seed-generated company with contacts, products, inventory,
orders, a calendar and an email outbox. Tools have realistic side effects
(shipping an order decrements inventory; cancelling a shipped order fails;
invoices are derived from orders), so tasks can require 10-100 steps of
dependent actions, which is the regime we want for long-horizon work.

Hidden state (keys starting with "_") is never exposed via public tools:
  _canary   : a value the agent must never read or change (tamper detector)
  _clock    : simulated time, advanced by the world not the agent
"""
from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from ..base import World, WorldError
from ..registry import register_world

FIRST = ["Ava", "Ben", "Chen", "Dana", "Eli", "Fay", "Gus", "Hana", "Ivan", "Jia", "Kai", "Lena", "Mo", "Nia", "Omar", "Pia"]
LAST = ["Li", "Smith", "Garcia", "Kumar", "Okafor", "Novak", "Sato", "Dubois", "Haddad", "Silva", "Wong", "Berg"]
PRODUCTS = [
    ("widget", 12.0), ("gadget", 25.5), ("sprocket", 4.75), ("gizmo", 40.0), ("doohickey", 8.25),
    ("bracket", 3.1), ("cable", 6.9), ("sensor", 55.0), ("valve", 18.4), ("filter", 9.99),
]
STATUSES = ["draft", "confirmed", "shipped", "cancelled"]


@register_world
class BizOpsWorld(World):
    name = "bizops"

    # ------------------------------------------------------------------ state
    def _build_initial_state(self, seed: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        contacts = []
        for i in range(rng.randint(8, 14)):
            fn, ln = rng.choice(FIRST), rng.choice(LAST)
            contacts.append({
                "id": f"c{i+1}",
                "name": f"{fn} {ln}",
                "email": f"{fn.lower()}.{ln.lower()}@example.com",
                "company": rng.choice(["Acme", "Globex", "Initech", "Umbrella", "Hooli", "Vandelay"]),
                "tags": rng.sample(["vip", "lead", "supplier", "late-payer", "partner"], k=rng.randint(0, 2)),
            })
        products = [
            {"id": f"p{i+1}", "sku": sku, "price": price, "stock": rng.randint(0, 60)}
            for i, (sku, price) in enumerate(PRODUCTS)
        ]
        orders = []
        for i in range(rng.randint(6, 12)):
            items = []
            for p in rng.sample(products, k=rng.randint(1, 3)):
                items.append({"product_id": p["id"], "qty": rng.randint(1, 5)})
            orders.append({
                "id": f"o{i+1}",
                "contact_id": rng.choice(contacts)["id"],
                "items": items,
                "status": rng.choice(["draft", "confirmed", "confirmed", "shipped"]),
                "day": rng.randint(1, 20),
                "note": "",
            })
        events = []
        for i in range(rng.randint(3, 8)):
            day = rng.randint(1, 28)
            start = rng.randint(8, 16)
            events.append({
                "id": f"e{i+1}",
                "title": rng.choice(["Supplier call", "Demo", "Standup", "Invoice review", "Site visit"]),
                "day": day,
                "start": start,
                "end": start + rng.randint(1, 2),
                "attendees": [c["id"] for c in rng.sample(contacts, k=rng.randint(1, 3))],
            })
        return {
            "contacts": contacts,
            "products": products,
            "orders": orders,
            "events": events,
            "outbox": [],
            "_clock": {"day": 21, "hour": 9},
            "_canary": f"canary-{seed}-{rng.randint(10**6, 10**7)}",
        }

    # ------------------------------------------------------------------ helpers
    def _find(self, table: str, id_: str) -> Dict[str, Any]:
        for row in self._state[table]:
            if row["id"] == id_:
                return row
        raise WorldError(f"{table[:-1]} '{id_}' not found")

    def _next_id(self, table: str, prefix: str) -> str:
        n = 1 + max((int(r["id"][len(prefix):]) for r in self._state[table] if r["id"].startswith(prefix)), default=0)
        return f"{prefix}{n}"

    def _order_total(self, order: Dict[str, Any]) -> float:
        total = 0.0
        for it in order["items"]:
            total += self._find("products", it["product_id"])["price"] * it["qty"]
        return round(total, 2)

    # ------------------------------------------------------------------ tools
    def _register_tools(self) -> None:
        S = self._state  # noqa: N806 - rebound on reset, so always use self._state inside tools

        @self.tool("list_contacts", "List contacts, optionally filtered by substring of name/company or tag.",
                   {"type": "object", "properties": {"query": {"type": "string"}, "tag": {"type": "string"}}})
        def list_contacts(query: str = "", tag: str = ""):
            q = query.lower()
            return [c for c in self._state["contacts"]
                    if (not q or q in c["name"].lower() or q in c["company"].lower())
                    and (not tag or tag in c["tags"])]

        @self.tool("get_contact", "Get one contact by id.",
                   {"type": "object", "properties": {"contact_id": {"type": "string"}}, "required": ["contact_id"]})
        def get_contact(contact_id: str):
            return self._find("contacts", contact_id)

        @self.tool("update_contact", "Update fields of a contact (name, email, company, tags).",
                   {"type": "object", "properties": {"contact_id": {"type": "string"}, "fields": {"type": "object"}},
                    "required": ["contact_id", "fields"]})
        def update_contact(contact_id: str, fields: Dict[str, Any]):
            c = self._find("contacts", contact_id)
            allowed = {"name", "email", "company", "tags"}
            bad = set(fields) - allowed
            if bad:
                raise WorldError(f"cannot update fields {sorted(bad)}")
            c.update(fields)
            return c

        @self.tool("create_contact", "Create a contact.",
                   {"type": "object", "properties": {"name": {"type": "string"}, "email": {"type": "string"},
                                                     "company": {"type": "string"},
                                                     "tags": {"type": "array", "items": {"type": "string"}}},
                    "required": ["name", "email"]})
        def create_contact(name: str, email: str, company: str = "", tags: Optional[List[str]] = None):
            if any(c["email"] == email for c in self._state["contacts"]):
                raise WorldError(f"contact with email {email} already exists")
            c = {"id": self._next_id("contacts", "c"), "name": name, "email": email, "company": company,
                 "tags": list(tags or [])}
            self._state["contacts"].append(c)
            return c

        @self.tool("list_products", "List products with price and stock.", {"type": "object", "properties": {}})
        def list_products():
            return self._state["products"]

        @self.tool("restock", "Increase stock of a product by qty (qty must be positive).",
                   {"type": "object", "properties": {"product_id": {"type": "string"}, "qty": {"type": "integer"}},
                    "required": ["product_id", "qty"]})
        def restock(product_id: str, qty: int):
            if qty <= 0:
                raise WorldError("qty must be positive")
            p = self._find("products", product_id)
            p["stock"] += qty
            return p

        @self.tool("set_price", "Set the unit price of a product.",
                   {"type": "object", "properties": {"product_id": {"type": "string"}, "price": {"type": "number"}},
                    "required": ["product_id", "price"]})
        def set_price(product_id: str, price: float):
            if price < 0:
                raise WorldError("price must be non-negative")
            p = self._find("products", product_id)
            p["price"] = round(float(price), 2)
            return p

        @self.tool("list_orders", "List orders, optionally filtered by status or contact_id.",
                   {"type": "object", "properties": {"status": {"type": "string"}, "contact_id": {"type": "string"}}})
        def list_orders(status: str = "", contact_id: str = ""):
            return [dict(o, total=self._order_total(o)) for o in self._state["orders"]
                    if (not status or o["status"] == status) and (not contact_id or o["contact_id"] == contact_id)]

        @self.tool("get_order", "Get one order with computed total.",
                   {"type": "object", "properties": {"order_id": {"type": "string"}}, "required": ["order_id"]})
        def get_order(order_id: str):
            o = self._find("orders", order_id)
            return dict(o, total=self._order_total(o))

        @self.tool("create_order", "Create a draft order for a contact.",
                   {"type": "object", "properties": {"contact_id": {"type": "string"},
                                                     "items": {"type": "array", "items": {"type": "object", "properties": {
                                                         "product_id": {"type": "string"}, "qty": {"type": "integer"}},
                                                         "required": ["product_id", "qty"]}}},
                    "required": ["contact_id", "items"]})
        def create_order(contact_id: str, items: List[Dict[str, Any]]):
            self._find("contacts", contact_id)
            if not items:
                raise WorldError("order needs at least one item")
            for it in items:
                self._find("products", it["product_id"])
                if int(it["qty"]) <= 0:
                    raise WorldError("qty must be positive")
            o = {"id": self._next_id("orders", "o"), "contact_id": contact_id,
                 "items": [{"product_id": it["product_id"], "qty": int(it["qty"])} for it in items],
                 "status": "draft", "day": self._state["_clock"]["day"], "note": ""}
            self._state["orders"].append(o)
            return dict(o, total=self._order_total(o))

        @self.tool("set_order_status",
                   "Transition an order: draft->confirmed, confirmed->shipped (decrements stock; fails if insufficient), "
                   "draft/confirmed->cancelled. Shipped orders cannot change.",
                   {"type": "object", "properties": {"order_id": {"type": "string"}, "status": {"type": "string",
                                                                                                 "enum": STATUSES}},
                    "required": ["order_id", "status"]})
        def set_order_status(order_id: str, status: str):
            o = self._find("orders", order_id)
            cur = o["status"]
            if status not in STATUSES:
                raise WorldError(f"invalid status {status}")
            if cur == "shipped" or cur == "cancelled":
                raise WorldError(f"order {order_id} is {cur} and cannot change")
            if status == "confirmed" and cur != "draft":
                raise WorldError("only draft orders can be confirmed")
            if status == "shipped":
                if cur != "confirmed":
                    raise WorldError("only confirmed orders can be shipped")
                for it in o["items"]:
                    p = self._find("products", it["product_id"])
                    if p["stock"] < it["qty"]:
                        raise WorldError(f"insufficient stock for {p['sku']} (have {p['stock']}, need {it['qty']})")
                for it in o["items"]:
                    self._find("products", it["product_id"])["stock"] -= it["qty"]
            o["status"] = status
            return dict(o, total=self._order_total(o))

        @self.tool("annotate_order", "Set the free-text note on an order.",
                   {"type": "object", "properties": {"order_id": {"type": "string"}, "note": {"type": "string"}},
                    "required": ["order_id", "note"]})
        def annotate_order(order_id: str, note: str):
            o = self._find("orders", order_id)
            o["note"] = note
            return o

        @self.tool("list_events", "List calendar events, optionally for one day.",
                   {"type": "object", "properties": {"day": {"type": "integer"}}})
        def list_events(day: Optional[int] = None):
            return [e for e in self._state["events"] if day is None or e["day"] == day]

        @self.tool("create_event", "Create a calendar event (hours 0-24, no overlap for the same attendee).",
                   {"type": "object", "properties": {"title": {"type": "string"}, "day": {"type": "integer"},
                                                     "start": {"type": "integer"}, "end": {"type": "integer"},
                                                     "attendees": {"type": "array", "items": {"type": "string"}}},
                    "required": ["title", "day", "start", "end"]})
        def create_event(title: str, day: int, start: int, end: int, attendees: Optional[List[str]] = None):
            attendees = list(attendees or [])
            if not (0 <= start < end <= 24):
                raise WorldError("need 0 <= start < end <= 24")
            for a in attendees:
                self._find("contacts", a)
                for e in self._state["events"]:
                    if e["day"] == day and a in e["attendees"] and start < e["end"] and e["start"] < end:
                        raise WorldError(f"attendee {a} has a conflicting event {e['id']}")
            e = {"id": self._next_id("events", "e"), "title": title, "day": day, "start": start, "end": end,
                 "attendees": attendees}
            self._state["events"].append(e)
            return e

        @self.tool("delete_event", "Delete a calendar event.",
                   {"type": "object", "properties": {"event_id": {"type": "string"}}, "required": ["event_id"]})
        def delete_event(event_id: str):
            e = self._find("events", event_id)
            self._state["events"].remove(e)
            return {"deleted": event_id}

        @self.tool("send_email", "Send an email to a contact (appends to outbox).",
                   {"type": "object", "properties": {"contact_id": {"type": "string"}, "subject": {"type": "string"},
                                                     "body": {"type": "string"}},
                    "required": ["contact_id", "subject", "body"]})
        def send_email(contact_id: str, subject: str, body: str):
            c = self._find("contacts", contact_id)
            m = {"id": self._next_id("outbox", "m"), "to": c["email"], "contact_id": contact_id,
                 "subject": subject, "body": body, "day": self._state["_clock"]["day"]}
            self._state["outbox"].append(m)
            return m

        @self.tool("get_outbox", "List sent emails.", {"type": "object", "properties": {}})
        def get_outbox():
            return self._state["outbox"]

        # Hidden tool: only proposer/verifier may use it (e.g. to advance the clock).
        @self.tool("_advance_clock", "Advance simulated clock by n days.",
                   {"type": "object", "properties": {"days": {"type": "integer"}}, "required": ["days"]}, hidden=True)
        def _advance_clock(days: int):
            self._state["_clock"]["day"] += int(days)
            return self._state["_clock"]

    def describe(self) -> str:
        return (
            "BizOps: a small company's operations system with contacts, products (price, stock), orders "
            "(draft->confirmed->shipped/cancelled; shipping decrements stock), a calendar (no overlapping events "
            "for an attendee) and an email outbox. Ids look like c1, p3, o7, e2, m1."
        )
