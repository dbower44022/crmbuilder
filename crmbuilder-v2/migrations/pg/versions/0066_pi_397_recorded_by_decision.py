"""PI-397 (REQ-476, DEC-904/906, PG chain) — status-neutral decision edge.

Companion to the SQLite-chain ``0109``. Admits the new relationship kind
``requirement_recorded_by_decision`` in the shared ``refs.relationship_kind``
CHECK. A superset of the prior kind set, so no existing row is invalidated.

The kind lets a decision be recorded against a requirement without mutating it.
The prior two ``(requirement, decision)`` kinds both dispatch a status flip —
``requirement_approved_by_decision`` into ``activate_by_decision`` and
``requirement_changed_by_decision`` into ``reopen_by_decision`` — so a decision
that merely records a completion had no correct edge and silently de-confirmed
its requirement (DEC-903 reopened REQ-472 this way).

Downgrade drops rows carrying the new kind before narrowing the CHECK, or the
constraint would fail to validate against them.

PG chain head 0065 -> 0066. This is the migration walked against the live
Postgres store (``alembic -c migrations/pg/alembic.ini upgrade head``).
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS, _check_in

revision: str = "0066_pi_397_recorded_by_decision"
down_revision: str | None = "0065_pi_396_agent_profile_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KINDS = frozenset({"requirement_recorded_by_decision"})

_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _rebuild_ref_relationship_check(kinds: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def upgrade() -> None:
    _rebuild_ref_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM refs WHERE relationship_kind = "
        "'requirement_recorded_by_decision'"
    )
    _rebuild_ref_relationship_check(_KINDS_OLD)
