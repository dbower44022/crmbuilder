"""PI-244 (PRJ-041 / REQ-295) — area_specs table (per-area implementation + testable spec).

Creates the ``area_specs`` table from the ORM ``__table__`` with ``checkfirst``
(idempotent on the create_all-then-upgrade-head test path). The matrix back half's
append-only/versioned per-(release, area) design artifact (the implementation spec
the Developer builds to + the testable spec the Tester implements blind). Outside
the refs / change_log discipline, so no CHECK rebuilds. SQLite head 0076 -> 0077;
companion PG delta ``migrations/pg/versions/0034_pi_244_area_specs.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import AreaSpec

revision: str = "0077_pi_244_area_specs"
down_revision: str | None = "0076_pi_238_release_signoffs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    AreaSpec.__table__.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    if AreaSpec.__tablename__ in _tables():
        AreaSpec.__table__.drop(op.get_bind())
