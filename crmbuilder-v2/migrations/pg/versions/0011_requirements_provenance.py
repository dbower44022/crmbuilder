"""Requirements-provenance model (Phase 1, PG chain) — requirement columns + kinds.

Companion to the SQLite-chain ``0049``. Adds the three ``requirement_*``
provenance columns and their CHECKs, and rebuilds ``ck_ref_relationship`` to
admit the six provenance-model edge kinds, on Postgres deployments materialised
from an earlier baseline.

The PG baseline (``0001_pg_baseline``) is ``Base.metadata.create_all`` from the
live ORM models, so a freshly-built PG DB already carries the new columns, their
CHECKs, and the vocab-derived ``ck_ref_relationship`` predicate — the column /
CHECK adds are inspector-guarded and the relationship-CHECK rebuild is a
same-text no-op-equivalent there; on a pre-existing PG store they are real
changes. The refs rebuild is a superset, so no existing row is invalidated.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.vocab import (
    REFERENCE_RELATIONSHIPS,
    REQUIREMENT_ORIGINS,
    REQUIREMENT_REVIEW_STATES,
    _check_in,
)

revision: str = "0011_requirements_provenance"
down_revision: str | None = "0010_wtk_106_migration_mapping_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_KINDS = frozenset(
    {
        "requirement_refines_requirement",
        "requirement_defined_in_conversation",
        "requirement_belongs_to_topic",
        "conversation_belongs_to_topic",
        "requirement_approved_by_decision",
        "requirement_changed_by_decision",
    }
)
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS

_NEW_COLUMNS: tuple[tuple[str, dict], ...] = (
    ("requirement_origin", {"type_": sa.String(16), "nullable": True}),
    (
        "requirement_review_state",
        {
            "type_": sa.String(16),
            "nullable": False,
            "server_default": sa.text("'current'"),
        },
    ),
    ("requirement_approved_at", {"type_": sa.DateTime(timezone=True), "nullable": True}),
)
_NEW_CHECKS: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("ck_requirement_origin", "requirement_origin", REQUIREMENT_ORIGINS),
    (
        "ck_requirement_review_state",
        "requirement_review_state",
        REQUIREMENT_REVIEW_STATES,
    ),
)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _checks(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_check_constraints(table)}


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def upgrade() -> None:
    if "requirements" in _tables():
        have_cols = _columns("requirements")
        have_checks = _checks("requirements")
        for name, kwargs in _NEW_COLUMNS:
            if name not in have_cols:
                op.add_column("requirements", sa.Column(name, **kwargs))
        for ck_name, column, allowed in _NEW_CHECKS:
            if ck_name not in have_checks:
                op.create_check_constraint(
                    ck_name, "requirements", _check_in(column, allowed)
                )
    if "refs" in _tables():
        _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE relationship_kind IN ("
            + ", ".join(f"'{k}'" for k in sorted(_NEW_KINDS))
            + ")"
        )
        _rebuild_relationship_check(_KINDS_OLD)
    if "requirements" in existing:
        for ck_name, _column, _allowed in _NEW_CHECKS:
            op.drop_constraint(ck_name, "requirements", type_="check")
        for name, _kwargs in reversed(_NEW_COLUMNS):
            op.drop_column("requirements", name)
