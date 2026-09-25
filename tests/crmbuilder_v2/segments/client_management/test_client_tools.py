"""Connector tools for clients (PI-512 / REQ-589): ``list_clients``,
``get_client``, and ``get_active_engagement`` naming the primary client;
and ``list_applications`` (PI-575 / REQ-653)."""

from __future__ import annotations

import json

import httpx
from crmbuilder_v2.mcp_server.tools import tool_definitions


def _tool(funcs, name):
    return next(f for f in funcs if f.name == name)


def _envelope(data) -> httpx.Response:
    return httpx.Response(200, json={"data": data, "meta": {}, "errors": None})


def _store(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path == "/clients":
        return _envelope(
            [
                {"client_identifier": "CLI-001", "client_name": "A", "engagements": ["ENG-002"]},
            ]
        )
    if path == "/clients/CLI-001":
        return _envelope({"client_identifier": "CLI-001", "client_name": "A", "engagements": ["ENG-002"]})
    if path == "/engagements/ENG-002/clients":
        return _envelope(
            {
                "engagement": "ENG-002",
                "clients": [{"client_identifier": "CLI-001", "client_name": "A", "is_primary": True}],
                "primary": "CLI-001",
            }
        )
    if path == "/engagements/ENG-003/clients":
        return _envelope({"engagement": "ENG-003", "clients": [], "primary": None})
    if path == "/applications":
        record = {
            "engagement_identifier": "ENG-002",
            "engagement_defining_client": "CLI-001",
            "engagement_defining_client_name": "A",
            "engagement_visibility": "private",
        }
        if request.url.params.get("client") == "CLI-404":
            return httpx.Response(
                404, json={"data": None, "meta": {}, "errors": [{"code": "not_found"}]}
            )
        return _envelope([dict(record, filtered=request.url.params.get("client"))])
    if path == "/applications/ENG-002":
        return _envelope({"engagement_identifier": "ENG-002", "engagement_defining_client": "CLI-001", "engagement_visibility": "private"})
    if path == "/deployments":
        return _envelope([
            {
                "deployment_identifier": "DPL-001",
                "deployment_application": "ENG-002",
                "deployment_client": "CLI-001",
                "deployment_purpose": "client_own",
                "params": dict(request.url.params),
            }
        ])
    if path == "/deployments/DPL-001":
        return _envelope({"deployment_identifier": "DPL-001", "deployment_purpose": "client_own", "instance": {"instance_identifier": "INST-001"}, "provider_credentials": []})
    return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "not_found"}]})


async def test_application_and_deployment_read_tools():
    """PI-580: get_application, list_deployments (purpose on every row, the
    three filters) and get_deployment are read tools."""
    http = httpx.AsyncClient(base_url="http://testserver", transport=httpx.MockTransport(_store))
    try:
        funcs = tool_definitions(http)
        get_app = _tool(funcs, "get_application")
        assert not get_app.is_write
        assert (await get_app.func("ENG-002"))["engagement_defining_client"] == "CLI-001"
        listed = _tool(funcs, "list_deployments")
        assert not listed.is_write
        rows = await listed.func()
        assert rows[0]["deployment_purpose"] == "client_own" and rows[0]["params"] == {}
        rows = await listed.func(application="ENG-002", client="CLI-001", for_client="CLI-003", include_deleted=True)
        assert rows[0]["params"] == {"application": "ENG-002", "client": "CLI-001", "for_client": "CLI-003", "include_deleted": "true"}
        one = await _tool(funcs, "get_deployment").func("DPL-001")
        assert one["instance"]["instance_identifier"] == "INST-001"
        assert {"get_application", "list_deployments", "get_deployment"} <= {f.name for f in funcs}
    finally:
        await http.aclose()


async def test_list_and_get_client_tools():
    http = httpx.AsyncClient(base_url="http://testserver", transport=httpx.MockTransport(_store))
    try:
        funcs = tool_definitions(http)
        names = {f.name for f in funcs}
        assert {"list_clients", "get_client"} <= names
        assert not _tool(funcs, "list_clients").is_write
        listed = await _tool(funcs, "list_clients").func()
        assert listed[0]["engagements"] == ["ENG-002"]
        one = await _tool(funcs, "get_client").func("CLI-001")
        assert one["client_name"] == "A"
    finally:
        await http.aclose()


async def test_list_applications_tool():
    http = httpx.AsyncClient(base_url="http://testserver", transport=httpx.MockTransport(_store))
    try:
        funcs = tool_definitions(http)
        tool = _tool(funcs, "list_applications")
        assert not tool.is_write
        listed = await tool.func()
        assert listed[0]["engagement_defining_client"] == "CLI-001"
        assert listed[0]["engagement_visibility"] == "private"
        assert listed[0]["filtered"] is None
        narrowed = await tool.func(client="CLI-001")
        assert narrowed[0]["filtered"] == "CLI-001"
    finally:
        await http.aclose()


async def test_get_active_engagement_names_primary_client():
    http = httpx.AsyncClient(base_url="http://testserver", transport=httpx.MockTransport(_store))
    try:
        funcs = tool_definitions(http)
        select = _tool(funcs, "select_engagement").func
        get_active = _tool(funcs, "get_active_engagement").func
        assert await get_active() == {"active_engagement": None, "primary_client": None}
        await select("ENG-002")
        answer = await get_active()
        assert answer["active_engagement"] == "ENG-002"
        assert answer["primary_client"]["client_identifier"] == "CLI-001"
        await select("ENG-003")
        assert (await get_active())["primary_client"] is None
    finally:
        await http.aclose()


async def test_get_active_engagement_survives_an_unreachable_store():
    http = httpx.AsyncClient(base_url="http://127.0.0.1:1")
    try:
        funcs = tool_definitions(http)
        await _tool(funcs, "select_engagement").func("ENG-002")
        answer = await _tool(funcs, "get_active_engagement").func()
        assert answer == {"active_engagement": "ENG-002", "primary_client": None}
    finally:
        await http.aclose()


def test_tool_docstrings_are_plain_text():
    funcs = tool_definitions(httpx.AsyncClient(base_url="http://testserver"))
    for name in ("list_clients", "get_client"):
        assert json.dumps(_tool(funcs, name).description)
