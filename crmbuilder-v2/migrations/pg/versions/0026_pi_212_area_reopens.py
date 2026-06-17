"""PI-212 (PG chain) — area_reopens table.

Companion to the SQLite-chain ``0069``. Creates the ``area_reopens`` table
(DEC-508) on Postgres deployments materialised from an earlier baseline. The PG
baseline is ``create_all`` from the live models, so a fresh PG DB already carries
it — the create is inspector-guarded. Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import AreaReopen

revision: str = "0026_pi_212_area_reopens"
down_revision: str | None = "0025_pi_211_release_corrects_release"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if AreaReopen.__tablename__ not in _tables():
        AreaReopen.__table__.create(bind)


def downgrade() -> None:
    if AreaReopen.__tablename__ in _tables():
        AreaReopen.__table__.drop(op.get_bind())
