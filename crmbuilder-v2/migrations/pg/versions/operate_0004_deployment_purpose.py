"""PI-577 (REQ-654, DEC-1156): a deployment carries its purpose.

Adds ``deployment_purpose`` to ``deployments``: ``client_own`` (a client's
own installation) or ``demo_test`` (the one deployment the application's
defining client runs for other clients to try a release on), CHECK-
constrained and NOT NULL. Every deployment that exists when this runs is a
client's own, so the column is back-filled with ``client_own`` through a
server default; the API requires the purpose on every save from here on.

Bootstrap-safe (LSN-050): inspector-guarded both ways. Downgrade drops the
constraint and the column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "operate_0004_deployment_purpose"
down_revision: str | None = "operate_0003_deployments"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "deployments"
_COLUMN = "deployment_purpose"
_CHECK = "ck_deployment_purpose"


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(_TABLE)}


def _checks() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(_TABLE)}


def upgrade() -> None:
    if _COLUMN not in _columns():
        op.add_column(
            _TABLE,
            sa.Column(
                _COLUMN,
                sa.String(16),
                nullable=False,
                server_default=sa.text("'client_own'"),
            ),
        )
        op.execute(
            sa.text(
                f"UPDATE {_TABLE} SET {_COLUMN} = 'client_own' WHERE {_COLUMN} IS NULL"
            )
        )
    if _CHECK not in _checks():
        op.create_check_constraint(
            _CHECK, _TABLE, f"{_COLUMN} IN ('client_own', 'demo_test')"
        )


def downgrade() -> None:
    if _CHECK in _checks():
        op.drop_constraint(_CHECK, _TABLE, type_="check")
    if _COLUMN in _columns():
        op.drop_column(_TABLE, _COLUMN)
