"""MCP-server association + engine_override tool tests (PRJ-025 PI-189).

Boots a FastMCP instance whose httpx client routes through an ASGITransport
into the FastAPI app, then exercises the two composite design-record tool
families end-to-end: MCP tool dispatch → REST endpoint → access layer →
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


async def test_composite_tools_registered(mcp_server):
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    for expected in (
        "get_association",
        "list_associations",
        "create_association",
        "update_association",
        "delete_association",
        "restore_association",
        "get_engine_override",
        "list_engine_overrides",
        "create_engine_override",
        "update_engine_override",
        "delete_engine_override",
        "restore_engine_override",
    ):
        assert expected in names


async def test_association_lifecycle_via_tools(mcp_server):
    a = await _call(
        mcp_server, "create_entity", {"name": "Mentor", "description": "x"}
    )
    b = await _call(
        mcp_server, "create_entity", {"name": "Mentee", "description": "y"}
    )
    created = await _call(
        mcp_server,
        "create_association",
        {
            "name": "Mentor assignment",
            "source_entity": a["entity_identifier"],
            "target_entity": b["entity_identifier"],
            "cardinality": "many_to_many",
            "source_role": "mentor",
        },
    )
    asn = created["association_identifier"]
    assert asn.startswith("ASN-")
    assert created["association_cardinality"] == "many_to_many"

    patched = await _call(
        mcp_server,
        "update_association",
        {"identifier": asn, "status": "confirmed"},
    )
    assert patched["association_status"] == "confirmed"

    await _call(mcp_server, "delete_association", {"identifier": asn})
    restored = await _call(
        mcp_server, "restore_association", {"identifier": asn}
    )
    assert restored["association_identifier"] == asn


async def test_engine_override_lifecycle_via_tools(mcp_server):
    created = await _call(
        mcp_server,
        "create_engine_override",
        {
            "target_engine": "espocrm",
            "subject_type": "field",
            "subject_identifier": "FLD-001",
            "attribute": "formula",
            "value": {"expr": "concat(a, b)"},
        },
    )
    ovr = created["override_identifier"]
    assert ovr.startswith("OVR-")
    assert created["override_value"] == {"expr": "concat(a, b)"}

    listed = await _call(
        mcp_server, "list_engine_overrides", {"target_engine": "espocrm"}
    )
    listed = listed if isinstance(listed, list) else [listed]
    assert ovr in {o["override_identifier"] for o in listed}

    patched = await _call(
        mcp_server,
        "update_engine_override",
        {"identifier": ovr, "notes": "pinned"},
    )
    assert patched["override_notes"] == "pinned"
