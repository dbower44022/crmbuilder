"""Requirements-provenance Phase 3 (PG chain) — planning_item_implements_requirement.

Companion to SQLite-chain ``0050``. Widens ``ck_ref_relationship`` to admit the
new planning_item -> requirement edge kind on Postgres stores materialised from
an earlier baseline. The PG baseline is ``create_all`` from the live models, so
a fresh PG DB already carries the vocab-derived predicate — the rebuild is a
same-text no-op-equivalent there; on a pre-existing store it is a real widening.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS, _check_in

revision: str = "0012_planning_item_implements_requirement"
down_revision: str | None = "0011_requirements_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KINDS = frozenset({"planning_item_implements_requirement"})
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def upgrade() -> None:
    if "refs" in _tables():
        _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    if "refs" in _tables():
        op.execute(
            "DELETE FROM refs WHERE relationship_kind = "
            "'planning_item_implements_requirement'"
        )
        _rebuild_relationship_check(_KINDS_OLD)
