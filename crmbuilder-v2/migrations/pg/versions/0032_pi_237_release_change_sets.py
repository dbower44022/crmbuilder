"""PI-237 (PG chain) — release_change_sets table (the persisted reconciled change-set).

Companion to the SQLite-chain ``0075``. Creates the ``release_change_sets`` table
(the durable, reviewable reconciliation output, front-half completion of the Agent
System Redesign) on Postgres deployments materialised from an earlier baseline.
The PG baseline is ``create_all`` from the live models, so a fresh PG DB already
carries it — the create is inspector-guarded. Never replay the SQLite chain on
Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReleaseChangeSet

revision: str = "0032_pi_237_release_change_sets"
down_revision: str | None = "0031_pi_196_instance_basic_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if ReleaseChangeSet.__tablename__ not in _tables():
        ReleaseChangeSet.__table__.create(bind)


def downgrade() -> None:
    if ReleaseChangeSet.__tablename__ in _tables():
        ReleaseChangeSet.__table__.drop(op.get_bind())
