"""PI-215 (PRJ-031) — reconciliation_conflicts table.

Creates the ``reconciliation_conflicts`` table (the typed conflict store, RC-4)
from the ORM ``__table__`` with ``checkfirst`` (idempotent on the
create_all-then-upgrade-head test path). Outside the refs / change_log discipline
(no new entity type), so no CHECK rebuilds. Composite FK references ``releases``
(created in 0063). SQLite head 0066 -> 0067; companion PG delta
``migrations/pg/versions/0024_pi_215_reconciliation_conflicts.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReconciliationConflict

revision: str = "0067_pi_215_reconciliation_conflicts"
down_revision: str | None = "0066_pi_207_planning_area_claims"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    ReconciliationConflict.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if ReconciliationConflict.__tablename__ in _tables():
        ReconciliationConflict.__table__.drop(op.get_bind())
