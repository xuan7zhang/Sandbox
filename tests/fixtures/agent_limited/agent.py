"""Test fixture: like v0 but stops after MAX_ACTIONS tool calls, so tasks that
need more dependent actions fail. A mock improver that raises MAX_ACTIONS
therefore 'unlocks' harder tasks - a controlled stand-in for real scaffold
improvement, used to exercise acceptance / ANNECS / CMP logic offline."""
from __future__ import annotations

import json

MAX_ACTIONS = 2
NOTES = "limited agent"

FINISH = {"name": "finish", "description": "Done.",
          "input_schema": {"type": "object", "properties": {"report": {"type": "string"}}, "required": ["report"]}}


def run(task, tools, env, llm) -> str:
    messages = [{"role": "system", "content": "assistant"},
                {"role": "user", "content": f"World: {task.get('world_description', '')}\n\nTask: {task['instruction']}"}]
    actions = 0
    for _ in range(int(task.get("max_steps", 60)) + 5):
        resp = llm.chat(messages, list(tools) + [FINISH])
        messages.append({"role": "assistant", "content": resp.text,
                         "tool_calls": [{"id": tc.id, "name": tc.name, "args": tc.args} for tc in resp.tool_calls]})
        if not resp.tool_calls:
            return resp.text
        for tc in resp.tool_calls:
            if tc.name == "finish":
                return str(tc.args.get("report", ""))
            if actions >= MAX_ACTIONS:
                return "I did what I could."
            actions += 1
            r = env.call(tc.name, tc.args)
            content = json.dumps(r["output"], ensure_ascii=False) if r["ok"] else f"ERROR: {r['error']}"
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": content[:6000]})
    return "[max turns]"
