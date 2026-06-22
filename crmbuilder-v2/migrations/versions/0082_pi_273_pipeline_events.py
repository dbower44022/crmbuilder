"""PI-273 (PRJ-040 / REQ-312/313/314) — pipeline_events table (progress + agent activity).

Creates the ``pipeline_events`` table from the ORM ``__table__`` with
``checkfirst`` (idempotent on the create_all-then-upgrade-head test path). One row
per pipeline step (a stage transition, an agent dispatch, a verify, a merge, a
halt, a no-op) and one ``agent_outcome`` row per agent invocation. A telemetry
satellite — outside the refs / change_log discipline, so no CHECK rebuilds.
SQLite head 0081 -> 0082; companion PG delta
``migrations/pg/versions/0038_pi_273_pipeline_events.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import PipelineEvent

revision: str = "0082_pi_273_pipeline_events"
down_revision: str | None = "0081_pi_255_source_mapping_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    PipelineEvent.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if PipelineEvent.__tablename__ in _tables():
        PipelineEvent.__table__.drop(op.get_bind())
