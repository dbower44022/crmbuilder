"""PI-alpha (D9) — the unified-SQLite → Postgres migration harness test.

Gated on a real Postgres being available via ``CRMBUILDER_V2_TEST_PG_URL``
(CI spins one up; locally point it at the dev container, e.g.
``postgresql+psycopg://crmb:crmb@localhost:55432/crmbuilder_v2``). When the var
is unset the module skips, so the default SQLite suite never depends on Docker.

Builds a synthetic *unified* SQLite source with two engagements holding
**colliding identifiers** (both have ``DEC-001``/``TOP-001``/``PI-001`` and a
``topics`` self-FK chain), runs :func:`migrate`, and asserts the Postgres target:
preserves both engagements' rows (count + identifier parity), lands no NULL
``engagement_id``, keeps the ``topics`` self-FK valid, resets the surrogate-id
sequences so the next insert does not collide, and isolates engagements under the
scoped ORM (the PI-123 leak-test essence, run on Postgres).
"""

from __future__ import annotations

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, text

_PG_URL = os.environ.get("CRMBUILDER_V2_TEST_PG_URL")

pytestmark = pytest.mark.skipif(
    not _PG_URL,
    reason="set CRMBUILDER_V2_TEST_PG_URL to run the Postgres migration test",
)

_NOW = datetime(2026, 6, 2, tzinfo=UTC).isoformat()
_EXEC = "x" * 200


def _build_unified_source(path: Path, engagement_ids: tuple[str, ...]) -> None:
    """Create a unified-schema SQLite DB seeded for the given engagements."""
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    engine.dispose()
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys=OFF")
    for i, eng in enumerate(engagement_ids, start=1):
        conn.execute(
            "INSERT INTO engagements (engagement_identifier, engagement_code, "
            "engagement_name, engagement_purpose, engagement_status, "
            "engagement_created_at, engagement_updated_at) VALUES (?,?,?,?,?,?,?)",
            (eng, eng, eng, "p", "active", _NOW, _NOW),
        )
        base = i * 1_000_000_000  # disjoint surrogate-id space per engagement
        # topics — surrogate id PK + self-FK chain (TOP-002 -> TOP-001).
        conn.execute(
            "INSERT INTO topics (id, identifier, name, description, "
            "parent_topic_id, created_at, engagement_id) "
            "VALUES (?, 'TOP-001', 'root', '', NULL, ?, ?)",
            (base + 1, _NOW, eng),
        )
        conn.execute(
            "INSERT INTO topics (id, identifier, name, description, "
            "parent_topic_id, created_at, engagement_id) "
            "VALUES (?, 'TOP-002', 'child', '', ?, ?, ?)",
            (base + 2, base + 1, _NOW, eng),
        )
        # decisions — surrogate id PK; colliding identifier DEC-001.
        conn.execute(
            "INSERT INTO decisions (id, identifier, title, decision_date, status, "
            "context, decision, rationale, alternatives_considered, consequences, "
            "executive_summary, created_at, updated_at, engagement_id) "
            "VALUES (?, 'DEC-001', 't', '2026-06-02', 'Active', "
            "'c', 'd', 'r', 'a', 'cs', ?, ?, ?, ?)",
            (base + 1, _EXEC, _NOW, _NOW, eng),
        )
        # planning_items — identifier PK table with a JSON ``area`` array.
        conn.execute(
            "INSERT INTO planning_items (id, identifier, title, item_type, "
            "description, status, executive_summary, area, created_at, updated_at, "
            "engagement_id) "
            "VALUES (?, 'PI-001', 't', 'pending_work', 'd', 'Draft', ?, ?, ?, ?, ?)",
            (base + 1, _EXEC, '["storage","access"]', _NOW, _NOW, eng),
        )
    conn.commit()
    conn.close()


def _reset_pg_schema(url: str) -> None:
    engine = create_engine(url, future=True)
    try:
        with engine.begin() as c:
            c.execute(text("DROP SCHEMA public CASCADE"))
            c.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


def test_migrate_unified_sqlite_to_postgres(tmp_path: Path) -> None:
    from crmbuilder_v2.migration.sqlite_to_postgres import migrate

    src = tmp_path / "v2-unified.db"
    _build_unified_source(src, ("ENG-001", "ENG-002"))
    _reset_pg_schema(_PG_URL)

    result = migrate(src, _PG_URL, create_schema=True)

    assert result.ok, (
        result.count_mismatches + result.identifier_mismatches + result.errors
    )
    assert result.null_engagement_rows == 0
    assert result.isolation_ok is True
    assert result.sequences_reset > 0
    assert result.per_engagement_rows == {"ENG-001": 4, "ENG-002": 4}

    engine = create_engine(_PG_URL, future=True)
    try:
        with engine.connect() as c:
            # Both engagements' colliding identifiers coexist.
            assert c.execute(
                text("SELECT COUNT(*) FROM decisions WHERE identifier='DEC-001'")
            ).scalar() == 2
            assert c.execute(
                text("SELECT COUNT(*) FROM topics WHERE identifier='TOP-001'")
            ).scalar() == 2
            # The topics self-FK survived and stays within-engagement.
            for eng in ("ENG-001", "ENG-002"):
                parent_eng, parent_ident = c.execute(
                    text(
                        "SELECT p.engagement_id, p.identifier FROM topics ch "
                        "JOIN topics p ON p.id = ch.parent_topic_id "
                        "WHERE ch.identifier='TOP-002' AND ch.engagement_id=:e"
                    ),
                    {"e": eng},
                ).one()
                assert parent_eng == eng
                assert parent_ident == "TOP-001"
            # Sequence reset: next id does not collide with the copied max.
            mx = c.execute(text("SELECT MAX(id) FROM decisions")).scalar()
        with engine.begin() as c:
            nxt = c.execute(
                text("SELECT nextval(pg_get_serial_sequence('decisions','id'))")
            ).scalar()
        assert nxt > mx
        # JSONB round-trip of the planning_items area array.
        with engine.connect() as c:
            area = c.execute(
                text(
                    "SELECT area FROM planning_items "
                    "WHERE engagement_id='ENG-001' AND identifier='PI-001'"
                )
            ).scalar()
            assert area == ["storage", "access"]
    finally:
        engine.dispose()


def test_migrate_refuses_nonempty_target(tmp_path: Path) -> None:
    from crmbuilder_v2.migration.sqlite_to_postgres import migrate

    src = tmp_path / "v2-unified.db"
    _build_unified_source(src, ("ENG-001",))
    _reset_pg_schema(_PG_URL)
    # First migration populates the target.
    assert migrate(src, _PG_URL, create_schema=True).ok
    # A second run into the now-non-empty target must refuse.
    with pytest.raises(RuntimeError, match="non-empty"):
        migrate(src, _PG_URL, create_schema=True)
