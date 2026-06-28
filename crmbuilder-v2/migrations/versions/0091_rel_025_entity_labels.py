"""REL-025 (REQ-364) — entity display-label columns.

Adds ``entity_label`` and ``entity_label_plural`` (both TEXT NULL) to
``entities`` — the source CRM's singular/plural display labels captured during
audit alongside the internal/neutral name. Purely additive ``ADD COLUMN``
(no batch table-recreate), idempotent via a column-existence guard so it is a
no-op on the create_all-then-upgrade-head test path.

SQLite chain head 0090 -> 0091. Companion PG-chain delta:
``migrations/pg/versions/0048_rel_025_entity_labels.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0091_rel_025_entity_labels"
down_revision: str | None = "0090_pi_318_reconcile_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("entity_label", "entity_label_plural")


def _has_entities() -> bool:
    return "entities" in sa.inspect(op.get_bind()).get_table_names()


def _existing() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("entities")}


def upgrade() -> None:
    # Guard on table existence: a mid-stream chain entry (a DB stamped past the
    # migration that creates ``entities``) leaves the table absent, and
    # get_columns() would raise NoSuchTableError. Mirrors 0083/0085/0087.
    if not _has_entities():
        return
    have = _existing()
    for col in _COLUMNS:
        if col not in have:
            op.add_column("entities", sa.Column(col, sa.Text(), nullable=True))


def downgrade() -> None:
    if not _has_entities():
        return
    have = _existing()
    with op.batch_alter_table("entities") as batch:
        for col in _COLUMNS:
            if col in have:
                batch.drop_column(col)
