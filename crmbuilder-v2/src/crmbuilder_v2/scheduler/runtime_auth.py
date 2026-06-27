"""Orchestrator self-authentication for the ADO scheduler's REST calls (REQ-382).

The scheduler talks to the V2 API over HTTP (``dispatcher`` / ``agent_prompt`` /
``ado_scheduler``). When ``principal_auth_enabled`` is on, those calls must carry
the orchestrator's bearer token or they 401. This module is the single place
that builds the scheduler's request headers, mirroring the MCP server's
``Authorization: Bearer {mcp_token}`` pattern (``mcp_server/server.py``).

When ``Settings.orchestrator_token`` is empty (the default localhost flow with
auth off), no ``Authorization`` header is sent and behaviour is unchanged.
Side-band writes that go straight to the DB (``event_capture`` / ``cost_capture``
/ ``agent_identity``) bypass HTTP and need none of this.
"""

from __future__ import annotations


def auth_headers(engagement: str, *, content_type: bool = False) -> dict[str, str]:
    """Build the scheduler's request headers for ``engagement``.

    Always sets ``X-Engagement``; adds ``Content-Type: application/json`` when
    ``content_type`` is true; adds ``Authorization: Bearer <orchestrator_token>``
    when that token is configured (so the orchestrator authenticates as its own
    principal). Read fresh each call so a token set after import is honoured.
    """
    from crmbuilder_v2.config import get_settings

    headers = {"X-Engagement": engagement}
    if content_type:
        headers["Content-Type"] = "application/json"
    token = get_settings().orchestrator_token
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
