"""PI-425 (REQ-523) — built-in fields are audited; ``fields.field_built_in``.

NOT NULL boolean with a ``false`` server default and a boolean-domain CHECK;
every existing row is correctly "not built-in". Inspector-guarded; mirrors 0046.

PG chain head 0078 -> 0079. Companion SQLite-chain delta:
``migrations/versions/0122_pi_425_field_built_in.py``.

NOTE (live application): applied to the live Postgres store through
``crmbuilder-v2-bootstrap-db``, verified on a copy first, and performed by Doug
(GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0079_pi_425_field_built_in"
down_revision: str | None = "0078_pi_421_rule_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COL = "field_built_in"
_CHECK = "ck_field_built_in_boolean"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    have = _cols("fields")
    if not have:
        return
    if _COL not in have:
        op.add_column(
            "fields",
            sa.Column(_COL, sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if _CHECK not in _checks("fields"):
        op.create_check_constraint(_CHECK, "fields", _BooleanDomainCheck(_COL))


def downgrade() -> None:
    if not _cols("fields"):
        return
    if _CHECK in _checks("fields"):
        op.drop_constraint(_CHECK, "fields", type_="check")
    if _COL in _cols("fields"):
        op.drop_column("fields", _COL)
