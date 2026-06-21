"""PI-238 (PG chain) — release_signoffs table (front-half review sign-offs).

Companion to the SQLite-chain ``0076``. Creates the ``release_signoffs`` table
(the append-only, freshness-checked human review sign-offs gating the front-half
transitions) on Postgres deployments materialised from an earlier baseline. The
PG baseline is ``create_all`` from the live models, so a fresh PG DB already
carries it — the create is inspector-guarded. Never replay the SQLite chain on
Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReleaseSignoff

revision: str = "0033_pi_238_release_signoffs"
down_revision: str | None = "0032_pi_237_release_change_sets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if ReleaseSignoff.__tablename__ not in _tables():
        ReleaseSignoff.__table__.create(bind)


def downgrade() -> None:
    if ReleaseSignoff.__tablename__ in _tables():
        ReleaseSignoff.__table__.drop(op.get_bind())
