"""PI-575 (REQ-653, DEC-1155, DEC-1183): the engagement row is the application
record and gains its visibility.

Adds ``engagement_visibility`` to ``engagements``: ``private`` or ``public``,
CHECK-constrained, defaulting to ``private``, and back-filled to ``private``
for every existing row. The application's defining client is not a new
column: DEC-1183 reuses the ``engagement_clients`` row marked primary, so
the holding table created by ``client_management_0002_clients`` is unchanged.

Inspector-guarded both ways. Downgrade drops the constraint and the column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "client_management_0003_application_attributes"
down_revision: str | None = "client_management_0002_clients"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "engagements"
_COLUMN = "engagement_visibility"
_CHECK = "ck_engagement_visibility"


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def _checks() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {c["name"] for c in inspector.get_check_constraints(_TABLE)}


def upgrade() -> None:
    if _COLUMN not in _columns():
        op.add_column(
            _TABLE,
            sa.Column(
                _COLUMN,
                sa.String(16),
                nullable=False,
                server_default=sa.text("'private'"),
            ),
        )
        # The server default already fills existing rows on ADD COLUMN; the
        # explicit back-fill states the intent and covers any NULL a partial
        # earlier run could have left.
        op.execute(
            sa.text(
                f"UPDATE {_TABLE} SET {_COLUMN} = 'private' WHERE {_COLUMN} IS NULL"
            )
        )
    if _CHECK not in _checks():
        op.create_check_constraint(
            _CHECK, _TABLE, f"{_COLUMN} IN ('private', 'public')"
        )


def downgrade() -> None:
    if _CHECK in _checks():
        op.drop_constraint(_CHECK, _TABLE, type_="check")
    if _COLUMN in _columns():
        op.drop_column(_TABLE, _COLUMN)
