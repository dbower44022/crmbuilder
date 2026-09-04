"""PI-407 (REQ-486 / REQ-487) — data-bearing classification and active subsets.

Two columns, one on each side of the construct:

* ``fields.field_data_bearing`` — the classification that no application
  logic, in the CRM or in any consumer, branches on the field's value. NOT
  NULL with a ``0`` server default: an unclassified field is ineligible for a
  per-instance active subset until someone rules it data-bearing, so "not
  classified" and "false" must read the same way. Boolean-domain CHECK as for
  the other field flags (mirrors 0122).
* ``system_settings.system_setting_active_subset_field`` — when set, the
  governed setting names the active subset of that enum field's complete
  option list and its per-instance value is the list of active option values.
  Nullable; an ordinary setting names no field. Indexed so "which settings
  narrow this field" is a lookup, not a scan.

The complete option list needs no schema change: ``field_options`` already
carries it and continues to deploy identically to every instance.

Inspector-guarded on both columns and the CHECK so the chain is safe to enter
mid-stream and safe on a create_all-built database (LSN-050 / LSN-064).

SQLite chain head 0135 -> 0136. Companion PG-chain delta:
``migrations/pg/versions/0093_pi_407_active_subset.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0136_pi_407_active_subset"
down_revision: str | None = "0135_pi_413_workflow_membership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FIELD_COL = "field_data_bearing"
_FIELD_CHECK = "ck_field_data_bearing_boolean"
_SETTING_COL = "system_setting_active_subset_field"
_SETTING_INDEX = "ix_system_settings_active_subset_field"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    tables = _tables()
    if "fields" in tables:
        have_cols = _cols("fields")
        have_checks = _checks("fields")
        with op.batch_alter_table("fields") as batch:
            if _FIELD_COL not in have_cols:
                batch.add_column(
                    sa.Column(
                        _FIELD_COL, sa.Boolean(), nullable=False, server_default="0"
                    )
                )
            if _FIELD_CHECK not in have_checks:
                batch.create_check_constraint(
                    _FIELD_CHECK, _BooleanDomainCheck(_FIELD_COL)
                )
    if "system_settings" in tables:
        if _SETTING_COL not in _cols("system_settings"):
            with op.batch_alter_table("system_settings") as batch:
                batch.add_column(
                    sa.Column(_SETTING_COL, sa.String(32), nullable=True)
                )
        if _SETTING_INDEX not in _indexes("system_settings"):
            op.create_index(_SETTING_INDEX, "system_settings", [_SETTING_COL])


def downgrade() -> None:
    tables = _tables()
    if "system_settings" in tables:
        if _SETTING_INDEX in _indexes("system_settings"):
            op.drop_index(_SETTING_INDEX, table_name="system_settings")
        if _SETTING_COL in _cols("system_settings"):
            with op.batch_alter_table("system_settings") as batch:
                batch.drop_column(_SETTING_COL)
    if "fields" in tables:
        with op.batch_alter_table("fields") as batch:
            if _FIELD_CHECK in _checks("fields"):
                batch.drop_constraint(_FIELD_CHECK, type_="check")
            if _FIELD_COL in _cols("fields"):
                batch.drop_column(_FIELD_COL)
