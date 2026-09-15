"""PI-509 (REQ-601, DEC-1089): drop ``source_mapping_joins`` and
``field_mapping_translations``.

Both were created with the source-mapping family (PI-255) as children of a
source mapping and a field mapping, but no code path ever inserted a row: the
reconcile screens resolve mapping candidates into source, target, field,
association and value mappings and never wrote a join or a translation. The
live store held zero rows in each. Build owns the family, so the drop lands on
this branch; the five live mapping tables are untouched.

Downgrade recreates both from their frozen definitions in
``crmbuilder_v2.migration.retired_tables``. Inspector-guarded both ways.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.migration.retired_tables import (
    field_mapping_translations_table,
    source_mapping_joins_table,
)

revision: str = "build_0002_drop_orphan_mapping_tables"
down_revision: str | None = "build_0001_branch"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("field_mapping_translations", "source_mapping_joins")


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    existing = _tables()
    for name in _TABLES:
        if name in existing:
            op.drop_table(name)


def downgrade() -> None:
    existing = _tables()
    bind = op.get_bind()
    if "source_mapping_joins" not in existing:
        source_mapping_joins_table().create(bind)
    if "field_mapping_translations" not in existing:
        field_mapping_translations_table().create(bind)
