"""PI-189 slice 3 — dedup_rules + message_templates tables + entity-type
CHECK rebuilds.

Implements the final storage slice of the PRJ-025 PI-189 design
(``engine-neutral-design-model-and-adapters.md`` §8) for the two
dedup-and-template design records:

- creates the ``dedup_rules`` (``DUP-NNN``) and ``message_templates``
  (``MSG-NNN``) tables from the ORM ``__table__`` with ``checkfirst``
  (idempotent on the create_all-then-upgrade-head test path) — each carries
  its identifier-format / domain / non-empty-JSON-array CHECKs and indexes;
- rebuilds ``ck_changelog_entity_type`` and the ``refs``
  ``ck_ref_source_type`` / ``ck_ref_target_type`` CHECKs to admit the two new
  entity types ``dedup_rule`` + ``message_template`` (the known gotcha: tests
  build via create_all and miss it; the live DB 500s without it — see
  0034 / 0043 / 0045 / 0048 / 0052 / 0054 / 0055).

Slice 3 adds **no** new relationship_kind — these records carry their subject
and listed-entity as columns, not ``refs`` edges, so ``ck_ref_relationship``
is left untouched. All CHECK predicates derive from the current vocab so they
cannot drift from the models; the rebuilds are supersets, so no existing row
is invalidated. Every rebuild helper inspects the live tables first and skips
absent ones so the chain is safe to enter mid-stream (the stamp-0036
isolated-migration path, where ``refs`` / ``change_log`` don't exist yet).
The ``change_log`` / ``refs`` tables carry only plain column indexes
(``ix_refs_source`` / ``ix_refs_target``) — no expression indexes (those live
on ``engagements``) — so the batch recreate round-trips their indexes via
reflection with no manual restore needed (unlike 0040). Downgrade follows the
0055 delete-then-rebuild posture: refs and change_log rows naming the new
types are deleted before the narrower CHECKs are restored, then the tables
are dropped.

SQLite chain head 0055 -> 0056.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import DedupRule, MessageTemplate
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    _check_in,
)

revision: str = "0056_pi_189_dedup_template_design_records"
down_revision: str | None = "0055_pi_189_condition_design_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPES = frozenset({"dedup_rule", "message_template"})

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - _NEW_TYPES
_LOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - _NEW_TYPES


def _tables() -> set[str]:
    # Touched tables are absent when the chain is entered mid-stream
    # (the stamp-0036 isolated-migration test path).
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(
    types: frozenset[str], log_types: frozenset[str]
) -> None:
    existing = _tables()
    if "change_log" in existing:
        with op.batch_alter_table("change_log") as batch:
            batch.drop_constraint("ck_changelog_entity_type", type_="check")
            batch.create_check_constraint(
                "ck_changelog_entity_type", _check_in("entity_type", log_types)
            )
    if "refs" in existing:
        with op.batch_alter_table("refs") as batch:
            batch.drop_constraint("ck_ref_source_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_source_type", _check_in("source_type", types)
            )
            batch.drop_constraint("ck_ref_target_type", type_="check")
            batch.create_check_constraint(
                "ck_ref_target_type", _check_in("target_type", types)
            )


def upgrade() -> None:
    bind = op.get_bind()
    DedupRule.__table__.create(bind, checkfirst=True)
    MessageTemplate.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_TYPES_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type IN "
            "('dedup_rule', 'message_template') "
            "OR target_type IN ('dedup_rule', 'message_template')"
        )
    if "change_log" in existing:
        op.execute(
            "DELETE FROM change_log WHERE entity_type IN "
            "('dedup_rule', 'message_template')"
        )
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_TYPES_OLD)
    if MessageTemplate.__tablename__ in _tables():
        MessageTemplate.__table__.drop(bind)
    if DedupRule.__tablename__ in _tables():
        DedupRule.__table__.drop(bind)
