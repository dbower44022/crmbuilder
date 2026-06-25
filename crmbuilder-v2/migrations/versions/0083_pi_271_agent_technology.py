"""PI-271 (PRJ-039 / REQ-281) — agent_profiles.technology + work_tasks.work_task_technology.

Adds a nullable build-technology discriminator so one functional area can carry
multiple technology variants (e.g. the ``ui`` area's ``qt-desktop`` vs ``web``
profiles), and so a Work Task can name the technology it targets for the dispatcher
to route on. Column-adds are guarded so the migration is a no-op on a
create_all-materialised DB (the test path). SQLite head 0082 -> 0083; companion PG
delta ``migrations/pg/versions/0040_pi_271_agent_technology.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0083_pi_271_agent_technology"
down_revision: str | None = "0082_pi_273_pipeline_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _has_table(table: str) -> bool:
    return table in sa.inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    # Guard on table existence, not just column existence: a mid-stream chain
    # entry (a DB stamped past 0032, where agent_profiles/work_tasks are created)
    # leaves these tables absent, and _cols() returns an empty set for a missing
    # table — so the column-absence check alone would ALTER a nonexistent table.
    # Mirrors the table-existence guard in 0085 / 0087.
    if _has_table("agent_profiles") and "technology" not in _cols("agent_profiles"):
        with op.batch_alter_table("agent_profiles") as batch:
            batch.add_column(sa.Column("technology", sa.String(32), nullable=True))
    if _has_table("work_tasks") and "work_task_technology" not in _cols("work_tasks"):
        with op.batch_alter_table("work_tasks") as batch:
            batch.add_column(
                sa.Column("work_task_technology", sa.String(32), nullable=True)
            )


def downgrade() -> None:
    if "technology" in _cols("agent_profiles"):
        with op.batch_alter_table("agent_profiles") as batch:
            batch.drop_column("technology")
    if "work_task_technology" in _cols("work_tasks"):
        with op.batch_alter_table("work_tasks") as batch:
            batch.drop_column("work_task_technology")
