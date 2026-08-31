"""REQ-541 / PI-438 — audience and moment on the governance-rules REST surface."""

from __future__ import annotations

import pytest

# Uses the shared ``client`` fixture (TestClient with X-Engagement: ENG-001).


def _create(client, body, **extra):
    r = client.post("/governance-rules", json={"source_decision": "DEC-001", "body": body, "enforcement": "advisory", **extra})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def test_create_defaults_and_explicit_values(client):
    plain = _create(client, "plain")
    assert (plain["applies_to"], plain["applies_when"]) == ("all", "always")
    keyed = _create(client, "keyed", applies_to="claude_code", applies_when="deploy")
    assert (keyed["applies_to"], keyed["applies_when"]) == ("claude_code", "deploy")


def test_bad_vocab_is_422(client):
    r = client.post(
        "/governance-rules",
        json={"source_decision": "DEC-001", "body": "x", "enforcement": "advisory", "applies_to": "robot"},
    )
    assert r.status_code == 422
    assert r.json()["errors"][0]["field"] == "applies_to"


def test_list_filters_raw_and_effective(client):
    _create(client, "agent", applies_to="ado_agent")
    _create(client, "session commit", applies_to="claude_code", applies_when="commit")
    _create(client, "everyone")
    raw = client.get("/governance-rules", params={"applies_to": "claude_code"}).json()["data"]
    assert [r["body"] for r in raw] == ["session commit"]
    eff = client.get(
        "/governance-rules", params={"resolution": "effective", "applies_when": "commit"}
    ).json()["data"]
    assert [r["body"] for r in eff] == ["session commit"]
    both = client.get(
        "/governance-rules", params={"applies_to": "all", "applies_when": "always"}
    ).json()["data"]
    assert [r["body"] for r in both] == ["everyone"]


def test_patch_audience_and_moment(client):
    rule = _create(client, "later")
    r = client.patch(
        f"/governance-rules/{rule['identifier']}",
        json={"applies_to": "ui", "applies_when": "release"},
    )
    assert r.status_code == 200, r.text
    assert (r.json()["data"]["applies_to"], r.json()["data"]["applies_when"]) == ("ui", "release")

# REQ-543 / PI-440: a rule names the decision that ruled it.
@pytest.fixture(autouse=True)
def _source_decision(client):
    r = client.post("/decisions", json={
        "identifier": "DEC-001", "title": "Test ruling", "decision_date": "2026-01-01",
        "status": "Active",
        "executive_summary": "A decision that exists so tests can create governance rules that "
                             "name their source decision, as REQ-543 requires of every new rule; "
                             "it carries no other content and stands in for whichever real ruling "
                             "would have made the rule under test.",
    })
    assert r.status_code in (201, 409), r.text
