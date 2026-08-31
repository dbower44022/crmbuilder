"""PI-414 (PG chain) — the field vocabulary's subtractive half.

Companion to the SQLite-chain ``0130``. Removes the two legacy spellings the
PI-414 qualifying properties replaced:

* ``multiline`` leaves ``FIELD_FORMATS`` (it lives in ``FIELD_DISPLAYS``,
  REQ-508 / DEC-933) — rows carrying it as a format convert to the display.
* ``field_externally_populated`` is dropped; ``field_supplied_by``
  (REQ-514 / DEC-939) says the same thing and more. Flagged rows backfill
  ``field_supplied_by = 'another_system'`` when they declare no supplier.

Conversions run before the subtraction, mirroring 0069/0112: data first, then
the schema stops admitting the old spelling. ``FIELD_VOCABULARY_VERSION``
bumps to 2 in the same commit.

PG chain head 0086 -> 0087.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0087_pi_414_field_vocabulary_subtractive"
down_revision: str | None = "0086_pi_444_instance_feature_selection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COL = "field_externally_populated"
_CHECK = "ck_field_externally_populated_boolean"


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    # Convert first — the subtraction must not meet a row that still needs it.
    op.execute(
        sa.text(
            "UPDATE fields SET field_display = 'multiline' "
            "WHERE field_format = 'multiline' AND field_display IS NULL"
        )
    )
    op.execute(
        sa.text(
            "UPDATE fields SET field_format = NULL "
            "WHERE field_format = 'multiline'"
        )
    )
    if _COL in _cols("fields"):
        op.execute(
            sa.text(
                f"UPDATE fields SET field_supplied_by = 'another_system' "
                f"WHERE {_COL} AND field_supplied_by IS NULL"
            )
        )
        if _CHECK in _checks("fields"):
            op.drop_constraint(_CHECK, "fields", type_="check")
        op.drop_column("fields", _COL)


def downgrade() -> None:
    if _COL not in _cols("fields"):
        op.add_column(
            "fields",
            sa.Column(_COL, sa.Boolean(), nullable=False, server_default="false"),
        )
        op.create_check_constraint(_CHECK, "fields", _BooleanDomainCheck(_COL))
        op.execute(
            sa.text(
                f"UPDATE fields SET {_COL} = true "
                "WHERE field_supplied_by = 'another_system'"
            )
        )
    # The retired ``multiline`` format spelling is deliberately not restored.
