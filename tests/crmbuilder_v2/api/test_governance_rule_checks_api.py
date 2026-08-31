"""REQ-542 / PI-439 — checks and enforcement overrides on the REST surface."""

from __future__ import annotations

CHECK = {"kind": "forbidden_command", "pattern": r"\bgit\s+push\s+--force\b"}


def test_enforced_without_check_is_422(client):
    r = client.post("/governance-rules", json={"body": "x", "enforcement": "enforced"})
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "enforced_requires_check"


def test_enforcement_override_round_trip(client):
    r = client.post(
        "/governance-rules",
        json={"body": "no force push", "enforcement": "enforced_with_override", "predicate": CHECK},
    )
    assert r.status_code == 201, r.text
    rid = r.json()["data"]["identifier"]
    o = client.post(
        f"/governance-rules/{rid}/enforcement-overrides",
        json={"reason": "rewriting my own branch", "command": "git push --force", "session_ref": "s1"},
    )
    assert o.status_code == 201, o.text
    assert o.json()["data"]["reason"] == "rewriting my own branch"
    listed = client.get(f"/governance-rules/{rid}/enforcement-overrides").json()["data"]
    assert [x["session_ref"] for x in listed] == ["s1"]


def test_override_on_hard_enforced_rule_is_422(client):
    r = client.post(
        "/governance-rules",
        json={"body": "never", "enforcement": "enforced", "predicate": CHECK},
    )
    rid = r.json()["data"]["identifier"]
    o = client.post(f"/governance-rules/{rid}/enforcement-overrides", json={"reason": "x"})
    assert o.status_code == 422
    assert o.json()["errors"][0]["code"] == "not_overridable"
