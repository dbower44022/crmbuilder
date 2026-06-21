"""PI-238 (PRJ-041 / REQ-285) — release_signoffs table (front-half review sign-offs).

Creates the ``release_signoffs`` table from the ORM ``__table__`` with
``checkfirst`` (idempotent on the create_all-then-upgrade-head test path). The
append-only, freshness-checked human review sign-offs that gate the
reconciliation and architecture-planning transitions. Outside the refs /
change_log discipline, so no CHECK rebuilds. SQLite head 0075 -> 0076; companion
PG delta ``migrations/pg/versions/0033_pi_238_release_signoffs.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReleaseSignoff

revision: str = "0076_pi_238_release_signoffs"
down_revision: str | None = "0075_pi_237_release_change_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    ReleaseSignoff.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if ReleaseSignoff.__tablename__ in _tables():
        ReleaseSignoff.__table__.drop(op.get_bind())
