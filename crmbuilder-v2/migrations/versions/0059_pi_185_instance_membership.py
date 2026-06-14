"""PI-185 (PRJ-027) — instance_memberships join table.

Creates the ``instance_memberships`` table (the per-(canonical design object,
instance) join, §5 of the PRJ-027 architecture) from the ORM ``__table__`` with
``checkfirst`` (idempotent on the create_all-then-upgrade-head test path). It is
a lightweight engagement-scoped child table — **not** a prefixed-identifier
governance entity — so it carries no ``change_log`` / ``refs`` participation and
this migration rebuilds **no** entity-type / relationship CHECKs. It carries its
own member_type / state CHECKs, the (engagement, instance, member) uniqueness
constraint, the FK to ``instances`` (CASCADE), and two lookup indexes.

SQLite chain head 0058 -> 0059. Companion PG-chain delta:
``migrations/pg/versions/0017_pi_185_instance_membership.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import InstanceMembership

revision: str = "0059_pi_185_instance_membership"
down_revision: str | None = "0058_pi_189_dedup_template_design_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    InstanceMembership.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if InstanceMembership.__tablename__ in _tables():
        InstanceMembership.__table__.drop(op.get_bind())
