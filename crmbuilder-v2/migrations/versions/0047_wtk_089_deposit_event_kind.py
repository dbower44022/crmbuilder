"""WTK-089 — `deposit_event_kind` discriminator on deposit_events.

Implements D3 of the WTK-089 design spec (governance-schema-specs/
deposit-path-provenance-and-schema.md §4): adds the NOT NULL
``deposit_event_kind`` column (``close_out_apply`` | ``audit_deposit``)
with a ``'close_out_apply'`` server default that backfills every existing
row to the kind it factually is, plus ``ck_deposit_event_kind`` and the
kind index mirroring the outcome index. The kind-conditional access rules
(parent-edge requirement vs prohibition, the audit ``apply_context``
shape) are repository-layer work outside this migration.

Ordered after the PI-153 set per WTK-089 §5 (canonical order: consumed
substrate first, deposit-path delta second); the merged refs-CHECK rebuild
already landed in 0046, so this migration touches only ``deposit_events``.
The whole upgrade keys off column absence, so it is a clean no-op on the
create_all-then-upgrade-head test path (the model already carries the
column) and a real delta on a pre-existing store. Downgrade deletes
``audit_deposit`` rows and their refs edges (they violate the old world's
unconditional parent-edge invariant) before dropping the column —
destructive on downgrade, consistent with the 0044 posture.

SQLite chain head 0046 -> 0047. Companion PG-chain delta:
``migrations/pg/versions/0009_wtk_089_deposit_event_kind.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import DEPOSIT_EVENT_KINDS, _check_in

revision: str = "0047_wtk_089_deposit_event_kind"
down_revision: str | None = "0046_pi_153_rejected_and_utilization_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "deposit_events"
_COLUMN = "deposit_event_kind"
_CHECK = "ck_deposit_event_kind"
_INDEX = "ix_deposit_events_deposit_event_kind"


def _has_table() -> bool:
    # deposit_events is absent when the chain is entered mid-stream
    # (the stamp-0036 isolated-migration test path).
    return _TABLE in set(sa.inspect(op.get_bind()).get_table_names())


def _has_column() -> bool:
    inspector = sa.inspect(op.get_bind())
    return _COLUMN in {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    if not _has_table() or _has_column():
        return
    # Plain ADD COLUMN (no recreate) — the server default backfills every
    # pre-existing row to 'close_out_apply', the kind it factually is.
    op.add_column(
        _TABLE,
        sa.Column(
            _COLUMN,
            sa.String(length=32),
            nullable=False,
            server_default="close_out_apply",
        ),
    )
    # The CHECK needs a recreate-table batch on SQLite. deposit_events
    # carries plain column indexes only, so the batch-recreate
    # expression-index hazard (fixed in 0040) does not apply.
    with op.batch_alter_table(_TABLE) as batch:
        batch.create_check_constraint(_CHECK, _check_in(_COLUMN, DEPOSIT_EVENT_KINDS))
    op.create_index(_INDEX, _TABLE, [_COLUMN])


def downgrade() -> None:
    if not _has_table() or not _has_column():
        return
    # audit_deposit rows violate the old world's unconditional
    # parent-edge invariant — delete them and their refs edges (their
    # wrote_record / parent edges, and any observed_in edges targeting
    # them) before dropping the column.
    if "refs" in set(sa.inspect(op.get_bind()).get_table_names()):
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
    with op.batch_alter_table(_TABLE) as batch:
        batch.drop_constraint(_CHECK, type_="check")
        batch.drop_column(_COLUMN)
