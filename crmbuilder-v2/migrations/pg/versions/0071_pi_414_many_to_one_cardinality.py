"""PI-414 (REQ-506 / DEC-932, PG chain) — admit ``many_to_one`` as a cardinality.

Every other many-to-one link is recorded as ``one_to_many`` from the "one"
(owning) side, which is why the neutral set did without the word — the reader
processes the ``hasMany`` side and skips the reciprocal ``belongsTo``.

A link whose target may be any of several kinds breaks that convention. Its
"one" side is polymorphic, so there is no single owning entity to record from,
and recording one relationship per permitted kind is exactly the duplication
DEC-932 exists to remove. The polymorphic link is therefore recorded from the
child side — ``Call.parent``, ``Meeting.parent`` — and needs a word that says
so. ``one_to_many`` there would assert that one child has many parents, which is
false, and a stored falsehood is what this vocabulary work exists to remove.

New terminology, approved by Doug on 2026-08-29 under GVR-232.

Widening only: the rebuilt CHECK is a strict superset of the old one, so no
existing row can be invalidated. The downgrade narrows, and converts any
``many_to_one`` row back to ``one_to_many`` first — reversed, the narrowed
constraint would meet rows it forbids and the migration would fail against any
database that had used the new word.

PG chain head 0070 -> 0071. Companion SQLite-chain delta:
``migrations/versions/0114_pi_414_many_to_one_cardinality.py``.

NOTE (live application): the live store is create_all-managed and is NOT walked
through this PG chain. This migration is the canonical record of the delta;
the live application goes through ``crmbuilder-v2-bootstrap-db``, verified on a
copy first, and is performed by Doug (GVR-240) — never from here.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import ASSOCIATION_CARDINALITIES, _check_in

revision: str = "0071_pi_414_many_to_one_cardinality"
down_revision: str | None = "0070_pi_414_relationship_link_properties"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ADDED = "many_to_one"
_FALLBACK = "one_to_many"
_NEW = ASSOCIATION_CARDINALITIES
_OLD = ASSOCIATION_CARDINALITIES - {_ADDED}


def _has_table(table: str) -> bool:
    return table in set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_check(values: frozenset[str] | set[str]) -> None:
    # Batch mode, because SQLite cannot ALTER a constraint in place and needs
    # the copy-and-move strategy; on Postgres this issues a plain ALTER. Guarded
    # so the migration is a clean no-op when the chain is entered mid-stream and
    # the table does not exist yet.
    if not _has_table("associations"):
        return
    with op.batch_alter_table("associations") as batch:
        batch.drop_constraint("ck_association_cardinality", type_="check")
        batch.create_check_constraint(
            "ck_association_cardinality",
            _check_in("association_cardinality", frozenset(values)),
        )


def upgrade() -> None:
    _rebuild_check(_NEW)


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE associations SET association_cardinality = :fallback "
            "WHERE association_cardinality = :added"
        ).bindparams(fallback=_FALLBACK, added=_ADDED)
    )
    _rebuild_check(_OLD)
