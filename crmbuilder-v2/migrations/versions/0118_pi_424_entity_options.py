"""PI-424 (REQ-346 audit half) — entity display + behaviour options and base type.

V2 captured an entity's collection-search settings but none of the display and
behaviour options V1 audits into the ``settings:`` block, so a switched-on
kanban view or multi-assignee setting was invisible to conformance. Adds eight
``entities`` columns: four nullable strings (``entity_base_type`` — the platform
base type the scope declares — ``entity_icon``, ``entity_color``,
``entity_status_field``) and four NOT NULL toggles with a ``0`` server default
and boolean-domain CHECKs (``entity_kanban_view``, ``entity_count_disabled``,
``entity_optimistic_concurrency``, ``entity_multiple_assigned_users``). Existing
rows land at NULL / False, which reads as "platform default" — the same rule the
audit applies when an instance carries no value, so no existing row reads as
drift. Column/CHECK adds are inspector-guarded so the migration is idempotent on
a create_all-materialised DB. Mirrors 0089.

SQLite chain head 0117 -> 0118. Companion PG-chain delta:
``migrations/pg/versions/0075_pi_424_entity_options.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0118_pi_424_entity_options"
down_revision: str | None = "0117_pi_423_layout_types"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STR_COLS = ("entity_base_type", "entity_icon", "entity_color", "entity_status_field")
_BOOL_COLS = (
    "entity_kanban_view",
    "entity_count_disabled",
    "entity_optimistic_concurrency",
    "entity_multiple_assigned_users",
)


def _check_name(col: str) -> str:
    return f"ck_{col}_boolean"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    if "entities" not in _tables():
        return
    have_cols = _cols("entities")
    have_checks = _checks("entities")
    with op.batch_alter_table("entities") as batch:
        for col in _STR_COLS:
            if col not in have_cols:
                batch.add_column(sa.Column(col, sa.Text(), nullable=True))
        for col in _BOOL_COLS:
            if col not in have_cols:
                batch.add_column(
                    sa.Column(col, sa.Boolean(), nullable=False, server_default="0")
                )
            if _check_name(col) not in have_checks:
                batch.create_check_constraint(_check_name(col), _BooleanDomainCheck(col))


def downgrade() -> None:
    if "entities" not in _tables():
        return
    have_cols = _cols("entities")
    have_checks = _checks("entities")
    with op.batch_alter_table("entities") as batch:
        for col in _BOOL_COLS:
            if _check_name(col) in have_checks:
                batch.drop_constraint(_check_name(col), type_="check")
        for col in _BOOL_COLS + _STR_COLS:
            if col in have_cols:
                batch.drop_column(col)
