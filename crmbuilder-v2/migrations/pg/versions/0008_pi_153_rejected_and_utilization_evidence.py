"""PI-153 (PG chain) — `rejected` status + utilization_evidence + CHECK rebuilds.

Companion to the SQLite-chain ``0046``. Rebuilds the seven methodology
``ck_*_status`` CHECKs to admit ``rejected``, creates the
``utilization_evidence`` table, rebuilds ``ck_changelog_entity_type`` to
admit the ``utilization_evidence`` entity type, and rebuilds
``ck_ref_relationship`` to admit ``rejected_by_decision`` + the WTK-089
``observed_in`` kind (the merged refs-CHECK rebuild per WTK-089 §5.2) on
Postgres deployments materialised from an earlier baseline.

The PG baseline (``0001_pg_baseline``) is ``Base.metadata.create_all`` from
the live ORM models, so a freshly-built PG DB already carries the new table
and the vocab-derived CHECK predicates — the table create is inspector-
guarded and the constraint rebuilds are same-text no-op-equivalents there;
on a pre-existing PG store they are real changes. Supersets, so no existing
row is invalidated.
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

revision: str = "0008_pi_153_rejected_and_utilization_evidence"
down_revision: str | None = "0007_pi_134_findings_entity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_STATUS = "rejected"
_NEW_KINDS = frozenset({"rejected_by_decision", "observed_in"})

_KINDS_NEW = REFERENCE_RELATIONSHIPS
_KINDS_OLD = REFERENCE_RELATIONSHIPS - _NEW_KINDS
_LOG_TYPES_NEW = CHANGE_LOG_ENTITY_TYPES
_LOG_TYPES_OLD = CHANGE_LOG_ENTITY_TYPES - {"utilization_evidence"}

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
    return set(sa.inspect(op.get_bind()).get_table_names())


def _rebuild_status_checks(*, rejected_admitted: bool) -> None:
    for table, column, ck_name, statuses in _STATUS_TABLES:
        allowed = statuses if rejected_admitted else statuses - {_NEW_STATUS}
        op.drop_constraint(ck_name, table, type_="check")
        op.create_check_constraint(ck_name, table, _check_in(column, allowed))


def _rebuild_changelog_check(types: frozenset[str]) -> None:
    op.drop_constraint("ck_changelog_entity_type", "change_log", type_="check")
    op.create_check_constraint(
        "ck_changelog_entity_type", "change_log", _check_in("entity_type", types)
    )


def _rebuild_relationship_check(kinds: frozenset[str]) -> None:
    op.drop_constraint("ck_ref_relationship", "refs", type_="check")
    op.create_check_constraint(
        "ck_ref_relationship", "refs", _check_in("relationship_kind", kinds)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if UtilizationEvidence.__tablename__ not in _tables():
        UtilizationEvidence.__table__.create(bind)
    _rebuild_status_checks(rejected_admitted=True)
    _rebuild_changelog_check(_LOG_TYPES_NEW)
    _rebuild_relationship_check(_KINDS_NEW)


def downgrade() -> None:
    bind = op.get_bind()
    for table, column, _ck_name, _statuses in _STATUS_TABLES:
        op.execute(f"DELETE FROM {table} WHERE {column} = '{_NEW_STATUS}'")
    op.execute(
        "DELETE FROM refs WHERE relationship_kind IN "
        "('rejected_by_decision', 'observed_in')"
    )
    op.execute("DELETE FROM change_log WHERE entity_type = 'utilization_evidence'")
    _rebuild_status_checks(rejected_admitted=False)
    _rebuild_changelog_check(_LOG_TYPES_OLD)
    _rebuild_relationship_check(_KINDS_OLD)
    if UtilizationEvidence.__tablename__ in _tables():
        UtilizationEvidence.__table__.drop(bind)
