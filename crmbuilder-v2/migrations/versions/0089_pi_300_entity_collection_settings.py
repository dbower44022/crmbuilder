"""PI-300 (REQ-340) — entities collection-search settings.

Adds the remaining three neutral collection-search columns + the full-text-search
boolean-domain CHECK: ``entity_text_filter_fields`` (JSON list of quick-search
fields), ``entity_full_text_search`` (NOT NULL, ``0`` server default so existing
rows land at False), and ``entity_full_text_search_min_length`` (Integer NULL).
Together with the pre-existing ``entity_default_sort_field``/``_direction`` these
complete the five EspoCRM collection settings (orderBy/order/textFilterFields/
fullTextSearch/fullTextSearchMinLength). Column/CHECK adds go through
``batch_alter_table`` and are inspector-guarded so the migration is idempotent on a
create_all-materialised DB (the test path) and safe mid-chain. SQLite head 0088 ->
0089; companion PG delta ``migrations/pg/versions/0046_pi_300_entity_collection_settings.py``.
Mirrors 0084.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import JSONColumn, _BooleanDomainCheck

revision: str = "0089_pi_300_entity_collection_settings"
down_revision: str | None = "0088_pi_304_task_transitions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEXT_FILTER = "entity_text_filter_fields"
_FTS = "entity_full_text_search"
_FTS_MIN = "entity_full_text_search_min_length"
_CHECK = "ck_entity_full_text_search_boolean"


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    if "entities" not in _tables():
        return
    have_cols = _cols("entities")
    have_checks = _checks("entities")
    with op.batch_alter_table("entities") as batch:
        if _TEXT_FILTER not in have_cols:
            batch.add_column(sa.Column(_TEXT_FILTER, JSONColumn, nullable=True))
        if _FTS not in have_cols:
            batch.add_column(
                sa.Column(_FTS, sa.Boolean(), nullable=False, server_default="0")
            )
        if _FTS_MIN not in have_cols:
            batch.add_column(sa.Column(_FTS_MIN, sa.Integer(), nullable=True))
        if _CHECK not in have_checks:
            batch.create_check_constraint(_CHECK, _BooleanDomainCheck(_FTS))


def downgrade() -> None:
    if "entities" not in _tables():
        return
    have_cols = _cols("entities")
    with op.batch_alter_table("entities") as batch:
        if _CHECK in _checks("entities"):
            batch.drop_constraint(_CHECK, type_="check")
        if _FTS_MIN in have_cols:
            batch.drop_column(_FTS_MIN)
        if _FTS in have_cols:
            batch.drop_column(_FTS)
        if _TEXT_FILTER in have_cols:
            batch.drop_column(_TEXT_FILTER)
