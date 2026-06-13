"""Capability-coverage report — requirements-provenance Phase 3.

The no-orphan-capability check, both directions: a planning item with no
requirement above it is flagged; one linked to a requirement is not; an active
requirement with no planned work below it is flagged unbuilt.
"""

from __future__ import annotations

_EXEC = "Coverage report test executive summary line. " * 6  # ~270 chars


def _pi(client, ident, **over):
    body = {
        "identifier": ident,
        "title": f"PI {ident}",
        "item_type": "pending_work",
        "status": over.pop("status", "Draft"),
        "executive_summary": _EXEC,
    }
    body.update(over)
    r = client.post("/planning-items", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _req(client, name="A capability"):
    r = client.post(
        "/requirements",
        json={
            "requirement_name": name,
            "requirement_description": "What the system must do.",
            "requirement_acceptance_summary": "Verifiable when it happens.",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["data"]["requirement_identifier"]


def _ref(client, st, si, tt, ti, rel):
    return client.post(
        "/references",
        json={
            "source_type": st,
            "source_id": si,
            "target_type": tt,
            "target_id": ti,
            "relationship": rel,
        },
    )


def _coverage(client):
    r = client.get("/coverage/capabilities")
    assert r.status_code == 200, r.text
    return r.json()["data"]


def test_planning_item_without_requirement_is_an_orphan(client):
    _pi(client, "PI-001")
    cov = _coverage(client)
    ids = [o["identifier"] for o in cov["orphan_planning_items"]]
    assert "PI-001" in ids
    assert cov["summary"]["orphan_planning_items"] >= 1


def test_planning_item_with_requirement_is_not_an_orphan(client):
    rid = _req(client)
    _pi(client, "PI-001")
    linked = _ref(
        client, "planning_item", "PI-001", "requirement", rid,
        "planning_item_implements_requirement",
    )
    assert linked.status_code == 201, linked.text
    cov = _coverage(client)
    ids = [o["identifier"] for o in cov["orphan_planning_items"]]
    assert "PI-001" not in ids


def test_confirmed_requirement_without_plan_is_unbuilt(client):
    rid = _req(client)
    # Drive it to confirmed: provenance + topic + approve.
    assert _ref(client, "requirement", rid, "conversation", "CNV-001",
                "requirement_defined_in_conversation").status_code == 201
    assert _ref(client, "requirement", rid, "topic", "TOP-001",
                "requirement_belongs_to_topic").status_code == 201
    assert _ref(client, "requirement", rid, "decision", "DEC-001",
                "requirement_approved_by_decision").status_code == 201
    cov = _coverage(client)
    unbuilt = [u["requirement_identifier"] for u in cov["unbuilt_requirements"]]
    assert rid in unbuilt


def test_confirmed_requirement_with_a_plan_is_not_unbuilt(client):
    rid = _req(client)
    _ref(client, "requirement", rid, "conversation", "CNV-001",
         "requirement_defined_in_conversation")
    _ref(client, "requirement", rid, "topic", "TOP-001",
         "requirement_belongs_to_topic")
    _ref(client, "requirement", rid, "decision", "DEC-001",
         "requirement_approved_by_decision")
    _pi(client, "PI-001")
    assert _ref(client, "planning_item", "PI-001", "requirement", rid,
                "planning_item_implements_requirement").status_code == 201
    cov = _coverage(client)
    unbuilt = [u["requirement_identifier"] for u in cov["unbuilt_requirements"]]
    assert rid not in unbuilt
