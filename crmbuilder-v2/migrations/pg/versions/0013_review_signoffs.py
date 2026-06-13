"""Requirements-provenance Phase 6 (PG chain) — review_signoffs + change_log CHECK.

Companion to SQLite-chain ``0051``. Creates the append-only ``review_signoffs``
table and rebuilds ``ck_changelog_entity_type`` to admit ``review_signoff`` on
Postgres stores materialised from an earlier baseline. The PG baseline is
``create_all`` from the live models, so a fresh PG DB already carries the table
and the vocab-derived CHECK — both ops are inspector-guarded / same-text
no-op-equivalents there; on a pre-existing store they are real changes.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReviewSignoff
from crmbuilder_v2.access.vocab import CHANGE_LOG_ENTITY_TYPES, _check_in

revision: str = "0013_review_signoffs"
down_revision: str | None = "0012_planning_item_implements_requirement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - {"review_signoff"}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_changelog_check(types: frozenset[str]) -> None:
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type", "change_log", _check_in("entity_type", types)
    )


def upgrade() -> None:
    if "review_signoffs" not in _tables():
        ReviewSignoff.__table__.create(op.get_bind())
    if "change_log" in _tables():
        _rebuild_changelog_check(_LOG_NEW)


def downgrade() -> None:
    if "change_log" in _tables():
        op.execute("DELETE FROM change_log WHERE entity_type = 'review_signoff'")
        _rebuild_changelog_check(_LOG_OLD)
    if "review_signoffs" in _tables():
        ReviewSignoff.__table__.drop(op.get_bind())
