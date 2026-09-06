"""The connector's session-open and segment-advance tools (REQ-576 / PI-488).

Boots the MCP server against the in-process API, confirms the two tools are
registered as writes, and drives a two-segment kind of work from the opening
answer to completion through them — the same operations the desktop calls.
"""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.access.repositories import session_opening as so
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.mcp_server.server import build_server
from crmbuilder_v2.mcp_server.tools import tool_definitions

_SUMMARY = "s" * 200


@pytest.fixture
async def mcp_env(v2_env):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    http = httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=10.0,
                             headers={"X-Engagement": "ENG-001"})
    server = build_server(http=http)
    yield server, http
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
    return parsed[0] if len(parsed) == 1 else parsed


async def _post(http, path, body):
    r = await http.post(path, json=body)
    assert r.status_code == 201, (path, r.text)
    return r.json()["data"]


async def _seed(http):
    await _post(http, "/decisions", {"identifier": "DEC-001", "title": "T", "decision_date": "2026-01-01",
                                     "status": "Active", "executive_summary": _SUMMARY})
    cross_rule = (await _post(http, "/governance-rules", {"source_decision": "DEC-001", "body": "cross",
                                                          "enforcement": "advisory"}))["identifier"]
    phase_rule = (await _post(http, "/governance-rules", {"source_decision": "DEC-001", "body": "interview",
                                                          "enforcement": "advisory"}))["identifier"]
    cross = (await _post(http, "/agent-profiles", {"area": so.CROSS_CUTTING_AREA, "tier": "orchestrator",
                                                   "description": "cross", "scope": "system"}))["identifier"]
    await _post(http, f"/agent-profiles/{cross}/bindings", {"target_type": "governance_rule", "target_id": cross_rule,
                                                            "mode": "bind", "scope": "system"})
    interviewer = (await _post(http, "/agent-profiles", {"area": "requirements-capture", "tier": "orchestrator",
                                                         "description": "Interviewer", "scope": "system"}))["identifier"]
    await _post(http, f"/agent-profiles/{interviewer}/bindings", {"target_type": "governance_rule",
                                                                  "target_id": phase_rule, "mode": "bind", "scope": "system"})
    dom = (await _post(http, "/domains", {"domain_name": "Requirements Capture", "domain_purpose": "p",
                                          "domain_description": "d"}))["domain_identifier"]
    project = (await _post(http, "/projects", {"project_name": "P", "project_purpose": "p",
                                               "project_description": "d", "project_status": "in_flight"}))["project_identifier"]
    await _post(http, "/processes", {
        "process_name": "Define new business processes", "process_domain_identifier": dom, "process_purpose": "kw",
        "process_steps": so.catalogue_steps_block([
            {"position": 1, "domain": dom, "profile": interviewer, "area": "requirements-capture",
             "label": "Requirements Interviewer", "status": "active"},
            {"position": 2, "domain": dom, "profile": None, "area": "solution-design",
             "label": "Solution Designer", "status": "pending"}]),
        "process_triggers": json.dumps(["define new business processes", "capture requirements", "interview"])})
    return {"cross_rule": cross_rule, "phase_rule": phase_rule, "interviewer": interviewer, "project": project}


async def test_tools_registered_as_writes(mcp_env):
    server, http = mcp_env
    names = {t.name for t in await server.list_tools()}
    assert {"open_session", "advance_session_segment"} <= names
    by_name = {td.name: td for td in tool_definitions(http)}
    assert by_name["open_session"].is_write and by_name["advance_session_segment"].is_write
    description = " ".join(by_name["open_session"].description.split())
    assert "What do you want to do today?" in description
    assert "confirmation_line" in description


async def test_open_then_advance_to_completion(mcp_env):
    server, http = mcp_env
    seed = await _seed(http)
    out = await _call(server, "open_session", {"opening_answer": "define new business processes",
                                               "medium": "chat", "project_identifier": seed["project"]})
    sid = out["session"]["session_identifier"]
    assert out["kind_of_work_name"] == "Define new business processes"
    assert out["confirmation_line"].endswith("I will start with the Requirements Interviewer.")
    rule_ids = {r["identifier"] for r in out["contract"]["advisory_rules"]}
    assert rule_ids == {seed["cross_rule"], seed["phase_rule"]}
    assert out["session"]["session_medium"] == "chat"

    nxt = await _call(server, "advance_session_segment", {"identifier": sid})
    assert nxt["completed"] is False and nxt["segment"]["label"] == "Solution Designer"
    assert {r["identifier"] for r in nxt["contract"]["advisory_rules"]} == {seed["cross_rule"]}
    done = await _call(server, "advance_session_segment", {"identifier": sid})
    assert done["completed"] is True and done["contract"] is None

    rec = (await http.get(f"/sessions/{sid}")).json()["data"]
    assert rec["session_opening_answer"] == "define new business processes"
    assert all(s["entered_at"] and s["left_at"] for s in rec["session_phase_segments"])


async def test_open_without_answer_and_miss(mcp_env):
    server, http = mcp_env
    await _seed(http)
    empty = await _call(server, "open_session", {})
    assert empty["kind_of_work"] is None and empty["first_line"] == so.NO_KIND_OF_WORK_LINE
    miss = await _call(server, "open_session", {"opening_answer": "send birthday cards"})
    assert miss["follow_up_question"] == so.FOLLOW_UP_QUESTION
    assert miss["planning_item"]["title"].startswith("Catalogue miss:")
