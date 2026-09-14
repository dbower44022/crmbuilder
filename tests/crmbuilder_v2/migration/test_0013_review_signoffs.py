"""Phase 6 — migration 0051 creates review_signoffs + rebuilds change_log CHECK.

create_all (the table + the change_log CHECK come from the ORM), stamp at 0051,
downgrade to 0050 (drops the table + narrows the CHECK), assert the pre-state,
upgrade back to 0051, assert the table returns and change_log admits a
``review_signoff`` row.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_MIGRATION_0050 = "0012_planning_item_implements_requirement"
_MIGRATION_0051 = "0013_review_signoffs"
_TABLE = "review_signoffs"




def _insert_changelog(db: Path) -> None:
    eng = create_engine(db)
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO change_log "
                "(timestamp, entity_type, entity_identifier, operation, actor, "
                "engagement_id) VALUES (CURRENT_TIMESTAMP, 'review_signoff', '1', "
                "'insert', 'claude_session', 'ENG-001')"
            )
        )
    eng.dispose()


def test_0013_review_signoffs_round_trip() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()

    assert _alembic(["stamp", _MIGRATION_0051], db).returncode == 0
    down = _alembic(["downgrade", _MIGRATION_0050], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    assert _TABLE not in set(inspect(create_engine(db)).get_table_names())
    rejected = False
    try:
        _insert_changelog(db)
    except (IntegrityError, OperationalError):
        rejected = True
    assert rejected, "change_log should reject review_signoff before 0051"

    up = _alembic(["upgrade", _MIGRATION_0051], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _TABLE in set(inspect(create_engine(db)).get_table_names())
    _insert_changelog(db)  # now admitted
