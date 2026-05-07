"""MCP stdio server entry point.

The server is a thin protocol adapter: it boots a FastMCP instance,
connects an ``httpx.Client`` to the configured REST API base URL, and
registers the tool surface defined in :mod:`crmbuilder_v2.mcp_server.tools`.

Local usage:

.. code-block:: shell

    crmbuilder-v2-api &        # start the REST API
    crmbuilder-v2-mcp          # talk MCP over stdio (Claude Desktop pipes here)
"""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

from crmbuilder_v2.config import get_settings
from crmbuilder_v2.mcp_server.tools import register_tools


def build_server(http: httpx.AsyncClient | None = None) -> FastMCP:
    """Build an MCP server bound to ``http``. Used by both the CLI entry
    point and the smoke test."""
    server = FastMCP(
        "crmbuilder-v2",
        instructions=(
            "Tools for the CRMBuilder v2 storage system. Read and write "
            "the project's structured database — charter, status, "
            "decisions, sessions, risks, planning items, topics, and "
            "cross-entity references."
        ),
    )
    settings = get_settings()
    client = http or httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0)
    register_tools(server, client)
    return server


def main() -> None:
    server = build_server()
    server.run("stdio")
