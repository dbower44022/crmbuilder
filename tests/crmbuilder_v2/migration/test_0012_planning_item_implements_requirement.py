"""Phase 3 — migration 0050 widens ck_ref_relationship for the implements kind.

create_all (the kind is admitted from the ORM-derived CHECK), stamp at 0050,
downgrade to 0049 (narrows the CHECK + drops any edges of the kind), assert the
kind is now rejected, upgrade back to 0050, assert it is admitted again.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_MIGRATION_0049 = "0011_requirements_provenance"
_MIGRATION_0050 = "0012_planning_item_implements_requirement"
_KIND = "planning_item_implements_requirement"




def _insert_kind(db: Path, ref_id: str) -> None:
    eng = create_engine(db)
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO refs (reference_identifier, source_type, source_id, "
                "target_type, target_id, relationship_kind, created_at, engagement_id) "
                f"VALUES ('{ref_id}', 'planning_item', 'PI-001', 'requirement', "
                f"'REQ-001', '{_KIND}', CURRENT_TIMESTAMP, 'ENG-001')"
            )
        )
    eng.dispose()


def test_0050_implements_kind_round_trip() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()

    assert _alembic(["stamp", _MIGRATION_0050], db).returncode == 0
    down = _alembic(["downgrade", _MIGRATION_0049], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    rejected = False
    try:
        _insert_kind(db, "REF-9201")
    except (IntegrityError, OperationalError):
        rejected = True
    assert rejected, "implements kind should be rejected before 0050"

    up = _alembic(["upgrade", _MIGRATION_0050], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    _insert_kind(db, "REF-9202")  # now admitted
