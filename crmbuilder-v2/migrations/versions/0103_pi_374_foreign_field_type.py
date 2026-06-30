"""PI-374 (REQ-435) — add ``foreign`` to FIELD_TYPES; rebuild the field_type CHECK.

A field that mirrors a scalar from a linked record (EspoCRM ``foreign``) had no
engine-neutral kind, so the audit collapsed it to ``derived`` and surfaced it as
text (CBM ``MentorProfile.postalCode``). Declaring ``foreign`` in
``vocab.FIELD_TYPES`` gives it a distinct kind; the audit now maps EspoCRM
``foreign`` -> neutral ``foreign`` instead of ``derived``.

Only the ``fields`` ``field_type`` CHECK moves — it derives from ``FIELD_TYPES``.
No ``change_log`` entity-type or ``refs`` relationship-kind change (``foreign`` is
a field-type value, not an entity type or relationship kind). The rebuilt CHECK is
a superset, so no existing row is invalidated.

SQLite chain head 0102 -> 0103. Companion PG-chain delta:
``migrations/pg/versions/0060_pi_374_foreign_field_type.py``.

NOTE (live application): the live store (``data/v2-unified.db``) is
create_all-managed and is NOT walked through this SQLite chain. This migration is
the canonical record of the delta; the live application is performed via
``crmbuilder-v2-bootstrap-db`` (and verified on a copy first) per the standard
runbook.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import FIELD_TYPES, _check_in

revision: str = "0103_pi_374_foreign_field_type"
down_revision: str | None = "0102_pi_365_widen_overflow_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "foreign"
_FIELD_TYPES_NEW = FIELD_TYPES
_FIELD_TYPES_OLD = FIELD_TYPES - {_NEW_TYPE}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_field_type_check(field_types: frozenset[str]) -> None:
    if "fields" not in _tables():  # absent when the chain is entered mid-stream
        return
    with op.batch_alter_table("fields") as batch:
        batch.drop_constraint("ck_field_type", type_="check")
        batch.create_check_constraint(
            "ck_field_type", _check_in("field_type", field_types)
        )


def upgrade() -> None:
    _rebuild_field_type_check(_FIELD_TYPES_NEW)


def downgrade() -> None:
    # Drop any rows the widened CHECK newly admitted, then restore the old CHECK.
    if "fields" in _tables():
        op.execute("DELETE FROM fields WHERE field_type = 'foreign'")
    _rebuild_field_type_check(_FIELD_TYPES_OLD)
