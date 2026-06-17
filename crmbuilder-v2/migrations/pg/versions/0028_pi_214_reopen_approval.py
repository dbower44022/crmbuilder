"""PI-214 (PG chain) — area-reopen approval columns (RW5).

Companion to the SQLite-chain ``0071``. Adds ``approval_tier`` (+ CHECK),
``approval_decision_identifier`` and ``triggering_finding_identifier`` to
``area_reopens`` on Postgres deployments materialised from an earlier baseline.
Guarded (no-op when create_all already made them). Never replay the SQLite chain
on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import REOPEN_APPROVAL_TIERS, _check_in

revision: str = "0028_pi_214_reopen_approval"
down_revision: str | None = "0027_pi_213_cascade_revalidation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _existing() -> set[str]:
    insp = sa.inspect(op.get_bind())
    if "area_reopens" not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns("area_reopens")}


def upgrade() -> None:
    have = _existing()
    if "approval_tier" not in have:
        op.add_column(
            "area_reopens",
            sa.Column(
                "approval_tier", sa.String(16), nullable=False,
                server_default="lead_auto",
            ),
        )
        op.create_check_constraint(
            "ck_area_reopen_approval_tier", "area_reopens",
            _check_in("approval_tier", REOPEN_APPROVAL_TIERS),
        )
    if "approval_decision_identifier" not in have:
        op.add_column(
            "area_reopens",
            sa.Column("approval_decision_identifier", sa.String(32), nullable=True),
        )
    if "triggering_finding_identifier" not in have:
        op.add_column(
            "area_reopens",
            sa.Column("triggering_finding_identifier", sa.String(32), nullable=True),
        )


def downgrade() -> None:
    have = _existing()
    if "approval_tier" in have:
        op.drop_constraint("ck_area_reopen_approval_tier", "area_reopens", type_="check")
    for col in (
        "approval_tier",
        "approval_decision_identifier",
        "triggering_finding_identifier",
    ):
        if col in have:
            op.drop_column("area_reopens", col)
