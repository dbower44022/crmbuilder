"""The reference identifier may carry more than four digits.

``refs.reference_identifier`` was checked against ``^REF-[0-9]{4}$``. The
store reached REF-9999 on 2026-09-17 and the next identifier, REF-10000, was
rejected by that CHECK — so **every** reference write failed with a server
error, in every engagement and for every relationship kind, and with it every
governance record that needs an edge: a requirement's provenance, a planning
item's link to its requirement, a decision's link to what it resolves.

The CHECK is widened to ``^REF-[0-9]{4,}$``. Nothing else changes: the
minting code already formats the next value as ``REF-{n:04d}``, which yields
REF-10000 unpadded once the count passes four digits, and every existing row
keeps its four-digit identifier.

This is the reference table's version of the decision series passing DEC-999
(PI-493 / DEC-1091). A series the machine writes will reach its ceiling; the
CHECK now states a floor.

Downgrade narrows the CHECK again, and refuses when a row would violate it,
because narrowing past live data would leave the table unable to satisfy its
own constraint.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "shared_core_0003_reference_identifier_beyond_9999"
down_revision: str | None = "shared_core_0002_retire_service_reference_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT = "ck_ref_reference_identifier_format"
_WIDE = "reference_identifier IS NULL OR reference_identifier ~ '^REF-[0-9]{4,}$'"
_NARROW = "reference_identifier IS NULL OR reference_identifier ~ '^REF-[0-9]{4}$'"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "refs", type_="check")
    op.create_check_constraint(_CONSTRAINT, "refs", sa.text(_WIDE))


def downgrade() -> None:
    bind = op.get_bind()
    over = bind.execute(
        sa.text(
            "SELECT count(*) FROM refs "
            "WHERE reference_identifier IS NOT NULL "
            "AND reference_identifier !~ '^REF-[0-9]{4}$'"
        )
    ).scalar_one()
    if over:
        raise RuntimeError(
            f"{over} reference identifier(s) carry more than four digits; "
            "narrowing the CHECK would leave the table violating it. Move or "
            "renumber those rows first."
        )
    op.drop_constraint(_CONSTRAINT, "refs", type_="check")
    op.create_check_constraint(_CONSTRAINT, "refs", sa.text(_NARROW))
