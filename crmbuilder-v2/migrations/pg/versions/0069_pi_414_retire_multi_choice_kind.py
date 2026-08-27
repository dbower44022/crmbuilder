"""PI-414 (REQ-512 / DEC-937, PG chain) — retire the multi-choice field kind.

Companion to the SQLite-chain ``0112``. Converts every field carrying the retired
kind into a choice that holds several, then narrows the ``field_type`` CHECK to
exclude it.

Why: the design had two words for a choice field differing only in how many
values were allowed, so multiplicity was baked into a kind instead of stated and
was therefore unavailable to every other kind. DEC-937 made it a property any
kind may state; this removes the word it replaces.

Conversion: ``field_type`` ``multi_enum`` -> ``enum``, ``field_holds`` ->
``several``, ``field_values`` -> ``fixed``. 21 rows across the store, all in
ENG-002.

The conversion runs before the CHECK narrows — reversed, the new constraint would
meet rows it forbids and the migration would fail against any real database. The
downgrade widens first for the same reason, and restores only fields that hold
several, so it cannot invent a retired kind where a single choice stood.

PG chain head 0068 -> 0069.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import FIELD_TYPES, _check_in

revision: str = "0069_pi_414_retire_multi_choice_kind"
down_revision: str | None = "0068_pi_414_field_vocabulary_additive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RETIRED = "multi_enum"
_REPLACEMENT = "enum"
_FIELD_TYPES_NEW = FIELD_TYPES
_FIELD_TYPES_OLD = FIELD_TYPES | {_RETIRED}


def _rebuild_field_type_check(field_types: frozenset[str] | set[str]) -> None:
    op.drop_constraint("ck_field_type", "fields", type_="check")
    op.create_check_constraint(
        "ck_field_type", "fields", _check_in("field_type", frozenset(field_types))
    )


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE fields "
            "SET field_type = :new, field_holds = 'several', field_values = 'fixed' "
            "WHERE field_type = :old"
        ).bindparams(new=_REPLACEMENT, old=_RETIRED)
    )
    _rebuild_field_type_check(_FIELD_TYPES_NEW)


def downgrade() -> None:
    _rebuild_field_type_check(_FIELD_TYPES_OLD)
    op.execute(
        sa.text(
            "UPDATE fields "
            "SET field_type = :old, field_holds = NULL, field_values = NULL "
            "WHERE field_type = :new AND field_holds = 'several'"
        ).bindparams(new=_REPLACEMENT, old=_RETIRED)
    )
