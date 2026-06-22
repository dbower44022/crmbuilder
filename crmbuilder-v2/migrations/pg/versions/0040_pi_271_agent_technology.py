"""PI-271 (PG chain) — agent_profiles.technology + work_tasks.work_task_technology.

Companion to the SQLite-chain ``0083``. Adds the nullable build-technology
discriminator on Postgres deployments materialised from an earlier baseline. The
PG baseline is ``create_all`` from the live models, so a fresh PG DB already
carries the columns — the adds are inspector-guarded. Chains after
``0039_pi_273_pipeline_events``. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040_pi_271_agent_technology"
down_revision: str | None = "0039_pi_273_pipeline_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if "technology" not in _cols("agent_profiles"):
        op.add_column(
            "agent_profiles", sa.Column("technology", sa.String(32), nullable=True)
        )
    if "work_task_technology" not in _cols("work_tasks"):
        op.add_column(
            "work_tasks",
            sa.Column("work_task_technology", sa.String(32), nullable=True),
        )


def downgrade() -> None:
    if "technology" in _cols("agent_profiles"):
        op.drop_column("agent_profiles", "technology")
    if "work_task_technology" in _cols("work_tasks"):
        op.drop_column("work_tasks", "work_task_technology")
