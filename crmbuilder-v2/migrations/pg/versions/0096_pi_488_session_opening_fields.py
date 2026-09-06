"""PI-488 (REQ-568 / DEC-1063): the session fields that record the opening
answer and what followed from it.

A session opened through the session-open operation stores the user's
opening answer as given (``session_opening_answer``), the kind of work the
answer was classified into (``session_kind_of_work`` — the ``PROC-NNN``
catalogue entry, NULL when no kind of work was chosen), the confirmation
line the system said back (``session_confirmation_line``), and the ordered
list of phase segments run (``session_phase_segments`` — JSON, each segment
``{position, domain, profile, label, status, entered_at, left_at}``; an
empty list when the session opened without an answer).

All four columns are additive: existing rows read NULL / ``[]``. Inspector-
guarded so the chain is safe to enter mid-stream.

PG chain head 0095 -> 0096. Companion of the SQLite-chain
``0139_pi_488_session_opening_fields``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0096_pi_488_session_opening_fields"
down_revision: str | None = "0095_pi_462_withdraws_and_claude_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "sessions"
_JSON = sa.JSON().with_variant(JSONB(), "postgresql")
_NEW_COLUMNS = (
    "session_opening_answer",
    "session_kind_of_work",
    "session_confirmation_line",
    "session_phase_segments",
)


def _columns() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if _TABLE not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(_TABLE)}


def upgrade() -> None:
    present = _columns()
    if not present:
        return
    if "session_opening_answer" not in present:
        op.add_column(_TABLE, sa.Column("session_opening_answer", sa.Text(), nullable=True))
    if "session_kind_of_work" not in present:
        op.add_column(_TABLE, sa.Column("session_kind_of_work", sa.String(32), nullable=True))
    if "session_confirmation_line" not in present:
        op.add_column(
            _TABLE, sa.Column("session_confirmation_line", sa.Text(), nullable=True)
        )
    if "session_phase_segments" not in present:
        op.add_column(
            _TABLE,
            sa.Column(
                "session_phase_segments",
                _JSON,
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )


def downgrade() -> None:
    present = _columns()
    if not present:
        return
    for name in _NEW_COLUMNS:
        if name in present:
            op.drop_column(_TABLE, name)
