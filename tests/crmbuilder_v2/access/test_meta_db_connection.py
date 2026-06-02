"""v0.5 slice A — meta DB connection pool isolation tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.access import db as engagement_db
from crmbuilder_v2.access.db import reset_engine_cache
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    data_dir,
    get_meta_session_factory,
    init_meta_db_pool,
    meta_db_path,
    reset_meta_engine_cache,
)
from crmbuilder_v2.access.meta_models import EngagementRow
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.migration.lazy_migration import engagement_db_path
from sqlalchemy import text


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
    """A write to the meta DB does not appear in the per-engagement DB.

    PI-123 Slice 1 folded the ``engagements`` table into the main ``Base``,
    so a per-engagement DB built from that schema now *has* an
    ``engagements`` table too (and, under PI-123 Stage 2, the test fixture
    seeds the default engagement ``ENG-001`` into it as the FK target). The
    invariant under test is no longer "the engagement DB lacks the table" but
    the stronger, still-true point: the two are separate physical DBs, so a
    row written *only* to the meta DB does not appear in the per-engagement
    DB's ``engagements`` table. (At the Deployment cutover the two collapse
    into one; until then they are distinct files and this isolation holds.)
    """
    # Seed a distinct identifier into the meta DB so it is unambiguously the
    # meta row (the fixture's ENG-001 lives in the per-engagement DB).
    _seed_meta_schema_and_row(identifier="ENG-777")

    # The per-engagement DB carries the folded-in engagements table (PI-123
    # Slice 1) seeded with the fixture's default engagement, but it is a
    # distinct physical DB: the meta-only row must not be visible here.
    with engagement_db.session_scope(export=False) as eng_session:
        table = eng_session.execute(
            text("SELECT name FROM sqlite_master WHERE name='engagements'")
        ).fetchone()
        assert table is not None, (
            "per-engagement DB should carry the folded-in engagements table "
            "(PI-123 Slice 1)"
        )
        meta_only = eng_session.execute(
            text("SELECT COUNT(*) FROM engagements WHERE engagement_identifier='ENG-777'")
        ).scalar_one()
        # The meta DB's row did not bleed into the per-engagement DB.
        assert meta_only == 0

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


@pytest.mark.parametrize(
    "db_path_template",
    [
        "{root}/data/v2.db",
        "{root}/data/engagements/CRMBUILDER.db",
    ],
)
def test_data_dir_normalises_both_layouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    db_path_template: str,
) -> None:
    """``data_dir`` must collapse v2.db and per-engagement db_path to ``data/``.

    Regression: prior to the v0.5 slice D follow-up,
    ``meta_db_path`` and ``engagement_db_path`` used ``db_path.parent``
    directly, which produces a wrong nested path when ``db_path`` is
    the activation-worker shape ``data/engagements/{code}.db``. The
    activation worker has been setting ``CRMBUILDER_V2_DB_PATH`` to
    that shape since slice D landed, so a real spawned API would route
    the meta DB to ``data/engagements/engagements.db`` (wrong) and
    ``engagement_db_path("X")`` to ``data/engagements/engagements/X.db``
    (also wrong). The slice E end-to-end test masks this by stubbing
    the launch with no-ops.
    """
    db_path = Path(db_path_template.format(root=tmp_path))
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(db_path))
    reset_settings_cache()
    reset_engine_cache()
    reset_meta_engine_cache()

    assert data_dir() == tmp_path / "data"
    assert meta_db_path() == tmp_path / "data" / "engagements.db"
    assert (
        engagement_db_path("CRMBUILDER")
        == tmp_path / "data" / "engagements" / "CRMBUILDER.db"
    )
