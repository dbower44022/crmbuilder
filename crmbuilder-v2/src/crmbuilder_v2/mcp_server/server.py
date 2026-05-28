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


def _build_auth():
    """Build (provider, AuthSettings) for the OAuth-enabled HTTP transport.

    Returns ``(None, None)`` when OAuth is disabled or Google credentials
    are unconfigured, so the server can still boot unauthenticated (e.g. a
    purely local probe). ``issuer_url`` and ``resource_server_url`` are both
    the public MCP URL — we are simultaneously the authorization server and
    the protected resource, and that URL must equal what claude.ai users
    enter as the connector URL (it becomes the PRM ``resource``).
    """
    from mcp.server.auth.settings import (
        AuthSettings,
        ClientRegistrationOptions,
        RevocationOptions,
    )

    from crmbuilder_v2.mcp_server.auth import CRMBuilderOAuthProvider

    settings = get_settings()
    if not settings.oauth_enabled:
        return None, None
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError(
            "OAuth is enabled but Google credentials are unset. Set "
            "CRMBUILDER_V2_GOOGLE_CLIENT_ID and "
            "CRMBUILDER_V2_GOOGLE_CLIENT_SECRET, or set "
            "CRMBUILDER_V2_OAUTH_ENABLED=false for an unauthenticated server."
        )
    provider = CRMBuilderOAuthProvider(settings)
    auth_settings = AuthSettings(
        issuer_url=settings.mcp_public_url,
        resource_server_url=settings.mcp_public_url,
        client_registration_options=ClientRegistrationOptions(enabled=True),
        revocation_options=RevocationOptions(enabled=True),
    )
    return provider, auth_settings


def build_server(
    http: httpx.AsyncClient | None = None,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    enable_auth: bool = False,
) -> FastMCP:
    """Build an MCP server bound to ``http``.

    ``host`` and ``port`` are wired into the FastMCP instance so that
    when ``server.run("streamable-http")`` is invoked the HTTP transport
    binds the right address. They are ignored for stdio transport.

    ``streamable_http_path`` is set to ``"/"`` so the MCP transport
    mounts at the application root, making the URL claude.ai users enter —
    ``https://mcp.crmbuilder.ai`` — match the emitted Protected Resource
    Metadata ``resource`` field exactly (Anthropic's connector spec
    requires this).

    When ``enable_auth`` is true (the HTTP transport path), the server runs
    its own OAuth 2.1 + PKCE authorization server (Google-backed) instead of
    relying on an external one — see :mod:`crmbuilder_v2.mcp_server.auth`.
    stdio transport is always unauthenticated.
    """
    settings = get_settings()
    resolved_port = port if port is not None else settings.mcp_http_port
    provider, auth_settings = (_build_auth() if enable_auth else (None, None))
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
        streamable_http_path="/",
        auth_server_provider=provider,
        auth=auth_settings,
    )
    client = http or httpx.AsyncClient(base_url=settings.api_base_url, timeout=30.0)
    register_tools(server, client)
    if provider is not None:
        from crmbuilder_v2.mcp_server.auth import register_oauth_routes

        register_oauth_routes(server, provider)
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

    For ``streamable-http`` the server runs its own OAuth 2.1 + PKCE
    authorization server (Google-backed; see
    :mod:`crmbuilder_v2.mcp_server.auth`) so claude.ai can register a custom
    connector and authenticate. This replaced Cloudflare Managed OAuth,
    whose Beta dropped the per-request ``resource``/``code_challenge`` params
    across its login step. stdio (Claude Desktop) remains unauthenticated.
    """
    if transport == "stdio":
        server = build_server()
        server.run("stdio")
    elif transport == "streamable-http":
        server = build_server(host=host, port=port, enable_auth=True)
        server.run("streamable-http")
    else:
        raise ValueError(f"unknown MCP transport: {transport!r}")
