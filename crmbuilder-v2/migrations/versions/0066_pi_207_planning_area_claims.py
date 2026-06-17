"""PI-207 (PRJ-031) — planning_area_claims table (single-threaded-by-area).

Creates the ``planning_area_claims`` table (DEC-505) from the ORM ``__table__``
with ``checkfirst`` (idempotent on the create_all-then-upgrade-head test path).
Outside the refs / change_log discipline, so no CHECK rebuilds. Its composite FK
references ``releases`` (created in 0063). SQLite head 0065 -> 0066; companion PG
delta ``migrations/pg/versions/0023_pi_207_planning_area_claims.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import PlanningAreaClaim

revision: str = "0066_pi_207_planning_area_claims"
down_revision: str | None = "0065_pi_206_release_qa_test_stamps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    PlanningAreaClaim.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if PlanningAreaClaim.__tablename__ in _tables():
        PlanningAreaClaim.__table__.drop(op.get_bind())
