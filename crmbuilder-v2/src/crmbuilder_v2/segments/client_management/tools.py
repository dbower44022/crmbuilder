"""The Client Management connector tools (PI-508 / REQ-591): engagement
selection, the client records above the engagement (PI-512 / REQ-589), and
the application reading of the engagement (PI-575 / REQ-653).
``mcp_server.tools`` appends these to the shared list, so tool names are
unchanged for the connector and the chat dispatcher.
"""

from __future__ import annotations

import inspect
from typing import Any

import httpx

from crmbuilder_v2.mcp_server._tooling import ToolDefinition, _is_write, _unwrap


def tool_definitions(http: httpx.AsyncClient) -> list[ToolDefinition]:
    """Build this segment's tools bound to ``http``."""

    async def select_engagement(engagement: str) -> Any:
        """Scope all subsequent tool calls to one application.

        ``engagement`` is the application's identifier (``ENG-NNN``, the
        prefix the application record keeps internally) or its code (e.g.
        ``CRMBUILDER``). It is sent as the ``X-Engagement`` header on every
        following REST call until changed, mirroring the desktop's active
        application. Pass an empty string to clear it (leaving subsequent
        calls unscoped). The default comes from
        ``CRMBUILDER_V2_MCP_ENGAGEMENT``.
        """
        if engagement:
            http.headers["X-Engagement"] = engagement
        else:
            http.headers.pop("X-Engagement", None)
        return {"active_engagement": engagement or None}

    async def get_active_engagement() -> Any:
        """Return the application currently scoping tool calls, and the
        client that defines it.

        ``active_engagement`` is the value of the ``X-Engagement`` header
        sent on every REST call, or ``None`` when unscoped.
        ``primary_client`` is the client record that defines the
        application, or ``None`` when no client defines it or the store
        cannot be asked.
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
        """List client records (the organisations that define and deploy
        applications), each with the identifiers of the applications it
        defines under ``engagements``. Use it to find an application by
        client name before ``select_engagement``."""
        params = {"include_deleted": "true"} if include_deleted else None
        return await _unwrap(await http.get("/clients", params=params))

    async def get_client(identifier: str) -> Any:
        """Return one client record by its ``CLI-NNN`` identifier, with the
        identifiers of the applications it defines."""
        return await _unwrap(await http.get(f"/clients/{identifier}"))

    async def list_applications(
        client: str | None = None, include_deleted: bool = False
    ) -> Any:
        """List application records, each with ``engagement_defining_client``
        (a ``CLI-NNN`` identifier), ``engagement_defining_client_name`` and
        ``engagement_visibility`` (``private`` or ``public``). ``client``
        narrows the list to the applications that client defines. A record
        no client defines is not an application and is not listed here."""
        params: dict[str, str] = {}
        if client:
            params["client"] = client
        if include_deleted:
            params["include_deleted"] = "true"
        return await _unwrap(await http.get("/applications", params=params or None))

    async def get_application(identifier: str) -> Any:
        """Return one application record by its ``ENG-NNN`` identifier, with
        its defining client and visibility (PI-580 / REQ-653)."""
        return await _unwrap(await http.get(f"/applications/{identifier}"))

    async def list_deployments(
        application: str | None = None,
        client: str | None = None,
        for_client: str | None = None,
        include_deleted: bool = False,
    ) -> Any:
        """List deployment records (``DPL-NNN``): one installation of one
        application for one client on one hosting provider. Every row
        carries ``deployment_purpose`` (``client_own`` or ``demo_test``),
        ``deployment_application``, ``deployment_client``,
        ``deployment_hosting_provider``, ``deployment_status`` and the
        instance, deploy configuration and credential flags it holds.
        ``application`` and ``client`` narrow the list; ``for_client``
        returns what a client may see: its own deployments plus the
        demo/test deployment of every application it may deploy (REQ-654).
        """
        params: dict[str, str] = {}
        if application:
            params["application"] = application
        if client:
            params["client"] = client
        if for_client:
            params["for_client"] = for_client
        if include_deleted:
            params["include_deleted"] = "true"
        return await _unwrap(await http.get("/deployments", params=params or None))

    async def get_deployment(identifier: str) -> Any:
        """Return one deployment record by its ``DPL-NNN`` identifier, composed
        with the instance it holds, that instance's deploy configuration and
        the provider credentials that apply (never a token)."""
        return await _unwrap(await http.get(f"/deployments/{identifier}"))

    funcs = [
        select_engagement,
        get_active_engagement,
        list_clients,
        get_client,
        list_applications,
        get_application,
        list_deployments,
        get_deployment,
    ]
    return [
        ToolDefinition(
            name=f.__name__,
            func=f,
            description=inspect.getdoc(f) or "",
            is_write=_is_write(f.__name__),
        )
        for f in funcs
    ]
