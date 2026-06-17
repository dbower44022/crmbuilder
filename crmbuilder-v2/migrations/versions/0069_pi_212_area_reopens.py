"""PI-212 (PRJ-034) — area_reopens table (in-lane frozen-area reopen).

Creates the ``area_reopens`` table (DEC-508) from the ORM ``__table__`` with
``checkfirst`` (idempotent on the create_all-then-upgrade-head test path). Outside
the refs / change_log discipline, so no CHECK rebuilds. Composite FK references
``releases`` (created in 0063). SQLite head 0068 -> 0069; companion PG delta
``migrations/pg/versions/0026_pi_212_area_reopens.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import AreaReopen

revision: str = "0069_pi_212_area_reopens"
down_revision: str | None = "0068_pi_211_release_corrects_release"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    AreaReopen.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if AreaReopen.__tablename__ in _tables():
        AreaReopen.__table__.drop(op.get_bind())
