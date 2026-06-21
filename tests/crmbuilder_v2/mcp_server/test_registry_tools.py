"""PI-122 slice 6 — registry MCP tools + system-profile seed."""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories.registry_seed import seed_system_profiles
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.mcp_server.server import build_server


@pytest.fixture
async def mcp(v2_env):
    app = create_app()
    http = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        timeout=10.0,
        headers={"X-Engagement": "ENG-001"},
    )
    server = build_server(http=http)
    yield server
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


async def test_registry_tools_registered(mcp):
    names = {t.name for t in await mcp.list_tools()}
    for n in (
        "resolve_agent_profile_contract",
        "list_agent_profiles",
        "create_agent_profile",
        "list_skills",
        "list_governance_rules",
        "list_learnings",
        "capture_learning",
    ):
        assert n in names


async def test_create_profile_and_capture_learning_over_mcp(mcp):
    prof = await _call(
        mcp, "create_agent_profile",
        {"area": "storage", "tier": "developer", "description": "Storage dev."},
    )
    assert prof["identifier"].startswith("AGP-")

    contract = await _call(
        mcp, "resolve_agent_profile_contract", {"identifier": prof["identifier"]}
    )
    assert contract["profile_id"] == prof["identifier"]
    assert "version_stamp" in contract

    lrn = await _call(
        mcp, "capture_learning",
        {"area": "storage", "tier": "developer", "category": "gotcha",
         "content": "learned over MCP"},
    )
    assert lrn["identifier"].startswith("LRN-")
    assert lrn["confidence"] == 0


def test_seed_decomposes_proven_prompts_into_resolvable_contracts(v2_env):
    """The seed ingests the proven prompts as REAL content — resolving a seeded
    profile reconstructs the proven contract (prompt + tools + ruleset), not a
    placeholder pointer."""
    from crmbuilder_v2.access.repositories import agent_profiles, registry_resolver

    with session_scope() as s:
        created = seed_system_profiles(s)
        # PI-240 (Phase 3): the full per-(area,tier) catalog — 9 build areas x
        # {architect,developer,tester} (27) + 4 methodology architects + the 3
        # release-level planning-org agents (model/planning/release) = 34.
        assert len(created) == 34
        assert all(p["scope"] == "system" for p in created)

        archs = agent_profiles.list_all(s, area="storage", tier="architect")
        arch_contract = registry_resolver.resolve_contract(s, archs[0]["identifier"])
        # The real proven Architect prompt body — not a one-line pointer.
        assert "your one job" in arch_contract["system_prompt"].lower()
        assert "feed-forward" in arch_contract["system_prompt"].lower()
        # Its tool-skills are the substrate endpoints it drives.
        callables = {t["backing_callable"] for t in arch_contract["tools"]}
        assert any("/scope" in c for c in callables)
        assert any("prior-phase-outputs" in c for c in callables)
        # Advisory rules composed in; no enforced rule for the scoper.
        assert "layer rank" in arch_contract["system_prompt"].lower()
        assert arch_contract["enforced_ruleset"] == []

        devs = agent_profiles.list_all(s, area="storage", tier="developer")
        dev_contract = registry_resolver.resolve_contract(s, devs[0]["identifier"])
        assert "self-verify" in dev_contract["system_prompt"].lower() or any(
            "self-verify" in r["body"].lower() for r in dev_contract["enforced_ruleset"]
        )
        # The Developer's self-verify gate is an ENFORCED rule.
        assert any(
            "ruff" in r["body"].lower() and "pytest" in r["body"].lower()
            for r in dev_contract["enforced_ruleset"]
        )
        assert any("/claim" in t["backing_callable"] for t in dev_contract["tools"])

    # Idempotent on re-run.
    with session_scope() as s:
        assert seed_system_profiles(s) == []
