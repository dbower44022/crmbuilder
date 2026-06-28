"""REL-025 (REQ-366) — field display-label column.

Adds ``field_label`` (TEXT NULL) to ``fields`` — the source CRM's display label
captured during audit alongside the internal/neutral field name. Additive
``ADD COLUMN``, idempotent via a column-existence guard.

SQLite chain head 0091 -> 0092. Companion PG-chain delta:
``migrations/pg/versions/0049_rel_025_field_label.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0092_rel_025_field_label"
down_revision: str | None = "0091_rel_025_entity_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("fields")}


def upgrade() -> None:
    # ``fields`` is created pre-0037, so a partial-chain run (stamp 0036 ->
    # upgrade head, skipping the catalog seed) never has it — tolerate its
    # absence as a no-op, matching the sibling 0089 guard.
    if "fields" not in _tables():
        return
    if "field_label" not in _existing():
        op.add_column("fields", sa.Column("field_label", sa.Text(), nullable=True))


def downgrade() -> None:
    if "fields" not in _tables():
        return
    if "field_label" in _existing():
        with op.batch_alter_table("fields") as batch:
            batch.drop_column("field_label")
