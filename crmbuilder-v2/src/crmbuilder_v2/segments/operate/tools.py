"""The Operate connector tools (PI-513 / REQ-591). Operate exposes no
connector tool today; the factory exists so the registry finds this segment
the same way as every other.
"""

from __future__ import annotations

import httpx

from crmbuilder_v2.mcp_server._tooling import ToolDefinition


def tool_definitions(http: httpx.AsyncClient) -> list[ToolDefinition]:
    """Build this segment's tools bound to ``http``: none today."""
    return []
