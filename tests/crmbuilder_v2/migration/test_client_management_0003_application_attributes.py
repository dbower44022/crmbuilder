"""PI-575 — ``client_management_0003_application_attributes`` adds
``engagement_visibility`` to ``engagements`` on the client_management branch:
CHECK-constrained to private or public, defaulting to private, back-filled to
private for existing rows, re-runnable, and dropped by the downgrade."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import (
    fresh_db,
    requires_postgres,
    stamp_heads,
)

pytestmark = requires_postgres

_PREVIOUS = "client_management_0002_clients"
_REVISION = "client_management_0003_application_attributes"
_COLUMN = "engagement_visibility"


def _columns(db: str) -> set[str]:
    eng = create_engine(db)
    try:
        return {c["name"] for c in inspect(eng).get_columns("engagements")}
    finally:
        eng.dispose()


def _seed_engagement(db: str, identifier: str) -> None:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO engagements (engagement_identifier, engagement_code, "
                    "engagement_name, engagement_purpose, engagement_status, "
                    "engagement_created_at, engagement_updated_at) VALUES "
                    "(:i, :c, :n, 'p', 'active', NOW(), NOW())"
                ),
                {
                    "i": identifier,
                    "c": identifier.replace("-", ""),
                    "n": f"Engagement {identifier}",
                },
            )
    finally:
        eng.dispose()


def _rows(db: str, sql: str) -> list:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            return list(c.execute(text(sql)).all())
    finally:
        eng.dispose()


def test_add_backfill_check_rerun_and_drop() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert _COLUMN in _columns(db)
    assert stamp_heads(db).returncode == 0

    # Downgrade the branch one step: the column goes.
    down = _alembic(["downgrade", f"client_management@{_PREVIOUS}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    assert _COLUMN not in _columns(db)

    # An engagement that predates the column is back-filled to private.
    _seed_engagement(db, "ENG-001")
    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _COLUMN in _columns(db)
    assert _rows(
        db, "SELECT engagement_visibility FROM engagements WHERE engagement_identifier = 'ENG-001'"
    ) == [("private",)]

    # A new row without a visibility gets private; a value outside the
    # vocabulary is refused by the CHECK.
    _seed_engagement(db, "ENG-002")
    assert _rows(
        db, "SELECT engagement_visibility FROM engagements WHERE engagement_identifier = 'ENG-002'"
    ) == [("private",)]
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            c.execute(
                text(
                    "UPDATE engagements SET engagement_visibility = 'public' "
                    "WHERE engagement_identifier = 'ENG-002'"
                )
            )
        with pytest.raises(IntegrityError), eng.begin() as c:
            c.execute(
                text(
                    "UPDATE engagements SET engagement_visibility = 'secret' "
                    "WHERE engagement_identifier = 'ENG-002'"
                )
            )
    finally:
        eng.dispose()

    # Re-running the upgrade is a no-op.
    assert _alembic(["upgrade", "heads"], db).returncode == 0
    assert _rows(db, "SELECT count(*) FROM engagements")[0][0] == 2

    # This revision is now the client_management head.
    heads = _alembic(["heads"], db)
    assert _REVISION in heads.stdout
    assert _PREVIOUS not in heads.stdout
