"""MCP server smoke test.

Boots a FastMCP instance whose ``httpx.Client`` is wired through
``ASGITransport`` to the in-process FastAPI app. Confirms a representative
slice of tools end-to-end: the call traverses MCP tool dispatch → REST
endpoint → access layer → SQLite database, and the response envelope
unwraps to the expected shape.
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
        transport=transport, base_url="http://testserver", timeout=10.0
    )
    server = build_server(http=http)
    yield server
    await http.aclose()


async def _call(server, name: str, args: dict):
    """Invoke a tool by name and return its decoded JSON output.

    FastMCP serialises list-typed tool returns as one TextContent block per
    item, and dict-typed returns as a single block. Reassemble accordingly.
    """
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


async def test_tool_count(mcp_server):
    tools = await mcp_server.list_tools()
    # Sanity check: we registered ~40 tools across all entities.
    names = {t.name for t in tools}
    assert "get_current_charter" in names
    assert "create_decision" in names
    assert "list_recent_sessions" in names
    assert "add_reference" in names
    assert len(tools) >= 30


async def test_charter_create_then_read(mcp_server):
    out = await _call(
        mcp_server, "replace_charter", {"payload": {"scope": "smoke"}}
    )
    assert out["version"] == 1
    out = await _call(mcp_server, "get_current_charter", {})
    assert out["payload"] == {"scope": "smoke"}


async def test_decision_lifecycle(mcp_server):
    out = await _call(
        mcp_server,
        "create_decision",
        {
            "identifier": "DEC-001",
            "title": "Smoke decision",
            "decision_date": "05-07-26",
            "status": "Active",
            "executive_summary": "PI-102 test executive summary. " * 7,
        },
    )
    assert out["identifier"] == "DEC-001"

    out = await _call(mcp_server, "get_decision", {"identifier": "DEC-001"})
    assert out["status"] == "Active"

    out = await _call(
        mcp_server,
        "update_decision",
        {"identifier": "DEC-001", "status": "Superseded"},
    )
    assert out["status"] == "Superseded"


async def test_orientation_decisions_for_session(mcp_server):
    await _call(
        mcp_server,
        "create_session",
        {
            "identifier": "SES-001",
            "title": "Smoke session",
            "session_date": "05-07-26",
            "status": "Complete",
        },
    )
    for did in ("DEC-001", "DEC-002"):
        await _call(
            mcp_server,
            "create_decision",
            {
                "identifier": did,
                "title": did,
                "decision_date": "05-07-26",
                "status": "Active",
            },
        )
        await _call(
            mcp_server,
            "add_reference",
            {
                "source_type": "session",
                "source_id": "SES-001",
                "target_type": "decision",
                "target_id": did,
                "relationship": "decided_in",
            },
        )
    out = await _call(
        mcp_server, "list_decisions_for_session", {"identifier": "SES-001"}
    )
    assert isinstance(out, list)
    assert sorted(d["identifier"] for d in out) == ["DEC-001", "DEC-002"]


async def test_validation_error_propagates(mcp_server):
    with pytest.raises(Exception):
        await _call(
            mcp_server,
            "create_decision",
            {
                "identifier": "DEC-001",
                "title": "x",
                "decision_date": "05-07-26",
                "status": "BogusStatus",
            },
        )
