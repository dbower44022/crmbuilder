"""PI-462 (REQ-560 / DEC-1034, REQ-561 / DEC-1035): the ``withdraws`` reference
kind and the ``claude_code`` session medium.

A decision that withdraws an artifact without replacing it now records a
``withdraws`` edge (decision → the withdrawn governed record) alongside the
status change, so the close-out completeness audit finds every withdrawal from
the edges alone, as it finds every supersession through ``supersedes``. A
session run in Claude Code with the live store reachable records the medium
``claude_code``; a claude.ai sandbox conversation keeps ``chat``.

Rebuilds ``ck_ref_relationship`` (last rebuilt by 0066) and
``ck_session_medium`` from the live vocabulary — both supersets, no row
invalidated; inspector-guarded so the chain is safe to enter mid-stream.
Mirrors 0092 / 0094.

Downgrade removes the ``withdraws`` rows and maps ``claude_code`` sessions back
to ``chat`` (the fallback variant the requirement names — a session record is
never deleted) before narrowing the CHECKs.

PG chain head 0094 -> 0095. Companion of the SQLite-chain
``0138_pi_462_withdraws_and_claude_code``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this chain. This migration is the canonical record of the delta; the
live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import (
    REFERENCE_RELATIONSHIPS,
    SESSION_MEDIUMS,
    _check_in,
)

revision: str = "0095_pi_462_withdraws_and_claude_code"
down_revision: str | None = "0094_pi_418_portal_layout_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KIND = "withdraws"
_NEW_MEDIUM = "claude_code"
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - {_NEW_KIND}
_MEDIUMS_NEW = SESSION_MEDIUMS
_MEDIUMS_OLD = SESSION_MEDIUMS - {_NEW_MEDIUM}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_ref_relationship_check(kinds: frozenset[str]) -> None:
    if "refs" not in _tables():
        return
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def _rebuild_session_medium_check(mediums: frozenset[str]) -> None:
    if "sessions" not in _tables():
        return
    op.drop_constraint("ck_session_medium", "sessions", type_="check")
    op.create_check_constraint(
        "ck_session_medium", "sessions", _check_in("session_medium", mediums)
    )


def upgrade() -> None:
    _rebuild_ref_relationship_check(_KINDS_NEW)
    _rebuild_session_medium_check(_MEDIUMS_NEW)


def downgrade() -> None:
    tables = _tables()
    if "refs" in tables:
        op.execute(f"DELETE FROM refs WHERE relationship_kind = '{_NEW_KIND}'")
    if "sessions" in tables:
        op.execute(
            "UPDATE sessions SET session_medium = 'chat' "
            f"WHERE session_medium = '{_NEW_MEDIUM}'"
        )
    _rebuild_ref_relationship_check(_KINDS_OLD)
    _rebuild_session_medium_check(_MEDIUMS_OLD)
