"""ADO (PI-114 / WTK-001) — Workstream state-model substrate

Revision ID: 0036_ado_workstream_state_model_substrate
Revises: 0035_ado_session_works_work_task
Create Date: 2026-05-31

Agent Delivery Organization state-model substrate (design §5, DEC-349/DEC-359).
Three coordinated schema changes on ``workstreams``:

1. Rename the phase-type vocab value ``Design`` → ``Architecture`` — rebuild
   ``ck_workstream_phase_type`` and data-rewrite any ``Design`` rows (none live
   at authoring, handled defensively).
2. Expand the lifecycle from ``{Planned, In Progress, Complete, Blocked}`` to the
   gate model ``{Planned, Scoping, Ready, In Progress, Complete, Not Applicable,
   Blocked}`` — rebuild ``ck_workstream_status`` (superset; no row rewrite).
3. Add the orthogonal human-escape flag ``workstream_needs_attention`` (bool,
   default false) + ``workstream_needs_attention_reason`` (text, nullable).

Reversible: ``downgrade`` rewrites ``Architecture`` → ``Design`` and folds the
new statuses back to their nearest legacy value before narrowing the CHECKs, and
drops the two flag columns.
"""

from collections.abc import Sequence
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "0036_ado_workstream_state_model_substrate"
down_revision: Union[str, None] = "0035_ado_session_works_work_task"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _check_in(name: str, allowed: set[str]) -> str:
    quoted = ", ".join(f"'{v}'" for v in sorted(allowed))
    return f"{name} IN ({quoted})"


_PHASE_NEW = {
    "Architecture",
    "Development",
    "Testing",
    "Documentation",
    "Data Migration",
    "Deployment",
}
_PHASE_OLD = (_PHASE_NEW - {"Architecture"}) | {"Design"}

_STATUS_NEW = {
    "Planned",
    "Scoping",
    "Ready",
    "In Progress",
    "Complete",
    "Not Applicable",
    "Blocked",
}
_STATUS_OLD = {"Planned", "In Progress", "Complete", "Blocked"}


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Add the flag columns + swap the status CHECK (superset) + drop the old
    #    phase CHECK so the data rewrite below is admissible.
    with op.batch_alter_table("workstreams", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "workstream_needs_attention",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "workstream_needs_attention_reason", sa.Text(), nullable=True
            )
        )
        batch_op.drop_constraint("ck_workstream_status", type_="check")
        batch_op.create_check_constraint(
            "ck_workstream_status", _check_in("workstream_status", _STATUS_NEW)
        )
        batch_op.drop_constraint("ck_workstream_phase_type", type_="check")

    # 2. Rewrite Design → Architecture now the phase CHECK is absent.
    bind.execute(
        sa.text(
            "UPDATE workstreams SET workstream_phase_type='Architecture' "
            "WHERE workstream_phase_type='Design'"
        )
    )

    # 3. Re-add the phase CHECK with the renamed vocab.
    with op.batch_alter_table("workstreams", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_workstream_phase_type",
            _check_in("workstream_phase_type", _PHASE_NEW),
        )


def downgrade() -> None:
    bind = op.get_bind()

    # Drop the renamed-phase CHECK, fold Architecture back to Design.
    with op.batch_alter_table("workstreams", schema=None) as batch_op:
        batch_op.drop_constraint("ck_workstream_phase_type", type_="check")
    bind.execute(
        sa.text(
            "UPDATE workstreams SET workstream_phase_type='Design' "
            "WHERE workstream_phase_type='Architecture'"
        )
    )

    # Fold the new statuses back to their nearest legacy value before narrowing.
    bind.execute(
        sa.text(
            "UPDATE workstreams SET workstream_status='Planned' "
            "WHERE workstream_status IN ('Scoping', 'Ready')"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE workstreams SET workstream_status='Complete' "
            "WHERE workstream_status='Not Applicable'"
        )
    )

    with op.batch_alter_table("workstreams", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "ck_workstream_phase_type",
            _check_in("workstream_phase_type", _PHASE_OLD),
        )
        batch_op.drop_constraint("ck_workstream_status", type_="check")
        batch_op.create_check_constraint(
            "ck_workstream_status", _check_in("workstream_status", _STATUS_OLD)
        )
        batch_op.drop_column("workstream_needs_attention_reason")
        batch_op.drop_column("workstream_needs_attention")
