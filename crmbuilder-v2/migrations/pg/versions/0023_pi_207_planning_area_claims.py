"""PI-207 (PG chain) — planning_area_claims table.

Companion to the SQLite-chain ``0066``. Creates the ``planning_area_claims`` table
(DEC-505) on Postgres deployments materialised from an earlier baseline. The PG
baseline is ``create_all`` from the live models, so a fresh PG DB already carries
it — the create is inspector-guarded. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import PlanningAreaClaim

revision: str = "0023_pi_207_planning_area_claims"
down_revision: str | None = "0022_pi_206_release_qa_test_stamps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if PlanningAreaClaim.__tablename__ not in _tables():
        PlanningAreaClaim.__table__.create(bind)


def downgrade() -> None:
    if PlanningAreaClaim.__tablename__ in _tables():
        PlanningAreaClaim.__table__.drop(op.get_bind())
