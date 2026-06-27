"""association_mapping repo + router tests — PI-255 (PRJ-027 / DEC-654).

Covers the relationship-level mapping decision entity (``AMP-``): auto-assigned
and explicit identifiers, list filters, the gated status lifecycle (resolve /
mark-stale), patch, soft-delete/restore, and the REST surface.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError, UnprocessableError
from crmbuilder_v2.access.repositories import association_mapping as amap
from crmbuilder_v2.api.main import create_app
from fastapi.testclient import TestClient

from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID

# --- repo -------------------------------------------------------------------


def test_create_autoassigns_identifier(v2_env):
    with session_scope() as s:
        a = amap.create_association_mapping(
            s, instance_identifier="INST-001",
            source_association_name="dueses", decision_type="direct",
        )
        assert a["association_mapping_identifier"] == "AMP-001"
        assert a["status"] == "unresolved"
        b = amap.create_association_mapping(
            s, instance_identifier="INST-001",
            source_association_name="mentors", decision_type="referential",
        )
        assert b["association_mapping_identifier"] == "AMP-002"


def test_explicit_identifier_and_collision(v2_env):
    with session_scope() as s:
        amap.create_association_mapping(
            s, instance_identifier="INST-001",
            source_association_name="dueses", decision_type="direct",
            identifier="AMP-050",
        )
        with pytest.raises(ConflictError):
            amap.create_association_mapping(
                s, instance_identifier="INST-001",
                source_association_name="dueses", decision_type="direct",
                identifier="AMP-050",
            )


def test_bad_decision_type_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            amap.create_association_mapping(
                s, instance_identifier="INST-001",
                source_association_name="x", decision_type="decomposition",
            )


def test_list_filters_by_instance_and_status(v2_env):
    with session_scope() as s:
        amap.create_association_mapping(
            s, instance_identifier="INST-001",
            source_association_name="a", decision_type="direct",
        )
        b = amap.create_association_mapping(
            s, instance_identifier="INST-002",
            source_association_name="b", decision_type="direct",
        )
        amap.update_association_mapping(
            s, b["association_mapping_identifier"],
            source_association_name="b", decision_type="direct",
            status="resolved",
        )
        only_1 = amap.list_association_mappings(s, instance_identifier="INST-001")
        assert [r["association_mapping_identifier"] for r in only_1] == ["AMP-001"]
        resolved = amap.list_association_mappings(s, status="resolved")
        assert [r["association_mapping_identifier"] for r in resolved] == ["AMP-002"]


def test_resolve_then_mark_stale(v2_env):
    with session_scope() as s:
        a = amap.create_association_mapping(
            s, instance_identifier="INST-001",
            source_association_name="dueses", decision_type="direct",
        )
        aid = a["association_mapping_identifier"]
        resolved = amap.update_association_mapping(
            s, aid, source_association_name="dueses", decision_type="direct",
            status="resolved", target_association_identifier="ASC-001",
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None
        stale = amap.mark_stale(s, aid, reason="source_changed", severity="high")
        assert stale["status"] == "stale"
        assert stale["stale_reason"] == "source_changed"


def test_patch_and_soft_delete_restore(v2_env):
    with session_scope() as s:
        a = amap.create_association_mapping(
            s, instance_identifier="INST-001",
            source_association_name="dueses", decision_type="direct",
        )
        aid = a["association_mapping_identifier"]
        patched = amap.patch_association_mapping(
            s, aid, notes="reviewed", decision_type="referential",
        )
        assert patched["notes"] == "reviewed"
        assert patched["decision_type"] == "referential"
        amap.delete_association_mapping(s, aid)
        assert amap.get_association_mapping(s, aid) is None
        amap.restore_association_mapping(s, aid)
        assert amap.get_association_mapping(s, aid) is not None


# --- router -----------------------------------------------------------------


@pytest.fixture
def client(v2_env):
    tc = TestClient(create_app())
    tc.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})
    return tc


def test_router_crud_and_mark_stale(client):
    r = client.post("/association-mappings", json={
        "association_mapping_instance_identifier": "INST-001",
        "association_mapping_source_association_name": "dueses",
        "association_mapping_decision_type": "direct",
    })
    assert r.status_code == 201, r.text
    aid = r.json()["data"]["association_mapping_identifier"]

    assert client.get(f"/association-mappings/{aid}").status_code == 200
    listed = client.get(
        "/association-mappings", params={"instance_identifier": "INST-001"}
    ).json()["data"]
    assert len(listed) == 1

    r = client.put(f"/association-mappings/{aid}", json={
        "association_mapping_source_association_name": "dueses",
        "association_mapping_decision_type": "direct",
        "association_mapping_status": "resolved",
        "association_mapping_target_association_identifier": "ASC-001",
    })
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "resolved"

    r = client.post(
        f"/association-mappings/{aid}/mark-stale",
        json={"reason": "source_changed", "severity": "low"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["data"]["status"] == "stale"

    assert client.delete(f"/association-mappings/{aid}").status_code == 200
    assert client.get(f"/association-mappings/{aid}").status_code == 404


def test_router_next_identifier(client):
    r = client.get("/association-mappings/next-identifier")
    assert r.status_code == 200
    assert r.json()["data"]["next"] == "AMP-001"
