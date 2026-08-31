"""REQ-543 / PI-440 — the rule lifecycle on the REST surface."""

from __future__ import annotations

import pytest

SUMMARY = ("A ruling recorded so a governance rule under test can name the decision that made "
           "it, as every new rule must; the summary itself carries no further content and is "
           "long enough to satisfy the two-hundred-character floor the record type requires.")


@pytest.fixture(autouse=True)
def _decision(client):
    r = client.post("/decisions", json={"identifier": "DEC-001", "title": "ruling",
                                        "decision_date": "2026-01-01", "status": "Active",
                                        "executive_summary": SUMMARY})
    assert r.status_code == 201, r.text


def _create(client, body, **extra):
    r = client.post("/governance-rules", json={"body": body, "enforcement": "advisory",
                                               "source_decision": "DEC-001", **extra})
    assert r.status_code == 201, r.text
    return r.json()["data"]


def test_create_without_source_decision_is_rejected(client):
    r = client.post("/governance-rules", json={"body": "x", "enforcement": "advisory"})
    assert r.status_code == 422


def test_create_with_unknown_decision_is_404(client):
    r = client.post("/governance-rules", json={"body": "x", "enforcement": "advisory",
                                               "source_decision": "DEC-999"})
    assert r.status_code == 404


def test_duplicate_text_is_422(client):
    _create(client, "One rule per text.")
    r = client.post("/governance-rules", json={"body": "one rule per TEXT.", "enforcement": "advisory",
                                               "source_decision": "DEC-001"})
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "duplicate_rule_text"


def test_wording_and_meaning_changes(client):
    rule = _create(client, "Never force-push main.")
    rid = rule["identifier"]
    r = client.patch(f"/governance-rules/{rid}", json={"body": "Never force push main."})
    assert r.status_code == 422 and r.json()["errors"][0]["code"] == "change_kind_required"
    r = client.patch(f"/governance-rules/{rid}", json={"body": "Never force push main.", "change": "wording"})
    assert r.status_code == 200 and r.json()["data"]["version"] == 2
    r = client.patch(f"/governance-rules/{rid}", json={"body": "Never force push any shared branch.",
                                                       "change": "meaning", "source_decision": "DEC-001"})
    assert r.status_code == 200, r.text
    succ = r.json()["data"]
    assert succ["identifier"] != rid and succ["supersedes"] == [rid] and succ["version"] == 1
    assert client.get(f"/governance-rules/{rid}").json()["data"]["status"] == "retired"


def test_severity_scale_is_enforced(client):
    r = client.post("/governance-rules", json={"body": "x", "enforcement": "advisory",
                                               "severity": "warning", "source_decision": "DEC-001"})
    assert r.status_code == 422
