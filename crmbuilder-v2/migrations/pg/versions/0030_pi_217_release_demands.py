"""PI-217 (PG chain) — release_demands table.

Companion to the SQLite-chain ``0073``. Creates the ``release_demands`` table
(the agent-layer demand-set store) on Postgres deployments materialised from an
earlier baseline. The PG baseline is ``create_all`` from the live models, so a
fresh PG DB already carries it — the create is inspector-guarded. Never replay the
SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReleaseDemand

revision: str = "0030_pi_217_release_demands"
down_revision: str | None = "0029_pi_203_resource_locks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if ReleaseDemand.__tablename__ not in _tables():
        ReleaseDemand.__table__.create(bind)


def downgrade() -> None:
    if ReleaseDemand.__tablename__ in _tables():
        ReleaseDemand.__table__.drop(op.get_bind())
