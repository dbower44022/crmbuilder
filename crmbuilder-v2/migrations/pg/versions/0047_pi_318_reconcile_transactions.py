"""PI-318 (REL-024) — reconcile_transactions log table (Postgres chain).

PG-chain companion of SQLite ``0090_pi_318_reconcile_transactions``. Creates the
``reconcile_transactions`` table from the ORM ``__table__`` with ``checkfirst``;
the dialect-aware column/CHECK constructs render their Postgres form. A
lightweight engagement-scoped child table — no ``change_log`` / ``refs``
participation, no entity-type / relationship CHECK rebuild.

PG chain head 0046 -> 0047.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReconcileTransaction

revision: str = "0047_pi_318_reconcile_transactions"
down_revision: str | None = "0046_pi_300_entity_collection_settings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    ReconcileTransaction.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if ReconcileTransaction.__tablename__ in _tables():
        ReconcileTransaction.__table__.drop(op.get_bind())
