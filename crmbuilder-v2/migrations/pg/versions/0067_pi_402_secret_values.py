"""PI-402 (REQ-481, REQ-157 amended, DEC-913, PG chain) — encrypted secret store.

Companion to the SQLite-chain ``0110``. Adds ``secret_values``: the ciphertext
behind each opaque ``crmbuilder:{uuid}`` reference already stored on an instance
row.

Why: secrets lived only in an OS keyring, so they stranded on the machine that
created them. The hosted API has no keyring backend at all — it could neither
save an instance's credentials nor resolve them to publish. Ciphertext in the
shared store travels with the database.

REQ-157 is unchanged in substance: the owning row still holds only a reference,
and nothing here is readable without ``CRMBUILDER_V2_SECRET_KEY``.

Additive — no existing table or row is touched, and a keyring-held secret keeps
resolving through the fallback until it is migrated. Downgrade drops the table,
which discards any secret that had been migrated into it; those values must be
re-entered (or restored from the keyring) afterwards.

PG chain head 0066 -> 0067.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0067_pi_402_secret_values"
down_revision: str | None = "0066_pi_397_recorded_by_decision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "secret_values",
        sa.Column("secret_ref", sa.String(64), primary_key=True),
        sa.Column("secret_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "secret_created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "secret_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )


def downgrade() -> None:
    op.drop_table("secret_values")
