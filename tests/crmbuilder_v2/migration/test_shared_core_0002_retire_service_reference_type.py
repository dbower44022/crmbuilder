"""PI-509 — ``shared_core_0002_retire_service_reference_type`` narrows the
``refs`` CHECKs so the retired ``service`` type and kinds are refused, refuses
to run while a row still names them, and its downgrade widens them again.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import (
    fresh_db,
    requires_postgres,
    stamp_heads,
)

pytestmark = requires_postgres

_FORK = "shared_core_0001_branch"
_ROW = (
    "INSERT INTO refs (engagement_id, source_type, source_id, target_type, target_id, "
    "relationship_kind, created_at) VALUES ('ENG-001', 'process', :src, 'service', "
    "'SVC-001', 'process_consumes_service', CURRENT_TIMESTAMP)"
)


def _insert_service_ref(db: str, source_id: str = "PROC-001") -> None:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            c.execute(text(_ROW), {"src": source_id})
    finally:
        eng.dispose()


def _delete_service_refs(db: str) -> None:
    eng = create_engine(db)
    try:
        with eng.begin() as c:
            c.execute(text("DELETE FROM refs WHERE target_type = 'service'"))
    finally:
        eng.dispose()


def test_narrow_refuse_and_widen() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    assert stamp_heads(db).returncode == 0

    # Head shape: the retired type is refused by the CHECK.
    with pytest.raises(IntegrityError):
        _insert_service_ref(db)

    # Downgrade widens the CHECKs; the retired type is admitted again.
    down = _alembic(["downgrade", f"shared_core@{_FORK}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    _insert_service_ref(db)

    # Upgrade refuses while a row names the retired type, and changes nothing.
    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode != 0
    assert "still name the retired reference type" in (up.stdout + up.stderr)
    _insert_service_ref(db, "PROC-002")  # CHECK still wide: the refusal wrote nothing

    # With the rows gone the upgrade narrows the CHECKs.
    _delete_service_refs(db)
    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    with pytest.raises(IntegrityError):
        _insert_service_ref(db)
