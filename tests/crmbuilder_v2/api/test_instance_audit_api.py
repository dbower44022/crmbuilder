"""Instance audit + membership API tests — PI-185 (PRJ-027).

Exercises POST /instances/{id}/audit (entity reconcile via a monkeypatched
introspection client) and GET /instances/{id}/memberships, plus the role and
credential gates.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
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

    def get_entity_field_list(self, entity):
        # Custom entities expose a native base field (skipped) + a custom field
        # (reconciled). The native Account exposes only base fields, so it is
        # not a "customized native" entity and is left out of the inventory.
        if entity in ("CEngagement", "CDues"):
            return (200, {
                "name": {"type": "varchar"},
                "cStatus": {"type": "enum", "isCustom": True, "required": True},
            })
        return (200, {"name": {"type": "varchar"}})

    def get_all_links(self, entity):
        # CEngagement has a custom-to-custom hasMany to CDues; CDues' reciprocal
        # belongsTo is skipped.
        if entity == "CEngagement":
            return (200, {"dueses": {"type": "hasMany", "entity": "CDues"}})
        return (200, {"engagement": {"type": "belongsTo", "entity": "CEngagement"}})

    def get_layout(self, entity, layout_type):
        # CEngagement detail layout only; other types/entities have none.
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


def _create(client, **over):
    body = {
        "instance_name": "src",
        "instance_url": "https://src.example.org",
        "instance_role": "source",
        "secret": "api-key",
    }
    body.update(over)
    return client.post("/instances", json=body).json()["data"]


def test_audit_reconciles_and_lists_memberships(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    inst = _create(client)
    iid = inst["instance_identifier"]
    r = client.post(f"/instances/{iid}/audit")
    assert r.status_code == 200, r.text
    summary = r.json()["data"]
    assert summary["entities"]["created"] == 2
    assert summary["entities"]["present"] == 2
    # One custom field per custom entity reconciled.
    assert summary["fields"]["created"] == 2
    assert summary["fields"]["present"] == 2
    # One custom-to-custom relationship reconciled.
    assert summary["associations"]["created"] == 1
    assert summary["associations"]["present"] == 1
    # One detail layout, one role, one team.
    assert summary["layouts"]["created"] == 1
    assert summary["roles"]["created"] == 1
    assert summary["teams"]["created"] == 1
    # Memberships: 2 entities + 2 fields + 1 association + 1 layout + 1 role + 1 team.
    rows = client.get(f"/instances/{iid}/memberships").json()["data"]
    assert len(rows) == 8
    types = sorted(row["member_type"] for row in rows)
    assert types == [
        "association", "entity", "entity", "field", "field",
        "layout", "role", "team",
    ]
    assert all(row["state"] == "present" for row in rows)
    # Filter by member_type.
    only_fields = client.get(
        f"/instances/{iid}/memberships", params={"member_type": "field"}
    ).json()["data"]
    assert len(only_fields) == 2


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


def test_membership_summary(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    iid = _create(client)["instance_identifier"]
    client.post(f"/instances/{iid}/audit")
    summary = client.get(f"/instances/{iid}/membership-summary").json()["data"]
    assert summary["entity"]["present"] == 2
    assert summary["field"]["present"] == 2
    assert summary["association"]["present"] == 1


def test_publish_plan_target_needs_everything(client, monkeypatch):
    monkeypatch.setattr(instances_router, "EspoIntrospectionClient", _FakeClient)
    # Audit a source -> canonical inventory populated, all present in source.
    src = _create(client)["instance_identifier"]
    client.post(f"/instances/{src}/audit")
    src_plan = client.get(f"/instances/{src}/publish-plan").json()["data"]
    assert src_plan["item_count"] == 0  # source already matches the canonical design

    # A fresh target (never audited) needs the whole canonical design pushed.
    tgt = _create(client, instance_name="tgt", instance_role="target")[
        "instance_identifier"
    ]
    tgt_plan = client.get(f"/instances/{tgt}/publish-plan").json()["data"]
    assert tgt_plan["target_instance"] == tgt
    # 2 entities + 2 fields + 1 association + 1 layout + 1 role + 1 team.
    assert tgt_plan["item_count"] == 8
    assert all(it["reason"] == "never_audited" for it in tgt_plan["items"])


def test_publish_plan_and_summary_404(client):
    assert client.get("/instances/INST-999/publish-plan").status_code == 404
    assert client.get("/instances/INST-999/membership-summary").status_code == 404


def test_audit_missing_instance_404(client):
    assert client.post("/instances/INST-999/audit").status_code == 404
    assert client.get("/instances/INST-999/memberships").status_code == 404
