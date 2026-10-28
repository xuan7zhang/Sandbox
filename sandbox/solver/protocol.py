"""JSON-lines protocol between the host (world + verifier) and the agent child.

The agent process never holds the world object, the verifier, or hidden state;
it only sees tool outputs. The host records the authoritative trajectory, so an
agent cannot forge its own log. All messages are single-line JSON.

child -> host : {"type": "call", "id": int, "tool": str, "args": {...}}
host  -> child: {"type": "result", "id": int, "ok": bool, "output": any, "error": str|null}
child -> host : {"type": "log", "msg": str}
child -> host : {"type": "done", "answer": str, "usage": {...}, "notes": any}
child -> host : {"type": "fatal", "error": str, "usage": {...}}
host  -> child: {"type": "abort", "reason": str}   (sent as a result to any call)
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional, TextIO


def send(fp: TextIO, msg: Dict[str, Any]) -> None:
    fp.write(json.dumps(msg, ensure_ascii=False) + "\n")
    fp.flush()


def recv(fp: TextIO) -> Optional[Dict[str, Any]]:
    line = fp.readline()
    if not line:
        return None
    line = line.strip()
    if not line:
        return recv(fp)
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return {"type": "garbage", "raw": line[:500]}


class EnvClient:
    """Agent-side handle. `call` is the only way to touch the world."""

    class Aborted(Exception):
        pass

    def __init__(self, inp: TextIO, out: TextIO):
        self._in = inp
        self._out = out
        self._n = 0
        self.calls = 0

    def call(self, tool: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._n += 1
        self.calls += 1
        send(self._out, {"type": "call", "id": self._n, "tool": tool, "args": args or {}})
        while True:
            msg = recv(self._in)
            if msg is None:
                raise EnvClient.Aborted("host closed connection")
            if msg.get("type") == "abort":
                raise EnvClient.Aborted(msg.get("reason", "aborted"))
            if msg.get("type") == "result" and msg.get("id") == self._n:
                return {"ok": msg["ok"], "output": msg.get("output"), "error": msg.get("error")}

    def log(self, msg: str) -> None:
        send(self._out, {"type": "log", "msg": str(msg)[:2000]})
