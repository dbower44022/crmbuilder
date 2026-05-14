"""MCP-server catalog tool tests.

Boots a FastMCP instance whose httpx client routes through an ASGITransport
into the FastAPI app, then invokes each catalog tool end-to-end against
the same fixture catalog used by the API route tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.bootstrap.catalog_loader import load_catalog
from crmbuilder_v2.mcp_server.server import build_server


_FIXTURE_CATALOG = (
    Path(__file__).resolve().parents[1] / "bootstrap" / "fixtures" / "catalog"
)


@pytest.fixture
async def mcp_server(v2_env):
    with session_scope(export=False) as s:
        load_catalog(s, _FIXTURE_CATALOG)
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    http = httpx.AsyncClient(
        transport=transport, base_url="http://testserver", timeout=10.0
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


async def test_catalog_tools_registered(mcp_server):
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    assert "catalog_search" in names
    assert "catalog_get_entity" in names
    assert "catalog_get_cross_system_map" in names
    assert "catalog_gap_check" in names


async def test_catalog_search_returns_ranked_hits(mcp_server):
    out = await _call(mcp_server, "catalog_search", {"query": "account"})
    assert isinstance(out, list)
    # Exact match for "account" should rank first.
    assert out[0]["catalog_id"] == "account"
    assert out[0]["kind"] == "entity"


async def test_catalog_search_synonym(mcp_server):
    out = await _call(mcp_server, "catalog_search", {"query": "Company"})
    # _call unwraps single-item lists to the item itself; normalise here.
    hits = out if isinstance(out, list) else [out]
    cids = [h.get("catalog_id") for h in hits]
    assert "account" in cids


async def test_catalog_search_limit(mcp_server):
    out = await _call(mcp_server, "catalog_search", {"query": "a", "limit": 2})
    assert isinstance(out, list)
    assert len(out) <= 2


async def test_catalog_get_entity_full_nested(mcp_server):
    out = await _call(mcp_server, "catalog_get_entity", {"catalog_id": "account"})
    assert out["catalog_id"] == "account"
    assert "systems" in out
    assert len(out["systems"]) == 3
    assert "attributes" in out
    attr_names = {a["name"] for a in out["attributes"]}
    assert attr_names == {"accountName", "accountType"}


async def test_catalog_get_entity_subclass(mcp_server):
    out = await _call(
        mcp_server, "catalog_get_entity", {"catalog_id": "donation-major-gift"}
    )
    assert out["entry_kind"] == "subclass"
    assert out["parent_catalog_id"] == "donation"
    assert out["discriminator_attribute"] == "donationType"


async def test_catalog_get_cross_system_map_all(mcp_server):
    out = await _call(
        mcp_server, "catalog_get_cross_system_map", {"catalog_id": "account"}
    )
    assert out["entity"]["catalog_id"] == "account"
    # All 7 surveyed systems present.
    assert len(out["systems"]) == 7
    sf = out["systems"]["salesforce"]
    assert sf["entity_name"] == "Account"
    sf_attrs = {a["catalog_name"]: a for a in sf["attributes"]}
    assert sf_attrs["accountName"]["api_name"] == "Name"


async def test_catalog_get_cross_system_map_filtered(mcp_server):
    out = await _call(
        mcp_server,
        "catalog_get_cross_system_map",
        {"catalog_id": "account", "target_system": "civicrm"},
    )
    assert list(out["systems"].keys()) == ["civicrm"]
    cv = out["systems"]["civicrm"]
    cv_attrs = {a["catalog_name"]: a for a in cv["attributes"]}
    assert cv_attrs["accountName"]["api_name"] == "organization_name"


async def test_catalog_gap_check_returns_missing(mcp_server):
    out = await _call(
        mcp_server,
        "catalog_gap_check",
        {
            "based_on_catalog_id": "account",
            "draft_attribute_names": [],
            "min_systems": 3,
        },
    )
    names = [m["name"] for m in out["missing"]]
    assert "accountName" in names
    assert "accountType" in names


async def test_catalog_gap_check_excludes_drafted(mcp_server):
    out = await _call(
        mcp_server,
        "catalog_gap_check",
        {
            "based_on_catalog_id": "account",
            "draft_attribute_names": ["accountName"],
            "min_systems": 3,
        },
    )
    names = [m["name"] for m in out["missing"]]
    assert "accountName" not in names


async def test_catalog_get_entity_not_found_raises(mcp_server):
    with pytest.raises(Exception):
        await _call(mcp_server, "catalog_get_entity", {"catalog_id": "ghost"})


async def test_catalog_search_empty_query_raises(mcp_server):
    """min_length=1 on the REST layer rejects empty strings — surfaces as
    httpx error → tool error."""
    with pytest.raises(Exception):
        await _call(mcp_server, "catalog_search", {"query": ""})
