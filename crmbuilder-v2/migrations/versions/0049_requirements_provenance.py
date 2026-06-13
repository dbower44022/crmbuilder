"""Requirements-provenance model (Phase 1) — requirement columns + 6 refs kinds.

Implements Phase 1 of ``requirements-provenance-build-translation.md``:

- adds three columns to ``requirements`` — ``requirement_origin`` (NULL for
  legacy rows predating the model), ``requirement_review_state`` (NOT NULL,
  default ``current``), and ``requirement_approved_at`` — plus their
  ``ck_requirement_origin`` / ``ck_requirement_review_state`` CHECKs;
- rebuilds ``ck_ref_relationship`` to admit the six provenance-model edge kinds
  (``requirement_refines_requirement``, ``requirement_defined_in_conversation``,
  ``requirement_belongs_to_topic``, ``conversation_belongs_to_topic``,
  ``requirement_approved_by_decision``, ``requirement_changed_by_decision``).

No new entity types, so ``ck_changelog_entity_type`` is untouched. CHECK
predicates derive from the current vocab so they cannot drift from the models;
the refs rebuild is a superset, so no existing row is invalidated. The column /
CHECK adds are guarded against the create_all-then-upgrade-head test path (the
columns already exist there), mirroring 0046's ``checkfirst`` table create. The
``_tables()`` guard keeps the migration safe when the chain is entered
mid-stream (the stamp-0036 isolated path).

SQLite chain head 0048 -> 0049. Companion PG-chain delta:
``migrations/pg/versions/0011_requirements_provenance.py``.
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

revision: str = "0049_requirements_provenance"
down_revision: str | None = "0048_wtk_106_migration_mapping_entity"
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

# (column name, kwargs) for the three new requirement columns.
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
    if "refs" not in _tables():
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def upgrade() -> None:
    if "requirements" in _tables():
        have_cols = _columns("requirements")
        have_checks = _checks("requirements")
        missing_cols = [c for c in _NEW_COLUMNS if c[0] not in have_cols]
        missing_checks = [c for c in _NEW_CHECKS if c[0] not in have_checks]
        if missing_cols or missing_checks:
            with op.batch_alter_table("requirements") as batch:
                for name, kwargs in missing_cols:
                    batch.add_column(sa.Column(name, **kwargs))
                for ck_name, column, allowed in missing_checks:
                    batch.create_check_constraint(ck_name, _check_in(column, allowed))
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
        with op.batch_alter_table("requirements") as batch:
            for ck_name, _column, _allowed in _NEW_CHECKS:
                batch.drop_constraint(ck_name, type_="check")
            for name, _kwargs in reversed(_NEW_COLUMNS):
                batch.drop_column(name)
