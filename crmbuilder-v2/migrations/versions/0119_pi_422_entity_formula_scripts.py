"""PI-422 (REQ-122 audit half / DEC-947) — entity formula scripts captured verbatim.

V1's audit reads ``formula.<Entity>`` and emits the scripts verbatim as a
``formulaScript:`` block; V2 had nowhere to hold an entity-level script. Per
DEC-947 the scripts live as one nullable JSON attribute on the entity record
(``entity_formula_scripts``, ``{hook: script}``) rather than a new entity type,
because the content is capture-only (DEC-420: no platform write path) and has
no lifecycle of its own. NULL = no formula, which is the correct value for
every existing row. Additive; inspector-guarded; mirrors 0089.

SQLite chain head 0118 -> 0119. Companion PG-chain delta:
``migrations/pg/versions/0076_pi_422_entity_formula_scripts.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import JSONColumn

revision: str = "0119_pi_422_entity_formula_scripts"
down_revision: str | None = "0118_pi_424_entity_options"
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
        with op.batch_alter_table("entities") as batch:
            batch.add_column(sa.Column(_COL, JSONColumn, nullable=True))


def downgrade() -> None:
    if _COL in _cols("entities"):
        with op.batch_alter_table("entities") as batch:
            batch.drop_column(_COL)
