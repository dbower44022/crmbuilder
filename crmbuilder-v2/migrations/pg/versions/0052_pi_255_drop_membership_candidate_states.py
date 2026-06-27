"""PI-255 (PG chain) — drop the two source-mapping membership states.

Companion to the SQLite-chain ``0095`` (SES-247, DEC-650). Rebuilds the
``instance_memberships`` ``ck_instance_membership_state`` CHECK back to
{present, drifted, absent} on a Postgres deployment materialised from an earlier
baseline that carried the ``candidate_pending`` / ``mapping_stale`` states. The
PG baseline is ``create_all`` from the live models, so a fresh PG DB already has
the tightened CHECK (derived from current vocab) — this delta only matters for an
existing DB. Guarded for table existence; never replay the SQLite chain on PG.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.vocab import INSTANCE_MEMBERSHIP_STATES, _check_in
from sqlalchemy import inspect

revision: str = "0052_pi_255_drop_membership_candidate_states"
down_revision: str | None = "0051_pi_294_release_execution_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_DROPPED_STATES = frozenset({"candidate_pending", "mapping_stale"})


def _rebuild_membership_state_check(states: frozenset[str]) -> None:
    bind = op.get_bind()
    if "instance_memberships" not in set(inspect(bind).get_table_names()):
        return
    op.drop_constraint(
        "ck_instance_membership_state",
        "instance_memberships",
        type_="check",
    )
    op.create_check_constraint(
        "ck_instance_membership_state",
        "instance_memberships",
        _check_in("state", states),
    )


def upgrade() -> None:
    bind = op.get_bind()
    if "instance_memberships" in set(inspect(bind).get_table_names()):
        dropped = "', '".join(sorted(_DROPPED_STATES))
        op.execute(
            f"DELETE FROM instance_memberships WHERE state IN ('{dropped}')"
        )
    _rebuild_membership_state_check(INSTANCE_MEMBERSHIP_STATES)


def downgrade() -> None:
    _rebuild_membership_state_check(INSTANCE_MEMBERSHIP_STATES | _DROPPED_STATES)
