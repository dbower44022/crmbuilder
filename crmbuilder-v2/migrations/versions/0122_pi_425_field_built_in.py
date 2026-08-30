"""PI-425 (REQ-523) — built-in fields are audited; ``fields.field_built_in``.

The audit now records a built-in entity's platform-shipped fields once the
entity is in the design, so a change an administrator makes to a built-in
field on one instance surfaces as drift. The flag marks such a field so the
publish path never creates it (it already exists on every target) and the
reconcile surface offers it for capture only. NOT NULL with a ``0`` server
default: every existing row is a field the design authored or the audit
discovered as custom, which is correctly "not built-in". Boolean-domain CHECK
as for the other field flags; inspector-guarded; mirrors 0089.

SQLite chain head 0121 -> 0122. Companion PG-chain delta:
``migrations/pg/versions/0079_pi_425_field_built_in.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0122_pi_425_field_built_in"
down_revision: str | None = "0121_pi_421_rule_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COL = "field_built_in"
_CHECK = "ck_field_built_in_boolean"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    if "fields" not in _tables():
        return
    have_cols = _cols("fields")
    have_checks = _checks("fields")
    with op.batch_alter_table("fields") as batch:
        if _COL not in have_cols:
            batch.add_column(
                sa.Column(_COL, sa.Boolean(), nullable=False, server_default="0")
            )
        if _CHECK not in have_checks:
            batch.create_check_constraint(_CHECK, _BooleanDomainCheck(_COL))


def downgrade() -> None:
    if "fields" not in _tables():
        return
    with op.batch_alter_table("fields") as batch:
        if _CHECK in _checks("fields"):
            batch.drop_constraint(_CHECK, type_="check")
        if _COL in _cols("fields"):
            batch.drop_column(_COL)
