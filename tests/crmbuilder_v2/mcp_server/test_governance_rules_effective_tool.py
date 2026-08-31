"""MCP ``list_governance_rules`` passes ``resolution`` / ``engagement`` through (REQ-536 / PI-441).

An agent on Claude Desktop reaches the store only through MCP, so the tool must
return the same override-resolved ruleset a REST caller gets from
``GET /governance-rules?resolution=effective`` (PI-435).
"""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.mcp_server.server import build_server


@pytest.fixture
async def env(v2_env):
    app = create_app()
    http = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=10.0,
        headers={"X-Engagement": "ENG-001"},
    )
    yield build_server(http=http), http
    await http.aclose()


async def _call(server, name, args):
    result = await server.call_tool(name, args)
    if isinstance(result, tuple):
        content, structured = result
        if structured is not None:
            return structured.get("result", structured)
        result = content
    if not isinstance(result, list):
        return result
    parsed = [json.loads(b.text) for b in result if getattr(b, "text", None)]
    return parsed[0] if len(parsed) == 1 else parsed


async def _rule(http, *, body, rule_type, scope):
    resp = await http.post(
        "/governance-rules",
        json={"body": body, "enforcement": "advisory", "rule_type": rule_type, "scope": scope},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["identifier"]


async def test_effective_resolution_matches_rest(env):
    server, http = env
    react = await _rule(http, body="Custom apps use React.", rule_type="ui_framework", scope="system")
    angular = await _rule(
        http, body="ENG-001 apps use Angular.", rule_type="ui_framework", scope="ENG-001"
    )
    other = await _rule(http, body="Never force-push.", rule_type="no_force_push", scope="system")

    # Effective for the active engagement: identical to the REST view, override
    # substituted for the default and annotated with what it shadows.
    via_tool = await _call(server, "list_governance_rules", {"resolution": "effective"})
    via_rest = (await http.get("/governance-rules", params={"resolution": "effective"})).json()["data"]
    assert via_tool == via_rest
    ids = {r["identifier"]: r for r in via_tool}
    assert angular in ids and react not in ids and other in ids
    assert ids[angular]["shadows"] == [react]

    # Another engagement sees the system default.
    elsewhere = await _call(
        server, "list_governance_rules", {"resolution": "effective", "engagement": "ENG-002"}
    )
    other_ids = {r["identifier"] for r in elsewhere}
    assert react in other_ids and angular not in other_ids

    # Omitting both keeps the raw stored listing: every row, no shadows.
    raw = await _call(server, "list_governance_rules", {})
    raw_ids = {r["identifier"] for r in raw}
    assert {react, angular, other} <= raw_ids
    assert all("shadows" not in r for r in raw)
