"""PI-407 (REQ-486 / REQ-487, PG chain) — data-bearing classification and
active subsets.

Companion to the SQLite-chain ``0136``. Adds ``fields.field_data_bearing``
(NOT NULL, ``false`` server default, boolean-domain CHECK — mirrors 0079) and
``system_settings.system_setting_active_subset_field`` (nullable, indexed).
Inspector-guarded on every column, CHECK and index.

PG chain head 0092 -> 0093.

NOTE (live application): applied to the live Postgres store through
``crmbuilder-v2-bootstrap-db``, verified on a copy first, and performed by Doug
(GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0093_pi_407_active_subset"
down_revision: str | None = "0092_pi_413_workflow_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FIELD_COL = "field_data_bearing"
_FIELD_CHECK = "ck_field_data_bearing_boolean"
_SETTING_COL = "system_setting_active_subset_field"
_SETTING_INDEX = "ix_system_settings_active_subset_field"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    field_cols = _cols("fields")
    if field_cols:
        if _FIELD_COL not in field_cols:
            op.add_column(
                "fields",
                sa.Column(
                    _FIELD_COL,
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.text("false"),
                ),
            )
        if _FIELD_CHECK not in _checks("fields"):
            op.create_check_constraint(
                _FIELD_CHECK, "fields", _BooleanDomainCheck(_FIELD_COL)
            )
    setting_cols = _cols("system_settings")
    if setting_cols:
        if _SETTING_COL not in setting_cols:
            op.add_column(
                "system_settings",
                sa.Column(_SETTING_COL, sa.String(32), nullable=True),
            )
        if _SETTING_INDEX not in _indexes("system_settings"):
            op.create_index(_SETTING_INDEX, "system_settings", [_SETTING_COL])


def downgrade() -> None:
    if _cols("system_settings"):
        if _SETTING_INDEX in _indexes("system_settings"):
            op.drop_index(_SETTING_INDEX, table_name="system_settings")
        if _SETTING_COL in _cols("system_settings"):
            op.drop_column("system_settings", _SETTING_COL)
    if _cols("fields"):
        if _FIELD_CHECK in _checks("fields"):
            op.drop_constraint(_FIELD_CHECK, "fields", type_="check")
        if _FIELD_COL in _cols("fields"):
            op.drop_column("fields", _FIELD_COL)
