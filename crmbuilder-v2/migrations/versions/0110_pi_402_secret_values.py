"""PI-402 (REQ-481, REQ-157 amended, DEC-913, SQLite chain) — encrypted secret store.

Companion to the PG-chain ``0067``. Adds ``secret_values``: the ciphertext
behind each opaque ``crmbuilder:{uuid}`` reference already stored on an instance
row.

Why: secrets lived only in an OS keyring, so they stranded on the machine that
created them. The hosted API has no keyring backend at all — it could neither
save an instance's credentials nor resolve them to publish. Ciphertext in the
shared store travels with the database.

REQ-157 is unchanged in substance: the owning row still holds only a reference,
and nothing here is readable without ``CRMBUILDER_V2_SECRET_KEY``.

Additive: no existing table or row is touched, and a keyring-held secret keeps
resolving through the fallback until it is migrated. Bootstrap-safe too — it
no-ops when the table is already present, which is what the create_all +
stamp-behind path produces. Downgrade drops the table, discarding any secret
migrated into it; those values must then be re-entered (or restored from the
keyring).

SQLite chain head 0109 -> 0110.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0110_pi_402_secret_values"
down_revision: str | None = "0109_pi_397_recorded_by_decision"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    """Whether ``name`` is already present in the target database.

    The PI-308 bootstrap path (LSN-002/LSN-007) creates the *head* schema with
    ``Base.metadata.create_all``, stamps it one revision behind, then upgrades —
    so the trailing migration runs against a database that already has every
    table. A bare ``create_table`` fails there ("table secret_values already
    exists"). Earlier migrations happened not to notice because they altered
    rather than created.
    """
    if op.get_context().as_sql:
        # No connection to inspect when generating SQL offline; emit the CREATE
        # unconditionally so `alembic upgrade --sql` still produces a usable script.
        return False
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _table_exists("secret_values"):
        return
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
    if _table_exists("secret_values"):
        op.drop_table("secret_values")
