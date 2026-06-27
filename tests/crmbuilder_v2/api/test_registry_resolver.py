"""PI-122 slice 2 — binding edges + contract resolver."""

from __future__ import annotations


def _ref(client, source_id, relationship, target_type, target_id):
    return client.post(
        "/references",
        json={
            "source_type": "agent_profile",
            "source_id": source_id,
            "target_type": target_type,
            "target_id": target_id,
            "relationship": relationship,
        },
    )


def test_bindings_and_contract_resolution(client):
    prof = client.post(
        "/agent-profiles",
        json={"area": "storage", "tier": "architect", "description": "Storage architect."},
    ).json()["data"]["identifier"]

    instr = client.post(
        "/skills",
        json={"name": "sequence by layer rank", "kind": "instruction",
              "description": "Sequence Work Tasks by layer rank."},
    ).json()["data"]["identifier"]
    tool = client.post(
        "/skills",
        json={"name": "scope", "kind": "tool", "description": "Record Work Tasks.",
              "io_contract": {"type": "object"}, "backing_callable": "POST /workstreams/{id}/scope"},
    ).json()["data"]["identifier"]
    advisory = client.post(
        "/governance-rules",
        json={"body": "Prefer additive replanning.", "enforcement": "advisory"},
    ).json()["data"]["identifier"]
    enforced = client.post(
        "/governance-rules",
        json={"body": "Cannot mark a Workstream Ready without Work Tasks.",
              "enforcement": "enforced", "severity": "high"},
    ).json()["data"]["identifier"]

    assert _ref(client, prof, "agent_profile_has_skill", "skill", instr).status_code == 201
    assert _ref(client, prof, "agent_profile_has_skill", "skill", tool).status_code == 201
    assert _ref(client, prof, "agent_profile_governed_by_rule", "governance_rule", advisory).status_code == 201
    assert _ref(client, prof, "agent_profile_governed_by_rule", "governance_rule", enforced).status_code == 201

    contract = client.get(f"/agent-profiles/{prof}/contract").json()["data"]
    assert contract["profile_id"] == prof
    assert "Storage architect." in contract["system_prompt"]
    assert "Sequence Work Tasks by layer rank." in contract["system_prompt"]
    assert "Prefer additive replanning." in contract["system_prompt"]
    assert [t["identifier"] for t in contract["tools"]] == [tool]
    assert contract["tools"][0]["backing_callable"] == "POST /workstreams/{id}/scope"
    # REQ-380: tools carry their description so the runtime can tell the agent
    # what each tool does.
    assert contract["tools"][0]["description"] == "Record Work Tasks."
    assert [r["identifier"] for r in contract["enforced_ruleset"]] == [enforced]
    assert contract["active_learnings"] == []
    stamp1 = contract["version_stamp"]
    assert stamp1

    # The stamp changes when a bound item changes.
    client.patch(f"/skills/{tool}", json={"version": 2})
    stamp2 = client.get(f"/agent-profiles/{prof}/contract").json()["data"]["version_stamp"]
    assert stamp2 != stamp1


def test_contract_scope_merge(client):
    """A system skill is always in scope; an engagement-overlay skill only when
    resolving for that engagement (D-δ4)."""
    prof = client.post(
        "/agent-profiles",
        json={"area": "api", "tier": "developer", "description": "API dev."},
    ).json()["data"]["identifier"]
    sys_skill = client.post(
        "/skills", json={"name": "sys", "kind": "instruction", "description": "system skill"},
    ).json()["data"]["identifier"]
    eng_skill = client.post(
        "/skills", json={"name": "eng", "kind": "instruction", "description": "engagement skill",
                         "scope": "ENG-001"},
    ).json()["data"]["identifier"]
    _ref(client, prof, "agent_profile_has_skill", "skill", sys_skill)
    _ref(client, prof, "agent_profile_has_skill", "skill", eng_skill)

    # Resolving for a different engagement: only the system skill is in scope.
    other = client.get(f"/agent-profiles/{prof}/contract?engagement=ENG-002").json()["data"]
    assert "system skill" in other["system_prompt"]
    assert "engagement skill" not in other["system_prompt"]
    # Resolving for ENG-001: both.
    eng = client.get(f"/agent-profiles/{prof}/contract?engagement=ENG-001").json()["data"]
    assert "system skill" in eng["system_prompt"]
    assert "engagement skill" in eng["system_prompt"]


def _enforced_ids(contract) -> list[str]:
    return [r["identifier"] for r in contract["enforced_ruleset"]]


def _rule(client, *, body, enforcement="enforced", rule_type=None, scope=None, severity=None):
    payload = {"body": body, "enforcement": enforcement}
    if rule_type is not None:
        payload["rule_type"] = rule_type
    if scope is not None:
        payload["scope"] = scope
    if severity is not None:
        payload["severity"] = severity
    return client.post("/governance-rules", json=payload).json()["data"]["identifier"]


def test_engagement_rule_overrides_system_rule_of_same_type(client):
    """An engagement overlay rule with the same ``rule_type`` as a system rule
    wins; the system rule of that type is dropped from the contract (WTK-001)."""
    prof = client.post(
        "/agent-profiles",
        json={"area": "access", "tier": "developer", "description": "Access dev."},
    ).json()["data"]["identifier"]

    sys_rule = _rule(
        client, body="System: two approvals required.",
        rule_type="approval_threshold", scope="system",
    )
    eng_rule = _rule(
        client, body="ENG-001: one approval required.",
        rule_type="approval_threshold", scope="ENG-001",
    )
    # A system rule of a *different* type is untouched by the override.
    other_sys = _rule(
        client, body="System: no force push.", rule_type="no_force_push", scope="system",
    )

    for rid in (sys_rule, eng_rule, other_sys):
        _ref(client, prof, "agent_profile_governed_by_rule", "governance_rule", rid)

    # For ENG-001 the engagement rule replaces the system rule of the same type;
    # the unrelated system rule survives.
    eng = client.get(f"/agent-profiles/{prof}/contract?engagement=ENG-001").json()["data"]
    assert sys_rule not in _enforced_ids(eng)
    assert eng_rule in _enforced_ids(eng)
    assert other_sys in _enforced_ids(eng)

    # For a different engagement the overlay is out of scope, so the original
    # system rule stands.
    other = client.get(f"/agent-profiles/{prof}/contract?engagement=ENG-002").json()["data"]
    assert sys_rule in _enforced_ids(other)
    assert eng_rule not in _enforced_ids(other)
    assert other_sys in _enforced_ids(other)


def test_engagement_disable_suppresses_named_system_rule(client):
    """An engagement ``disable:<id-or-rule_type>`` overlay suppresses a system rule
    for that engagement only, and is itself never emitted (WTK-001)."""
    prof = client.post(
        "/agent-profiles",
        json={"area": "access", "tier": "developer", "description": "Access dev."},
    ).json()["data"]["identifier"]

    by_id = _rule(client, body="System rule, disabled by id.", scope="system")
    by_type = _rule(
        client, body="System rule, disabled by type.",
        rule_type="long_sessions", scope="system",
    )
    kept = _rule(client, body="System rule that survives.", scope="system")

    disable_by_id = _rule(
        client, body=f"Disable {by_id}.", rule_type=f"disable:{by_id}", scope="ENG-001",
    )
    disable_by_type = _rule(
        client, body="Disable long_sessions.",
        rule_type="disable:long_sessions", scope="ENG-001",
    )

    for rid in (by_id, by_type, kept, disable_by_id, disable_by_type):
        _ref(client, prof, "agent_profile_governed_by_rule", "governance_rule", rid)

    eng = client.get(f"/agent-profiles/{prof}/contract?engagement=ENG-001").json()["data"]
    eng_ids = _enforced_ids(eng)
    # The two named system rules are suppressed; the disable directives themselves
    # are never emitted; the unrelated system rule remains.
    assert by_id not in eng_ids
    assert by_type not in eng_ids
    assert disable_by_id not in eng_ids
    assert disable_by_type not in eng_ids
    assert kept in eng_ids

    # For a different engagement the disable overlays are out of scope, so every
    # system rule is present.
    other = client.get(f"/agent-profiles/{prof}/contract?engagement=ENG-002").json()["data"]
    other_ids = _enforced_ids(other)
    assert by_id in other_ids
    assert by_type in other_ids
    assert kept in other_ids


# --- agent search endpoint (PI-343 / REQ-383) -----------------------------


def test_search_agents_area_anchored_and_tier_filter(client):
    a = client.post(
        "/agent-profiles",
        json={"area": "storage", "tier": "architect", "description": "s arch"},
    ).json()["data"]["identifier"]
    d = client.post(
        "/agent-profiles",
        json={"area": "storage", "tier": "developer", "description": "s dev"},
    ).json()["data"]["identifier"]
    u = client.post(
        "/agent-profiles",
        json={"area": "ui", "tier": "developer", "description": "u dev"},
    ).json()["data"]["identifier"]

    # Area is the hard backstop: only storage profiles come back.
    res = client.get("/agent-profiles/search", params={"area": "storage"}).json()["data"]
    ids = {r["identifier"] for r in res}
    assert ids == {a, d}
    assert u not in ids

    # Tier narrows within the area.
    res2 = client.get(
        "/agent-profiles/search", params={"area": "storage", "tier": "architect"}
    ).json()["data"]
    assert [r["identifier"] for r in res2] == [a]


def test_search_agents_needs_ranking(client):
    plain = client.post(
        "/agent-profiles",
        json={"area": "api", "tier": "developer", "description": "plain"},
    ).json()["data"]["identifier"]
    matchy = client.post(
        "/agent-profiles",
        json={"area": "api", "tier": "developer", "description": "matchy",
              "capability_description": {"specialties": ["rest", "auth"]}},
    ).json()["data"]["identifier"]
    res = client.get(
        "/agent-profiles/search", params={"area": "api", "needs": "auth"}
    ).json()["data"]
    # The capability match ranks first; the plain profile still appears.
    assert res[0]["identifier"] == matchy
    assert plain in {r["identifier"] for r in res}


def test_search_agents_requires_area(client):
    assert client.get("/agent-profiles/search").status_code == 422
