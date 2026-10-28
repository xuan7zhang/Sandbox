"""Agent v0: minimal tool-use loop. This file is the object of self-improvement.

Contract (must be preserved by any self-modification):
    run(task: dict, tools: list[dict], env, llm) -> str
      task  : {"id", "instruction", "world", "max_steps", ...}
      tools : JSON-schema tool list, format {"name","description","input_schema"}
      env   : env.call(tool_name, args_dict) -> {"ok","output","error"}; env.log(msg)
      llm   : llm.chat(messages, tools) -> LLMResponse(text, tool_calls[ToolCall(id,name,args)], stop_reason)
    Returns the agent's final answer / report as a string.

Optional: a module-level NOTES string is returned to the archive for diagnostics.
"""
from __future__ import annotations

import json

NOTES = "v0: plain ReAct loop, no memory, no verification of own work"

SYSTEM = """You are an operations assistant acting inside a company's software system through tools.
Complete the user's task fully and precisely. Inspect state before changing it. When you are
done, call the `finish` tool with a short report of what you did. Do not call `finish` until
every requirement of the task is satisfied."""

FINISH = {
    "name": "finish",
    "description": "Call when the task is complete. Give a concise report of what was done.",
    "input_schema": {"type": "object", "properties": {"report": {"type": "string"}}, "required": ["report"]},
}


def run(task, tools, env, llm) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"World: {task.get('world_description', '')}\n\nTask: {task['instruction']}"},
    ]
    all_tools = list(tools) + [FINISH]
    max_turns = int(task.get("max_steps", 60)) + 5
    for _ in range(max_turns):
        resp = llm.chat(messages, all_tools)
        messages.append({"role": "assistant", "content": resp.text,
                         "tool_calls": [{"id": tc.id, "name": tc.name, "args": tc.args} for tc in resp.tool_calls]})
        if not resp.tool_calls:
            # Model answered in text without finishing; nudge once, then stop.
            messages.append({"role": "user", "content": "If the task is complete call `finish`, otherwise continue."})
            if resp.text.strip() and _nudged(messages):
                return resp.text
            continue
        for tc in resp.tool_calls:
            if tc.name == "finish":
                return str(tc.args.get("report", ""))
            r = env.call(tc.name, tc.args)
            content = json.dumps(r["output"], ensure_ascii=False) if r["ok"] else f"ERROR: {r['error']}"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content[:6000]})
    return "[max turns reached]"


def _nudged(messages) -> bool:
    return sum(1 for m in messages if m["role"] == "user" and m["content"].startswith("If the task is complete")) >= 2
