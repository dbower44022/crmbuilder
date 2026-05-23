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
from crmbuilder_v2.mcp_server.middleware import SharedSecretMiddleware
from crmbuilder_v2.mcp_server.tools import register_tools


def build_server(
    http: httpx.AsyncClient | None = None,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    shared_secret: str | None = None,
) -> FastMCP:
    """Build an MCP server bound to ``http``.

    ``host`` and ``port`` are wired into the FastMCP instance so that
    when ``server.run("streamable-http")`` is invoked the HTTP transport
    binds the right address. They are ignored for stdio transport.

    When ``shared_secret`` is set (HTTP transport only), the FastMCP's
    ``streamable_http_app`` factory is wrapped so the returned Starlette
    app has :class:`SharedSecretMiddleware` registered before uvicorn
    serves it. The installed FastMCP SDK has no constructor
    ``middleware=`` kwarg and exposes no ``add_middleware`` method on
    the FastMCP class itself; the Starlette app returned by
    ``streamable_http_app()`` is the only registration surface, and
    ``Starlette.add_middleware()`` must be called before the app
    starts handling requests — which is the case here, since the wrap
    runs inside ``run_streamable_http_async`` before serving begins.
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
    if shared_secret:
        _install_shared_secret_middleware(server, shared_secret)
    client = http or httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0)
    register_tools(server, client)
    return server


def _install_shared_secret_middleware(server: FastMCP, secret: str) -> None:
    """Wrap ``server.streamable_http_app`` so the Starlette app it
    returns has :class:`SharedSecretMiddleware` registered.

    See ``build_server`` for the rationale on why wrapping the factory
    method is the chosen registration path.
    """
    original_factory = server.streamable_http_app

    def streamable_http_app_with_middleware(*args, **kwargs):
        app = original_factory(*args, **kwargs)
        app.add_middleware(SharedSecretMiddleware, expected_secret=secret)
        return app

    server.streamable_http_app = streamable_http_app_with_middleware  # type: ignore[method-assign]


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

    The streamable-http transport requires
    ``CRMBUILDER_V2_MCP_SHARED_SECRET`` to be set in the environment
    (DEC-204 second-layer auth). Startup hard-fails if it is not.
    """
    if transport == "stdio":
        server = build_server()
        server.run("stdio")
    elif transport == "streamable-http":
        settings = get_settings()
        if not settings.mcp_shared_secret:
            raise RuntimeError(
                "CRMBUILDER_V2_MCP_SHARED_SECRET must be set when "
                "transport is streamable-http (DEC-204 second-layer auth)"
            )
        server = build_server(
            host=host,
            port=port,
            shared_secret=settings.mcp_shared_secret,
        )
        server.run("streamable-http")
    else:
        raise ValueError(f"unknown MCP transport: {transport!r}")
