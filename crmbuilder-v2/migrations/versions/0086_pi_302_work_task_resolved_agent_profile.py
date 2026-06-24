"""PI-302 (PRJ-039) — work_tasks.work_task_resolved_agent_profile.

Adds a nullable ``work_task_resolved_agent_profile`` column so a Work Task can be
stamped with the architect-chosen specialist (an ``AGP-NNN`` agent_profile) it is
authoritatively routed to (Phase 5b). A plain identifier-bearing column like
``work_task_claimed_by`` — no FK to agent_profiles and no CHECK (the access layer
enforces the area backstop). A plain nullable add-column: no refs/change_log CHECK
rebuild is needed (not a new entity type or relationship kind). The add is
inspector-guarded so the migration is a no-op on a create_all-materialised DB (the
test path) and safe mid-chain. SQLite head 0085 -> 0086; companion PG delta
``migrations/pg/versions/0043_pi_302_work_task_resolved_agent_profile.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0086_pi_302_work_task_resolved_agent_profile"
down_revision: str | None = "0085_pi_301_agent_capability_description"
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
        with op.batch_alter_table("work_tasks") as batch:
            batch.add_column(sa.Column(_COLUMN, sa.String(length=32), nullable=True))


def downgrade() -> None:
    if _COLUMN in _cols("work_tasks"):
        with op.batch_alter_table("work_tasks") as batch:
            batch.drop_column(_COLUMN)
