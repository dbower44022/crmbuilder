"""MCP-server entity + field tool tests (PI-181).

Boots a FastMCP instance whose httpx client routes through an
ASGITransport into the FastAPI app, then exercises the entity and field
methodology tools end-to-end: MCP tool dispatch → REST endpoint → access
layer → SQLite database, and the response envelope unwraps as expected.
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
        # PI-β: name the engagement per request; v2_env seeds ENG-001.
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


async def test_entity_and_field_tools_registered(mcp_server):
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    for expected in (
        "get_entity",
        "list_entities",
        "create_entity",
        "update_entity",
        "delete_entity",
        "restore_entity",
        "get_field",
        "list_fields",
        "create_field",
        "update_field",
        "delete_field",
        "restore_field",
    ):
        assert expected in names


async def test_entity_lifecycle(mcp_server):
    created = await _call(
        mcp_server,
        "create_entity",
        {"name": "Mentor", "description": "A person who mentors."},
    )
    ident = created["entity_identifier"]
    assert ident.startswith("ENT-")
    assert created["entity_name"] == "Mentor"

    fetched = await _call(mcp_server, "get_entity", {"identifier": ident})
    assert fetched["entity_identifier"] == ident

    listed = await _call(mcp_server, "list_entities", {})
    listed = listed if isinstance(listed, list) else [listed]
    assert ident in {e["entity_identifier"] for e in listed}

    patched = await _call(
        mcp_server,
        "update_entity",
        {"identifier": ident, "description": "Updated description."},
    )
    assert patched["entity_description"] == "Updated description."

    await _call(mcp_server, "delete_entity", {"identifier": ident})
    restored = await _call(mcp_server, "restore_entity", {"identifier": ident})
    assert restored["entity_identifier"] == ident


async def test_create_field_establishes_parent_edge(mcp_server):
    entity = await _call(
        mcp_server,
        "create_entity",
        {"name": "Mentee", "description": "A person being mentored."},
    )
    ent_id = entity["entity_identifier"]

    field = await _call(
        mcp_server,
        "create_field",
        {
            "entity_identifier": ent_id,
            "name": "preferredName",
            "description": "What the mentee likes to be called.",
            "type": "text",
        },
    )
    fld_id = field["field_identifier"]
    assert fld_id.startswith("FLD-")

    # The mandatory field_belongs_to_entity edge is established atomically:
    # the entity-filtered list returns the new field.
    scoped = await _call(
        mcp_server, "list_fields", {"entity_identifier": ent_id}
    )
    scoped = scoped if isinstance(scoped, list) else [scoped]
    assert fld_id in {f["field_identifier"] for f in scoped}


async def test_field_lifecycle(mcp_server):
    entity = await _call(
        mcp_server,
        "create_entity",
        {"name": "Engagement", "description": "A mentoring engagement."},
    )
    ent_id = entity["entity_identifier"]
    field = await _call(
        mcp_server,
        "create_field",
        {
            "entity_identifier": ent_id,
            "name": "status",
            "description": "Engagement status.",
            "type": "enum",
        },
    )
    fld_id = field["field_identifier"]

    fetched = await _call(mcp_server, "get_field", {"identifier": fld_id})
    assert fetched["field_identifier"] == fld_id

    patched = await _call(
        mcp_server,
        "update_field",
        {"identifier": fld_id, "required": True},
    )
    assert patched["field_required"] is True

    await _call(mcp_server, "delete_field", {"identifier": fld_id})
    restored = await _call(mcp_server, "restore_field", {"identifier": fld_id})
    assert restored["field_identifier"] == fld_id


async def test_create_field_missing_parent_raises(mcp_server):
    # field_belongs_to_entity_identifier is REQUIRED by the REST layer;
    # omitting entity_identifier surfaces as a tool error.
    with pytest.raises(Exception):
        await _call(
            mcp_server,
            "create_field",
            {
                "name": "orphan",
                "description": "No parent entity.",
                "type": "text",
            },
        )


async def test_create_field_unknown_parent_raises(mcp_server):
    with pytest.raises(Exception):
        await _call(
            mcp_server,
            "create_field",
            {
                "entity_identifier": "ENT-999",
                "name": "ghostChild",
                "description": "Parent does not exist.",
                "type": "text",
            },
        )


# ---------------------------------------------------------------------------
# PRJ-025 PI-182 — intrinsic design-intent attributes + options
# ---------------------------------------------------------------------------


async def test_create_entity_with_intrinsics(mcp_server):
    created = await _call(
        mcp_server,
        "create_entity",
        {
            "name": "SortedEntity",
            "description": "d",
            "default_sort_field": "createdAt",
            "default_sort_direction": "desc",
            "track_activity": True,
        },
    )
    assert created["entity_default_sort_field"] == "createdAt"
    assert created["entity_default_sort_direction"] == "desc"
    assert created["entity_track_activity"] is True


async def test_create_field_with_intrinsics_and_options(mcp_server):
    entity = await _call(
        mcp_server,
        "create_entity",
        {"name": "OptionHost", "description": "d"},
    )
    ent_id = entity["entity_identifier"]
    field = await _call(
        mcp_server,
        "create_field",
        {
            "entity_identifier": ent_id,
            "name": "stage",
            "description": "pipeline stage",
            "type": "enum",
            "tooltip": "pick a stage",
            "format": "multiline",
            "read_only": True,
            "unique": True,
            "max_length": 64,
            "options": [
                {"option_value": "lead", "option_label": "Lead"},
                {"option_value": "won"},
            ],
        },
    )
    assert field["field_tooltip"] == "pick a stage"
    assert field["field_format"] == "multiline"
    assert field["field_read_only"] is True
    assert field["field_unique"] is True
    assert field["field_max_length"] == 64
    assert [o["option_value"] for o in field["field_options"]] == ["lead", "won"]


async def test_update_field_replaces_options(mcp_server):
    entity = await _call(
        mcp_server,
        "create_entity",
        {"name": "OptionHost2", "description": "d"},
    )
    ent_id = entity["entity_identifier"]
    field = await _call(
        mcp_server,
        "create_field",
        {
            "entity_identifier": ent_id,
            "name": "stage",
            "description": "d",
            "type": "enum",
            "options": [{"option_value": "a"}],
        },
    )
    fld_id = field["field_identifier"]
    updated = await _call(
        mcp_server,
        "update_field",
        {
            "identifier": fld_id,
            "tooltip": "updated help",
            "options": [{"option_value": "x"}, {"option_value": "y"}],
        },
    )
    assert updated["field_tooltip"] == "updated help"
    assert [o["option_value"] for o in updated["field_options"]] == ["x", "y"]
