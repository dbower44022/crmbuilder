"""PI-424 (REQ-346 audit half) — entity display + behaviour options and base type.

Adds eight ``entities`` columns: four nullable strings (``entity_base_type``,
``entity_icon``, ``entity_color``, ``entity_status_field``) and four NOT NULL
toggles with a ``false`` server default and boolean-domain CHECKs
(``entity_kanban_view``, ``entity_count_disabled``,
``entity_optimistic_concurrency``, ``entity_multiple_assigned_users``). Existing
rows land at NULL / false, which reads as "platform default" — the same rule the
audit applies when an instance carries no value, so no existing row reads as
drift. Inspector-guarded; mirrors 0046.

PG chain head 0074 -> 0075. Companion SQLite-chain delta:
``migrations/versions/0118_pi_424_entity_options.py``.

NOTE (live application): applied to the live Postgres store through
``crmbuilder-v2-bootstrap-db``, verified on a copy first, and performed by Doug
(GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0075_pi_424_entity_options"
down_revision: str | None = "0074_pi_423_layout_types"
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


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    have_cols = _cols("entities")
    if not have_cols:
        return
    have_checks = _checks("entities")
    for col in _STR_COLS:
        if col not in have_cols:
            op.add_column("entities", sa.Column(col, sa.Text(), nullable=True))
    for col in _BOOL_COLS:
        if col not in have_cols:
            op.add_column(
                "entities",
                sa.Column(
                    col, sa.Boolean(), nullable=False, server_default=sa.text("false")
                ),
            )
        if _check_name(col) not in have_checks:
            op.create_check_constraint(_check_name(col), "entities", _BooleanDomainCheck(col))


def downgrade() -> None:
    have_cols = _cols("entities")
    if not have_cols:
        return
    have_checks = _checks("entities")
    for col in _BOOL_COLS:
        if _check_name(col) in have_checks:
            op.drop_constraint(_check_name(col), "entities", type_="check")
    for col in _BOOL_COLS + _STR_COLS:
        if col in have_cols:
            op.drop_column("entities", col)
