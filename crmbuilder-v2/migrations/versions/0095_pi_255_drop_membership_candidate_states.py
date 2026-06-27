"""PI-255 (PRJ-027 / SES-247, DEC-650) — drop the two source-mapping membership states.

The reconciler design pass settled that ``instance_membership`` stays
canonical-only: candidacy lives in ``mapping_candidate`` and staleness on the
mapping record's ``status``. The ``candidate_pending`` / ``mapping_stale`` states
added by ``0081`` are removed from the vocab and the
``ck_instance_membership_state`` CHECK rebuilt back to {present, drifted, absent}.

Candidate-gating was never shipped, so no live row uses the dropped states — the
upgrade clears any defensively and rebuilds the tighter CHECK. The CHECK predicate
derives from current vocab, and the rebuild inspects the live table first so the
chain is safe to enter mid-stream. SQLite chain head 0094 -> 0095; companion PG
delta ``migrations/pg/versions/0052_pi_255_drop_membership_candidate_states.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import INSTANCE_MEMBERSHIP_STATES, _check_in

revision: str = "0095_pi_255_drop_membership_candidate_states"
down_revision: str | None = "0094_pi_294_release_execution_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The two states 0081 added and this migration removes (SES-247, DEC-650).
_DROPPED_STATES = frozenset({"candidate_pending", "mapping_stale"})


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_membership_state_check(states: frozenset[str]) -> None:
    if "instance_memberships" not in _tables():
        return
    with op.batch_alter_table("instance_memberships") as batch:
        batch.drop_constraint("ck_instance_membership_state", type_="check")
        batch.create_check_constraint(
            "ck_instance_membership_state", _check_in("state", states)
        )


def upgrade() -> None:
    # No live row should carry a dropped state (candidate-gating never shipped),
    # but clear any defensively so the tighter CHECK can be created.
    if "instance_memberships" in _tables():
        dropped = "', '".join(sorted(_DROPPED_STATES))
        op.execute(
            f"DELETE FROM instance_memberships WHERE state IN ('{dropped}')"
        )
    _rebuild_membership_state_check(INSTANCE_MEMBERSHIP_STATES)


def downgrade() -> None:
    _rebuild_membership_state_check(INSTANCE_MEMBERSHIP_STATES | _DROPPED_STATES)
