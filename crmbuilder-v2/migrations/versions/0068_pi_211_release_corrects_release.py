"""PI-211 (PRJ-034, RW1) — admit the release_corrects_release relationship kind.

Rebuilds the ``refs.relationship_kind`` CHECK to admit ``release_corrects_release``
(the traceable "plan corrections go to a new release" edge). No table, no
entity-type change. The predicate derives from current vocab (a superset, no row
invalidated); the rebuild inspects live tables first so the chain is safe to enter
mid-stream. SQLite head 0067 -> 0068; companion PG delta
``migrations/pg/versions/0025_pi_211_release_corrects_release.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS, _check_in

revision: str = "0068_pi_211_release_corrects_release"
down_revision: str | None = "0067_pi_215_reconciliation_conflicts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KIND = "release_corrects_release"
_REL_NEW = REFERENCE_RELATIONSHIPS
_REL_OLD = REFERENCE_RELATIONSHIPS - {_NEW_KIND}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild(rels: frozenset[str]) -> None:
    if "refs" not in _tables():
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", rels)
        )


def upgrade() -> None:
    _rebuild(_REL_NEW)


def downgrade() -> None:
    if "refs" in _tables():
        op.execute(
            "DELETE FROM refs WHERE relationship_kind = 'release_corrects_release'"
        )
    _rebuild(_REL_OLD)
