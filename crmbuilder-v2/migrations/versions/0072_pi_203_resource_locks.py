"""PI-203 (PRJ-030) — resource_locks table (the file-level lock backstop).

Creates the ``resource_locks`` table (FL-4) from the ORM ``__table__`` with
``checkfirst`` (idempotent on the create_all-then-upgrade-head test path),
including the ``uq_resource_locks_active`` partial unique index (at most one active
lock per resource). Outside the refs / change_log discipline, so no CHECK rebuilds.
SQLite head 0071 -> 0072; companion PG delta
``migrations/pg/versions/0029_pi_203_resource_locks.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ResourceLock

revision: str = "0072_pi_203_resource_locks"
down_revision: str | None = "0071_pi_214_reopen_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    ResourceLock.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if ResourceLock.__tablename__ in _tables():
        ResourceLock.__table__.drop(op.get_bind())
