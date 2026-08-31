"""PI-439 (PG chain) — the rule_enforcement_overrides audit table.

Companion to the SQLite-chain ``0127_pi_439_rule_enforcement_overrides``; see
its docstring. The PG baseline is ``create_all`` from the live models, so a
fresh PG DB already carries the table — the create is existence-guarded.
Chains after ``0083_pi_411_publish_run_plan_fingerprint``. Never replay the SQLite
chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0084_pi_439_rule_enforcement_overrides"
down_revision: str | None = "0083_pi_411_publish_run_plan_fingerprint"
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
