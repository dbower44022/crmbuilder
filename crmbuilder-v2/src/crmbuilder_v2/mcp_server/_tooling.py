"""The connector tool building blocks shared by the connector's own tool
list and every segment package's ``tools`` module (PI-508 / REQ-591).

Kept apart from ``mcp_server.tools`` so a package can import them without
importing the whole shared tool list.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

# Name-prefix → write classification (design §4). Consumed by the chat
# tool dispatcher's mode toggle (Full / Read-only / Ask before write).
_WRITE_PREFIXES = ("create_", "update_", "delete_", "add_", "replace_", "open_", "advance_")


def _is_write(name: str) -> bool:
    return name.startswith(_WRITE_PREFIXES)


@dataclass(frozen=True)
class ToolDefinition:
    """One governance tool: name, async callable, cleaned docstring, and
    read/write classification.

    The single source of truth shared by the MCP stdio/HTTP server
    (:func:`crmbuilder_v2.mcp_server.tools.register_tools`) and the chat
    UI's ``ChatToolDispatcher`` (Anthropic Messages API), so the two
    surfaces never drift.
    """

    name: str
    func: Callable[..., Any]
    description: str
    is_write: bool


async def _unwrap(response: httpx.Response) -> Any:
    """Pull the envelope's ``data`` field, or raise on error envelopes.

    A refused write must reach the caller saying which check it failed
    (REQ-586), so the error envelope is read before the status is raised on:
    the store answers a failed check with 422 and a list of field errors, and
    a bare "422 Unprocessable Entity" would throw that list away. A response
    that carries no readable envelope still raises the status error.
    """
    try:
        body = response.json()
    except ValueError:
        body = None
    if isinstance(body, dict) and body.get("errors"):
        raise RuntimeError(body["errors"])
    response.raise_for_status()
    if not isinstance(body, dict):
        return body
    return body.get("data")
