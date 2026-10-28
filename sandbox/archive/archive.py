"""Archive: lineage of agents, versioned tasks, every episode, per-generation
summaries. SQLite for queries + plain files for code and trajectories so a run
can be inspected (and rolled back) with ordinary tools.

Layout of a run directory:
  archive.sqlite
  agents/<version>/agent.py        (+ rationale.md written by the improver)
  tasks/<task_id>.json             current version of each task (hidden verifier included)
  tasks/history/<task_id>.v<k>.json
  episodes/g<gen>/<episode_id>.json
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from typing import Any, Dict, Iterable, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
  version TEXT PRIMARY KEY, parent TEXT, generation INTEGER, created_at REAL,
  status TEXT, notes TEXT, rationale TEXT
);
CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY, generation INTEGER, world TEXT, seed INTEGER, difficulty INTEGER,
  tags TEXT, verifier_version INTEGER, novel_at_creation INTEGER, first_solved_gen INTEGER,
  status TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS episodes (
  id TEXT PRIMARY KEY, generation INTEGER, agent_version TEXT, task_id TEXT, verifier_version INTEGER,
  purpose TEXT, passed INTEGER, score REAL, hacking INTEGER, flags TEXT, steps INTEGER,
  input_tokens INTEGER, output_tokens INTEGER, llm_calls INTEGER, wall_s REAL, status TEXT, created_at REAL
);
CREATE TABLE IF NOT EXISTS generations (
  gen INTEGER PRIMARY KEY, started_at REAL, finished_at REAL, summary TEXT
);
CREATE INDEX IF NOT EXISTS ep_agent ON episodes(agent_version);
CREATE INDEX IF NOT EXISTS ep_task ON episodes(task_id);
CREATE INDEX IF NOT EXISTS ep_gen ON episodes(generation);
"""


class Archive:
    def __init__(self, run_dir: str):
        self.run_dir = os.path.abspath(run_dir)
        for d in ("agents", "tasks", "tasks/history", "episodes"):
            os.makedirs(os.path.join(self.run_dir, d), exist_ok=True)
        self.db = sqlite3.connect(os.path.join(self.run_dir, "archive.sqlite"))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self._ep_counter = self._count("episodes")

    # ------------------------------------------------------------------ agents
    def agent_dir(self, version: str) -> str:
        return os.path.join(self.run_dir, "agents", version)

    def add_agent(self, version: str, code: str, *, parent: Optional[str], generation: int, notes: str = "",
                  rationale: str = "", status: str = "candidate") -> str:
        d = self.agent_dir(version)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "agent.py"), "w") as f:
            f.write(code)
        if rationale:
            with open(os.path.join(d, "rationale.md"), "w") as f:
                f.write(rationale)
        self.db.execute("INSERT OR REPLACE INTO agents VALUES (?,?,?,?,?,?,?)",
                        (version, parent, generation, time.time(), status, notes, rationale[:5000]))
        self.db.commit()
        return d

    def add_agent_from_dir(self, version: str, src_dir: str, **kw) -> str:
        with open(os.path.join(src_dir, "agent.py")) as f:
            return self.add_agent(version, f.read(), **kw)

    def agent_code(self, version: str) -> str:
        with open(os.path.join(self.agent_dir(version), "agent.py")) as f:
            return f.read()

    def set_agent_status(self, version: str, status: str) -> None:
        self.db.execute("UPDATE agents SET status=? WHERE version=?", (status, version))
        self.db.commit()

    def agents(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        q = "SELECT * FROM agents" + (" WHERE status=?" if status else "") + " ORDER BY generation, version"
        return [dict(r) for r in self.db.execute(q, (status,) if status else ())]

    def children(self, version: str) -> List[str]:
        return [r["version"] for r in self.db.execute("SELECT version FROM agents WHERE parent=?", (version,))]

    def clade(self, version: str) -> List[str]:
        out, stack = [], [version]
        while stack:
            v = stack.pop()
            out.append(v)
            stack.extend(self.children(v))
        return out

    # ------------------------------------------------------------------ tasks
    def task_path(self, task_id: str) -> str:
        return os.path.join(self.run_dir, "tasks", f"{task_id}.json")

    def add_task(self, task: Dict[str, Any], status: str = "active") -> None:
        """`status`: "active" (used for selection, acceptance and improver diagnostics) or "heldout"
        (only ever used to report the champion; never seen by selection, acceptance or the improver)."""
        task.setdefault("meta", {})["verifier_version"] = 1
        with open(self.task_path(task["id"]), "w") as f:
            json.dump(task, f, ensure_ascii=False, indent=1)
        self._snapshot_task(task, 1, "created")
        self.db.execute("INSERT OR REPLACE INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (task["id"], task["generation"], task["world"], task["seed"], task["difficulty"],
                         json.dumps(task.get("tags", [])), 1, None, None, status, time.time()))
        self.db.commit()

    def update_task(self, task: Dict[str, Any], reason: str) -> int:
        """Persist a modified task (e.g. hardened verifier); bumps verifier_version."""
        v = int(task.get("meta", {}).get("verifier_version", 1)) + 1
        task["meta"]["verifier_version"] = v
        with open(self.task_path(task["id"]), "w") as f:
            json.dump(task, f, ensure_ascii=False, indent=1)
        self._snapshot_task(task, v, reason)
        self.db.execute("UPDATE tasks SET verifier_version=? WHERE id=?", (v, task["id"]))
        self.db.commit()
        return v

    def _snapshot_task(self, task: Dict[str, Any], version: int, reason: str) -> None:
        p = os.path.join(self.run_dir, "tasks", "history", f"{task['id']}.v{version}.json")
        with open(p, "w") as f:
            json.dump({"reason": reason, "task": task}, f, ensure_ascii=False, indent=1)

    def task(self, task_id: str) -> Dict[str, Any]:
        with open(self.task_path(task_id)) as f:
            return json.load(f)

    def tasks(self, status: str = "active", generation: Optional[int] = None) -> List[Dict[str, Any]]:
        q, args = "SELECT id FROM tasks WHERE status=?", [status]
        if generation is not None:
            q += " AND generation=?"
            args.append(generation)
        return [self.task(r["id"]) for r in self.db.execute(q + " ORDER BY id", args)]

    def set_task_fields(self, task_id: str, **fields: Any) -> None:
        cols = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE tasks SET {cols} WHERE id=?", (*fields.values(), task_id))
        self.db.commit()

    def task_rows(self) -> List[Dict[str, Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM tasks ORDER BY id")]

    # ------------------------------------------------------------------ episodes
    def add_episode(self, generation: int, task: Dict[str, Any], ep_json: Dict[str, Any], verdict: Dict[str, Any],
                    purpose: str = "eval", final_state: Optional[Dict[str, Any]] = None) -> str:
        self._ep_counter += 1
        eid = f"ep{self._ep_counter:06d}"
        d = os.path.join(self.run_dir, "episodes", f"g{generation}")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, f"{eid}.json"), "w") as f:
            json.dump({"episode": ep_json, "verdict": verdict, "task_id": task["id"],
                       "verifier_version": task.get("meta", {}).get("verifier_version", 1),
                       "final_state": final_state}, f, ensure_ascii=False)
        u = ep_json.get("usage", {})
        self.db.execute(
            "INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, generation, ep_json.get("agent_version"), task["id"], task.get("meta", {}).get("verifier_version", 1),
             purpose, int(bool(verdict.get("passed"))), float(verdict.get("score") or 0.0),
             int(bool(verdict.get("hacking_suspected"))), json.dumps([f["check"] for f in verdict.get("flags", [])]),
             int(ep_json.get("steps", 0)), int(u.get("input_tokens", 0)), int(u.get("output_tokens", 0)),
             int(u.get("calls", 0)), float(ep_json.get("wall_s", 0.0)), ep_json.get("status"), time.time()))
        self.db.commit()
        return eid

    def episode_file(self, eid: str, generation: int) -> Dict[str, Any]:
        with open(os.path.join(self.run_dir, "episodes", f"g{generation}", f"{eid}.json")) as f:
            return json.load(f)

    def episodes(self, **where: Any) -> List[Dict[str, Any]]:
        q = "SELECT * FROM episodes"
        if where:
            q += " WHERE " + " AND ".join(f"{k}=?" for k in where)
        return [dict(r) for r in self.db.execute(q + " ORDER BY id", tuple(where.values()))]

    def pass_rate(self, agent_version: str, *, exclude_hacks: bool = True, task_ids: Optional[Iterable[str]] = None,
                  purpose: str = "eval", generation: Optional[int] = None) -> Optional[float]:
        where: Dict[str, Any] = {"agent_version": agent_version, "purpose": purpose}
        if generation is not None:
            where["generation"] = generation
        eps = self.episodes(**where)
        if task_ids is not None:
            ids = set(task_ids)
            eps = [e for e in eps if e["task_id"] in ids]
        if not eps:
            return None
        ok = sum(1 for e in eps if e["passed"] and not (exclude_hacks and e["hacking"]))
        return ok / len(eps)

    # ------------------------------------------------------------------ generations
    def start_generation(self, gen: int) -> None:
        self.db.execute("INSERT OR REPLACE INTO generations VALUES (?,?,?,?)", (gen, time.time(), None, None))
        self.db.commit()

    def finish_generation(self, gen: int, summary: Dict[str, Any]) -> None:
        self.db.execute("UPDATE generations SET finished_at=?, summary=? WHERE gen=?",
                        (time.time(), json.dumps(summary, ensure_ascii=False), gen))
        self.db.commit()
        with open(os.path.join(self.run_dir, "generations.jsonl"), "a") as f:
            f.write(json.dumps({"gen": gen, **summary}, ensure_ascii=False) + "\n")

    def generations(self) -> List[Dict[str, Any]]:
        out = []
        for r in self.db.execute("SELECT * FROM generations ORDER BY gen"):
            d = dict(r)
            d["summary"] = json.loads(d["summary"]) if d["summary"] else None
            out.append(d)
        return out

    # ------------------------------------------------------------------ rollback
    def rollback_task_verifier(self, task_id: str, version: int) -> Dict[str, Any]:
        p = os.path.join(self.run_dir, "tasks", "history", f"{task_id}.v{version}.json")
        with open(p) as f:
            task = json.load(f)["task"]
        with open(self.task_path(task_id), "w") as f:
            json.dump(task, f, ensure_ascii=False, indent=1)
        self.db.execute("UPDATE tasks SET verifier_version=? WHERE id=?", (version, task_id))
        self.db.commit()
        return task

    def _count(self, table: str) -> int:
        return self.db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def close(self) -> None:
        self.db.close()
