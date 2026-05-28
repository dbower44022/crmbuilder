"""Chat tool dispatcher (PI-052 Slice B).

Slice B wires exactly one tool — ``get_current_status`` — dispatched
against the existing FastAPI surface at ``127.0.0.1:8765``. The schema
lives in a module-level ``TOOL_DEFINITIONS: list[dict]`` constant rather
than being hardcoded inside :func:`invoke`. This is the forward-
compatible shape called out in the kickoff's open question: Slice C
replaces the constant with the output of the shared ``tool_definitions()``
helper (design doc Appendix A) and grows :func:`invoke`'s dispatch table
to all 44 tools, leaving the rest of the chat module untouched.

No read/write partition here — that machinery lands in Slice C when
there are 44 tools to partition for the mode toggle.
"""

from __future__ import annotations

from typing import Any

import httpx

# Anthropic-API ``tools=[...]`` block. Slice C replaces this with the
# auto-generated definitions from ``crmbuilder_v2.mcp_server`` per the
# refactor in design doc Appendix A.
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_current_status",
        "description": (
            "Return the current crmbuilder v2 governance project status singleton."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]


def _unwrap(response: httpx.Response) -> Any:
    """Raise on transport / envelope errors, else return the ``data`` field.

    Mirrors the REST envelope contract (``{data, meta, errors}``) used by
    the Slice A spike and the storage client.
    """
    response.raise_for_status()
    body = response.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body.get("data")


async def invoke(name: str, args: dict[str, Any], http: httpx.AsyncClient) -> Any:
    """Dispatch a tool call to the REST API and return its unwrapped data.

    ``http`` is the worker thread's ``httpx.AsyncClient`` (base_url points
    at the local API). Slice B knows one tool; an unknown name raises so
    the worker can feed an ``is_error`` tool_result back to Claude.
    """
    if name == "get_current_status":
        return _unwrap(await http.get("/status"))
    raise ValueError(f"unknown tool: {name}")


def summarize_result(name: str, result: Any) -> str:
    """Build the one-line collapsed summary shown on a ``ToolResultItem``.

    Kept deliberately generic so Slice C's larger tool surface gets a
    reasonable default without a per-tool table.
    """
    if isinstance(result, dict):
        version = result.get("version")
        if version is not None:
            return f"{name} → version {version} ({len(result)} fields)"
        return f"{name} → {len(result)} fields"
    if isinstance(result, list):
        return f"{name} → {len(result)} items"
    return f"{name} → {result!r}"
