"""REL-025 (REQ-366) — field display-label column (Postgres chain).

PG-chain companion of SQLite ``0092_rel_025_field_label``. Adds ``field_label``
(TEXT NULL) to ``fields``; additive, idempotent via a column-existence guard.

PG chain head 0048 -> 0049.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_rel_025_field_label"
down_revision: str | None = "0048_rel_025_entity_labels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("fields")}


def upgrade() -> None:
    if "field_label" not in _existing():
        op.add_column("fields", sa.Column("field_label", sa.Text(), nullable=True))


def downgrade() -> None:
    if "field_label" in _existing():
        op.drop_column("fields", "field_label")
