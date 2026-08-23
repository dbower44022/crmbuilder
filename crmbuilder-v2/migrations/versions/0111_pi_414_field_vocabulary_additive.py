"""PI-414 — the expressive field vocabulary, additive half (REQ-501 and children).

The design's field vocabulary described a field more coarsely than the CRMs it
describes: 9 of EspoCRM's 46 field types survived a round trip out and back, and
30 of roughly 46 distinctions the three surveyed CRMs make had no representation
at all. DEC-932 through DEC-940 settled what the vocabulary must carry. This is
the half of the schema change that only adds.

**Four columns**, all nullable, mirroring ``field_format``'s intrinsic-attribute
precedent from PI-182 — validated against their vocabulary at the access layer,
not by a database CHECK (only ``field_type`` and ``field_status`` carry CHECKs on
this table):

* ``field_display``     — how a field is shown, as distinct from what its value
  is (REQ-508 / DEC-933). The two were one property, which is why nothing stopped
  a field being declared both an email address and a tick-list.
* ``field_values``      — how constrained the permitted values are: fixed, open
  or suggested (REQ-510 / DEC-935).
* ``field_holds``       — one value or several (REQ-512 / DEC-937).
* ``field_supplied_by`` — a person, this CRM, or another system (REQ-514 /
  DEC-939).

**Six kinds** join ``FIELD_TYPES``, so the ``field_type`` CHECK is rebuilt:
``postal_address``, ``person_name``, ``place`` (values made of several fixed
parts, described as one field — DEC-934), and ``file``, ``time``,
``structured_data`` (kinds the vocabulary simply lacked — DEC-936).

New ``FIELD_FORMATS`` values (``image``, ``duration``, ``secret``, ``colour``,
``time_optional``) need no migration: that column has never carried a CHECK.

**Nothing here can invalidate an existing row.** The columns are nullable and the
rebuilt CHECK is a strict superset of the old one. The subtractive half — retiring
``multi_enum`` after converting the 21 design fields still using it, dropping
``field_externally_populated`` in favour of ``field_supplied_by``, and trimming
``FIELD_FORMATS`` — is deliberately a separate migration, so the half that
converts records can be read and rolled back on its own.

SQLite chain head 0110 -> 0111. Companion PG-chain delta:
``migrations/pg/versions/0068_pi_414_field_vocabulary_additive.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import FIELD_TYPES, _check_in

revision: str = "0111_pi_414_field_vocabulary_additive"
down_revision: str | None = "0110_pi_402_secret_values"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: The kinds this migration admits. ``FIELD_TYPES`` is the post-change set, so
#: the pre-change set is it minus these — the same shape migration 0103 used for
#: ``foreign``, which keeps the two CHECKs derivable from one source.
_NEW_TYPES: frozenset[str] = frozenset(
    {"postal_address", "person_name", "place", "file", "time", "structured_data"}
)
_FIELD_TYPES_NEW = FIELD_TYPES
_FIELD_TYPES_OLD = FIELD_TYPES - _NEW_TYPES

#: Nullable Text, like every other intrinsic attribute on this table.
_NEW_COLUMNS: tuple[str, ...] = (
    "field_display",
    "field_values",
    "field_holds",
    "field_supplied_by",
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns() -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("fields")}


def _rebuild_field_type_check(field_types: frozenset[str]) -> None:
    if "fields" not in _tables():  # absent when the chain is entered mid-stream
        return
    with op.batch_alter_table("fields") as batch:
        batch.drop_constraint("ck_field_type", type_="check")
        batch.create_check_constraint(
            "ck_field_type", _check_in("field_type", field_types)
        )


def upgrade() -> None:
    if "fields" not in _tables():
        return
    existing = _columns()
    for column in _NEW_COLUMNS:
        # Idempotent against a create_all-built database that already carries the
        # model's columns and is then walked forward (the PI-308 bootstrap path,
        # LSN-050): adding a column that is already there would abort the chain.
        if column not in existing:
            op.add_column("fields", sa.Column(column, sa.Text(), nullable=True))
    _rebuild_field_type_check(_FIELD_TYPES_NEW)


def downgrade() -> None:
    if "fields" not in _tables():
        return
    # Drop rows the widened CHECK newly admitted before restoring it, so the
    # narrower constraint cannot fail against data it never permitted.
    for kind in sorted(_NEW_TYPES):
        op.execute(sa.text("DELETE FROM fields WHERE field_type = :k").bindparams(k=kind))
    _rebuild_field_type_check(_FIELD_TYPES_OLD)
    existing = _columns()
    for column in _NEW_COLUMNS:
        if column in existing:
            op.drop_column("fields", column)
