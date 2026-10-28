"""Provider-agnostic chat+tools LLM client with usage accounting.

Three backends:
  anthropic : Claude models via the anthropic SDK
  openai    : any OpenAI-compatible endpoint (OpenAI, vLLM, SGLang, Together...)
  mock      : deterministic scripted responses for offline tests

Selection via env: LLM_PROVIDER (anthropic|openai|mock), LLM_MODEL, LLM_BASE_URL.
Every call is metered into `Usage` so matched-budget baselines are possible.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolCall:
    id: str
    name: str
    args: Dict[str, Any]


@dataclass
class LLMResponse:
    text: str
    tool_calls: List[ToolCall]
    stop_reason: str
    raw: Any = None


@dataclass
class Usage:
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    wall_s: float = 0.0

    def add(self, inp: int, out: int, wall: float) -> None:
        self.calls += 1
        self.input_tokens += inp
        self.output_tokens += out
        self.wall_s += wall

    def to_json(self) -> Dict[str, Any]:
        return {"calls": self.calls, "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens, "wall_s": round(self.wall_s, 3)}

    @staticmethod
    def from_json(d: Dict[str, Any]) -> "Usage":
        return Usage(d.get("calls", 0), d.get("input_tokens", 0), d.get("output_tokens", 0), d.get("wall_s", 0.0))

    def __iadd__(self, other: "Usage") -> "Usage":
        self.calls += other.calls
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.wall_s += other.wall_s
        return self


# Messages use a neutral format:
#   {"role": "system"|"user"|"assistant"|"tool", "content": str,
#    "tool_calls": [ToolCall-dicts] (assistant), "tool_call_id": str (tool)}


class LLM:
    def __init__(self, model: str):
        self.model = model
        self.usage = Usage()

    def chat(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None,
             max_tokens: int = 2048, temperature: float = 0.0) -> LLMResponse:
        raise NotImplementedError

    def text(self, prompt: str, system: str = "", max_tokens: int = 2048, temperature: float = 0.0) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
        return self.chat(msgs, None, max_tokens=max_tokens, temperature=temperature).text


# --------------------------------------------------------------------------- anthropic
class AnthropicLLM(LLM):
    def __init__(self, model: str):
        super().__init__(model)
        import anthropic  # lazy

        self._c = anthropic.Anthropic()

    def chat(self, messages, tools=None, max_tokens=2048, temperature=0.0) -> LLMResponse:
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        conv: List[Dict[str, Any]] = []
        for m in messages:
            if m["role"] == "user":
                conv.append({"role": "user", "content": m["content"]})
            elif m["role"] == "assistant":
                blocks: List[Dict[str, Any]] = []
                if m.get("content"):
                    blocks.append({"type": "text", "text": m["content"]})
                for tc in m.get("tool_calls", []):
                    blocks.append({"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["args"]})
                conv.append({"role": "assistant", "content": blocks})
            elif m["role"] == "tool":
                block = {"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
                if conv and conv[-1]["role"] == "user" and isinstance(conv[-1]["content"], list):
                    conv[-1]["content"].append(block)
                else:
                    conv.append({"role": "user", "content": [block]})
        kwargs: Dict[str, Any] = dict(model=self.model, max_tokens=max_tokens, messages=conv, temperature=temperature)
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        t0 = time.time()
        r = self._c.messages.create(**kwargs)
        self.usage.add(r.usage.input_tokens, r.usage.output_tokens, time.time() - t0)
        text = "".join(b.text for b in r.content if b.type == "text")
        calls = [ToolCall(b.id, b.name, dict(b.input)) for b in r.content if b.type == "tool_use"]
        return LLMResponse(text, calls, r.stop_reason or "", raw=r)


# --------------------------------------------------------------------------- openai-compatible
class OpenAILLM(LLM):
    def __init__(self, model: str, base_url: Optional[str] = None):
        super().__init__(model)
        import openai  # lazy

        self._c = openai.OpenAI(base_url=base_url or os.environ.get("LLM_BASE_URL") or None,
                                api_key=os.environ.get("OPENAI_API_KEY", "EMPTY"))

    def chat(self, messages, tools=None, max_tokens=2048, temperature=0.0) -> LLMResponse:
        conv: List[Dict[str, Any]] = []
        for m in messages:
            if m["role"] == "assistant":
                d: Dict[str, Any] = {"role": "assistant", "content": m.get("content") or None}
                if m.get("tool_calls"):
                    d["tool_calls"] = [{"id": tc["id"], "type": "function",
                                        "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])}}
                                       for tc in m["tool_calls"]]
                conv.append(d)
            elif m["role"] == "tool":
                conv.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
            else:
                conv.append({"role": m["role"], "content": m["content"]})
        kwargs: Dict[str, Any] = dict(model=self.model, messages=conv, max_tokens=max_tokens, temperature=temperature)
        if tools:
            kwargs["tools"] = [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                                  "parameters": t["input_schema"]}} for t in tools]
        t0 = time.time()
        r = self._c.chat.completions.create(**kwargs)
        u = r.usage
        self.usage.add(getattr(u, "prompt_tokens", 0) or 0, getattr(u, "completion_tokens", 0) or 0, time.time() - t0)
        msg = r.choices[0].message
        calls = []
        for tc in msg.tool_calls or []:
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {"_raw": tc.function.arguments}
            calls.append(ToolCall(tc.id, tc.function.name, args))
        return LLMResponse(msg.content or "", calls, r.choices[0].finish_reason or "", raw=r)


# --------------------------------------------------------------------------- mock
class MockLLM(LLM):
    """Scripted LLM for offline tests.

    `script` is a callable (messages, tools) -> LLMResponse | str | list[ToolCall].
    Token usage is approximated by character counts so budgets still work.
    """

    def __init__(self, script: Optional[Callable[..., Any]] = None, model: str = "mock"):
        super().__init__(model)
        self.script = script or (lambda messages, tools: "")
        self.history: List[List[Dict[str, Any]]] = []

    def chat(self, messages, tools=None, max_tokens=2048, temperature=0.0) -> LLMResponse:
        self.history.append(messages)
        out = self.script(messages, tools)
        if isinstance(out, LLMResponse):
            resp = out
        elif isinstance(out, str):
            resp = LLMResponse(out, [], "end_turn")
        else:
            resp = LLMResponse("", list(out), "tool_use")
        inp = sum(len(str(m.get("content", ""))) for m in messages) // 4
        outp = (len(resp.text) + sum(len(json.dumps(tc.args)) for tc in resp.tool_calls)) // 4
        self.usage.add(inp, outp, 0.0)
        return resp


# --------------------------------------------------------------------------- factory
def get_llm(provider: Optional[str] = None, model: Optional[str] = None, **kw) -> LLM:
    provider = (provider or os.environ.get("LLM_PROVIDER") or "anthropic").lower()
    model = model or os.environ.get("LLM_MODEL") or {
        "anthropic": "claude-sonnet-4-5", "openai": "gpt-4.1-mini", "mock": "mock"}[provider]
    if provider == "anthropic":
        return AnthropicLLM(model)
    if provider == "openai":
        return OpenAILLM(model, kw.get("base_url"))
    if provider == "mock":
        script = kw.get("script")
        if script is None and os.environ.get("LLM_MOCK_SCRIPT"):
            # "package.module:callable" so a subprocess can load a scripted mock.
            import importlib

            mod_name, _, attr = os.environ["LLM_MOCK_SCRIPT"].partition(":")
            script = getattr(importlib.import_module(mod_name), attr)
            if isinstance(script, type):
                script = script()
        return MockLLM(script)
    raise ValueError(f"unknown LLM provider {provider}")
