"""PI-414 (REQ-501 and children, PG chain) — expressive field vocabulary, additive half.

Companion to the SQLite-chain ``0111``. Adds the four qualifying properties the
field vocabulary gained, and widens the ``field_type`` CHECK by six kinds.

Why: the design described a field more coarsely than the CRMs it describes, so a
field read from an instance could not be rendered back as the same field — 9 of
EspoCRM's 46 field types survived the round trip. DEC-932 through DEC-940 settled
what the vocabulary must carry.

Columns (all nullable Text, validated at the access layer like ``field_format``,
per the PI-182 intrinsic precedent):

* ``field_display``     — how a field is shown (REQ-508 / DEC-933)
* ``field_values``      — fixed, open or suggested (REQ-510 / DEC-935)
* ``field_holds``       — one value or several (REQ-512 / DEC-937)
* ``field_supplied_by`` — a person, this CRM, another system (REQ-514 / DEC-939)

Kinds admitted: ``postal_address``, ``person_name``, ``place``, ``file``,
``time``, ``structured_data``.

Additive throughout: nullable columns and a CHECK that is a strict superset of
the one it replaces, so no existing row can be invalidated and nothing needs
converting. The subtractive half — retiring ``multi_enum``, dropping
``field_externally_populated``, trimming ``FIELD_FORMATS`` — is a separate
migration so the half that converts records stands on its own.

Bootstrap-safe: each column is added only when absent, which is what the
create_all + stamp-behind path (LSN-050) requires.

PG chain head 0067 -> 0068.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import FIELD_TYPES, _check_in

revision: str = "0068_pi_414_field_vocabulary_additive"
down_revision: str | None = "0067_pi_402_secret_values"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES: frozenset[str] = frozenset(
    {"postal_address", "person_name", "place", "file", "time", "structured_data"}
)
# The vocabulary AS IT STOOD AT THIS REVISION, not the live one: the next
# migration retires ``multi_enum`` (converting its rows), so the live
# ``FIELD_TYPES`` no longer admits it — but the rows still hold it when this
# CHECK is rebuilt. Deriving the CHECK from the live vocabulary made the
# "strict superset" promise above false and aborted the production upgrade
# on 39 rows (found by rehearsing the chain on a clone of the live store).
_FIELD_TYPES_NEW = FIELD_TYPES | {"multi_enum"}
_FIELD_TYPES_OLD = _FIELD_TYPES_NEW - _NEW_TYPES

_NEW_COLUMNS: tuple[str, ...] = (
    "field_display",
    "field_values",
    "field_holds",
    "field_supplied_by",
)


def _existing_columns() -> set[str]:
    """Columns already on ``fields``; empty when generating SQL offline."""
    if op.get_context().as_sql:
        return set()
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns("fields")}


def _rebuild_field_type_check(field_types: frozenset[str]) -> None:
    op.drop_constraint("ck_field_type", "fields", type_="check")
    op.create_check_constraint(
        "ck_field_type", "fields", _check_in("field_type", field_types)
    )


def upgrade() -> None:
    existing = _existing_columns()
    for column in _NEW_COLUMNS:
        if column not in existing:
            op.add_column("fields", sa.Column(column, sa.Text(), nullable=True))
    _rebuild_field_type_check(_FIELD_TYPES_NEW)


def downgrade() -> None:
    # Remove rows the widened CHECK newly admitted before narrowing it again.
    for kind in sorted(_NEW_TYPES):
        op.execute(sa.text("DELETE FROM fields WHERE field_type = :k").bindparams(k=kind))
    _rebuild_field_type_check(_FIELD_TYPES_OLD)
    existing = _existing_columns()
    for column in _NEW_COLUMNS:
        if column in existing:
            op.drop_column("fields", column)
