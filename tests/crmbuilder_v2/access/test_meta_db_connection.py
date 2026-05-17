"""v0.5 slice A — meta DB connection pool isolation tests."""

from __future__ import annotations

from sqlalchemy import text

from crmbuilder_v2.access import db as engagement_db
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    get_meta_session_factory,
    init_meta_db_pool,
    meta_db_path,
    reset_meta_engine_cache,
)
from crmbuilder_v2.access.meta_models import EngagementRow


def _seed_meta_schema_and_row(identifier: str = "ENG-001"):
    from datetime import UTC, datetime

    reset_meta_engine_cache()
    bootstrap_meta_db()
    factory = get_meta_session_factory()
    session = factory()
    try:
        now = datetime.now(UTC)
        session.add(
            EngagementRow(
                engagement_identifier=identifier,
                engagement_code="TESTENG",
                engagement_name="Test Engagement",
                engagement_purpose="Pool isolation smoke",
                engagement_status="active",
                engagement_export_dir=None,
                engagement_created_at=now,
                engagement_updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()


def test_init_meta_db_pool_idempotent(v2_env):
    init_meta_db_pool()
    bootstrap_meta_db()
    init_meta_db_pool()  # second call is a no-op
    assert meta_db_path().exists()


def test_meta_db_separate_from_engagement_db(v2_env):
    """A write to the meta DB does not appear in the per-engagement DB."""
    _seed_meta_schema_and_row()

    # Engagement DB has its own tables; meta DB has the engagements
    # table — but a SELECT against the engagement DB should not see
    # the engagements row.
    with engagement_db.session_scope(export=False) as eng_session:
        result = eng_session.execute(
            text("SELECT name FROM sqlite_master WHERE name='engagements'")
        ).fetchone()
        # The engagement DB never has the engagements table.
        assert result is None

    # Meta DB has exactly the row we inserted.
    factory = get_meta_session_factory()
    session = factory()
    try:
        count = session.execute(
            text("SELECT COUNT(*) FROM engagements")
        ).scalar_one()
        assert count == 1
    finally:
        session.close()


def test_pool_teardown_reset(v2_env):
    init_meta_db_pool()
    bootstrap_meta_db()
    reset_meta_engine_cache()
    # After reset, init_meta_db_pool re-creates cleanly.
    init_meta_db_pool()
    bootstrap_meta_db()
    assert meta_db_path().exists()
