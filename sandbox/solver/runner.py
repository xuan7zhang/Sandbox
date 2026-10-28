"""Host-side episode runner.

Runs an agent directory against a world for one task and returns an
`EpisodeResult` with the authoritative trajectory, final state, usage and
limit flags. Two modes:

  isolate=True  (default): agent runs in a subprocess speaking the JSON-lines
                 protocol; it never sees the world object or hidden state.
  isolate=False: agent runs in-process with an in-memory EnvClient. Used for
                 tests with a scripted MockLLM. Not for untrusted agent code.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..llm import LLM, Usage
from ..world.base import World
from .protocol import EnvClient, recv, send


@dataclass
class EpisodeResult:
    task_id: str
    agent_version: str
    answer: str
    trajectory: List[Dict[str, Any]]  # host-recorded tool calls
    initial_state: Dict[str, Any]
    final_state: Dict[str, Any]
    usage: Usage
    steps: int
    wall_s: float
    status: str  # "done" | "fatal" | "timeout" | "step_limit"
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    notes: Any = None

    def to_json(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id, "agent_version": self.agent_version, "answer": self.answer,
            "trajectory": self.trajectory, "usage": self.usage.to_json(), "steps": self.steps,
            "wall_s": round(self.wall_s, 3), "status": self.status, "error": self.error,
            "logs": self.logs[-50:], "notes": self.notes,
        }


# --------------------------------------------------------------------------- shared tool serving
class _Host:
    def __init__(self, world: World, max_steps: int, forbidden_tools: Optional[List[str]] = None):
        self.world = world
        self.max_steps = max_steps
        self.forbidden = set(forbidden_tools or [])
        self.trajectory: List[Dict[str, Any]] = []
        self.hit_step_limit = False

    def serve(self, tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if len(self.trajectory) >= self.max_steps:
            self.hit_step_limit = True
            return {"ok": False, "output": None, "error": "step limit reached", "_abort": True}
        if tool in self.forbidden or tool.startswith(World.HIDDEN_PREFIX):
            res = {"ok": False, "output": None, "error": f"tool '{tool}' is not available"}
            self.trajectory.append({"step": len(self.trajectory) + 1, "tool": tool, "args": args,
                                    "ok": False, "error": res["error"], "forbidden": True, "wall_ms": 0.0})
            return res
        r = self.world.call(tool, args)
        self.trajectory.append({"step": len(self.trajectory) + 1, "tool": tool, "args": args, "ok": r.ok,
                                "error": r.error, "wall_ms": round(r.wall_ms, 3),
                                "output_preview": _preview(r.output)})
        return {"ok": r.ok, "output": r.output, "error": r.error}


def _preview(x: Any, n: int = 300) -> str:
    try:
        s = json.dumps(x, ensure_ascii=False)
    except TypeError:
        s = str(x)
    return s if len(s) <= n else s[:n] + "..."


# --------------------------------------------------------------------------- public API
def run_episode(agent_dir: str, world: World, task: Dict[str, Any], *, agent_version: str = "?",
                llm: Optional[LLM] = None, llm_cfg: Optional[Dict[str, Any]] = None, max_steps: int = 60,
                timeout_s: float = 600.0, isolate: bool = True,
                forbidden_tools: Optional[List[str]] = None) -> EpisodeResult:
    initial = world.state()
    tools = world.tool_schemas(include_hidden=False)
    host = _Host(world, max_steps, forbidden_tools)
    t0 = time.time()
    if isolate:
        out = _run_subprocess(agent_dir, host, task, tools, llm_cfg or {}, timeout_s)
    else:
        if llm is None:
            raise ValueError("in-process mode needs an llm object")
        out = _run_inprocess(agent_dir, host, task, tools, llm, timeout_s)
    wall = time.time() - t0
    status = out["status"]
    if host.hit_step_limit and status == "done":
        status = "step_limit"
    return EpisodeResult(
        task_id=task.get("id", "?"), agent_version=agent_version, answer=out.get("answer", ""),
        trajectory=host.trajectory, initial_state=initial, final_state=world.state(),
        usage=Usage.from_json(out.get("usage", {})), steps=len(host.trajectory), wall_s=wall, status=status,
        error=out.get("error"), logs=out.get("logs", []), notes=out.get("notes"),
    )


# --------------------------------------------------------------------------- subprocess mode
def _run_subprocess(agent_dir: str, host: _Host, task, tools, llm_cfg, timeout_s) -> Dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [_repo_root(), env.get("PYTHONPATH", "")]))
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-I", "-m", "sandbox.solver.child", "--agent-dir", os.path.abspath(agent_dir)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
        cwd=_scratch_dir(),
    )
    assert proc.stdin and proc.stdout and proc.stderr
    stderr_buf: List[str] = []
    threading.Thread(target=lambda: stderr_buf.extend(proc.stderr.read().splitlines()), daemon=True).start()  # type: ignore[union-attr]

    send(proc.stdin, {"type": "hello", "task": task, "tools": tools, "llm": llm_cfg})
    deadline = time.time() + timeout_s
    logs: List[str] = []
    result: Dict[str, Any] = {"status": "fatal", "error": "no result", "usage": {}}
    watchdog = threading.Timer(timeout_s, proc.kill)
    watchdog.start()
    try:
        while True:
            msg = recv(proc.stdout)
            if msg is None:
                if time.time() >= deadline:
                    result = {"status": "timeout", "error": f"timeout after {timeout_s}s", "usage": {}}
                break
            t = msg.get("type")
            if t == "call":
                r = host.serve(msg.get("tool", ""), msg.get("args") or {})
                if r.pop("_abort", False):
                    send(proc.stdin, {"type": "abort", "reason": r["error"]})
                else:
                    send(proc.stdin, {"type": "result", "id": msg.get("id"), **r})
            elif t == "log":
                logs.append(msg.get("msg", ""))
            elif t == "done":
                result = {"status": "done", "answer": msg.get("answer", ""), "usage": msg.get("usage", {}),
                          "notes": msg.get("notes")}
                break
            elif t == "fatal":
                result = {"status": "fatal", "error": msg.get("error"), "usage": msg.get("usage", {})}
                break
            else:
                logs.append(f"[garbage] {msg}")
    finally:
        watchdog.cancel()
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    result["logs"] = logs + [f"[stderr] {l}" for l in stderr_buf[-30:]]
    return result


# --------------------------------------------------------------------------- in-process mode
class _InMemoryEnv(EnvClient):
    def __init__(self, host: _Host):
        self._host = host
        self.calls = 0
        self.logs: List[str] = []

    def call(self, tool: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self.calls += 1
        r = self._host.serve(tool, args or {})
        if r.pop("_abort", False):
            raise EnvClient.Aborted(r["error"])
        return r

    def log(self, msg: str) -> None:
        self.logs.append(str(msg)[:2000])


def _run_inprocess(agent_dir: str, host: _Host, task, tools, llm: LLM, timeout_s) -> Dict[str, Any]:
    env = _InMemoryEnv(host)
    path = os.path.join(agent_dir, "agent.py")
    spec = importlib.util.spec_from_file_location(f"agent_{abs(hash(path))}", path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        answer = mod.run(task, tools, env, llm)
        return {"status": "done", "answer": str(answer)[:5000], "usage": llm.usage.to_json(),
                "notes": getattr(mod, "NOTES", None), "logs": env.logs}
    except EnvClient.Aborted as e:
        return {"status": "done", "answer": f"[aborted: {e}]", "usage": llm.usage.to_json(), "logs": env.logs}
    except Exception as e:  # noqa: BLE001
        import traceback

        return {"status": "fatal", "error": traceback.format_exc()[-4000:], "usage": llm.usage.to_json(),
                "logs": env.logs}


# --------------------------------------------------------------------------- paths
def _repo_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _scratch_dir() -> str:
    d = os.environ.get("SANDBOX_SCRATCH") or os.path.join(os.path.expanduser("~"), ".rsi_sandbox", "scratch")
    os.makedirs(d, exist_ok=True)
    return d
