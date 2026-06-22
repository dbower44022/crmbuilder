"""Source-mapping model REST CRUD tests — PI-255 (PRJ-027).

Smoke-covers the five source-mapping routers end to end (source mappings, field
mappings, targets, value mappings, reconciler candidates) so the routers +
schemas + repos wire correctly through the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient

from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID


@pytest.fixture
def client(v2_env):
    tc = TestClient(create_app())
    tc.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})
    return tc


def _make_source_mapping(client, **overrides):
    body = {
        "source_mapping_instance_identifier": "INS-001",
        "source_mapping_source_entity_name": "LegacyContact",
        "source_mapping_decision_type": "direct",
    }
    body.update(overrides)
    r = client.post("/source-mappings", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _make_field_mapping(client, smg, **overrides):
    body = {
        "field_mapping_source_mapping_identifier": smg,
        "field_mapping_source_field_name": "legacy_email",
        "field_mapping_decision_type": "direct",
    }
    body.update(overrides)
    r = client.post("/field-mappings", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


# --- source mappings -------------------------------------------------------


def test_source_mapping_crud(client):
    created = _make_source_mapping(client)
    smg = created["source_mapping_identifier"]
    assert smg == "SMG-001"
    assert created["status"] == "unresolved"

    got = client.get(f"/source-mappings/{smg}").json()["data"]
    assert got["source_entity_name"] == "LegacyContact"
    assert got["decision_type"] == "direct"

    listed = client.get("/source-mappings").json()["data"]
    assert len(listed) == 1
    # filter by instance + status
    assert (
        len(client.get("/source-mappings?instance_identifier=INS-001").json()["data"])
        == 1
    )
    assert (
        client.get("/source-mappings?status=resolved").json()["data"] == []
    )
    assert (
        client.get("/source-mappings/next-identifier").json()["data"]["next"]
        == "SMG-002"
    )

    # patch a patchable field
    patched = client.patch(
        f"/source-mappings/{smg}",
        json={"source_mapping_decision_type": "referential"},
    )
    assert patched.json()["data"]["decision_type"] == "referential"

    # bad enum rejected
    bad = client.post(
        "/source-mappings",
        json={
            "source_mapping_instance_identifier": "INS-001",
            "source_mapping_source_entity_name": "X",
            "source_mapping_decision_type": "bogus",
        },
    )
    assert bad.status_code == 422


def test_source_mapping_mark_stale_and_soft_delete(client):
    smg = _make_source_mapping(client)["source_mapping_identifier"]

    # full replace → resolved
    replaced = client.put(
        f"/source-mappings/{smg}",
        json={
            "source_mapping_source_entity_name": "LegacyContact",
            "source_mapping_decision_type": "direct",
            "source_mapping_status": "resolved",
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["data"]["status"] == "resolved"

    # status transition: mark stale
    staled = client.post(
        f"/source-mappings/{smg}/mark-stale",
        json={"reason": "source_changed", "severity": "high"},
    )
    assert staled.status_code == 200, staled.text
    data = staled.json()["data"]
    assert data["status"] == "stale"
    assert data["stale_reason"] == "source_changed"
    assert data["stale_severity"] == "high"

    # soft-delete → 404 on plain get → restore → visible again
    assert client.delete(f"/source-mappings/{smg}").status_code == 200
    assert client.get(f"/source-mappings/{smg}").status_code == 404
    assert (
        client.get(
            f"/source-mappings/{smg}?include_deleted=true"
        ).status_code
        == 200
    )
    restored = client.post(f"/source-mappings/{smg}/restore")
    assert restored.status_code == 200, restored.text
    assert client.get(f"/source-mappings/{smg}").status_code == 200


def test_source_mapping_get_missing_404(client):
    assert client.get("/source-mappings/SMG-999").status_code == 404


# --- field mappings --------------------------------------------------------


def test_field_mapping_crud(client):
    smg = _make_source_mapping(client)["source_mapping_identifier"]
    created = _make_field_mapping(
        client, smg, field_mapping_target_entity_identifier="ENT-001"
    )
    fmp = created["field_mapping_identifier"]
    assert fmp == "FMP-001"
    assert created["status"] == "unresolved"
    assert created["target_entity_identifier"] == "ENT-001"

    got = client.get(f"/field-mappings/{fmp}").json()["data"]
    assert got["source_field_name"] == "legacy_email"

    # filter by parent source mapping
    listed = client.get(
        f"/field-mappings?source_mapping_identifier={smg}"
    ).json()["data"]
    assert len(listed) == 1
    assert (
        client.get("/field-mappings/next-identifier").json()["data"]["next"]
        == "FMP-002"
    )

    # patch
    patched = client.patch(
        f"/field-mappings/{fmp}",
        json={"field_mapping_target_field_identifier": "FLD-009"},
    )
    assert patched.json()["data"]["target_field_identifier"] == "FLD-009"

    # full replace → resolved, then mark stale
    replaced = client.put(
        f"/field-mappings/{fmp}",
        json={
            "field_mapping_source_field_name": "legacy_email",
            "field_mapping_decision_type": "referential_exact",
            "field_mapping_status": "resolved",
        },
    )
    assert replaced.status_code == 200, replaced.text
    assert replaced.json()["data"]["status"] == "resolved"

    staled = client.post(
        f"/field-mappings/{fmp}/mark-stale",
        json={"reason": "design_changed", "severity": "low"},
    )
    assert staled.json()["data"]["status"] == "stale"

    # soft-delete / restore
    assert client.delete(f"/field-mappings/{fmp}").status_code == 200
    assert client.get(f"/field-mappings/{fmp}").status_code == 404
    assert client.post(f"/field-mappings/{fmp}/restore").status_code == 200
    assert client.get(f"/field-mappings/{fmp}").status_code == 200


def test_field_mapping_bad_enum_rejected(client):
    smg = _make_source_mapping(client)["source_mapping_identifier"]
    bad = client.post(
        "/field-mappings",
        json={
            "field_mapping_source_mapping_identifier": smg,
            "field_mapping_source_field_name": "x",
            "field_mapping_decision_type": "bogus",
        },
    )
    assert bad.status_code == 422


# --- source mapping targets ------------------------------------------------


def test_source_mapping_targets(client):
    smg = _make_source_mapping(client)["source_mapping_identifier"]

    # add (idempotent)
    r1 = client.post(
        "/source-mapping-targets",
        json={"source_mapping_identifier": smg, "entity_identifier": "ENT-001"},
    )
    assert r1.status_code == 201, r1.text
    r2 = client.post(
        "/source-mapping-targets",
        json={"source_mapping_identifier": smg, "entity_identifier": "ENT-001"},
    )
    assert r2.status_code == 201
    listed = client.get(
        f"/source-mapping-targets?source_mapping_identifier={smg}"
    ).json()["data"]
    assert len(listed) == 1

    # set (replace-all)
    set_resp = client.put(
        "/source-mapping-targets",
        json={
            "source_mapping_identifier": smg,
            "entity_identifiers": ["ENT-002", "ENT-003"],
        },
    )
    assert set_resp.status_code == 200, set_resp.text
    assert len(set_resp.json()["data"]) == 2
    names = {
        t["entity_identifier"]
        for t in client.get(
            f"/source-mapping-targets?source_mapping_identifier={smg}"
        ).json()["data"]
    }
    assert names == {"ENT-002", "ENT-003"}

    # remove (body on DELETE)
    rm = client.request(
        "DELETE",
        "/source-mapping-targets",
        json={"source_mapping_identifier": smg, "entity_identifier": "ENT-002"},
    )
    assert rm.status_code == 200, rm.text
    assert rm.json()["data"] is None
    remaining = client.get(
        f"/source-mapping-targets?source_mapping_identifier={smg}"
    ).json()["data"]
    assert {t["entity_identifier"] for t in remaining} == {"ENT-003"}


# --- value mappings --------------------------------------------------------


def test_value_mappings(client):
    smg = _make_source_mapping(client)["source_mapping_identifier"]
    fmp = _make_field_mapping(
        client, smg, field_mapping_decision_type="referential_interpreted"
    )["field_mapping_identifier"]

    created = client.post(
        "/value-mappings",
        json={
            "field_mapping_identifier": fmp,
            "source_value": "OLD",
            "decision_type": "interpreted",
            "target_value": "NEW",
        },
    )
    assert created.status_code == 201, created.text
    vid = created.json()["data"]["id"]
    assert created.json()["data"]["target_value"] == "NEW"

    got = client.get(f"/value-mappings/{vid}").json()["data"]
    assert got["source_value"] == "OLD"

    listed = client.get(
        f"/value-mappings?field_mapping_identifier={fmp}"
    ).json()["data"]
    assert len(listed) == 1

    # update
    updated = client.put(
        f"/value-mappings/{vid}",
        json={"decision_type": "direct", "target_value": "NEW2"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["data"]["target_value"] == "NEW2"

    # supersede by a replacement row
    replacement = client.post(
        "/value-mappings",
        json={
            "field_mapping_identifier": fmp,
            "source_value": "OLD2",
            "decision_type": "direct",
        },
    ).json()["data"]
    sup = client.post(
        f"/value-mappings/{vid}/supersede",
        json={"replacement_id": replacement["id"]},
    )
    assert sup.status_code == 200, sup.text
    assert sup.json()["data"]["status"] == "superseded"
    assert sup.json()["data"]["superseded_by"] == replacement["id"]

    # superseded row hidden by default, shown with include_superseded
    active = client.get(
        f"/value-mappings?field_mapping_identifier={fmp}"
    ).json()["data"]
    assert vid not in {v["id"] for v in active}
    with_all = client.get(
        f"/value-mappings?field_mapping_identifier={fmp}&include_superseded=true"
    ).json()["data"]
    assert vid in {v["id"] for v in with_all}


def test_value_mapping_get_missing_404(client):
    assert client.get("/value-mappings/999").status_code == 404


# --- mapping candidates ----------------------------------------------------


def test_mapping_candidates(client):
    created = client.post(
        "/mapping-candidates",
        json={
            "instance_identifier": "INS-001",
            "candidate_type": "entity",
            "source_entity_name": "UnknownThing",
            "suggestion_confidence": "high",
            "suggestion_basis": "name match",
        },
    )
    assert created.status_code == 201, created.text
    cid = created.json()["data"]["id"]
    assert created.json()["data"]["resolved"] is False

    got = client.get(f"/mapping-candidates/{cid}").json()["data"]
    assert got["candidate_type"] == "entity"

    # filters
    assert (
        len(
            client.get(
                "/mapping-candidates?instance_identifier=INS-001"
            ).json()["data"]
        )
        == 1
    )
    assert (
        client.get("/mapping-candidates?resolved=true").json()["data"] == []
    )

    # bulk create
    bulk = client.post(
        "/mapping-candidates/bulk",
        json={
            "candidates": [
                {
                    "instance_identifier": "INS-001",
                    "candidate_type": "field",
                    "source_entity_name": "LegacyContact",
                    "source_field_name": "weird_field",
                },
                {
                    "instance_identifier": "INS-001",
                    "candidate_type": "value",
                    "source_entity_name": "LegacyContact",
                    "source_field_name": "status",
                    "source_value": "Z",
                },
            ]
        },
    )
    assert bulk.status_code == 201, bulk.text
    assert len(bulk.json()["data"]) == 2
    assert len(client.get("/mapping-candidates").json()["data"]) == 3

    # resolve
    resolved = client.post(
        f"/mapping-candidates/{cid}/resolve",
        json={"resolved_to_source_mapping_identifier": "SMG-001"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["data"]["resolved"] is True
    assert (
        resolved.json()["data"]["resolved_to_source_mapping_identifier"]
        == "SMG-001"
    )
    assert (
        len(client.get("/mapping-candidates?resolved=true").json()["data"]) == 1
    )


def test_mapping_candidate_get_missing_404(client):
    assert client.get("/mapping-candidates/999").status_code == 404
