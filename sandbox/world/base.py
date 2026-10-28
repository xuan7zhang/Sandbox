"""World: a synthetic, stateful tool environment.

Design goals (from the survey):
  * State is a plain JSON-serialisable dict so that state-diff verification,
    snapshot/restore and lineage logging are trivial and cheap.
  * Tools are declared with JSON schemas so any LLM provider can call them.
  * The world never exposes hidden fields (canaries, verifier targets) through
    public tools: `public_state()` is what the agent may see; `state()` is what
    the verifier sees.
  * Every call is logged with wall-clock so that per-step environment cost can
    be reported as a first-class metric.
"""
from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


class WorldError(Exception):
    """Raised for invalid tool calls. The message is returned to the agent."""


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON schema for the arguments object
    hidden: bool = False  # hidden tools are available to proposer/verifier only


@dataclass
class ToolResult:
    ok: bool
    output: Any
    error: Optional[str] = None
    wall_ms: float = 0.0

    def to_json(self) -> Dict[str, Any]:
        return {"ok": self.ok, "output": self.output, "error": self.error, "wall_ms": self.wall_ms}


@dataclass
class CallRecord:
    step: int
    tool: str
    args: Dict[str, Any]
    result: ToolResult
    t: float


class World:
    """Base class. Subclasses implement `_build_initial_state` and tools.

    Tools are registered with `self.tool(...)` in `__init__` (after super().__init__).
    """

    name: str = "base"
    HIDDEN_PREFIX = "_"  # keys in state starting with this are hidden from the agent

    def __init__(self, seed: int = 0):
        self.seed = seed
        self._tools: Dict[str, ToolSpec] = {}
        self._impl: Dict[str, Callable[..., Any]] = {}
        self._state: Dict[str, Any] = {}
        self._log: List[CallRecord] = []
        self._step = 0
        self._register_tools()
        self.reset(seed)

    # ---- lifecycle -------------------------------------------------------
    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.seed = seed
        self._state = self._build_initial_state(self.seed)
        self._log = []
        self._step = 0

    def snapshot(self) -> Dict[str, Any]:
        return {"state": copy.deepcopy(self._state), "step": self._step, "seed": self.seed}

    def restore(self, snap: Dict[str, Any]) -> None:
        self._state = copy.deepcopy(snap["state"])
        self._step = snap["step"]
        self.seed = snap["seed"]
        self._log = []

    # ---- state views -----------------------------------------------------
    def state(self) -> Dict[str, Any]:
        """Full state including hidden keys. For verifier / proposer only."""
        return copy.deepcopy(self._state)

    def public_state(self) -> Dict[str, Any]:
        """State with hidden keys stripped (what the agent may inspect)."""
        return _strip_hidden(copy.deepcopy(self._state), self.HIDDEN_PREFIX)

    def log(self) -> List[CallRecord]:
        return list(self._log)

    # ---- tools -----------------------------------------------------------
    def tool(self, name: str, description: str, parameters: Dict[str, Any], hidden: bool = False):
        """Decorator to register a tool implementation."""

        def deco(fn: Callable[..., Any]):
            self._tools[name] = ToolSpec(name, description, parameters, hidden)
            self._impl[name] = fn
            return fn

        return deco

    def tools(self, include_hidden: bool = False) -> List[ToolSpec]:
        return [t for t in self._tools.values() if include_hidden or not t.hidden]

    def tool_schemas(self, include_hidden: bool = False) -> List[Dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.parameters}
            for t in self.tools(include_hidden)
        ]

    def call(self, name: str, args: Optional[Dict[str, Any]] = None, *, allow_hidden: bool = False) -> ToolResult:
        args = args or {}
        t0 = time.perf_counter()
        spec = self._tools.get(name)
        if spec is None or (spec.hidden and not allow_hidden):
            res = ToolResult(False, None, f"unknown tool: {name}")
        else:
            try:
                out = self._impl[name](**args)
                json.dumps(out)  # tool outputs must be JSON-serialisable
                res = ToolResult(True, out)
            except WorldError as e:
                res = ToolResult(False, None, str(e))
            except TypeError as e:
                res = ToolResult(False, None, f"bad arguments for {name}: {e}")
            except Exception as e:  # noqa: BLE001 - surfaced to agent as error
                res = ToolResult(False, None, f"{type(e).__name__}: {e}")
        res.wall_ms = (time.perf_counter() - t0) * 1000
        self._step += 1
        self._log.append(CallRecord(self._step, name, copy.deepcopy(args), res, time.time()))
        return res

    # ---- to implement ----------------------------------------------------
    def _register_tools(self) -> None:
        raise NotImplementedError

    def _build_initial_state(self, seed: int) -> Dict[str, Any]:
        raise NotImplementedError

    def describe(self) -> str:
        """Natural-language description shown to proposer and solver."""
        return self.__doc__ or self.name


def _strip_hidden(obj: Any, prefix: str) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_hidden(v, prefix) for k, v in obj.items() if not str(k).startswith(prefix)}
    if isinstance(obj, list):
        return [_strip_hidden(v, prefix) for v in obj]
    return obj


def state_diff(before: Dict[str, Any], after: Dict[str, Any], path: str = "") -> List[Dict[str, Any]]:
    """Flat list of changes between two JSON states. Used by verifiers and
    collateral-damage detection."""
    changes: List[Dict[str, Any]] = []
    if isinstance(before, dict) and isinstance(after, dict):
        for k in sorted(set(before) | set(after)):
            p = f"{path}/{k}"
            if k not in before:
                changes.append({"op": "add", "path": p, "value": after[k]})
            elif k not in after:
                changes.append({"op": "remove", "path": p, "value": before[k]})
            else:
                changes.extend(state_diff(before[k], after[k], p))
    elif isinstance(before, list) and isinstance(after, list):
        # Lists of records keyed by "id" are diffed by id; otherwise by index.
        if before and after and all(isinstance(x, dict) and "id" in x for x in before + after):
            bm = {x["id"]: x for x in before}
            am = {x["id"]: x for x in after}
            for k in sorted(set(bm) | set(am), key=str):
                p = f"{path}/[id={k}]"
                if k not in bm:
                    changes.append({"op": "add", "path": p, "value": am[k]})
                elif k not in am:
                    changes.append({"op": "remove", "path": p, "value": bm[k]})
                else:
                    changes.extend(state_diff(bm[k], am[k], p))
        elif before != after:
            changes.append({"op": "replace", "path": path, "before": before, "after": after})
    elif before != after:
        changes.append({"op": "replace", "path": path, "before": before, "after": after})
    return changes
