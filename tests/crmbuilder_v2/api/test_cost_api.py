"""Cost aggregation API — PI-265 (PRJ-041 / REQ-307), v1 surfacing.

The read-only /cost views over the cost_events telemetry: summary total, breakdown by a
dimension, and recent events — each over the active engagement and an optional filter.
Cost events are recorded internally (no API write path), so the tests seed via the
repository under the same engagement the client carries.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import cost_events


def _seed():
    with session_scope() as s:
        cost_events.record(s, source="sdk", model="claude-sonnet-4-6",
                           input_tokens=1_000_000, release_identifier="REL-1",
                           area="api", stage="qa")               # $3
        cost_events.record(s, source="claude_cli", model="claude-opus-4-8",
                           input_tokens=1_000_000, release_identifier="REL-1",
                           area="storage", stage="develop")       # $15
        cost_events.record(s, source="sdk", model="claude-sonnet-4-6",
                           input_tokens=1_000_000, release_identifier="REL-2",
                           area="api", stage="qa")                # $3


def test_summary_total_and_filter(client):
    _seed()
    total = client.get("/cost/summary")
    assert total.status_code == 200, total.text
    data = total.json()["data"]
    assert data["cost_usd"] == 21.0 and data["event_count"] == 3

    rel1 = client.get("/cost/summary", params={"release_identifier": "REL-1"})
    assert rel1.json()["data"]["cost_usd"] == 18.0
    api = client.get("/cost/summary", params={"area": "api"})
    assert api.json()["data"]["cost_usd"] == 6.0


def test_breakdown_by_dimension(client):
    _seed()
    r = client.get("/cost/by/area")
    assert r.status_code == 200, r.text
    rows = r.json()["data"]
    assert rows[0]["key"] == "storage" and rows[0]["cost_usd"] == 15.0
    by_source = {row["key"]: row["cost_usd"]
                 for row in client.get("/cost/by/source").json()["data"]}
    assert by_source == {"sdk": 6.0, "claude_cli": 15.0}


def test_bad_dimension_is_422(client):
    r = client.get("/cost/by/nonsense")
    assert r.status_code == 422, r.text


def test_events_listing_limit_and_filter(client):
    _seed()
    r = client.get("/cost/events", params={"limit": 2})
    assert r.status_code == 200, r.text
    assert len(r.json()["data"]) == 2
    rel2 = client.get("/cost/events", params={"release_identifier": "REL-2"})
    rows = rel2.json()["data"]
    assert len(rows) == 1 and rows[0]["release_identifier"] == "REL-2"


def test_events_limit_bounds_enforced(client):
    assert client.get("/cost/events", params={"limit": 0}).status_code == 422
    assert client.get("/cost/events", params={"limit": 9999}).status_code == 422


def test_estimate_endpoint(client):
    _seed()  # REL-1 = $18, REL-2 = $3 -> two release runs
    r = client.get("/cost/estimate")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["basis_runs"] == 2
    assert d["projected_cost_usd"] == 10.5      # mean of 18 and 3
    assert d["high_water_cost_usd"] == 18.0


def test_budget_gate_roundtrip(client):
    r = client.post("/cost/budget-approval", json={
        "release_identifier": "REL-9", "budget_usd": 20.0, "projected_usd": 10.5,
        "decision": "approved", "operator": "doug"})
    assert r.status_code == 201, r.text
    assert client.get("/cost/budget-gate/REL-9").json()["data"]["launch_approved"] is True
    # a later decline overrides the approval
    client.post("/cost/budget-approval", json={
        "release_identifier": "REL-9", "budget_usd": 20.0, "projected_usd": 10.5,
        "decision": "declined", "operator": "doug"})
    assert client.get("/cost/budget-gate/REL-9").json()["data"]["launch_approved"] is False
