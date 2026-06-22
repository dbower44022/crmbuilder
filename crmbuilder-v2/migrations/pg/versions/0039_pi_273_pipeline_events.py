"""PI-273 (PG chain) — pipeline_events table (progress + agent activity).

Companion to the SQLite-chain ``0082``. Creates the ``pipeline_events`` table (one
row per pipeline step + one ``agent_outcome`` row per agent invocation) on Postgres
deployments materialised from an earlier baseline. The PG baseline is ``create_all``
from the live models, so a fresh PG DB already carries it — the create is
inspector-guarded. Chains after ``0038_pi_255_source_mapping_tables``. Never replay
the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import PipelineEvent

revision: str = "0039_pi_273_pipeline_events"
down_revision: str | None = "0038_pi_255_source_mapping_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if PipelineEvent.__tablename__ not in _tables():
        PipelineEvent.__table__.create(bind)


def downgrade() -> None:
    if PipelineEvent.__tablename__ in _tables():
        PipelineEvent.__table__.drop(op.get_bind())
