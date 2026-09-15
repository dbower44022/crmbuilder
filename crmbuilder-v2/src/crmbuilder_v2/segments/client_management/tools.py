"""The Client Management connector tools (PI-508 / REQ-591): engagement
selection. ``mcp_server.tools`` appends these to the shared list, so tool
names are unchanged for the connector and the chat dispatcher.
"""

from __future__ import annotations

import inspect
from typing import Any

import httpx

from crmbuilder_v2.mcp_server._tooling import ToolDefinition, _is_write


def tool_definitions(http: httpx.AsyncClient) -> list[ToolDefinition]:
    """Build this segment's tools bound to ``http``."""

    async def select_engagement(engagement: str) -> Any:
        """Scope all subsequent tool calls to an engagement.

        ``engagement`` is an engagement identifier (``ENG-NNN``) or code
        (e.g. ``CRMBUILDER``). It is sent as the ``X-Engagement`` header on
        every following REST call until changed, mirroring the desktop's
        active-engagement context. Pass an empty string to clear it (leaving
        subsequent calls unscoped). The default comes from
        ``CRMBUILDER_V2_MCP_ENGAGEMENT``.
        """
        if engagement:
            http.headers["X-Engagement"] = engagement
        else:
            http.headers.pop("X-Engagement", None)
        return {"active_engagement": engagement or None}

    async def get_active_engagement() -> Any:
        """Return the engagement currently scoping tool calls.

        The value of the ``X-Engagement`` header sent on every REST call,
        or ``None`` when unscoped.
        """
        return {"active_engagement": http.headers.get("X-Engagement")}

    funcs = [select_engagement, get_active_engagement]
    return [
        ToolDefinition(
            name=f.__name__,
            func=f,
            description=inspect.getdoc(f) or "",
            is_write=_is_write(f.__name__),
        )
        for f in funcs
    ]
