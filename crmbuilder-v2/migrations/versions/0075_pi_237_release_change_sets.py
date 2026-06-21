"""PI-237 (PRJ-041 / REQ-285) — release_change_sets table (the persisted reconciled change-set).

Creates the ``release_change_sets`` table from the ORM ``__table__`` with
``checkfirst`` (idempotent on the create_all-then-upgrade-head test path). The
durable, reviewable reconciliation output persisted alongside the demand-set and
conflicts — front-half completion of the Agent System Redesign. Outside the
refs / change_log discipline, so no CHECK rebuilds. SQLite head 0074 -> 0075;
companion PG delta ``migrations/pg/versions/0032_pi_237_release_change_sets.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReleaseChangeSet

revision: str = "0075_pi_237_release_change_sets"
down_revision: str | None = "0074_pi_196_instance_basic_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    ReleaseChangeSet.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if ReleaseChangeSet.__tablename__ in _tables():
        ReleaseChangeSet.__table__.drop(op.get_bind())
