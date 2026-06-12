"""PI-134 — findings table + entity-type / relationship-kind CHECK rebuilds.

Creates the ``findings`` table (the reconciliation-gate ``finding`` entity,
DEC-400) and rebuilds the ``change_log`` + ``refs`` entity-type CHECKs to admit
the new ``finding`` entity type, and the ``refs`` relationship-kind CHECK to
admit the two new edge kinds ``finding_relates_to`` / ``finding_resolved_by``.
All three CHECKs are supersets, so no existing row is invalidated (the gotcha
that adding an ENTITY_TYPE must rebuild change_log + refs CHECKs; tests build via
create_all and miss it — see 0034 / 0043).

The table is created from the ORM ``__table__`` (carries the dialect-aware
identifier-format CHECK) with ``checkfirst`` so this is idempotent on the
create_all-then-upgrade-head test path. The CHECK predicates are derived from
the current vocab so they cannot drift from the models.

SQLite chain head 0044 -> 0045. Companion PG-chain delta:
``migrations/pg/versions/0007_pi_134_findings_entity.py``.

NOTE (live application): the live store (``data/v2-unified.db``) is
create_all-managed and is NOT walked through this SQLite chain. This migration
is the canonical record of the delta; the live application is performed (and
verified on a copy first) per ``pi-134-findings-migration-runbook.md`` and
authorized by a PM session.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import Finding
from crmbuilder_v2.access.vocab import (
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    _check_in,
)

revision: str = "0045_pi_134_findings_entity"
down_revision: str | None = "0044_pi_122_registry_binding_edges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_TYPE = "finding"
_NEW_KINDS = frozenset({"finding_relates_to", "finding_resolved_by"})

_TYPES_NEW = ENTITY_TYPES
_TYPES_OLD = ENTITY_TYPES - {_NEW_TYPE}
_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_entity_type_checks(types: frozenset[str]) -> None:
    existing = _tables()  # change_log/refs absent when the chain is entered mid-stream
    if "change_log" in existing:
        with op.batch_alter_table("change_log") as batch:
            batch.drop_constraint("ck_changelog_entity_type", type_="check")
            batch.create_check_constraint(
                "ck_changelog_entity_type", _check_in("entity_type", types | {"reference"})
            )
    if "refs" in existing:
        with op.batch_alter_table("refs") as batch:
            batch.drop_constraint("ck_ref_source_type", type_="check")
            batch.create_check_constraint("ck_ref_source_type", _check_in("source_type", types))
            batch.drop_constraint("ck_ref_target_type", type_="check")
            batch.create_check_constraint("ck_ref_target_type", _check_in("target_type", types))


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
    Finding.__table__.create(bind, checkfirst=True)
    _rebuild_entity_type_checks(_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE source_type = 'finding' OR target_type = 'finding' "
            "OR relationship_kind IN ('finding_relates_to', 'finding_resolved_by')"
        )
    if "change_log" in existing:
        op.execute("DELETE FROM change_log WHERE entity_type = 'finding'")
    _rebuild_entity_type_checks(_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if Finding.__tablename__ in _tables():
        Finding.__table__.drop(bind)
