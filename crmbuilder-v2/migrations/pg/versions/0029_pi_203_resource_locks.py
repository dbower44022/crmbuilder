"""PI-203 (PG chain) — resource_locks table.

Companion to the SQLite-chain ``0072``. Creates the ``resource_locks`` table
(FL-4, with its partial unique index) on Postgres deployments materialised from an
earlier baseline. The PG baseline is ``create_all`` from the live models, so a
fresh PG DB already carries it — the create is inspector-guarded. Never replay the
SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ResourceLock

revision: str = "0029_pi_203_resource_locks"
down_revision: str | None = "0028_pi_214_reopen_approval"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if ResourceLock.__tablename__ not in _tables():
        ResourceLock.__table__.create(bind)


def downgrade() -> None:
    if ResourceLock.__tablename__ in _tables():
        ResourceLock.__table__.drop(op.get_bind())
