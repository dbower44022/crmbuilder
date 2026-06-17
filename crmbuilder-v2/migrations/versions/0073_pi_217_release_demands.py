"""PI-217 (PRJ-033) — release_demands table (the agent-layer demand-set store).

Creates the ``release_demands`` table (AL-1 / DEC-512/513) from the ORM
``__table__`` with ``checkfirst`` (idempotent on the create_all-then-upgrade-head
test path). The persisted, replayable input to ``reconcile_release``. Outside the
refs / change_log discipline, so no CHECK rebuilds. SQLite head 0072 -> 0073;
companion PG delta ``migrations/pg/versions/0030_pi_217_release_demands.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReleaseDemand

revision: str = "0073_pi_217_release_demands"
down_revision: str | None = "0072_pi_203_resource_locks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    ReleaseDemand.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if ReleaseDemand.__tablename__ in _tables():
        ReleaseDemand.__table__.drop(op.get_bind())
