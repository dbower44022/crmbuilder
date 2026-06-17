"""PI-211 (PG chain) — admit the release_corrects_release relationship kind.

Companion to the SQLite-chain ``0068``. Rebuilds the ``refs.relationship_kind``
CHECK to admit ``release_corrects_release`` on Postgres deployments materialised
from an earlier baseline (a same-text no-op on a fresh create_all PG DB, a real
change on a pre-existing store). Never replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

from alembic import op
from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS, _check_in

revision: str = "0025_pi_211_release_corrects_release"
down_revision: str | None = "0024_pi_215_reconciliation_conflicts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KIND = "release_corrects_release"
_REL_NEW = REFERENCE_RELATIONSHIPS
_REL_OLD = REFERENCE_RELATIONSHIPS - {_NEW_KIND}


def _rebuild(rels: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", rels)
    )


def upgrade() -> None:
    _rebuild(_REL_NEW)


def downgrade() -> None:
    op.execute(
        "DELETE FROM refs WHERE relationship_kind = 'release_corrects_release'"
    )
    _rebuild(_REL_OLD)
