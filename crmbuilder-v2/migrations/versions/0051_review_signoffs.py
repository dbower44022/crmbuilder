"""Requirements-provenance Phase 6 — review_signoffs table + change_log CHECK.

Creates the append-only ``review_signoffs`` table (the recorded "reviewed, not
reviewable" attestation) and rebuilds ``ck_changelog_entity_type`` to admit the
new ``review_signoff`` entity type — the known gotcha: create_all-based tests
miss it, the live DB 500s without it (see 0046). The table create is
``checkfirst`` (idempotent on the create_all-then-upgrade-head path); the CHECK
rebuild is a vocab-derived superset, so no existing row is invalidated.
``_tables()``-guarded for mid-stream entry.

SQLite chain head 0050 -> 0051. Companion PG-chain delta:
``migrations/pg/versions/0013_review_signoffs.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import ReviewSignoff
from crmbuilder_v2.access.vocab import CHANGE_LOG_ENTITY_TYPES, _check_in

revision: str = "0051_review_signoffs"
down_revision: str | None = "0050_planning_item_implements_requirement"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_LOG_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_OLD = CHANGE_LOG_ENTITY_TYPES - {"review_signoff"}


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_changelog_check(types: frozenset[str]) -> None:
    if "change_log" not in _tables():
        return
    with op.batch_alter_table("change_log") as batch:
        batch.drop_constraint("ck_changelog_entity_type", type_="check")
        batch.create_check_constraint(
            "ck_changelog_entity_type", _check_in("entity_type", types)
        )


def upgrade() -> None:
    ReviewSignoff.__table__.create(op.get_bind(), checkfirst=True)
    _rebuild_changelog_check(_LOG_NEW)


def downgrade() -> None:
    if "change_log" in _tables():
        op.execute("DELETE FROM change_log WHERE entity_type = 'review_signoff'")
    _rebuild_changelog_check(_LOG_OLD)
    if "review_signoffs" in _tables():
        ReviewSignoff.__table__.drop(op.get_bind())
