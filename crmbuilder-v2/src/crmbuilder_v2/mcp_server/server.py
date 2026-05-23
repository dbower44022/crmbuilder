"""MCP server entry point.

The server is a thin protocol adapter: it boots a FastMCP instance,
connects an ``httpx.Client`` to the configured REST API base URL, and
registers the tool surface defined in :mod:`crmbuilder_v2.mcp_server.tools`.

Local usage:

.. code-block:: shell

    crmbuilder-v2-api &                            # start the REST API
    crmbuilder-v2-mcp                              # stdio (Claude Desktop pipes here)
    crmbuilder-v2-mcp --transport streamable-http  # HTTP for cloudflared ingress
"""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

from crmbuilder_v2.config import get_settings
from crmbuilder_v2.mcp_server.tools import register_tools


def build_server(
    http: httpx.AsyncClient | None = None,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
) -> FastMCP:
    """Build an MCP server bound to ``http``.

    ``host`` and ``port`` are wired into the FastMCP instance so that
    when ``server.run("streamable-http")`` is invoked the HTTP transport
    binds the right address. They are ignored for stdio transport.
    """
    settings = get_settings()
    resolved_port = port if port is not None else settings.mcp_http_port
    server = FastMCP(
        "crmbuilder-v2",
        instructions=(
            "Tools for the CRMBuilder v2 storage system. Read and write "
            "the project's structured database — charter, status, "
            "decisions, sessions, risks, planning items, topics, and "
            "cross-entity references."
        ),
        host=host,
        port=resolved_port,
    )
    client = http or httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0)
    register_tools(server, client)
    return server


def main(
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int | None = None,
) -> None:
    """Run the MCP server on the chosen transport.

    ``transport`` is ``"stdio"`` (default — Claude Desktop pipes here)
    or ``"streamable-http"`` (FastMCP HTTP transport bound to
    ``host:port`` for cloudflared / Cloudflare Tunnel ingress; see
    PI-045). For ``streamable-http``, ``host`` is hardcoded to
    ``127.0.0.1`` by the CLI per DEC-202; exposing it as a setting
    would invite a future ``0.0.0.0`` foot-gun.
    """
    if transport == "stdio":
        server = build_server()
        server.run("stdio")
    elif transport == "streamable-http":
        server = build_server(host=host, port=port)
        server.run("streamable-http")
    else:
        raise ValueError(f"unknown MCP transport: {transport!r}")
