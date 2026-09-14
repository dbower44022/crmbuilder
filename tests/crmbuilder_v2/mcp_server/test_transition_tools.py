"""Connector tools for transitions (REQ-586 / PI-471).

The connector gains a list tool, a get tool, an incompleteness-report tool and
a create tool. These tests boot the MCP server against the in-process API,
confirm the tools are registered with the right read/write classification, and
put the approved thirteen-row Mentor Application table through the create tool
— which is the path the Cleveland Business Mentors migration takes (DEC-1070).
"""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.mcp_server.server import build_server
from crmbuilder_v2.mcp_server.tools import tool_definitions

from tests.crmbuilder_v2.access._mentor_application import (
    MENTOR_STATUS_OPTIONS,
    PRE_ACTIVE,
)

READ_TOOLS = {
    "get_transition",
    "list_transitions",
    "list_incomplete_transitions",
}
WRITE_TOOLS = {"create_transition"}


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


async def _call(server, name: str, args: dict, *, collapse: bool = True):
    """Call one tool and return its payload.

    ``collapse`` flattens a one-block result, which is what a get or create
    tool returns. A list tool is called with ``collapse=False`` so a
    single-record list stays a list.
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
    if collapse and len(parsed) == 1:
        return parsed[0]
    if not collapse and len(parsed) == 1 and isinstance(parsed[0], list):
        return parsed[0]
    return parsed


async def _post(http, path: str, body: dict) -> dict:
    response = await http.post(path, json=body)
    assert response.status_code in (200, 201), response.text
    return response.json()["data"]


async def _seed(http) -> dict:
    dom = await _post(
        http,
        "/domains",
        {
            "domain_name": "Mentor Recruiting",
            "domain_purpose": "Bring new mentors in.",
            "domain_description": "Recruiting and onboarding mentors.",
        },
    )
    proc = await _post(
        http,
        "/processes",
        {
            "process_name": "Mentor Application",
            "process_domain_identifier": dom["domain_identifier"],
            "process_purpose": "Application to active.",
        },
    )
    profile = await _post(
        http,
        "/entities",
        {"entity_name": "MentorProfile", "entity_description": "A profile."},
    )
    await _post(
        http,
        "/references",
        {
            "source_type": "process",
            "source_id": proc["process_identifier"],
            "target_type": "entity",
            "target_id": profile["entity_identifier"],
            "relationship": "process_touches_entity",
        },
    )
    status_field = await _post(
        http,
        "/fields",
        {
            "field_belongs_to_entity_identifier": profile["entity_identifier"],
            "field_name": "mentorStatus",
            "field_description": "Where the mentor is.",
            "field_type": "enum",
            "field_options": [
                {"option_value": value, "option_order": index}
                for index, value in enumerate(MENTOR_STATUS_OPTIONS)
            ],
        },
    )
    decline_reason = await _post(
        http,
        "/fields",
        {
            "field_belongs_to_entity_identifier": profile["entity_identifier"],
            "field_name": "declineReason",
            "field_description": "Why the applicant was declined.",
            "field_type": "text",
        },
    )
    team = await _post(
        http,
        "/personas",
        {
            "persona_name": "Mentor Administration Team",
            "persona_role_summary": "Reviews and votes.",
        },
    )
    return {
        "process": proc["process_identifier"],
        "status_field": status_field["field_identifier"],
        "decline_reason": decline_reason["field_identifier"],
        "team": team["persona_identifier"],
    }


async def test_transition_tools_registered_with_the_right_classification(
    mcp_env,
):
    server, http = mcp_env
    names = {t.name for t in await server.list_tools()}
    assert READ_TOOLS <= names
    assert WRITE_TOOLS <= names
    by_name = {td.name: td for td in tool_definitions(http)}
    for name in READ_TOOLS:
        assert by_name[name].is_write is False, name
    for name in WRITE_TOOLS:
        assert by_name[name].is_write is True, name


async def test_create_list_and_get_a_transition_through_the_connector(mcp_env):
    server, http = mcp_env
    seed = await _seed(http)

    created = await _call(
        server,
        "create_transition",
        {
            "process": seed["process"],
            "field": seed["status_field"],
            "from_values": ["Candidate"],
            "to_value": "Under Review",
            "actor_kind": "persona",
            "actor_persona": seed["team"],
        },
    )
    identifier = created["transition_identifier"]
    assert identifier == "TRN-001"

    listed = await _call(
        server,
        "list_transitions",
        {"process": seed["process"]},
        collapse=False,
    )
    assert [r["transition_identifier"] for r in listed] == [identifier]

    got = await _call(server, "get_transition", {"identifier": identifier})
    assert got["transition_to_value"] == "Under Review"
    assert got["transition_actor_persona"] == seed["team"]
    assert got["transition_from_values"] == ["Candidate"]


async def test_thirteen_rows_go_in_through_the_connector(mcp_env):
    """REQ-586: listing the process's transitions returns thirteen records."""
    server, http = mcp_env
    seed = await _seed(http)
    team = seed["team"]

    rows = [
        {
            "from_kind": "record_creation",
            "to_value": "Candidate",
            "actor_kind": "system",
            "actor_occasion": "the intake application",
        },
        {"from_values": ["Prospect"], "to_value": "Candidate", "actor_kind": "system"},
        {"from_values": ["Declined"], "to_value": "Candidate", "actor_kind": "system"},
        {
            "from_values": ["Candidate"],
            "to_value": "Under Review",
            "actor_kind": "persona",
            "actor_persona": team,
        },
        {
            "from_values": ["Candidate"],
            "to_value": "Declined",
            "actor_kind": "persona",
            "actor_persona": team,
            "required_fields": [seed["decline_reason"]],
        },
        {
            "from_values": ["Under Review"],
            "to_value": "Accepted-Provisional",
            "actor_kind": "persona",
            "actor_persona": team,
            "actor_occasion": "first vote",
        },
        {
            "from_values": ["Under Review"],
            "to_value": "Declined",
            "actor_kind": "persona",
            "actor_persona": team,
            "actor_occasion": "first vote",
            "required_fields": [seed["decline_reason"]],
        },
        {
            "from_values": ["Accepted-Provisional"],
            "to_value": "Provisional",
            "actor_kind": "system",
            "actor_occasion": "the CRM",
        },
        {
            "from_values": ["Provisional"],
            "to_value": "Approved",
            "actor_kind": "persona",
            "actor_persona": team,
            "actor_occasion": "second vote",
            "consequence_notes": "Mentor login provisioning runs on the save.",
        },
        {
            "from_values": ["Provisional"],
            "to_value": "Declined",
            "actor_kind": "persona",
            "actor_persona": team,
            "actor_occasion": "second vote",
            "required_fields": [seed["decline_reason"]],
        },
        {
            "from_values": ["Approved"],
            "to_value": "Active",
            "actor_kind": "persona",
            "actor_persona": team,
        },
        {
            "from_values": list(PRE_ACTIVE),
            "to_value": "Dormant",
            "actor_kind": "persona",
            "actor_persona": team,
        },
        {
            "from_values": list(PRE_ACTIVE),
            "to_value": "Declined",
            "actor_kind": "persona",
            "actor_persona": team,
            "actor_occasion": "withdrawal",
            "required_fields": [seed["decline_reason"]],
        },
    ]
    for row in rows:
        created = await _call(
            server,
            "create_transition",
            {"process": seed["process"], "field": seed["status_field"], **row},
        )
        assert "transition_identifier" in created, created

    listed = await _call(
        server,
        "list_transitions",
        {"process": seed["process"]},
        collapse=False,
    )
    assert len(listed) == 13
    assert [r["transition_order"] for r in listed] == list(range(13))

    report = await _call(
        server,
        "list_incomplete_transitions",
        {"process": seed["process"]},
        collapse=False,
    )
    assert len(report) == 1
    assert report[0]["transition_to_value"] == "Approved"


async def test_a_create_that_fails_a_check_is_refused_by_name(mcp_env):
    """REQ-586: a create failing a check is refused with the check named — not
    with a bare status code the caller cannot act on."""
    server, http = mcp_env
    seed = await _seed(http)
    with pytest.raises(Exception) as exc:
        await _call(
            server,
            "create_transition",
            {
                "process": seed["process"],
                "field": seed["status_field"],
                "from_values": ["Candidate"],
                "to_value": "Retired",
                "actor_kind": "system",
            },
        )
    assert "to_value_not_an_option" in str(exc.value)
