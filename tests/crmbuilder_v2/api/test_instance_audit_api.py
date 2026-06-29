"""Instance audit + membership API tests — PI-185 / PI-255 (PRJ-027).

Exercises POST /instances/{id}/audit (reconcile via a monkeypatched
introspection client) and GET /instances/{id}/memberships, plus the role and
credential gates. Under PI-255 (REQ-300/319, DEC-648..654) a source/both audit is
**candidate-gated**: it never auto-creates canonical objects — undecided source
objects become ``mapping_candidate`` rows, and only a human-resolved
``source_mapping`` drives membership. A source audit reconciles entities / fields
/ associations only (DEC-653).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import mapping_candidate as candidate_repo
from crmbuilder_v2.access.repositories import source_mapping as smg_repo
from crmbuilder_v2.access.repositories import source_mapping_targets as smt_repo
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.api.routers import instances as instances_router
from fastapi.testclient import TestClient

from tests.crmbuilder_v2.conftest import DEFAULT_ENGAGEMENT_ID


@pytest.fixture(autouse=True)
def _keyring_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def client(v2_env):
    tc = TestClient(create_app())
    tc.headers.update({"X-Engagement": DEFAULT_ENGAGEMENT_ID})
    return tc


class _FakeClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_all_scopes(self):
        cust = {"entity": True, "customizable": True, "isCustom": True}
        return (200, {
            "CEngagement": {**cust, "stream": False},
            "CDues": {**cust, "stream": True},
            "Account": {"entity": True, "customizable": True, "isCustom": False},
        })

    def get_i18n(self, language="en_US"):
        return (200, {})

    def get_entity_field_list(self, entity):
        if entity in ("CEngagement", "CDues"):
            return (200, {
                "name": {"type": "varchar"},
                "cStatus": {"type": "enum", "isCustom": True, "required": True},
            })
        return (200, {"name": {"type": "varchar"}})

    def get_all_links(self, entity):
        if entity == "CEngagement":
            return (200, {"dueses": {"type": "hasMany", "entity": "CDues"}})
        return (200, {"engagement": {"type": "belongsTo", "entity": "CEngagement"}})

    def get_collection(self, entity):
        return (200, {})

    def get_layout(self, entity, layout_type):
        if entity == "CEngagement" and layout_type == "detail":
            return (200, {"rows": [["name"]]})
        return (404, None)

    def get_roles(self):
        return (200, {"list": [
            {"name": "Mentor", "data": {"Contact": "yes"},
             "assignmentPermission": "team"},
        ]})

    def get_teams(self):
        return (200, {"list": [{"name": "Coordinators", "description": "Ops"}]})

    def list_report_filters(self, entity_type):
        if entity_type == "CEngagement":
            return (200, {"list": [{"name": "Active", "data": {"status": "open"}}]})
        return (404, None)


def _create(client, **over):
    body = {
        "instance_name": "src",
        "instance_url": "https://src.example.org",
        "instance_role": "source",
        "secret": "api-key",
    }
    body.update(over)
    return client.post("/instances", json=body).json()["data"]


def _resolve_entity_mapping(iid, source_entity_name, target_entity_id):
    """Directly create + resolve a source_mapping (test setup)."""
    with session_scope() as s:
        m = smg_repo.create_source_mapping(
            s, instance_identifier=iid, source_entity_name=source_entity_name,
            decision_type="direct",
        )
        mid = m["source_mapping_identifier"]
        smt_repo.add_target(
            s, source_mapping_identifier=mid, entity_identifier=target_entity_id
        )
        smg_repo.update_source_mapping(
            s, mid, source_entity_name=source_entity_name,
            decision_type="direct", status="resolved",
        )


def test_source_audit_candidate_gates_no_auto_promotion(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client)["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit")
    assert r.status_code == 200, r.text
    summary = r.json()["data"]
    # DEC-653: a source audit reconciles entities / fields / associations only.
    assert set(summary) == {"entities", "fields", "associations"}
    # No canonical object auto-created; undecided entities surface as candidates.
    assert summary["entities"]["created"] == 0
    assert summary["entities"]["candidates"] == 2
    # Fields + associations are deferred until the parent entities are mapped.
    assert summary["fields"]["seen"] == 0
    assert summary["associations"]["seen"] == 0
    # No membership rows (candidates are not membership), and the candidates exist.
    rows = client.get(f"/instances/{iid}/memberships").json()["data"]
    assert rows == []
    with session_scope() as s:
        cands = candidate_repo.list_candidates(
            s, instance_identifier=iid, candidate_type="entity")
        assert {c["source_entity_name"] for c in cands} == {"CEngagement", "CDues"}


def test_source_audit_resolved_mapping_drives_membership(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client)["instance_identifier"]
    with session_scope() as s:
        ent = entity_repo.create_entity(s, name="Engagement", description="x")
        eid = ent["entity_identifier"]
    _resolve_entity_mapping(iid, "CEngagement", eid)
    r = client.post(f"/instances/{iid}/audit")
    assert r.status_code == 200, r.text
    summary = r.json()["data"]
    # The mapped entity reconciles to present; the unmapped one stays a candidate.
    assert summary["entities"]["present"] == 1
    assert summary["entities"]["candidates"] == 1
    rows = client.get(
        f"/instances/{iid}/memberships", params={"member_type": "entity"}
    ).json()["data"]
    assert len(rows) == 1 and rows[0]["member_identifier"] == eid


def test_audit_target_role_rejected(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    inst = _create(client, instance_role="target")
    r = client.post(f"/instances/{inst['instance_identifier']}/audit")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "not_auditable"


def test_audit_missing_credentials_rejected(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    inst = _create(client, secret=None)
    r = client.post(f"/instances/{inst['instance_identifier']}/audit")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "missing_credentials"


def test_audit_entity_endpoint_refreshes_one_entity(client, monkeypatch):
    """REQ-392: the entity-only endpoint re-audits a single entity's slice."""
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client, instance_role="both")["instance_identifier"]
    with session_scope() as s:
        eid = entity_repo.create_entity(
            s, name="Engagement", description="x"  # matches the fake's CEngagement
        )["entity_identifier"]
    r = client.post(f"/instances/{iid}/audit-entity/{eid}")
    assert r.status_code == 200, r.text
    summary = r.json()["data"]["summary"]
    assert summary["entity"] == "Engagement"
    assert summary["present"] is True
    assert "fields" in summary and "relationships" in summary and "layouts" in summary


def test_audit_entity_endpoint_rejects_target_only(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client, instance_role="target")["instance_identifier"]
    with session_scope() as s:
        eid = entity_repo.create_entity(s, name="Engagement", description="x")[
            "entity_identifier"
        ]
    r = client.post(f"/instances/{iid}/audit-entity/{eid}")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "not_auditable"


# -- per-area audit (PI-274 — REQ-308/309/310) -------------------------------


def test_audit_areas_list(client):
    r = client.get("/instances/audit/areas")
    assert r.status_code == 200, r.text
    areas = r.json()["data"]
    assert [a["area"] for a in areas] == [
        "entities", "fields", "associations", "layouts",
        "roles", "field-permissions", "teams", "filtered-tabs",
    ]
    assert areas[0]["label"] == "Entities"
    assert areas[2]["label"] == "Relationships"


def test_audit_single_area_candidate_gates(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client)["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit/entities")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["area"] == "entities"
    assert data["summary"]["created"] == 0
    assert data["summary"]["candidates"] == 2
    # No membership rows yet — candidates await human resolution.
    rows = client.get(f"/instances/{iid}/memberships").json()["data"]
    assert rows == []


def test_audit_source_skips_non_candidate_area(client, monkeypatch):
    # DEC-653: layouts/roles/teams/filtered-tabs are not reconciled on a source
    # audit — the per-area endpoint returns a skipped summary, not a reconcile.
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client)["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit/roles")
    assert r.status_code == 200, r.text
    assert r.json()["data"]["summary"]["skipped"] is True
    # Nothing was reconciled.
    rows = client.get(f"/instances/{iid}/memberships").json()["data"]
    assert rows == []


def test_both_audit_runs_full_drift_no_candidates(client, monkeypatch):
    """REQ-393 / WTK-256: a ``both``-role audit runs the full drift reconcile
    over every area, with no ``source_mapping`` rows and no candidates created."""
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client, instance_role="both")["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit")
    assert r.status_code == 200, r.text
    summary = r.json()["data"]
    # Every area is reconciled — not the truncated entities/fields/associations set.
    assert set(summary) == {
        "entities", "fields", "associations", "layouts",
        "roles", "field_permissions", "teams", "filtered_tabs",
    }
    # Drift path: live custom entities are discovered + marked present, never
    # deferred as candidates (a drift summary has no ``candidates`` key).
    assert summary["entities"]["present"] == 2
    assert "candidates" not in summary["entities"]
    # Membership was populated (the candidate-gated path would leave it empty).
    rows = client.get(
        f"/instances/{iid}/memberships", params={"member_type": "entity"}
    ).json()["data"]
    assert len(rows) == 2
    # No candidates and no source_mapping rows were created or required.
    with session_scope() as s:
        assert candidate_repo.list_candidates(s, instance_identifier=iid) == []
        assert smg_repo.list_source_mappings(s, instance_identifier=iid) == []


def test_both_audit_per_area_reconciles_non_candidate_area(client, monkeypatch):
    """REQ-393 / WTK-256: a deploy-fidelity area (roles) is reconciled on a
    ``both`` audit, not skipped the way a ``source`` audit skips it (DEC-653)."""
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client, instance_role="both")["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit/roles")
    assert r.status_code == 200, r.text
    summary = r.json()["data"]["summary"]
    assert summary.get("skipped") is not True


def test_both_audit_reports_present_drifted_and_absent(client, monkeypatch):
    """REQ-393 / WTK-261: a ``both``-role audit reports the full inventory —
    every object classified present / drifted / absent — with no pre-resolved
    ``source_mapping`` rows required.

    Three canonical entities force one of each state against the fake instance
    (which exposes custom ``CEngagement`` with ``stream`` off and ``CDues`` with
    ``stream`` on):

    * ``Engagement`` — audited attrs match live ``CEngagement`` -> **present**;
    * ``Dues`` — name matches live ``CDues`` but ``track_activity`` diverges from
      the live ``stream`` flag -> **drifted**;
    * ``Ghost`` — a prior present membership with no live counterpart -> **absent**
      (the absent sweep flips the stale membership row).
    """
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client, instance_role="both")["instance_identifier"]
    with session_scope() as s:
        # Present: track_activity matches the live CEngagement (stream off).
        eng = entity_repo.create_entity(
            s, name="Engagement", description="x", track_activity=False
        )["entity_identifier"]
        # Drifted: name matches CDues but track_activity diverges (live stream on).
        dues = entity_repo.create_entity(
            s, name="Dues", description="x", track_activity=False
        )["entity_identifier"]
        # Absent: a canonical with a prior present membership and no live object.
        ghost = entity_repo.create_entity(s, name="Ghost", description="x")[
            "entity_identifier"
        ]
        membership_repo.upsert_membership(
            s,
            instance_identifier=iid,
            member_type="entity",
            member_identifier=ghost,
            state="present",
        )

    r = client.post(f"/instances/{iid}/audit")
    assert r.status_code == 200, r.text
    ent = r.json()["data"]["entities"]
    # Full inventory: one object in each state, none auto-created, none deferred
    # as a candidate (the drift path classifies, it does not gate).
    assert ent["present"] == 1
    assert ent["drifted"] == 1
    assert ent["absent"] == 1
    assert ent["created"] == 0
    assert "candidates" not in ent
    # Membership reflects every state, keyed to the canonical objects.
    rows = client.get(
        f"/instances/{iid}/memberships", params={"member_type": "entity"}
    ).json()["data"]
    states = {row["member_identifier"]: row["state"] for row in rows}
    assert states[eng] == "present"
    assert states[dues] == "drifted"
    assert states[ghost] == "absent"
    # No pre-resolved mapping and no candidate gating was required for any of it.
    with session_scope() as s:
        assert smg_repo.list_source_mappings(s, instance_identifier=iid) == []
        assert candidate_repo.list_candidates(s, instance_identifier=iid) == []


def test_audit_unknown_area_404(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client)["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit/bogus")
    assert r.status_code == 404


class _FieldReadFailsClient(_FakeClient):
    """A mapped custom entity whose field list cannot be read — the
    swallowed-read warning REQ-310 surfaces."""

    def get_all_scopes(self):
        return (200, {
            "CEngagement": {
                "entity": True, "customizable": True, "isCustom": True,
                "stream": False,
            },
        })

    def get_entity_field_list(self, entity):
        return (500, None)


def test_audit_area_surfaces_field_read_warning(client, monkeypatch):
    monkeypatch.setattr(
        instances_router, "EspoIntrospectionClient", _FieldReadFailsClient
    )
    iid = _create(client)["instance_identifier"]
    # The entity must be mapped for its fields to be read at all (candidate-gating).
    with session_scope() as s:
        ent = entity_repo.create_entity(s, name="Engagement", description="x")
        eid = ent["entity_identifier"]
    _resolve_entity_mapping(iid, "CEngagement", eid)
    r = client.post(f"/instances/{iid}/audit/fields")
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert any(
        level == "warning" and "could not read fields" in msg
        for msg, level in data["log"]
    )


def test_audit_area_role_gate(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client, instance_role="target")["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit/entities")
    assert r.status_code == 422
    assert r.json()["errors"][0]["code"] == "not_auditable"


def test_membership_summary(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client)["instance_identifier"]
    with session_scope() as s:
        eid = entity_repo.create_entity(
            s, name="Engagement", description="x")["entity_identifier"]
        # The source field is 'cStatus' on a custom entity, where the c-prefix is
        # part of the natural name (no strip) — the canonical field must match it.
        field_repo.create_field(
            s, field_belongs_to_entity_identifier=eid, name="cStatus",
            description="x", type="enum", required=True,
        )
    _resolve_entity_mapping(iid, "CEngagement", eid)
    client.post(f"/instances/{iid}/audit")
    summary = client.get(f"/instances/{iid}/membership-summary").json()["data"]
    assert summary["entity"]["present"] == 1
    # The mapped entity's matching field reconciles to present membership.
    assert summary["field"]["present"] == 1


def test_publish_plan_target_needs_canonical_design(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    # Canonical design exists (authored, or resolved from an audit). A fresh
    # target (never audited) needs every canonical object pushed.
    with session_scope() as s:
        entity_repo.create_entity(s, name="Engagement", description="x")
    tgt = _create(client, instance_name="tgt", instance_role="target")[
        "instance_identifier"
    ]
    tgt_plan = client.get(f"/instances/{tgt}/publish-plan").json()["data"]
    assert tgt_plan["target_instance"] == tgt
    assert tgt_plan["item_count"] == 1
    assert all(it["reason"] == "never_audited" for it in tgt_plan["items"])


def test_publish_plan_and_summary_404(client):
    assert client.get("/instances/INST-999/publish-plan").status_code == 404
    assert client.get("/instances/INST-999/membership-summary").status_code == 404


def test_audit_missing_instance_404(client):
    assert client.post("/instances/INST-999/audit").status_code == 404
    assert client.get("/instances/INST-999/memberships").status_code == 404
