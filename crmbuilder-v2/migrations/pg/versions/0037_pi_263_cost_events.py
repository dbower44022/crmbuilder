"""PI-263 (PG chain) — cost_events table (AI spend telemetry).

Companion to the SQLite-chain ``0080``. Creates the ``cost_events`` table (one row per
AI spend event — token counts + computed cost_usd + nullable attribution tags) on
Postgres deployments materialised from an earlier baseline. The PG baseline is
``create_all`` from the live models, so a fresh PG DB already carries it — the create is
inspector-guarded. Chains after ``0036_pi_262_publish_runs`` (landed on main in
parallel). Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import CostEvent

revision: str = "0037_pi_263_cost_events"
down_revision: str | None = "0036_pi_262_publish_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if CostEvent.__tablename__ not in _tables():
        CostEvent.__table__.create(bind)


def downgrade() -> None:
    if CostEvent.__tablename__ in _tables():
        CostEvent.__table__.drop(op.get_bind())
