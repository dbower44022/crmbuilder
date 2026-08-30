"""PI-422 (REQ-122 audit half / DEC-947) — entity formula scripts captured verbatim.

One nullable JSON column on ``entities``: ``entity_formula_scripts``
(``{hook: script}``), capture-only per DEC-420. NULL = no formula, the correct
value for every existing row. Additive; inspector-guarded; mirrors 0046.

PG chain head 0075 -> 0076. Companion SQLite-chain delta:
``migrations/versions/0119_pi_422_entity_formula_scripts.py``.

NOTE (live application): applied to the live Postgres store through
``crmbuilder-v2-bootstrap-db``, verified on a copy first, and performed by Doug
(GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import JSONColumn

revision: str = "0076_pi_422_entity_formula_scripts"
down_revision: str | None = "0075_pi_424_entity_options"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COL = "entity_formula_scripts"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    have = _cols("entities")
    if have and _COL not in have:
        op.add_column("entities", sa.Column(_COL, JSONColumn, nullable=True))


def downgrade() -> None:
    if _COL in _cols("entities"):
        op.drop_column("entities", _COL)
