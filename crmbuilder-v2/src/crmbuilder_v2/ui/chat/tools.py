"""Chat tool dispatcher (PI-052 Slice C).

The dispatcher is the chat UI's view of the governance tool surface. It
reads the single source of truth — ``crmbuilder_v2.mcp_server.tools.
tool_definitions(http)`` — and exposes it in two forms the chat loop
needs:

* :meth:`ChatToolDispatcher.tools_block` — the Anthropic Messages API
  ``tools=[...]`` block (``{name, description, input_schema}`` per tool),
  with input schemas generated from each callable's signature.
* :meth:`ChatToolDispatcher.invoke` — dispatch a tool call by name to the
  underlying coroutine (which wraps a REST endpoint via the worker's
  ``httpx.AsyncClient``).

Because both this dispatcher and the MCP stdio server consume the same
``tool_definitions`` list, the chat UI and Claude Desktop never drift.

The read/write partition (``read_names`` / ``write_names``) drives the
mode toggle: Read-only mode exposes only the read tools; Ask-before-write
mode exposes everything but the controller confirms each write call.
"""

from __future__ import annotations

import inspect
import types
import typing
from typing import Any

import httpx

from crmbuilder_v2.mcp_server.tools import ToolDefinition, tool_definitions

_JSON_TYPES: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    dict: "object",
    list: "array",
}


def _annotation_to_json_type(tp: Any) -> str:
    """Map a resolved type annotation to a JSONSchema scalar type name.

    Unwraps ``X | None`` to ``X`` and parameterized generics
    (``list[str]``, ``dict[str, Any]``) to their origin. Anything
    unrecognized falls back to ``"string"`` — safe because every tool
    argument is JSON-encoded on the wire anyway.
    """
    origin = typing.get_origin(tp)
    if origin in (typing.Union, types.UnionType):
        non_none = [a for a in typing.get_args(tp) if a is not type(None)]
        if non_none:
            return _annotation_to_json_type(non_none[0])
        return "string"
    if origin is not None:
        tp = origin
    return _JSON_TYPES.get(tp, "string")


def _schema_from_signature(func: Any) -> dict[str, Any]:
    """Build an Anthropic ``input_schema`` from a callable's signature.

    Required params are those without a default; optional params (those
    with a default, typically ``X | None = None``) are omitted from
    ``required``.
    """
    sig = inspect.signature(func)
    try:
        hints = typing.get_type_hints(func)
    except Exception:  # noqa: BLE001 — fall back to string-typed params
        hints = {}
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in sig.parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue
        tp = hints.get(name, str)
        properties[name] = {"type": _annotation_to_json_type(tp)}
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {"type": "object", "properties": properties, "required": required}


class ChatToolDispatcher:
    """Builds the Anthropic tools block and dispatches tool calls.

    Constructed inside the worker thread with that thread's
    ``httpx.AsyncClient`` so every tool call runs on the worker's event
    loop.
    """

    def __init__(self, http: httpx.AsyncClient) -> None:
        self._defs: dict[str, ToolDefinition] = {
            td.name: td for td in tool_definitions(http)
        }

    @property
    def read_names(self) -> set[str]:
        return {n for n, td in self._defs.items() if not td.is_write}

    @property
    def write_names(self) -> set[str]:
        return {n for n, td in self._defs.items() if td.is_write}

    def is_write(self, name: str) -> bool:
        td = self._defs.get(name)
        return bool(td and td.is_write)

    def tools_block(self, *, read_only: bool = False) -> list[dict[str, Any]]:
        """Return the Anthropic ``tools=[...]`` block.

        ``read_only=True`` excludes write tools (Read-only mode).
        """
        block: list[dict[str, Any]] = []
        for td in self._defs.values():
            if read_only and td.is_write:
                continue
            block.append(
                {
                    "name": td.name,
                    "description": td.description,
                    "input_schema": _schema_from_signature(td.func),
                }
            )
        return block

    async def invoke(self, name: str, args: dict[str, Any]) -> Any:
        """Dispatch a tool call to its coroutine and return the result."""
        td = self._defs.get(name)
        if td is None:
            raise ValueError(f"unknown tool: {name}")
        return await td.func(**args)


def summarize_result(name: str, result: Any) -> str:
    """One-line collapsed summary shown on a ``ToolResultItem``.

    Generic across the whole tool surface — picks an identifier/version
    when present, else reports shape.
    """
    if isinstance(result, dict):
        for key in ("identifier", "version", "id"):
            if key in result:
                return f"{name} → {key}={result[key]}"
        return f"{name} → {len(result)} fields"
    if isinstance(result, list):
        return f"{name} → {len(result)} items"
    if result is None:
        return f"{name} → ok"
    return f"{name} → {result!r}"
