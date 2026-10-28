"""Task schema shared by proposer, verifier, archive and loop.

A task is a dict (kept as plain JSON so it can be logged/diffed/versioned):

{
  "id": "g1-0007",               # generation-created + ordinal
  "world": "bizops", "seed": 17,
  "instruction": "...",          # shown to the solver
  "max_steps": 40,
  "difficulty": 3,               # proposer's 1-5 estimate; refined by outcomes
  "generation": 1,               # generation in which it was created
  "proposer": "llm:claude-...",  # or "mock"
  "scope": {"tables": ["orders", "products"]},   # tables the task legitimately touches
  "verifier": {"kind": "python", "code": "def verify(initial, final, trajectory, answer): ..."},
  "reference_actions": [{"tool": "...", "args": {...}}, ...],   # hidden reference solution (optional)
  "tags": ["orders", "multi-step"],
  "meta": {...}                  # filter results, hardening history, etc.
}

Only `id, world, seed, instruction, max_steps, difficulty` are ever shown to the
solver (see `public_view`).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict

PUBLIC_FIELDS = ("id", "world", "seed", "instruction", "max_steps", "difficulty")


def public_view(task: Dict[str, Any], world_description: str = "") -> Dict[str, Any]:
    t = {k: task[k] for k in PUBLIC_FIELDS if k in task}
    if world_description:
        t["world_description"] = world_description
    return t


def task_fingerprint(task: Dict[str, Any]) -> str:
    """Stable hash of the parts that define the task (used for dedup)."""
    key = json.dumps({"world": task["world"], "seed": task["seed"], "instruction": task["instruction"].strip().lower()},
                     sort_keys=True)
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def new_task(world: str, seed: int, instruction: str, verifier_code: str, *, generation: int, proposer: str,
             scope_tables=None, max_steps: int = 40, difficulty: int = 2, reference_actions=None, tags=None,
             ordinal: int = 0) -> Dict[str, Any]:
    return {
        "id": f"g{generation}-{ordinal:04d}",
        "world": world,
        "seed": seed,
        "instruction": instruction.strip(),
        "max_steps": max_steps,
        "difficulty": difficulty,
        "generation": generation,
        "proposer": proposer,
        "scope": {"tables": list(scope_tables or [])},
        "verifier": {"kind": "python", "code": verifier_code},
        "reference_actions": list(reference_actions or []),
        "tags": list(tags or []),
        "meta": {},
    }
