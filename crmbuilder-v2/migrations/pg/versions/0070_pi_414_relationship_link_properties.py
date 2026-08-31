"""PI-414 (REQ-506 / REQ-507, DEC-932, PG chain) — relationships carry what the link field did.

A link between records is described once, as a relationship (DEC-932), and the
retired ``reference`` field type was carrying three things the relationship had
nowhere to hold. This adds them, so nothing is lost when the field side goes.

**Five columns**, all nullable, none of which can invalidate an existing row:

* ``association_target_kinds`` — the permitted kinds of a link whose target may
  be any of several (REQ-506). ``association_target_entity`` names exactly one
  kind and cannot say "any of these", which is why EspoCRM's ``linkParent`` —
  ``Call.parent`` and ``Meeting.parent`` in the CBM design — fell through the
  field translation table and was recorded as plain text. NULL keeps the
  ordinary single-target meaning; a list names every kind the link permits.
* ``association_source_label`` / ``association_target_label`` — how each side is
  labelled (REQ-507).
* ``association_source_required`` / ``association_target_required`` — whether
  each side is required (REQ-507).

Per side, because the two ends of one link are labelled and required
independently, and a reference field only ever described the end it sat on.
Folding one into a single pair of columns would lose the other end the moment a
link were described from both directions.

No CHECK is added. ``associations`` carries CHECKs on ``association_cardinality``
and ``association_status`` only, and these five follow ``field_format``'s
intrinsic-attribute precedent from PI-182: validated at the access layer against
their vocabulary, not by the database.

Guarded against a schema materialised from the current ORM models. The
associations table is created by 0056 via ``Association.__table__.create``,
which reads the live model — so on a walk entering the chain mid-stream the
table is born already carrying these columns and an unguarded ``add_column``
fails with a duplicate. The guard makes this migration a clean no-op there while
leaving it a real delta on a database that predates the columns.

Additive only. Retiring the ``reference`` field type and folding the 19 existing
reference field records is a separate migration, so the half that adds somewhere
to put the content can be read and rolled back without the half that moves it.

PG chain head 0069 -> 0070. Companion SQLite-chain delta:
``migrations/versions/0113_pi_414_relationship_link_properties.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this PG chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import JSONColumnNoneAsNull

revision: str = "0070_pi_414_relationship_link_properties"
down_revision: str | None = "0069_pi_414_retire_multi_choice_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: ``(name, type)`` for each added column, so upgrade and downgrade cannot drift.
_COLUMNS: list[tuple[str, object]] = [
    ("association_target_kinds", JSONColumnNoneAsNull),
    ("association_source_label", sa.String(255)),
    ("association_target_label", sa.String(255)),
    ("association_source_required", sa.Boolean()),
    ("association_target_required", sa.Boolean()),
]


def _has_table(table: str) -> bool:
    return table in set(sa.inspect(op.get_bind()).get_table_names())


def _has_column(table: str, column: str) -> bool:
    if not _has_table(table):
        return False
    return column in {
        c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)
    }


def upgrade() -> None:
    for name, type_ in _COLUMNS:
        if not _has_column("associations", name):
            op.add_column("associations", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    for name, _type in reversed(_COLUMNS):
        if _has_column("associations", name):
            op.drop_column("associations", name)
