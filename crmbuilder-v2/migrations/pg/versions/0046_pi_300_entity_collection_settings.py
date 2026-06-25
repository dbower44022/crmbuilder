"""PI-300 (REQ-340, PG chain) — entities collection-search settings.

Companion to the SQLite-chain ``0089``. Adds the remaining three neutral
collection-search columns (``entity_text_filter_fields`` JSONB,
``entity_full_text_search`` NOT NULL bool, ``entity_full_text_search_min_length``
Integer) + the full-text-search boolean-domain CHECK on Postgres deployments
materialised from an earlier baseline. The PG baseline is ``create_all`` from the
live models, so a fresh PG DB already carries them — the adds are inspector-guarded.
``entity_full_text_search`` is NOT NULL with a ``false`` server default. The CHECK
uses the same ``_BooleanDomainCheck`` construct as the model so it renders
identically to create_all. Chains after ``0045_pi_304_task_transitions``. Never
replay the SQLite chain on Postgres.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import JSONColumn, _BooleanDomainCheck

revision: str = "0046_pi_300_entity_collection_settings"
down_revision: str | None = "0045_pi_304_task_transitions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TEXT_FILTER = "entity_text_filter_fields"
_FTS = "entity_full_text_search"
_FTS_MIN = "entity_full_text_search_min_length"
_CHECK = "ck_entity_full_text_search_boolean"


def _cols(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    if table not in insp.get_table_names():
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def upgrade() -> None:
    have_cols = _cols("entities")
    if _TEXT_FILTER not in have_cols:
        op.add_column("entities", sa.Column(_TEXT_FILTER, JSONColumn, nullable=True))
    if _FTS not in have_cols:
        op.add_column(
            "entities",
            sa.Column(
                _FTS, sa.Boolean(), nullable=False, server_default=sa.text("false")
            ),
        )
    if _FTS_MIN not in have_cols:
        op.add_column("entities", sa.Column(_FTS_MIN, sa.Integer(), nullable=True))
    if _CHECK not in _checks("entities"):
        op.create_check_constraint(_CHECK, "entities", _BooleanDomainCheck(_FTS))


def downgrade() -> None:
    if _CHECK in _checks("entities"):
        op.drop_constraint(_CHECK, "entities", type_="check")
    have_cols = _cols("entities")
    if _FTS_MIN in have_cols:
        op.drop_column("entities", _FTS_MIN)
    if _FTS in have_cols:
        op.drop_column("entities", _FTS)
    if _TEXT_FILTER in have_cols:
        op.drop_column("entities", _TEXT_FILTER)
