"""Per-engagement governance-rule overrides (REQ-529..533 / DEC-955 / PI-435).

A system rule is the inheritable default; an engagement-scoped rule with the
same ``rule_type`` shadows it for that engagement only (most specific scope
wins). Every override records a ``supersedes`` edge to the default it
displaces, and an override that targets an untyped default by identifier is
rejected until the default is keyed.

The ``client`` fixture carries ``X-Engagement: ENG-001``; ``ENG-002`` is used as
the "other engagement" that must keep seeing the system default.
"""

from __future__ import annotations


def _rule(client, *, body, rule_type=None, scope=None, enforcement="advisory"):
    payload = {"body": body, "enforcement": enforcement}
    if rule_type is not None:
        payload["rule_type"] = rule_type
    if scope is not None:
        payload["scope"] = scope
    return client.post("/governance-rules", json=payload)


def _created(resp):
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _effective(client, engagement=None):
    params = {"resolution": "effective"}
    if engagement is not None:
        params["engagement"] = engagement
    resp = client.get("/governance-rules", params=params)
    assert resp.status_code == 200, resp.text
    return {r["identifier"]: r for r in resp.json()["data"]}


def _supersedes(client, rule_id):
    resp = client.get(
        "/references",
        params={
            "source_type": "governance_rule",
            "source_id": rule_id,
            "relationship_kind": "supersedes",
        },
    )
    assert resp.status_code == 200, resp.text
    return sorted(e["target_id"] for e in resp.json()["data"])


# --- REQ-530: engagement rule shadows the system rule by rule_type ----------


def test_effective_read_substitutes_engagement_rule_for_system_rule(client):
    react = _created(_rule(
        client, body="Custom apps are written in React.",
        rule_type="ui_framework", scope="system",
    ))["identifier"]
    angular = _created(_rule(
        client, body="ENG-001: custom apps are written in Angular.",
        rule_type="ui_framework", scope="ENG-001",
    ))["identifier"]
    untouched = _created(_rule(
        client, body="Never force-push.", rule_type="no_force_push", scope="system",
    ))["identifier"]

    # (a) Under the client engagement the override is the effective rule for
    #     the key and the system rule is shadowed.
    eng = _effective(client)  # X-Engagement: ENG-001
    assert angular in eng and react not in eng
    assert untouched in eng
    assert eng[angular]["shadows"] == [react]

    # (b) Any other engagement still sees the system default.
    other = _effective(client, engagement="ENG-002")
    assert react in other and angular not in other
    assert untouched in other

    # The raw listing is unchanged: both rows are stored.
    raw = {r["identifier"] for r in client.get("/governance-rules").json()["data"]}
    assert {react, angular, untouched} <= raw


def test_effective_read_is_active_only_and_rejects_unknown_resolution(client):
    retired = _created(_rule(client, body="Retired default.", rule_type="k", scope="system"))
    client.patch(f"/governance-rules/{retired['identifier']}", json={"status": "retired"})
    assert retired["identifier"] not in _effective(client)

    resp = client.get("/governance-rules", params={"resolution": "bogus"})
    assert resp.status_code == 422
    assert resp.json()["errors"][0]["field"] == "resolution"


# --- REQ-531: every override records a supersedes reference ----------------


def test_override_records_supersedes_edge_to_shadowed_default(client):
    react = _created(_rule(
        client, body="React by default.", rule_type="ui_framework", scope="system",
    ))["identifier"]
    angular = _created(_rule(
        client, body="Angular here.", rule_type="ui_framework", scope="ENG-001",
    ))
    assert angular["supersedes"] == [react]
    assert _supersedes(client, angular["identifier"]) == [react]

    # A disable directive is an override too — by identifier or by rule_type.
    by_id = _created(_rule(
        client, body=f"Disable {react}.", rule_type=f"disable:{react}", scope="ENG-001",
    ))
    assert _supersedes(client, by_id["identifier"]) == [react]
    by_type = _created(_rule(
        client, body="Disable ui_framework.", rule_type="disable:ui_framework",
        scope="ENG-001",
    ))
    assert _supersedes(client, by_type["identifier"]) == [react]

    # An engagement rule that shadows nothing is additive: no provenance edge.
    additive = _created(_rule(
        client, body="Client-only convention.", rule_type="client_only", scope="ENG-001",
    ))
    assert "supersedes" not in additive
    assert _supersedes(client, additive["identifier"]) == []

    # A client's full set of deviations is listable from the edges alone.
    deviations = client.get(
        "/references",
        params={"target_type": "governance_rule", "target_id": react,
                "relationship_kind": "supersedes"},
    ).json()["data"]
    assert sorted(e["source_id"] for e in deviations) == sorted(
        [angular["identifier"], by_id["identifier"], by_type["identifier"]]
    )


# --- REQ-532: untyped defaults are keyed on demand, at first override ------


def test_override_of_untyped_default_is_rejected_until_keyed(client):
    untyped = _created(_rule(client, body="Untyped default.", scope="system"))["identifier"]
    before = len(client.get("/governance-rules", params={"scope": "ENG-001"}).json()["data"])

    resp = _rule(
        client, body=f"Disable {untyped}.", rule_type=f"disable:{untyped}", scope="ENG-001",
    )
    assert resp.status_code == 422, resp.text
    err = resp.json()["errors"][0]
    assert err["code"] == "demand_driven_keying"
    assert untyped in err["message"]
    # The rejected override left no row behind.
    after = len(client.get("/governance-rules", params={"scope": "ENG-001"}).json()["data"])
    assert after == before

    # Key the default on demand, then the override is accepted and effective.
    keyed = client.patch(f"/governance-rules/{untyped}", json={"rule_type": "session_length"})
    assert keyed.status_code == 200, keyed.text
    disable = _created(_rule(
        client, body=f"Disable {untyped}.", rule_type=f"disable:{untyped}", scope="ENG-001",
    ))
    assert _supersedes(client, disable["identifier"]) == [untyped]
    assert untyped not in _effective(client)
    assert untyped in _effective(client, engagement="ENG-002")


# --- REQ-533: agent contracts assemble with the overrides substituted ------


def test_contract_assembly_substitutes_engagement_override(client):
    prof = client.post(
        "/agent-profiles",
        json={"area": "ui", "tier": "developer", "description": "UI dev."},
    ).json()["data"]["identifier"]
    react = _created(_rule(
        client, body="Custom apps are written in React.",
        rule_type="ui_framework", scope="system",
    ))["identifier"]
    angular = _created(_rule(
        client, body="ENG-001: custom apps are written in Angular.",
        rule_type="ui_framework", scope="ENG-001",
    ))["identifier"]
    for rid in (react, angular):
        assert client.post(
            "/references",
            json={"source_type": "agent_profile", "source_id": prof,
                  "target_type": "governance_rule", "target_id": rid,
                  "relationship": "agent_profile_governed_by_rule"},
        ).status_code == 201

    eng = client.get(f"/agent-profiles/{prof}/contract?engagement=ENG-001").json()["data"]
    eng_ids = [r["identifier"] for r in eng["advisory_rules"]]
    assert angular in eng_ids and react not in eng_ids
    assert "Angular" in eng["system_prompt"] and "React" not in eng["system_prompt"]

    other = client.get(f"/agent-profiles/{prof}/contract?engagement=ENG-002").json()["data"]
    other_ids = [r["identifier"] for r in other["advisory_rules"]]
    assert react in other_ids and angular not in other_ids

    # The contract and the effective read agree on the substitution.
    assert set(eng_ids) <= set(_effective(client))
