"""Migration 0089 (REQ-340 / PI-300) — entities collection-search settings.

Mirrors the test_0084 column-add round-trip: create_all (columns present from the
ORM), stamp at 0089, downgrade to 0088 (drops the three columns), assert the
pre-state, then upgrade back to 0089 (the real add path) and assert the columns
are present.
"""

from __future__ import annotations

from pathlib import Path

from crmbuilder_v2.access.models import Base
from sqlalchemy import create_engine, inspect

from tests.crmbuilder_v2.migration._pg_chain import alembic as _alembic
from tests.crmbuilder_v2.migration._pg_chain import fresh_db, requires_postgres

pytestmark = requires_postgres

_MIGRATION_PREV = "0045_pi_304_task_transitions"
_MIGRATION_THIS = "0046_pi_300_entity_collection_settings"
_NEW_COLUMNS = {
    "entity_text_filter_fields",
    "entity_full_text_search",
    "entity_full_text_search_min_length",
}




def _cols(db: Path, table: str) -> set[str]:
    insp = inspect(create_engine(db))
    return {c["name"] for c in insp.get_columns(table)}


def test_0089_column_round_trip() -> None:
    db = fresh_db()
    engine = create_engine(db)
    Base.metadata.create_all(engine)
    engine.dispose()

    stamp = _alembic(["stamp", _MIGRATION_THIS], db)
    assert stamp.returncode == 0, f"stamp failed:\n{stamp.stdout}\n{stamp.stderr}"
    down = _alembic(["downgrade", _MIGRATION_PREV], db)
    assert down.returncode == 0, f"downgrade failed:\n{down.stdout}\n{down.stderr}"

    # Pre-state: the new columns are gone; the sibling sort flag survives.
    cols = _cols(db, "entities")
    assert _NEW_COLUMNS.isdisjoint(cols)
    assert "entity_default_sort_field" in cols

    # The real add path.
    up = _alembic(["upgrade", _MIGRATION_THIS], db)
    assert up.returncode == 0, f"upgrade failed:\n{up.stdout}\n{up.stderr}"
    assert _NEW_COLUMNS <= _cols(db, "entities")
