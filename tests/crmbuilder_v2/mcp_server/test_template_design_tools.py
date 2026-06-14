"""MCP-server dedup_rule + message_template tool tests (PRJ-025 PI-189 slice 3).

Boots a FastMCP instance whose httpx client routes through an ASGITransport
into the FastAPI app, then exercises the two dedup-and-template design-record
tool families end-to-end: MCP tool dispatch -> REST endpoint -> access layer ->
SQLite, and the response envelope unwraps as expected.
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


async def test_template_tools_registered(mcp_server):
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    for expected in (
        "get_dedup_rule",
        "list_dedup_rules",
        "create_dedup_rule",
        "update_dedup_rule",
        "delete_dedup_rule",
        "restore_dedup_rule",
        "get_message_template",
        "list_message_templates",
        "create_message_template",
        "update_message_template",
        "delete_message_template",
        "restore_message_template",
    ):
        assert expected in names


async def test_dedup_rule_lifecycle_via_tools(mcp_server):
    e = await _call(
        mcp_server, "create_entity", {"name": "Contact", "description": "x"}
    )
    created = await _call(
        mcp_server,
        "create_dedup_rule",
        {
            "name": "Email match",
            "entity": e["entity_identifier"],
            "match_fields": ["email"],
            "on_match": "block",
            "normalize": {"email": "lowercase"},
        },
    )
    dup = created["dedup_rule_identifier"]
    assert dup.startswith("DUP-")
    assert created["dedup_rule_on_match"] == "block"

    patched = await _call(
        mcp_server,
        "update_dedup_rule",
        {"identifier": dup, "status": "confirmed"},
    )
    assert patched["dedup_rule_status"] == "confirmed"

    listed = await _call(
        mcp_server, "list_dedup_rules", {"entity": e["entity_identifier"]}
    )
    listed = listed if isinstance(listed, list) else [listed]
    assert dup in {r["dedup_rule_identifier"] for r in listed}

    await _call(mcp_server, "delete_dedup_rule", {"identifier": dup})
    restored = await _call(
        mcp_server, "restore_dedup_rule", {"identifier": dup}
    )
    assert restored["dedup_rule_identifier"] == dup


async def test_message_template_lifecycle_via_tools(mcp_server):
    created = await _call(
        mcp_server,
        "create_message_template",
        {
            "name": "Welcome",
            "body": "Hello {{name}}",
            "channel": "email",
            "subject": "Welcome {{name}}",
            "merge_fields": ["name"],
        },
    )
    msg = created["message_template_identifier"]
    assert msg.startswith("MSG-")
    assert created["message_template_channel"] == "email"
    assert created["message_template_body"] == "Hello {{name}}"

    patched = await _call(
        mcp_server,
        "update_message_template",
        {"identifier": msg, "audience": "new contacts"},
    )
    assert patched["message_template_audience"] == "new contacts"

    got = await _call(
        mcp_server, "get_message_template", {"identifier": msg}
    )
    assert got["message_template_identifier"] == msg
