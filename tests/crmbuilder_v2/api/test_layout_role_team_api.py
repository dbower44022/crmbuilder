"""Layout / role / team REST CRUD tests — PI-193 / PI-194 (PRJ-027).

Smoke-covers the three new design-family routers end to end (create, get, list,
patch, delete) so the routers + schemas + repos wire correctly.
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


def test_role_crud(client):
    r = client.post("/roles", json={
        "role_name": "Mentor", "role_scope_access": {"Contact": "yes"},
    })
    assert r.status_code == 201, r.text
    rid = r.json()["data"]["role_identifier"]
    assert rid == "ROL-001"
    assert client.get(f"/roles/{rid}").json()["data"]["role_name"] == "Mentor"
    assert len(client.get("/roles").json()["data"]) == 1
    patched = client.patch(f"/roles/{rid}", json={"role_status": "confirmed"})
    assert patched.json()["data"]["role_status"] == "confirmed"
    assert client.delete(f"/roles/{rid}").status_code == 200
    assert client.get(f"/roles/{rid}").status_code == 404


def test_team_crud(client):
    r = client.post("/teams", json={"team_name": "Ops", "team_description": "d"})
    assert r.status_code == 201, r.text
    tid = r.json()["data"]["team_identifier"]
    assert tid == "TM-001"
    assert client.get(f"/teams/{tid}").json()["data"]["team_description"] == "d"
    assert client.get("/teams/next-identifier").json()["data"]["next"] == "TM-002"


def test_layout_crud(client):
    r = client.post("/layouts", json={
        "layout_entity_identifier": "ENT-001", "layout_type": "detail",
        "layout_content": {"rows": [["name"]]},
    })
    assert r.status_code == 201, r.text
    lid = r.json()["data"]["layout_identifier"]
    assert lid == "LAY-001"
    got = client.get(f"/layouts/{lid}").json()["data"]
    assert got["layout_type"] == "detail"
    assert got["layout_content"] == {"rows": [["name"]]}
    # bad enum rejected
    bad = client.post("/layouts", json={
        "layout_entity_identifier": "ENT-001", "layout_type": "bogus",
    })
    assert bad.status_code == 422


def test_role_bad_enum_rejected(client):
    r = client.post("/roles", json={"role_name": "X", "role_status": "weird"})
    assert r.status_code == 422
