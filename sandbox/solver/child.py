"""Entry point of the agent child process.

    python -m sandbox.solver.child --agent-dir DIR

Reads one JSON line {"task": {...}, "tools": [...], "llm": {...}} from stdin,
imports DIR/agent.py, calls agent.run(task, tools, env, llm) and reports.

The agent's stdout is redirected to stderr so that stray prints cannot corrupt
the protocol stream.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import traceback

from .protocol import EnvClient, recv, send


def _load_agent(agent_dir: str):
    path = os.path.join(agent_dir, "agent.py")
    spec = importlib.util.spec_from_file_location("agent_under_test", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, agent_dir)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    if not hasattr(mod, "run"):
        raise ImportError("agent.py must define run(task, tools, env, llm) -> str")
    return mod


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-dir", required=True)
    a = ap.parse_args()

    proto_out = sys.stdout
    proto_in = sys.stdin
    sys.stdout = sys.stderr  # agent prints go to stderr

    hello = recv(proto_in)
    if not hello or hello.get("type") != "hello":
        send(proto_out, {"type": "fatal", "error": "expected hello", "usage": {}})
        return
    task, tools, llm_cfg = hello["task"], hello["tools"], hello.get("llm", {})

    from sandbox.llm import get_llm

    llm = get_llm(llm_cfg.get("provider"), llm_cfg.get("model"), base_url=llm_cfg.get("base_url"))
    env = EnvClient(proto_in, proto_out)
    try:
        mod = _load_agent(a.agent_dir)
        answer = mod.run(task, tools, env, llm)
        send(proto_out, {"type": "done", "answer": str(answer)[:5000], "usage": llm.usage.to_json(),
                         "notes": getattr(mod, "NOTES", None)})
    except EnvClient.Aborted as e:
        send(proto_out, {"type": "done", "answer": f"[aborted: {e}]", "usage": llm.usage.to_json(), "notes": None})
    except Exception:  # noqa: BLE001
        send(proto_out, {"type": "fatal", "error": traceback.format_exc()[-4000:], "usage": llm.usage.to_json()})


if __name__ == "__main__":
    main()
