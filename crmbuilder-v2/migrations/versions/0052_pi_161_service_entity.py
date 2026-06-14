"""PI-161 — services table + entity-type / relationship-kind CHECK rebuilds.

Implements the storage slice of the WTK-132 design spec
(methodology-schema-specs/service.md §4):

- creates the ``services`` table (the cross-domain service record type,
  ``SVC-NNN``) from the ORM ``__table__`` with ``checkfirst`` (idempotent on
  the create_all-then-upgrade-head test path) — carries the
  identifier-format and status CHECKs and the two indexes;
- rebuilds ``ck_changelog_entity_type`` and the ``refs``
  ``ck_ref_source_type`` / ``ck_ref_target_type`` CHECKs to admit the new
  ``service`` entity type (the known gotcha: tests build via create_all and
  miss it; the live DB 500s without it — see 0034 / 0043 / 0045 / 0048);
- rebuilds ``ck_ref_relationship`` to admit the two new edge kinds
  ``process_consumes_service`` / ``service_owns_entity`` (and, via the vocab
  derivation, the ``rejected_by_decision`` source-set extension to
  ``service``, which needs no CHECK change — the kind is already admitted).

All CHECK predicates derive from the current vocab so they cannot drift from
the models; the rebuilds are supersets, so no existing row is invalidated.
Every rebuild helper inspects the live tables first and skips absent ones so
the chain is safe to enter mid-stream (the stamp-0036 isolated-migration
path, where ``refs`` / ``change_log`` don't exist yet). Downgrade follows
the 0045 / 0048 delete-then-rebuild posture: refs and change_log rows naming
the new type/kinds are deleted before the narrower CHECKs are restored, then
the table is dropped.

SQLite chain head 0048 -> 0049. Companion PG-chain delta:
``migrations/pg/versions/0014_pi_161_service_entity.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import Service
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0052_pi_161_service_entity"
down_revision: str | None = "0051_review_signoffs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "service"
_NEW_KINDS = frozenset(
    {
        "process_consumes_service",
        "service_owns_entity",
    }
)

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_LOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - {_NEW_TYPE}
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


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


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    if "refs" not in _tables():
        return
    with op.batch_alter_table("refs") as batch:
        batch.drop_constraint("ck_ref_relationship", type_="check")
        batch.create_check_constraint(
            "ck_ref_relationship", _check_in("relationship_kind", kinds)
        )


def upgrade() -> None:
    bind = op.get_bind()
    Service.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW, _LOG_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type = 'service' "
            "OR target_type = 'service' "
            "OR relationship_kind IN "
            "('process_consumes_service', 'service_owns_entity')"
        )
    if "change_log" in existing:
        op.execute("DELETE FROM change_log WHERE entity_type = 'service'")
    _rebuild_entity_type_checks(_TYPES_OLD, _LOG_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if Service.__tablename__ in _tables():
        Service.__table__.drop(bind)
