"""PI-gamma — change_log principal attribution: principal_id column + actor CHECK.

Adds the ``change_log.principal_id`` soft-reference column (which principal made
the change; a plain string, not a FK, so the append-only audit log outlives a
deleted principal) and widens the ``ck_changelog_actor`` CHECK to admit the two
PI-gamma actor kinds (``service_agent``, ``user``).

The change_log actor CHECK is rebuilt from the current ``CHANGE_LOG_ACTORS`` —
a superset, so no existing row is invalidated (the gotcha that adding an actor
kind requires a CHECK migration; tests build via create_all and miss it).

SQLite chain head 0041 -> 0042. Companion PG-chain delta:
``migrations/pg/versions/0004_pi_gamma_changelog_principal_attribution.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042_pi_gamma_changelog_principal_attribution"
down_revision: str | None = "0041_pi_gamma_principals_tokens_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTORS_NEW = (
    "actor IN ('claude_session', 'migration', 'manual', "
    "'service_agent', 'user')"
)
_ACTORS_OLD = "actor IN ('claude_session', 'migration', 'manual')"


def _has_table(table: str) -> bool:
    return table in set(sa.inspect(op.get_bind()).get_table_names())


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if not _has_table("change_log"):
        return  # absent when the chain is entered mid-stream (isolated-migration tests)
    # Add the column with a simple ADD COLUMN (nullable, no recreate needed).
    if not _has_column("change_log", "principal_id"):
        op.add_column(
            "change_log",
            sa.Column("principal_id", sa.String(length=32), nullable=True),
        )
    # Rebuild the actor CHECK (recreate-table batch on SQLite).
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_actor", type_="check")
        batch_op.create_check_constraint("ck_changelog_actor", _ACTORS_NEW)


def downgrade() -> None:
    if not _has_table("change_log"):
        return
    op.get_bind().execute(
        sa.text(
            "DELETE FROM change_log WHERE actor IN ('service_agent', 'user')"
        )
    )
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_constraint("ck_changelog_actor", type_="check")
        batch_op.create_check_constraint("ck_changelog_actor", _ACTORS_OLD)
    if _has_column("change_log", "principal_id"):
        op.drop_column("change_log", "principal_id")
