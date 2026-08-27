"""PI-414 — retire the multi-choice field kind (REQ-512 / DEC-937).

The design had two words for a choice field, one for a single choice and one for
several, differing only in how many values were allowed. Multiplicity was
therefore baked into a kind rather than stated, which is why it was unavailable
to every other kind — several attachments and several web addresses had nowhere
to go. DEC-937 made it a property any kind may state, and this removes the word
it replaces.

**This migration converts data.** Every field carrying the retired kind becomes a
choice that holds several, with its values declared fixed:

* ``field_type``   ``multi_enum`` -> ``enum``
* ``field_holds``  -> ``several``
* ``field_values`` -> ``fixed``

21 rows across the whole store, all in the CBM engagement (ENG-002); ENG-001's
343 fields carry none. Nineteen have option sets that convert cleanly. The other
two are the deferred-options fields, which become a fixed list declaring no
options — drift under DEC-940, which is the correct reading of a field nobody has
finished describing, not a fault of this conversion.

**Order matters.** The conversion runs *before* the CHECK narrows. Reversing them
would leave the narrowed constraint rejecting rows the old one admitted, and the
migration would fail against any real database.

Nothing produces the retired kind any longer: the audit reads a multi-select as a
choice holding several, the emitter builds one from that, and the source-system
translation layer was brought up to the vocabulary first (DEC-942) precisely so
this removal could complete.

SQLite chain head 0111 -> 0112. Companion PG-chain delta:
``migrations/pg/versions/0069_pi_414_retire_multi_choice_kind.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this SQLite chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import FIELD_TYPES, _check_in

revision: str = "0112_pi_414_retire_multi_choice_kind"
down_revision: str | None = "0111_pi_414_field_vocabulary_additive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RETIRED = "multi_enum"
_REPLACEMENT = "enum"

#: ``FIELD_TYPES`` is the post-change set, so the pre-change set is it plus the
#: retired kind — the mirror of how migration 0103 derived both CHECKs from one
#: source when it *added* a kind.
_FIELD_TYPES_NEW = FIELD_TYPES
_FIELD_TYPES_OLD = FIELD_TYPES | {_RETIRED}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_field_type_check(field_types: frozenset[str] | set[str]) -> None:
    if "fields" not in _tables():  # absent when the chain is entered mid-stream
        return
    with op.batch_alter_table("fields") as batch:
        batch.drop_constraint("ck_field_type", type_="check")
        batch.create_check_constraint(
            "ck_field_type", _check_in("field_type", frozenset(field_types))
        )


def upgrade() -> None:
    if "fields" not in _tables():
        return
    # Convert first; the narrowed CHECK must not meet a row it forbids.
    op.execute(
        sa.text(
            "UPDATE fields "
            "SET field_type = :new, field_holds = 'several', field_values = 'fixed' "
            "WHERE field_type = :old"
        ).bindparams(new=_REPLACEMENT, old=_RETIRED)
    )
    _rebuild_field_type_check(_FIELD_TYPES_NEW)


def downgrade() -> None:
    if "fields" not in _tables():
        return
    # Widen the CHECK before restoring rows to the retired kind, for the same
    # reason the upgrade converts before narrowing.
    _rebuild_field_type_check(_FIELD_TYPES_OLD)
    # Only fields that hold several are restored — a single choice was never the
    # retired kind, and this reversal must not invent one.
    op.execute(
        sa.text(
            "UPDATE fields "
            "SET field_type = :old, field_holds = NULL, field_values = NULL "
            "WHERE field_type = :new AND field_holds = 'several'"
        ).bindparams(new=_REPLACEMENT, old=_RETIRED)
    )
