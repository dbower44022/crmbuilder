"""PI-214 (PRJ-034) — area-reopen approval columns (RW5).

Adds ``approval_tier`` (+ its CHECK), ``approval_decision_identifier`` and
``triggering_finding_identifier`` to ``area_reopens``. Column-adds + the CHECK are
guarded so the migration is a no-op on a create_all-materialised DB (the test
path). SQLite head 0070 -> 0071; companion PG delta
``migrations/pg/versions/0028_pi_214_reopen_approval.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import REOPEN_APPROVAL_TIERS, _check_in

revision: str = "0071_pi_214_reopen_approval"
down_revision: str | None = "0070_pi_213_cascade_revalidation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COLUMNS = (
    "approval_tier",
    "approval_decision_identifier",
    "triggering_finding_identifier",
)


def _existing() -> set[str]:
    insp = sa.inspect(op.get_bind())
    if "area_reopens" not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns("area_reopens")}


def upgrade() -> None:
    have = _existing()
    if all(c in have for c in _COLUMNS):
        return
    with op.batch_alter_table("area_reopens") as batch:
        if "approval_tier" not in have:
            batch.add_column(
                sa.Column(
                    "approval_tier", sa.String(16), nullable=False,
                    server_default="lead_auto",
                )
            )
            batch.create_check_constraint(
                "ck_area_reopen_approval_tier",
                _check_in("approval_tier", REOPEN_APPROVAL_TIERS),
            )
        if "approval_decision_identifier" not in have:
            batch.add_column(
                sa.Column("approval_decision_identifier", sa.String(32), nullable=True)
            )
        if "triggering_finding_identifier" not in have:
            batch.add_column(
                sa.Column(
                    "triggering_finding_identifier", sa.String(32), nullable=True
                )
            )


def downgrade() -> None:
    have = _existing()
    with op.batch_alter_table("area_reopens") as batch:
        if "approval_tier" in have:
            batch.drop_constraint("ck_area_reopen_approval_tier", type_="check")
        for col in _COLUMNS:
            if col in have:
                batch.drop_column(col)
