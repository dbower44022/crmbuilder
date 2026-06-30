"""PI-374 (PG chain) — foreign-field link/target columns on ``fields``.

Companion to the SQLite-chain ``0104``. Adds ``field_foreign_link`` and
``field_foreign_target`` (both TEXT NULL) so a ``foreign`` field records what it
mirrors — the link and the field on the linked entity — for round-trip deploy
and mirrored-result-type resolution (REQ-435/436 / PI-374). Both nullable; the
required-when-foreign rule lives at the access layer. No CHECK change.

PG chain head 0060 -> 0061.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061_pi_374_foreign_link_target"
down_revision: str | None = "0060_pi_374_foreign_field_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = ("field_foreign_link", "field_foreign_target")


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("fields")}


def upgrade() -> None:
    have = _columns()
    for name in _COLUMNS:
        if name not in have:
            op.add_column("fields", sa.Column(name, sa.Text(), nullable=True))


def downgrade() -> None:
    have = _columns()
    for name in _COLUMNS:
        if name in have:
            op.drop_column("fields", name)
