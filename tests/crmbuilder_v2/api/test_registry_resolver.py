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
