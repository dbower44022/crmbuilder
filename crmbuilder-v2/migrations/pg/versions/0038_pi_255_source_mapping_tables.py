"""PI-255 (PG chain) — source instance mapping model tables.

Companion to the SQLite-chain ``0081``. Creates the seven source mapping tables
on Postgres deployments materialised from an earlier baseline. The PG baseline
is ``create_all`` from the live models, so a fresh PG DB already carries these
tables (and their CHECKs, derived from current vocab) — the creates are
``checkfirst``-guarded no-ops there. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.models import (
    FieldMapping,
    MappingCandidate,
    SourceMapping,
    SourceMappingTarget,
    ValueMapping,
)
from crmbuilder_v2.migration.retired_tables import (
    field_mapping_translations_table,
    source_mapping_joins_table,
)

revision: str = "0038_pi_255_source_mapping_tables"
down_revision: str | None = "0037_pi_263_cost_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# PI-509 retired ``source_mapping_joins`` and ``field_mapping_translations`` (no
# code ever created a row); their definitions are frozen in ``retired_tables`` so
# this revision still creates the seven tables it always did.
_TABLES = (
    SourceMapping.__table__,
    SourceMappingTarget.__table__,
    source_mapping_joins_table(),
    FieldMapping.__table__,
    field_mapping_translations_table(),
    ValueMapping.__table__,
    MappingCandidate.__table__,
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in _TABLES:
        table.create(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    from sqlalchemy import inspect

    existing = set(inspect(bind).get_table_names())
    for table in reversed(_TABLES):
        if table.name in existing:
            table.drop(bind)
