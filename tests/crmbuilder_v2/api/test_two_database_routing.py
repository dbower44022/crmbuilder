"""v0.5 slice A — two-database API routing tests.

Verifies the FastAPI dependency wiring routes ``/engagements/*`` to
the meta DB pool and other endpoints to the per-engagement DB pool.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import text

from crmbuilder_v2.access.meta_db import (
    get_meta_session_factory,
    reset_meta_engine_cache,
)
from crmbuilder_v2.access.meta_models import EngagementRow


def _seed_engagement(identifier: str = "ENG-001", code: str = "TESTENG"):
    factory = get_meta_session_factory()
    session = factory()
    try:
        now = datetime.now(UTC)
        session.add(
            EngagementRow(
                engagement_identifier=identifier,
                engagement_code=code,
                engagement_name=f"Engagement {code}",
                engagement_purpose="routing test",
                engagement_status="active",
                engagement_created_at=now,
                engagement_updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()


def test_engagements_healthcheck_hits_meta_db(client):
    """``GET /engagements/healthcheck`` routes to the meta DB."""
    _seed_engagement("ENG-001", "ALPHA")
    _seed_engagement("ENG-002", "BETA")

    r = client.get("/engagements/healthcheck")
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] is None
    assert body["data"]["status"] == "ok"
    assert body["data"]["engagement_count"] == 2


def test_sessions_hits_engagement_db(client):
    """``GET /sessions`` routes to the per-engagement DB.

    A row inserted into the meta DB's engagements table does not
    appear in the sessions response.
    """
    _seed_engagement("ENG-001", "ALPHA")

    r = client.get("/sessions")
    assert r.status_code == 200
    body = r.json()
    assert body["errors"] is None
    # The engagement DB has no sessions; the engagement row in the
    # meta DB does not leak into the sessions endpoint.
    assert body["data"] == []


def test_pools_isolated(client):
    """Writing to the meta DB does not affect the engagement DB."""
    _seed_engagement("ENG-001", "ALPHA")

    # The engagement DB's sqlite_master should not contain an
    # ``engagements`` table — that lives in the meta DB only.
    from crmbuilder_v2.access import db as engagement_db

    with engagement_db.session_scope(export=False) as eng_session:
        row = eng_session.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE name='engagements'"
            )
        ).fetchone()
        assert row is None
