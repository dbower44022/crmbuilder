"""WTK-089 (PG chain) — `deposit_event_kind` discriminator on deposit_events.

Companion to the SQLite-chain ``0047``. Adds the NOT NULL
``deposit_event_kind`` column with the ``'close_out_apply'`` backfill
default, ``ck_deposit_event_kind``, and the kind index on Postgres
deployments materialised from an earlier baseline. Inspector-guarded on
column presence so it is a clean no-op on a fresh baseline (create_all
already has all three) and a real change on a pre-existing PG store.
Downgrade deletes ``audit_deposit`` rows and their refs edges before
dropping the column (they violate the old world's unconditional
parent-edge invariant).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import DEPOSIT_EVENT_KINDS, _check_in

revision: str = "0009_wtk_089_deposit_event_kind"
down_revision: str | None = "0008_pi_153_rejected_and_utilization_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "deposit_events"
_COLUMN = "deposit_event_kind"
_CHECK = "ck_deposit_event_kind"
_INDEX = "ix_deposit_events_deposit_event_kind"


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    return _COLUMN in {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    if _has_column():
        return
    op.add_column(
        _TABLE,
        sa.Column(
            _COLUMN,
            sa.String(length=32),
            nullable=False,
            server_default="close_out_apply",
        ),
    )
    op.create_check_constraint(_CHECK, _TABLE, _check_in(_COLUMN, DEPOSIT_EVENT_KINDS))
    op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    if not _has_column():
        return
    op.execute(
        "DELETE FROM refs WHERE "
        "(source_type = 'deposit_event' AND source_id IN "
        f"(SELECT deposit_event_identifier FROM {_TABLE} "
        f"WHERE {_COLUMN} = 'audit_deposit')) "
        "OR (target_type = 'deposit_event' AND target_id IN "
        f"(SELECT deposit_event_identifier FROM {_TABLE} "
        f"WHERE {_COLUMN} = 'audit_deposit'))"
    )
    op.execute(f"DELETE FROM {_TABLE} WHERE {_COLUMN} = 'audit_deposit'")
    op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_constraint(_CHECK, _TABLE, type_="check")
    op.drop_column(_TABLE, _COLUMN)
