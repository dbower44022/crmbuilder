"""PI-397 (REQ-476, DEC-904/906, SQLite chain) — status-neutral decision edge.

Companion to the PG-chain ``0066``. Admits the new relationship kind
``requirement_recorded_by_decision`` in the shared ``refs.relationship_kind``
CHECK. A superset of the prior kind set, so no existing row is invalidated.

The kind lets a decision be recorded against a requirement without mutating it.
The prior two ``(requirement, decision)`` kinds both dispatch a status flip —
``requirement_approved_by_decision`` into ``activate_by_decision`` and
``requirement_changed_by_decision`` into ``reopen_by_decision`` — so a decision
that merely records a completion had no correct edge and silently de-confirmed
its requirement (DEC-903 reopened REQ-472 this way).

SQLite cannot drop a CHECK in place, so the constraint is rebuilt through
``batch_alter_table`` (table copy). Downgrade drops rows carrying the new kind
before narrowing the CHECK, or the rebuilt table would reject them.

SQLite chain head 0108 -> 0109.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS, _check_in

revision: str = "0109_pi_397_recorded_by_decision"
down_revision: str | None = "0108_pi_396_agent_profile_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KINDS = frozenset({"requirement_recorded_by_decision"})

_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_ref_relationship_check(kinds: frozenset[str]) -> None:
    if "refs" not in _tables():  # absent when the chain is entered mid-stream
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def upgrade() -> None:
    _rebuild_ref_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    if "refs" in _tables():
        op.execute(
            "DELETE FROM refs WHERE relationship_kind = "
            "'requirement_recorded_by_decision'"
        )
    _rebuild_ref_relationship_check(_KINDS_OLD)
