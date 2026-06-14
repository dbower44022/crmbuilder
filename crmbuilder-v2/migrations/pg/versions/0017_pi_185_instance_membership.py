"""PI-185 (PG chain) — instance_memberships join table.

Companion to the SQLite-chain ``0059``. Creates the ``instance_memberships``
table on Postgres deployments materialised from an earlier baseline. The PG
baseline (``0001_pg_baseline``) is ``Base.metadata.create_all`` from the live
ORM models, so a freshly-built PG DB already carries the table — the create is
inspector-guarded. It is a lightweight engagement-scoped child table, so there
are no entity-type / relationship CHECK rebuilds. Never replay the SQLite chain
on a Postgres DB; the two files are siblings, not a sequence.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import InstanceMembership

revision: str = "0017_pi_185_instance_membership"
down_revision: str | None = "0016_pi_186_instance_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if InstanceMembership.__tablename__ not in _tables():
        InstanceMembership.__table__.create(op.get_bind())


def downgrade() -> None:
    if InstanceMembership.__tablename__ in _tables():
        InstanceMembership.__table__.drop(op.get_bind())
