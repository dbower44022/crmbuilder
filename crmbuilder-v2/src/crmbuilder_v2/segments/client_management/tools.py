"""The Client Management connector tools (PI-508 / REQ-591): engagement
selection, and the client records above the engagement (PI-512 / REQ-589). ``mcp_server.tools`` appends these to the shared list, so tool
names are unchanged for the connector and the chat dispatcher.
"""

from __future__ import annotations

import inspect
from typing import Any

import httpx

from crmbuilder_v2.mcp_server._tooling import ToolDefinition, _is_write, _unwrap


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
        """Return the engagement currently scoping tool calls, and its client.

        ``active_engagement`` is the value of the ``X-Engagement`` header
        sent on every REST call, or ``None`` when unscoped.
        ``primary_client`` is the client record the engagement primarily
        serves, or ``None`` when the engagement belongs to no client or the
        store cannot be asked.
        """
        active = http.headers.get("X-Engagement")
        primary: Any = None
        if active:
            try:
                answer = await _unwrap(await http.get(f"/engagements/{active}/clients"))
            except Exception:  # noqa: BLE001 - the header is the answer; the client is extra
                answer = None
            if isinstance(answer, dict):
                for record in answer.get("clients") or []:
                    if record.get("is_primary"):
                        primary = record
                        break
        return {"active_engagement": active or None, "primary_client": primary}

    async def list_clients(include_deleted: bool = False) -> Any:
        """List client records (the organisations above the engagements),
        each with the identifiers of the engagements it holds under
        ``engagements``. Use it to find an engagement by client name before
        ``select_engagement``."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(await http.get("/clients", params=params))

    async def get_client(identifier: str) -> Any:
        """Return one client record by its ``CLI-NNN`` identifier, with the
        identifiers of the engagements it holds."""
        return await _unwrap(await http.get(f"/clients/{identifier}"))

    funcs = [select_engagement, get_active_engagement, list_clients, get_client]
    return [
        ToolDefinition(
            name=f.__name__,
            func=f,
            description=inspect.getdoc(f) or "",
            is_write=_is_write(f.__name__),
        )
        for f in funcs
    ]
