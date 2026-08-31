"""PI-439 (REQ-542 / DEC-964) — the rule_enforcement_overrides audit table.

When a session waves a failing ``enforced_with_override`` check through with a
stated reason, the pre-action hook records the waiver here: which rule, why,
the command it applied to, and the hook session. An audit row, not a governance
entity — no reference edges, no change_log, no identifier prefix, so neither
the ``refs`` nor the ``change_log`` CHECKs move (LSN-001 does not apply).

SQLite chain head 0126 -> 0127. Companion PG-chain delta:
``migrations/pg/versions/0084_pi_439_rule_enforcement_overrides.py``.

Bootstrap-safe (LSN-050): the create_all + stamp-behind path already holds the
table, so the create and the drop are existence-guarded.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0127_pi_439_rule_enforcement_overrides"
down_revision: str | None = "0126_pi_411_publish_run_plan_fingerprint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "rule_enforcement_overrides"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    if _TABLE in _tables():
        return
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "engagement_id",
            sa.String(32),
            sa.ForeignKey("engagements.engagement_identifier", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "rule_identifier",
            sa.String(32),
            sa.ForeignKey("governance_rules.identifier", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("command", sa.Text(), nullable=True),
        sa.Column("session_ref", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rule_enforcement_overrides_rule", _TABLE, ["rule_identifier"])


def downgrade() -> None:
    if _TABLE in _tables():
        op.drop_table(_TABLE)
