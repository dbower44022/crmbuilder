"""REL-025 (REQ-364) — entity display-label columns (Postgres chain).

PG-chain companion of SQLite ``0091_rel_025_entity_labels``. Adds
``entity_label`` and ``entity_label_plural`` (TEXT NULL) to ``entities`` —
purely additive, idempotent via a column-existence guard.

PG chain head 0047 -> 0048.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048_rel_025_entity_labels"
down_revision: str | None = "0047_pi_318_reconcile_transactions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("entity_label", "entity_label_plural")


def _has_entities() -> bool:
    return "entities" in sa.inspect(op.get_bind()).get_table_names()


def _existing() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("entities")}


def upgrade() -> None:
    # Guard on table existence (a mid-stream chain entry leaves `entities`
    # absent; get_columns would raise NoSuchTableError). Mirrors the SQLite 0091.
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
    for col in _COLUMNS:
        if col in have:
            op.drop_column("entities", col)
