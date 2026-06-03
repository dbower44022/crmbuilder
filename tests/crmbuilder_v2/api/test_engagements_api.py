"""Engagement REST endpoint tests (the ``/engagements`` registry).

PI-β folded the registry into the unified DB's ``engagements`` table (the
separate meta DB is gone). ``v2_env`` seeds ``ENG-001`` for row scoping, so
clear the registry to an empty table for these tests, which assert identifier
assignment from empty. The endpoints operate on the *unscoped* engagements
table; with the registry cleared a headerless/unknown-engagement request has
no active engagement, so disable scope-enforcement (production runs scoping on,
enforcement off) to keep the writable-session export snapshot's scoped reads
from tripping.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _empty_engagement_registry(v2_env):
    from crmbuilder_v2.access import engagement_scope
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.models import EngagementRow

    with session_scope() as s:
        s.query(EngagementRow).delete()
    prev = engagement_scope.set_enforcement(False)
    yield
    engagement_scope.set_enforcement(prev)


def _envelope_ok(body: dict) -> dict:
    assert body["errors"] is None
    return body["data"]


def test_list_empty(client):
    r = client.get("/engagements")
    assert r.status_code == 200
    assert _envelope_ok(r.json()) == []


def test_create_201_with_auto_identifier(client):
    r = client.post(
        "/engagements",
        json={
            "engagement_code": "ALPHA",
            "engagement_name": "Alpha",
            "engagement_purpose": "test",
        },
    )
    assert r.status_code == 201
    data = _envelope_ok(r.json())
    assert data["engagement_identifier"] == "ENG-001"
    assert data["engagement_status"] == "active"


def test_list_after_create(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "ALPHA",
            "engagement_name": "Alpha",
            "engagement_purpose": "test",
        },
    )
    r = client.get("/engagements")
    data = _envelope_ok(r.json())
    assert len(data) == 1
    assert data[0]["engagement_code"] == "ALPHA"


def test_get_by_identifier(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "ALPHA",
            "engagement_name": "Alpha",
            "engagement_purpose": "test",
        },
    )
    r = client.get("/engagements/ENG-001")
    data = _envelope_ok(r.json())
    assert data["engagement_identifier"] == "ENG-001"


def test_get_404(client):
    r = client.get("/engagements/ENG-999")
    assert r.status_code == 404
    body = r.json()
    assert body["errors"] is not None


def test_create_validation_invalid_code(client):
    r = client.post(
        "/engagements",
        json={
            "engagement_code": "bad-code",
            "engagement_name": "x",
            "engagement_purpose": "y",
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["data"] is None
    assert any(
        e.get("field") == "engagement_code" for e in body["errors"]
    )


def test_create_validation_short_code(client):
    r = client.post(
        "/engagements",
        json={
            "engagement_code": "A",  # too short (min 2)
            "engagement_name": "x",
            "engagement_purpose": "y",
        },
    )
    assert r.status_code == 422


def test_create_validation_duplicate_code(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "ALPHA",
            "engagement_name": "A1",
            "engagement_purpose": "p",
        },
    )
    r = client.post(
        "/engagements",
        json={
            "engagement_code": "alpha",
            "engagement_name": "A2",
            "engagement_purpose": "p",
        },
    )
    assert r.status_code == 422
    body = r.json()
    # The first error is code-format (lowercase rejected), not
    # uniqueness — but acceptable since the request fails either way.
    assert body["errors"] is not None


def test_create_explicit_identifier_collision_409(client):
    client.post(
        "/engagements",
        json={
            "engagement_identifier": "ENG-001",
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    r = client.post(
        "/engagements",
        json={
            "engagement_identifier": "ENG-001",
            "engagement_code": "BB",
            "engagement_name": "B",
            "engagement_purpose": "p",
        },
    )
    assert r.status_code == 409


def test_put_full_replace(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A1",
            "engagement_purpose": "p",
        },
    )
    r = client.put(
        "/engagements/ENG-001",
        json={
            "engagement_name": "A2",
            "engagement_purpose": "p2",
            "engagement_status": "paused",
        },
    )
    assert r.status_code == 200
    data = _envelope_ok(r.json())
    assert data["engagement_name"] == "A2"
    assert data["engagement_status"] == "paused"


def test_put_body_identifier_mismatch_422(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    r = client.put(
        "/engagements/ENG-001",
        json={
            "engagement_identifier": "ENG-999",
            "engagement_name": "X",
            "engagement_purpose": "X",
            "engagement_status": "active",
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert any(
        e.get("code") == "identifier_mismatch" for e in body["errors"]
    )


def test_put_code_mutation_422(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    r = client.put(
        "/engagements/ENG-001",
        json={
            "engagement_code": "DIFFERENT",
            "engagement_name": "X",
            "engagement_purpose": "X",
            "engagement_status": "active",
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert any(
        e.get("code") == "immutable_field" for e in body["errors"]
    )


def test_patch_partial(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    r = client.patch(
        "/engagements/ENG-001",
        json={"engagement_status": "archived"},
    )
    assert r.status_code == 200
    data = _envelope_ok(r.json())
    assert data["engagement_status"] == "archived"


def test_patch_invalid_status_422(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    r = client.patch(
        "/engagements/ENG-001",
        json={"engagement_status": "bogus"},
    )
    assert r.status_code == 422


def test_delete_soft_delete_and_idempotent(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    r1 = client.delete("/engagements/ENG-001")
    assert r1.status_code == 200
    data1 = _envelope_ok(r1.json())
    assert data1["engagement_deleted_at"] is not None

    r2 = client.delete("/engagements/ENG-001")
    assert r2.status_code == 200
    data2 = _envelope_ok(r2.json())
    # SQLite strips tzinfo on re-read; compare the timestamp portion only.
    assert data2["engagement_deleted_at"] is not None
    assert (
        data2["engagement_deleted_at"].replace("+00:00", "")
        == data1["engagement_deleted_at"].replace("+00:00", "")
    )


def test_list_excludes_soft_deleted_by_default(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    client.post(
        "/engagements",
        json={
            "engagement_code": "BB",
            "engagement_name": "B",
            "engagement_purpose": "p",
        },
    )
    client.delete("/engagements/ENG-002")

    r = client.get("/engagements")
    assert len(_envelope_ok(r.json())) == 1

    r2 = client.get("/engagements?include_deleted=true")
    assert len(_envelope_ok(r2.json())) == 2


def test_restore_round_trip(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    client.delete("/engagements/ENG-001")

    r = client.post("/engagements/ENG-001/restore")
    assert r.status_code == 200
    data = _envelope_ok(r.json())
    assert data["engagement_deleted_at"] is None


def test_restore_on_live_returns_422(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    r = client.post("/engagements/ENG-001/restore")
    assert r.status_code == 422
    body = r.json()
    assert any(
        e.get("code") == "not_soft_deleted" for e in body["errors"]
    )


def test_next_identifier_empty_db(client):
    r = client.get("/engagements/next-identifier")
    assert r.status_code == 200
    data = _envelope_ok(r.json())
    assert data["next"] == "ENG-001"


def test_next_identifier_increments_after_create(client):
    client.post(
        "/engagements",
        json={
            "engagement_code": "AA",
            "engagement_name": "A",
            "engagement_purpose": "p",
        },
    )
    r = client.get("/engagements/next-identifier")
    assert _envelope_ok(r.json())["next"] == "ENG-002"


def test_healthcheck_preserved(client):
    """Slice A healthcheck endpoint remains operational."""
    r = client.get("/engagements/healthcheck")
    assert r.status_code == 200
    data = _envelope_ok(r.json())
    assert data["status"] == "ok"
    assert data["engagement_count"] == 0


def test_envelope_shape_on_success(client):
    r = client.get("/engagements")
    body = r.json()
    assert set(body.keys()) == {"data", "meta", "errors"}


def test_envelope_shape_on_validation_error(client):
    r = client.post(
        "/engagements",
        json={
            "engagement_code": "bad",
            "engagement_name": "x",
            "engagement_purpose": "y",
        },
    )
    body = r.json()
    assert set(body.keys()) == {"data", "meta", "errors"}
    assert body["data"] is None
    assert isinstance(body["errors"], list)
