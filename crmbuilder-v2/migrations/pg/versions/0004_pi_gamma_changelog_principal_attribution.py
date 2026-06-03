"""PI-gamma (PG chain) — change_log principal_id column + actor CHECK widen.

Companion to the SQLite-chain ``0042``. Adds ``change_log.principal_id`` and
widens ``ck_changelog_actor`` to admit ``service_agent`` / ``user`` on Postgres
deployments materialised from an earlier baseline. Inspector-guarded so it is a
clean no-op on a fresh baseline (which already has the column from create_all)
and a real change on a pre-existing PG store.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_pi_gamma_changelog_principal_attribution"
down_revision: str | None = "0003_pi_gamma_principals_tokens_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTORS_NEW = (
    "actor IN ('claude_session', 'migration', 'manual', "
    "'service_agent', 'user')"
)
_ACTORS_OLD = "actor IN ('claude_session', 'migration', 'manual')"


def _has_column(table: str, column: str) -> bool:
    return column in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)
    }


def upgrade() -> None:
    if not _has_column("change_log", "principal_id"):
        op.add_column(
            "change_log",
            sa.Column("principal_id", sa.String(length=32), nullable=True),
        )
    op.drop_constraint("ck_changelog_actor", "change_log", type_="check")
    op.create_check_constraint("ck_changelog_actor", "change_log", _ACTORS_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM change_log WHERE actor IN ('service_agent', 'user')"
    )
    op.drop_constraint("ck_changelog_actor", "change_log", type_="check")
    op.create_check_constraint("ck_changelog_actor", "change_log", _ACTORS_OLD)
    if _has_column("change_log", "principal_id"):
        op.drop_column("change_log", "principal_id")
