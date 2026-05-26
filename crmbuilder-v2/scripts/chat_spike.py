"""PI-052 Slice A terminal proof-of-concept (WT-048, DEC-261).

Blocking chat loop against the Anthropic API with three hand-defined
read-only governance tools (get_current_status, get_current_charter,
list_recent_sessions) dispatched against the local REST API at
127.0.0.1:8765. Throwaway code — Slice B is the first slice with
production code.
"""

from __future__ import annotations

import os
import sys

import anthropic
import httpx

API_BASE = "http://127.0.0.1:8765"
MODEL = "claude-opus-4-7"
SYSTEM = (
    "You are an assistant with read-only access to the crmbuilder v2 "
    "governance database via three tools: get_current_status, "
    "get_current_charter, and list_recent_sessions. Call them when the "
    "user asks about project state, governance principles, or recent "
    "session history. Answer concisely from tool results."
)

TOOLS = [
    {
        "name": "get_current_status",
        "description": "Return the current project status singleton.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_current_charter",
        "description": "Return the current charter singleton.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "list_recent_sessions",
        "description": "Return the most recent N sessions (default 3).",
        "input_schema": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 3}},
            "required": [],
        },
    },
]


def _unwrap(response: httpx.Response) -> object:
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body.get("data")


def get_current_status(http: httpx.Client) -> object:
    return _unwrap(http.get("/status"))


def get_current_charter(http: httpx.Client) -> object:
    return _unwrap(http.get("/charter"))


def list_recent_sessions(http: httpx.Client, limit: int = 3) -> object:
    return _unwrap(http.get("/orientation/recent-sessions", params={"limit": limit}))


def dispatch(name: str, args: dict, http: httpx.Client) -> object:
    if name == "get_current_status":
        return get_current_status(http)
    if name == "get_current_charter":
        return get_current_charter(http)
    if name == "list_recent_sessions":
        return list_recent_sessions(http, **args)
    raise ValueError(f"unknown tool: {name}")


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY not set", file=sys.stderr)
        return 1
    client = anthropic.Anthropic()
    http = httpx.Client(base_url=API_BASE, timeout=30.0)
    messages: list[dict] = []
    try:
        while True:
            try:
                user = input("> ").strip()
            except EOFError:
                print()
                return 0
            if not user:
                continue
            messages.append({"role": "user", "content": user})
            while True:
                response = client.messages.create(
                    model=MODEL, system=SYSTEM, tools=TOOLS,
                    messages=messages, max_tokens=8192,
                )
                messages.append({"role": "assistant", "content": response.content})
                if response.stop_reason != "tool_use":
                    text = "".join(b.text for b in response.content if b.type == "text")
                    print(text)
                    break
                tool_results = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    print(f"→ {block.name}({block.input})", file=sys.stderr)
                    try:
                        result = dispatch(block.name, dict(block.input), http)
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": block.id,
                            "content": repr(result),
                        })
                    except Exception as exc:
                        tool_results.append({
                            "type": "tool_result", "tool_use_id": block.id,
                            "content": f"error: {exc}", "is_error": True,
                        })
                messages.append({"role": "user", "content": tool_results})
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
