"""PI-244 (PG chain) — area_specs table (per-area implementation + testable spec).

Companion to the SQLite-chain ``0077``. Creates the ``area_specs`` table (the
matrix back half's append-only/versioned per-(release, area) design artifact) on
Postgres deployments materialised from an earlier baseline. The PG baseline is
``create_all`` from the live models, so a fresh PG DB already carries it — the
create is inspector-guarded. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import AreaSpec

revision: str = "0034_pi_244_area_specs"
down_revision: str | None = "0033_pi_238_release_signoffs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if AreaSpec.__tablename__ not in _tables():
        AreaSpec.__table__.create(bind)


def downgrade() -> None:
    if AreaSpec.__tablename__ in _tables():
        AreaSpec.__table__.drop(op.get_bind())
