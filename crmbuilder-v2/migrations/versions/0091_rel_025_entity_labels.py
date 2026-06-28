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


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("entities")}


def upgrade() -> None:
    # ``entities`` is created pre-0037, so a partial-chain run (stamp 0036 ->
    # upgrade head, skipping the catalog seed) never has it — tolerate its
    # absence as a no-op, matching the sibling 0089 guard.
    if "entities" not in _tables():
        return
    have = _existing()
    for col in _COLUMNS:
        if col not in have:
            op.add_column("entities", sa.Column(col, sa.Text(), nullable=True))


def downgrade() -> None:
    if "entities" not in _tables():
        return
    have = _existing()
    with op.batch_alter_table("entities") as batch:
        for col in _COLUMNS:
            if col in have:
                batch.drop_column(col)
