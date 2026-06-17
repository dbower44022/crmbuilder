"""PI-215 (PG chain) — reconciliation_conflicts table.

Companion to the SQLite-chain ``0067``. Creates the ``reconciliation_conflicts``
table (RC-4) on Postgres deployments materialised from an earlier baseline. The
PG baseline is ``create_all`` from the live models, so a fresh PG DB already
carries it — the create is inspector-guarded. Never replay the SQLite chain on
Postgres; siblings, not a sequence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReconciliationConflict

revision: str = "0024_pi_215_reconciliation_conflicts"
down_revision: str | None = "0023_pi_207_planning_area_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if ReconciliationConflict.__tablename__ not in _tables():
        ReconciliationConflict.__table__.create(bind)


def downgrade() -> None:
    if ReconciliationConflict.__tablename__ in _tables():
        ReconciliationConflict.__table__.drop(op.get_bind())
