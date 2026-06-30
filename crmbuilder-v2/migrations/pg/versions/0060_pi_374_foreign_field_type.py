"""PI-374 (PG chain) — add ``foreign`` to FIELD_TYPES; rebuild the field_type CHECK.

Companion to the SQLite-chain ``0103``. ``foreign`` is declared as an engine-neutral
field kind so a field mirroring a scalar from a linked record keeps a distinct type
instead of collapsing to ``derived``/text (REQ-435 / PI-374). Only the ``fields``
``field_type`` CHECK moves — it derives from ``FIELD_TYPES``. No ``change_log`` or
``refs`` CHECK change (``foreign`` is a field-type value). The rebuilt CHECK is a
superset, so no existing row is invalidated.

PG chain head 0059 -> 0060.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.vocab import FIELD_TYPES, _check_in

revision: str = "0060_pi_374_foreign_field_type"
down_revision: str | None = "0059_pi_365_widen_overflow_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "foreign"
_FIELD_TYPES_NEW = FIELD_TYPES
_FIELD_TYPES_OLD = FIELD_TYPES - {_NEW_TYPE}


def _rebuild_field_type_check(field_types: frozenset[str]) -> None:
    op.drop_constraint("ck_field_type", "fields", type_="check")
    op.create_check_constraint(
        "ck_field_type", "fields", _check_in("field_type", field_types)
    )


def upgrade() -> None:
    _rebuild_field_type_check(_FIELD_TYPES_NEW)


def downgrade() -> None:
    op.execute("DELETE FROM fields WHERE field_type = 'foreign'")
    _rebuild_field_type_check(_FIELD_TYPES_OLD)
