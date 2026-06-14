"""MCP-server rule + view + automation tool tests (PRJ-025 PI-189 slice 2).

Boots a FastMCP instance whose httpx client routes through an ASGITransport
into the FastAPI app, then exercises the three condition-carrying
design-record tool families end-to-end: MCP tool dispatch → REST endpoint →
access layer → SQLite, and the response envelope unwraps as expected.
"""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.mcp_server.server import build_server


@pytest.fixture
async def mcp_server(v2_env):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    http = httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=10.0,
        headers={"X-Engagement": "ENG-001"},
    )
    server = build_server(http=http)
    yield server
    await http.aclose()


async def _call(server, name: str, args: dict):
    result = await server.call_tool(name, args)
    if isinstance(result, tuple):
        content, structured = result
        if structured is not None:
            return structured.get("result", structured)
        result = content
    if not isinstance(result, list):
        return result
    parsed = []
    for block in result:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            parsed.append(json.loads(text))
        except json.JSONDecodeError:
            parsed.append(text)
    if not parsed:
        return None
    if len(parsed) == 1:
        return parsed[0]
    return parsed


async def test_condition_tools_registered(mcp_server):
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    for expected in (
        "get_rule",
        "list_rules",
        "create_rule",
        "update_rule",
        "delete_rule",
        "restore_rule",
        "get_view",
        "list_views",
        "create_view",
        "update_view",
        "delete_view",
        "restore_view",
        "get_automation",
        "list_automations",
        "create_automation",
        "update_automation",
        "delete_automation",
        "restore_automation",
    ):
        assert expected in names


async def test_rule_lifecycle_via_tools(mcp_server):
    e = await _call(
        mcp_server, "create_entity", {"name": "Opportunity", "description": "x"}
    )
    f = await _call(
        mcp_server,
        "create_field",
        {
            "entity_identifier": e["entity_identifier"],
            "name": "stage",
            "description": "y",
            "type": "text",
        },
    )
    created = await _call(
        mcp_server,
        "create_rule",
        {
            "name": "Stage required",
            "subject_type": "field",
            "subject_identifier": f["field_identifier"],
            "effect": "required_when",
            "condition": {"field": "stage", "op": "eq", "value": "won"},
        },
    )
    rul = created["rule_identifier"]
    assert rul.startswith("RUL-")
    assert created["rule_effect"] == "required_when"

    patched = await _call(
        mcp_server, "update_rule", {"identifier": rul, "status": "confirmed"}
    )
    assert patched["rule_status"] == "confirmed"

    await _call(mcp_server, "delete_rule", {"identifier": rul})
    restored = await _call(mcp_server, "restore_rule", {"identifier": rul})
    assert restored["rule_identifier"] == rul


async def test_view_lifecycle_via_tools(mcp_server):
    e = await _call(
        mcp_server, "create_entity", {"name": "Opportunity", "description": "x"}
    )
    created = await _call(
        mcp_server,
        "create_view",
        {
            "name": "Open opps",
            "entity": e["entity_identifier"],
            "columns": ["name", "stage"],
            "filter": {"any": [{"field": "stage", "op": "is_not_empty"}]},
            "sort_direction": "asc",
        },
    )
    vew = created["view_identifier"]
    assert vew.startswith("VEW-")
    assert created["view_columns"] == ["name", "stage"]

    listed = await _call(
        mcp_server, "list_views", {"entity": e["entity_identifier"]}
    )
    listed = listed if isinstance(listed, list) else [listed]
    assert vew in {v["view_identifier"] for v in listed}


async def test_automation_lifecycle_via_tools(mcp_server):
    e = await _call(
        mcp_server, "create_entity", {"name": "Opportunity", "description": "x"}
    )
    created = await _call(
        mcp_server,
        "create_automation",
        {
            "name": "Mark won",
            "entity": e["entity_identifier"],
            "trigger": "on_update",
            "actions": [{"type": "set_field", "field": "stage"}],
            "condition": {"field": "amount", "op": "gte", "value": 1000},
        },
    )
    aut = created["automation_identifier"]
    assert aut.startswith("AUT-")
    assert created["automation_trigger"] == "on_update"

    patched = await _call(
        mcp_server,
        "update_automation",
        {"identifier": aut, "notes": "reviewed"},
    )
    assert patched["automation_notes"] == "reviewed"
