"""PI-414 — the field vocabulary's subtractive half (REQ-508 / REQ-514).

The additive migration (0111) introduced the four qualifying properties and
promised this one: two legacy ways of saying things the new properties now say
better are removed, completing the separations the requirements describe.

* ``multiline`` leaves ``FIELD_FORMATS``. It says how a field is *shown*, not
  what sort of value it holds, so it belongs to ``FIELD_DISPLAYS`` (REQ-508 /
  DEC-933) — where it already sits. Until now it lived in both lists, and the
  value-vs-display separation stayed blurred by exactly one word.
* ``field_externally_populated`` is dropped. ``field_supplied_by`` replaces it
  (REQ-514 / DEC-939): the flag could say only that some outside system filled
  a field, never that the CRM numbered it itself, and keeping both left two
  competing ways to state one fact.

**This migration converts data.**

* A field carrying ``field_format = 'multiline'`` has the format cleared and —
  when it declares no display of its own — gains ``field_display =
  'multiline'``. A field that already declares a display keeps it; the retired
  format token is dropped either way.
* A field flagged externally populated backfills ``field_supplied_by =
  'another_system'`` when it declares no supplier of its own, then the column
  and its boolean CHECK go.

``FIELD_VOCABULARY_VERSION`` bumps to 2 in the same commit (REQ-504's mandate:
a stamp that lags its vocabulary asserts a false provenance).

Both conversions run *before* the subtraction they precede, mirroring 0112:
data first, then the schema stops admitting the old spelling.

SQLite chain head 0129 -> 0130. Companion PG-chain delta:
``migrations/pg/versions/0087_pi_414_field_vocabulary_subtractive.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import _BooleanDomainCheck

revision: str = "0130_pi_414_field_vocabulary_subtractive"
down_revision: str | None = "0129_pi_444_instance_feature_selection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COL = "field_externally_populated"
_CHECK = "ck_field_externally_populated_boolean"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    if "fields" not in _tables():  # absent when the chain is entered mid-stream
        return
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
        have_checks = _checks("fields")
        with op.batch_alter_table("fields") as batch:
            if _CHECK in have_checks:
                batch.drop_constraint(_CHECK, type_="check")
            batch.drop_column(_COL)


def downgrade() -> None:
    if "fields" not in _tables():
        return
    if _COL not in _cols("fields"):
        with op.batch_alter_table("fields") as batch:
            batch.add_column(
                sa.Column(_COL, sa.Boolean(), nullable=False, server_default="0")
            )
            batch.create_check_constraint(_CHECK, _BooleanDomainCheck(_COL))
        op.execute(
            sa.text(
                f"UPDATE fields SET {_COL} = 1 "
                "WHERE field_supplied_by = 'another_system'"
            )
        )
    # The display token stays — a multiline display is valid before and after.
    # Restoring the retired ``multiline`` format spelling would re-blur the
    # value-vs-display separation, so the downgrade deliberately leaves
    # formats as they are.
