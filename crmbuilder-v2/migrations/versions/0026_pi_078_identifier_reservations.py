"""PI-078 — create identifier_reservations table

Revision ID: 0026_pi_078_identifier_reservations
Revises: 0025_pi_077_planning_item_claim
Create Date: 2026-05-29

PI-078 satisfier. Adds the ``identifier_reservations`` table backing the
``POST /identifiers/reserve`` endpoint. Each row is one reserved block of
prefixed identifiers for one ``entity_type``, held server-side under the
requesting conversation's claim (``reserved_by``) with a TTL
(``expires_at``). The reservation logic treats an unexpired block as
"taken" when computing the next free number so concurrent child agents in
an orchestrator run never collide on next-available identifiers; expired
blocks are ignored and garbage-collected (the TTL auto-release).

Reservations are ephemeral runtime state, not governance records, so the
table is intentionally absent from the JSON snapshot exporter.

Reversibility: ``downgrade()`` drops the table. Any live reservations are
lost (acceptable — they are short-lived holds, not durable data).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_pi_078_identifier_reservations"
down_revision: Union[str, None] = "0025_pi_077_planning_item_claim"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "identifier_reservations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("reserved_identifiers", sa.JSON(), nullable=False),
        sa.Column("max_number", sa.Integer(), nullable=False),
        sa.Column("reserved_by", sa.String(length=64), nullable=True),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_identifier_reservations_lookup",
        "identifier_reservations",
        ["entity_type", "expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_identifier_reservations_lookup",
        table_name="identifier_reservations",
    )
    op.drop_table("identifier_reservations")
