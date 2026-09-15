"""PI-509 — ``build_0002_drop_orphan_mapping_tables`` drops
``source_mapping_joins`` and ``field_mapping_translations``; its downgrade
recreates both from the frozen definitions, and the five live mapping tables
are never touched.
"""

from __future__ import annotations

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect, text

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import (
    fresh_db,
    requires_postgres,
    stamp_heads,
)

pytestmark = requires_postgres

_RETIRED = {"source_mapping_joins", "field_mapping_translations"}
_LIVE = {"source_mappings", "source_mapping_targets", "field_mappings", "value_mappings", "mapping_candidates"}
_FORK = "build_0001_branch"


def _tables(db: str) -> set[str]:
    eng = create_engine(db)
    try:
        return set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def test_drop_and_recreate_orphan_mapping_tables() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()
    names = _tables(db)
    assert _LIVE <= names and not (_RETIRED & names)
    stamped = stamp_heads(db)
    assert stamped.returncode == 0, stamped.stderr

    down = _alembic(["downgrade", f"build@{_FORK}"], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"
    names = _tables(db)
    assert _RETIRED <= names and _LIVE <= names
    eng = create_engine(db)
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO field_mapping_translations (engagement_id, field_mapping_identifier, "
                "translation_type) VALUES ('ENG-001', 'FMP-001', 'expression')"
            )
        )
        c.execute(text("DELETE FROM field_mapping_translations"))
    eng.dispose()

    up = _alembic(["upgrade", "heads"], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    names = _tables(db)
    assert not (_RETIRED & names) and _LIVE <= names
