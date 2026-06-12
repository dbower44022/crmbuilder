"""PI-153 — `rejected` lifecycle status + utilization_evidence table + CHECK rebuilds.

Implements the WTK-088 design spec (methodology-schema-specs/
candidate-lifecycle-rejected-and-utilization-evidence.md):

- rebuilds the seven methodology ``ck_*_status`` CHECKs to admit the new
  truly-terminal ``rejected`` status (D1);
- creates the append-only ``utilization_evidence`` table (D2) from the ORM
  ``__table__`` with ``checkfirst`` (idempotent on the
  create_all-then-upgrade-head test path);
- rebuilds ``ck_changelog_entity_type`` to admit ``utilization_evidence``
  (the known gotcha: tests build via create_all and miss it; the live DB
  500s without it — see 0034 / 0043 / 0045);
- rebuilds ``ck_ref_relationship`` to admit ``rejected_by_decision``
  AND the WTK-089 ``observed_in`` provenance kind — the merged refs-CHECK
  rebuild per WTK-089 §5.2 (one Planning Item builds both designs, so the
  shared surface collapses into a single vocab-derived rebuild here; 0047
  carries only the deposit_events kind delta).

All CHECK predicates derive from the current vocab so they cannot drift
from the models; the status/refs/change_log rebuilds are supersets, so no
existing row is invalidated. Downgrade follows the 0044 delete-then-rebuild
posture: rows at ``rejected``, refs rows of the two new kinds, and
``utilization_evidence`` change_log rows are deleted before the narrower
CHECKs are restored.

SQLite chain head 0045 -> 0046. Companion PG-chain delta:
``migrations/pg/versions/0008_pi_153_rejected_and_utilization_evidence.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from crmbuilder_v2.access.models import UtilizationEvidence
from crmbuilder_v2.access.vocab import (
    CHANGE_LOG_ENTITY_TYPES,
    DOMAIN_STATUSES,
    ENTITY_STATUSES,
    FIELD_STATUSES,
    MANUAL_CONFIG_STATUSES,
    PERSONA_STATUSES,
    REFERENCE_RELATIONSHIPS,
    REQUIREMENT_STATUSES,
    TEST_SPEC_STATUSES,
    _check_in,
)

revision: str = "0046_pi_153_rejected_and_utilization_evidence"
down_revision: str | None = "0045_pi_134_findings_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_STATUS = "rejected"
# Merged refs-CHECK delta (WTK-089 §5.2): the PI-153 kind plus the
# deposit-path observation-provenance kind, rebuilt once.
_NEW_KINDS = frozenset({"rejected_by_decision", "observed_in"})

_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS
_LOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - {"utilization_evidence"}

# (table, status column, CHECK name, vocab set) for the seven status-bearing
# methodology entity types per WTK-088 §3.1.
_STATUS_TABLES: tuple[tuple[str, str, str, frozenset[str]], ...] = (
    ("domains", "domain_status", "ck_domain_status", DOMAIN_STATUSES),
    ("entities", "entity_status", "ck_entity_status", ENTITY_STATUSES),
    ("fields", "field_status", "ck_field_status", FIELD_STATUSES),
    ("personas", "persona_status", "ck_persona_status", PERSONA_STATUSES),
    (
        "requirements",
        "requirement_status",
        "ck_requirement_status",
        REQUIREMENT_STATUSES,
    ),
    (
        "manual_configs",
        "manual_config_status",
        "ck_manual_config_status",
        MANUAL_CONFIG_STATUSES,
    ),
    ("test_specs", "test_spec_status", "ck_test_spec_status", TEST_SPEC_STATUSES),
)


def _tables() -> set[str]:
    # Touched tables are absent when the chain is entered mid-stream
    # (the stamp-0036 isolated-migration test path).
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_status_checks(*, rejected_admitted: bool) -> None:
    existing = _tables()
    for table, column, ck_name, statuses in _STATUS_TABLES:
        if table not in existing:
            continue
        allowed = statuses if rejected_admitted else statuses - {_NEW_STATUS}
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(ck_name, type_="check")
            batch.create_check_constraint(ck_name, _check_in(column, allowed))


def _rebuild_changelog_check(types: frozenset[str]) -> None:
    if "change_log" not in _tables():
        return
    with op.batch_alter_table("change_log") as batch:
        batch.drop_constraint("ck_changelog_entity_type", type_="check")
        batch.create_check_constraint(
            "ck_changelog_entity_type", _check_in("entity_type", types)
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
    UtilizationEvidence.__table__.create(bind, checkfirst=True)
    _rebuild_status_checks(rejected_admitted=True)
    _rebuild_changelog_check(_LOG_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    existing = _tables()
    # Delete rows the narrower CHECKs would reject before rebuilding —
    # destructive on downgrade, consistent with the 0044 posture.
    for table, column, _ck_name, _statuses in _STATUS_TABLES:
        if table in existing:
            op.execute(f"DELETE FROM {table} WHERE {column} = '{_NEW_STATUS}'")
    if "refs" in existing:
        op.execute(
            "DELETE FROM refs WHERE relationship_kind IN "
            "('rejected_by_decision', 'observed_in')"
        )
    if "change_log" in existing:
        op.execute(
            "DELETE FROM change_log WHERE entity_type = 'utilization_evidence'"
        )
    _rebuild_status_checks(rejected_admitted=False)
    _rebuild_changelog_check(_LOG_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if UtilizationEvidence.__tablename__ in _tables():
        UtilizationEvidence.__table__.drop(bind)
