"""PI-318 (REL-024) — reconcile_transactions log table.

Creates the ``reconcile_transactions`` table (the append-only trust-but-log trail
for reconcile actions, DEC-722/723) from the ORM ``__table__`` with
``checkfirst`` (idempotent on the create_all-then-upgrade-head test path). A
lightweight engagement-scoped child table — **not** a prefixed-identifier
governance entity — so it carries no ``change_log`` / ``refs`` participation and
rebuilds **no** entity-type / relationship CHECKs. It carries its own
direction / status CHECKs and two lookup indexes.

SQLite chain head 0089 -> 0090. Companion PG-chain delta:
``migrations/pg/versions/0047_pi_318_reconcile_transactions.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReconcileTransaction

revision: str = "0090_pi_318_reconcile_transactions"
down_revision: str | None = "0089_pi_300_entity_collection_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    ReconcileTransaction.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if ReconcileTransaction.__tablename__ in _tables():
        ReconcileTransaction.__table__.drop(op.get_bind())
