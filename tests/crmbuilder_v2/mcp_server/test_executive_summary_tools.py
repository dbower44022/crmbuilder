"""PI-105: MCP create/update tools accept and persist executive_summary.

End-to-end through the FastMCP server -> FastAPI app -> access layer (the
same ASGITransport harness the other MCP tests use). Proves the gap the
SES-114 close-out hit is closed: update_planning_item / update_decision
forward executive_summary, and conversation/session update tools persist
the prefixed variant.
"""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import sessions as sr
from crmbuilder_v2.access.repositories import projects as wr
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.mcp_server.server import build_server

_EXEC = "PI-105 end-to-end executive summary padding. " * 6  # ~270 chars
_EXEC2 = "PI-105 refreshed executive summary padding. " * 6


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
    return parsed[0] if len(parsed) == 1 else parsed


async def test_update_planning_item_refreshes_executive_summary(mcp_server):
    await _call(
        mcp_server,
        "create_planning_item",
        {
            "identifier": "PI-001",
            "title": "Smoke PI",
            "item_type": "pending_work",
            "status": "Open",
            "description": "d",
            "executive_summary": _EXEC,
        },
    )
    out = await _call(
        mcp_server,
        "update_planning_item",
        {"identifier": "PI-001", "executive_summary": _EXEC2},
    )
    assert out["executive_summary"] == _EXEC2


async def test_update_decision_refreshes_executive_summary(mcp_server):
    await _call(
        mcp_server,
        "create_decision",
        {
            "identifier": "DEC-001",
            "title": "Smoke decision",
            "decision_date": "2026-05-30",
            "status": "Active",
            "executive_summary": _EXEC,
        },
    )
    out = await _call(
        mcp_server,
        "update_decision",
        {"identifier": "DEC-001", "executive_summary": _EXEC2},
    )
    assert out["executive_summary"] == _EXEC2


async def test_update_conversation_sets_executive_summary(mcp_server):
    # Conversations need a parent-session membership edge the create tool
    # can't author yet, so seed via the access layer, then refresh via MCP.
    with session_scope() as s:
        cr.create_conversation(
            s,
            title="Seed conv",
            purpose="p",
            description="d",
            identifier="CNV-001",
            references=[{
                "source_type": "conversation",
                "source_id": "CNV-001",
                "target_type": "session",
                "target_id": "CONV-049",
                "relationship": "conversation_belongs_to_session",
            }],
        )
    out = await _call(
        mcp_server,
        "update_conversation",
        {"identifier": "CNV-001", "executive_summary": _EXEC},
    )
    assert out["conversation_executive_summary"] == _EXEC


async def test_update_session_refreshes_executive_summary(mcp_server):
    # Sessions require a workstream-membership edge; seed via access then
    # refresh the session_executive_summary via MCP.
    with session_scope() as s:
        wid = wr.create_project(s, name="WS", purpose="p", description="d")[
            "project_identifier"
        ]
        sr.create_session(
            s,
            title="Seed session",
            description="d",
            medium="chat",
            status="planned",
            executive_summary=_EXEC,
            references=[{
                "source_type": "session",
                "source_id": "SES-001",
                "target_type": "project",
                "target_id": wid,
                "relationship": "session_belongs_to_project",
            }],
            identifier="SES-001",
        )
    out = await _call(
        mcp_server,
        "update_session",
        {"identifier": "SES-001", "executive_summary": _EXEC2},
    )
    assert out["session_executive_summary"] == _EXEC2
