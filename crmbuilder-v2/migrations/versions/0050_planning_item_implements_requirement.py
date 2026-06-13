"""Requirements-provenance Phase 3 — planning_item_implements_requirement kind.

Adds the planning_item -> requirement edge kind to ``ck_ref_relationship`` so a
planning item can trace up to the requirement it realizes (the "planned" stage
of the spine). Backs the no-orphan-capability coverage report. No columns, no
new entity types — a single refs-CHECK widening, vocab-derived (a superset, so
no existing row is invalidated) and guarded with ``_tables()`` for the
mid-stream / create_all-then-upgrade-head paths.

SQLite chain head 0049 -> 0050. Companion PG-chain delta:
``migrations/pg/versions/0012_planning_item_implements_requirement.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import REFERENCE_RELATIONSHIPS, _check_in

revision: str = "0050_planning_item_implements_requirement"
down_revision: str | None = "0049_requirements_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KINDS = frozenset({"planning_item_implements_requirement"})
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    if "refs" not in _tables():
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def upgrade() -> None:
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    if "refs" in _tables():
        op.execute(
            "DELETE FROM refs WHERE relationship_kind = "
            "'planning_item_implements_requirement'"
        )
    _rebuild_relationship_check(_KINDS_OLD)
