"""Read tools for the requirements-workflow record set (REQ-567 / PI-469).

The connector gains a list tool and a get tool for each of six record
types: process, requirement, domain, persona, project and term. Each
wraps the existing REST read endpoint. These tests boot the MCP server
against the in-process API, confirm the twelve tools are registered and
read-only, and round-trip one record of each type through its list and
get tools.
"""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.mcp_server.server import build_server
from crmbuilder_v2.mcp_server.tools import tool_definitions

READ_TOOLS = {
    "get_process",
    "list_processes",
    "get_requirement",
    "list_requirements",
    "get_domain",
    "list_domains",
    "get_persona",
    "list_personas",
    "get_project",
    "list_projects",
    "get_term",
    "list_terms",
}


@pytest.fixture
async def mcp_env(v2_env):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    http = httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=10.0,
        headers={"X-Engagement": "ENG-001"},
    )
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
    if not parsed:
        return None
    if len(parsed) == 1:
        return parsed[0]
    return parsed


async def _post(http, path: str, body: dict) -> dict:
    response = await http.post(path, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def test_read_tools_registered_and_read_only(mcp_env):
    server, http = mcp_env
    names = {t.name for t in await server.list_tools()}
    assert READ_TOOLS <= names
    by_name = {td.name: td for td in tool_definitions(http)}
    for name in READ_TOOLS:
        assert by_name[name].is_write is False, name


async def test_domain_and_process_round_trip(mcp_env):
    server, http = mcp_env
    domain = await _post(
        http,
        "/domains",
        {
            "domain_name": "Mentor Recruitment",
            "domain_purpose": "Why it exists",
            "domain_description": "What it covers",
        },
    )
    process = await _post(
        http,
        "/processes",
        {
            "process_name": "Mentor Application",
            "process_domain_identifier": domain["domain_identifier"],
            "process_purpose": "Take a prospective mentor to Active or Declined",
        },
    )

    got = await _call(server, "get_domain", {"identifier": domain["domain_identifier"]})
    assert got["domain_name"] == "Mentor Recruitment"
    listed = await _call(server, "list_domains", {})
    assert [d["domain_identifier"] for d in _as_list(listed)] == [
        domain["domain_identifier"]
    ]

    got = await _call(
        server, "get_process", {"identifier": process["process_identifier"]}
    )
    assert got["process_name"] == "Mentor Application"
    assert got["process_domain_identifier"] == domain["domain_identifier"]
    listed = await _call(server, "list_processes", {})
    assert [p["process_identifier"] for p in _as_list(listed)] == [
        process["process_identifier"]
    ]


async def test_requirement_round_trip(mcp_env):
    server, http = mcp_env
    requirement = await _post(
        http,
        "/requirements",
        {
            "requirement_name": "Capture mentor availability slots",
            "requirement_description": (
                "When a mentor registers, capture their weekly windows."
            ),
            "requirement_acceptance_summary": (
                "A mentor record carries at least one availability window."
            ),
        },
    )
    got = await _call(
        server,
        "get_requirement",
        {"identifier": requirement["requirement_identifier"]},
    )
    assert got["requirement_name"] == "Capture mentor availability slots"
    listed = await _call(server, "list_requirements", {})
    assert [r["requirement_identifier"] for r in _as_list(listed)] == [
        requirement["requirement_identifier"]
    ]


async def test_persona_round_trip_with_include_deleted(mcp_env):
    server, http = mcp_env
    persona = await _post(
        http,
        "/personas",
        {
            "persona_name": "Mentor Coordinator",
            "persona_role_summary": "Oversees the mentor program day-to-day",
        },
    )
    identifier = persona["persona_identifier"]
    got = await _call(server, "get_persona", {"identifier": identifier})
    assert got["persona_name"] == "Mentor Coordinator"

    response = await http.delete(f"/personas/{identifier}")
    assert response.status_code in (200, 204), response.text
    assert _as_list(await _call(server, "list_personas", {})) == []
    listed = await _call(server, "list_personas", {"include_deleted": True})
    assert [p["persona_identifier"] for p in _as_list(listed)] == [identifier]
    got = await _call(
        server, "get_persona", {"identifier": identifier, "include_deleted": True}
    )
    assert got["persona_identifier"] == identifier


async def test_project_round_trip_with_status_filter(mcp_env):
    server, http = mcp_env
    project = await _post(
        http,
        "/projects",
        {
            "project_name": "Connector read tools",
            "project_purpose": "p",
            "project_description": "d",
        },
    )
    identifier = project["project_identifier"]
    got = await _call(server, "get_project", {"identifier": identifier})
    assert got["project_name"] == "Connector read tools"
    listed = await _call(
        server, "list_projects", {"status": project["project_status"]}
    )
    assert [p["project_identifier"] for p in _as_list(listed)] == [identifier]
    assert _as_list(await _call(server, "list_projects", {"status": "complete"})) == []


async def test_term_round_trip_with_scope_filter(mcp_env):
    server, http = mcp_env
    term = await _post(
        http, "/terms", {"name": "Connector", "definition": "The MCP surface."}
    )
    got = await _call(server, "get_term", {"identifier": term["identifier"]})
    assert got["name"] == "Connector"
    listed = await _call(server, "list_terms", {})
    assert [t["identifier"] for t in _as_list(listed)] == [term["identifier"]]
    listed = await _call(server, "list_terms", {"scope": "system"})
    assert [t["identifier"] for t in _as_list(listed)] == [term["identifier"]]


def _as_list(value):
    """FastMCP returns a one-item list as a bare dict; normalise."""
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    return value
