"""PI-302 (PG chain) — work_tasks.work_task_resolved_agent_profile.

Companion to the SQLite-chain ``0086``. Adds the nullable
``work_task_resolved_agent_profile`` column (a ``VARCHAR(32)`` holding the
architect-chosen ``AGP-NNN`` specialist, no FK / CHECK) on Postgres deployments
materialised from an earlier baseline. The PG baseline is ``create_all`` from the
live models, so a fresh PG DB already carries the column — the add is
inspector-guarded. Chains after ``0043_pi_051_security_rules``. Never
replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044_pi_302_work_task_resolved_agent_profile"
down_revision: str | None = "0043_pi_051_security_rules"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMN = "work_task_resolved_agent_profile"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if "work_tasks" not in sa.inspect(op.get_bind()).get_table_names():
        return
    if _COLUMN not in _cols("work_tasks"):
        op.add_column(
            "work_tasks",
            sa.Column(_COLUMN, sa.String(length=32), nullable=True),
        )


def downgrade() -> None:
    if _COLUMN in _cols("work_tasks"):
        op.drop_column("work_tasks", _COLUMN)
