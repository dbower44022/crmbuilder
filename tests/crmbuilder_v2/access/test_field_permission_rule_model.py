"""Storage-layer tests for the ``field_permission_rules`` table (WTK-202).

Exercises the schema-boundary CHECK constraints and the partial unique index
the WTK-197 design (``field-permission-rule-design.md`` §6, §8) puts on the
table itself, via raw SQL against a ``create_all`` SQLite store — repository
and access-layer validation (live-subject resolution, status transitions, the
rule->role binding) is a sibling Work Task and is deliberately not covered here.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base, FieldPermissionRule
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

_INSERT = text(
    "INSERT INTO field_permission_rules "
    "(engagement_id, field_permission_rule_identifier, "
    "field_permission_rule_name, field_permission_rule_role, "
    "field_permission_rule_target_field, "
    "field_permission_rule_permission_level, field_permission_rule_status, "
    "field_permission_rule_deployment_status, "
    "field_permission_rule_created_at, field_permission_rule_updated_at) "
    "VALUES (:eng, :ident, :name, :role, :field, :level, :status, :deploy, "
    "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
)

_ROW = {
    "eng": "ENG-001",
    "ident": "FPR-001",
    "name": "Contact.backgroundCheckCompleted — Mentor",
    "role": "ROL-001",
    "field": "FLD-001",
    "level": "read_only",
    "status": "candidate",
    "deploy": "not_deployed",
}


@pytest.fixture
def engine(tmp_path: Path):
    eng = create_engine(f"sqlite:///{tmp_path / 'v2.db'}")
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(
            text(
                "INSERT INTO engagements "
                "(engagement_identifier, engagement_code, engagement_name, "
                "engagement_purpose, engagement_status, engagement_created_at, "
                "engagement_updated_at) "
                "VALUES ('ENG-001', 'TEST', 'Test', 'p', 'active', "
                "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            )
        )
    yield eng
    eng.dispose()


def _insert(engine, **overrides) -> None:
    with engine.begin() as c:
        c.execute(_INSERT, {**_ROW, **overrides})


def test_models_define_field_permission_rules_table():
    assert "field_permission_rules" in Base.metadata.tables
    assert FieldPermissionRule.__tablename__ == "field_permission_rules"


def test_minimal_row_round_trips(engine):
    _insert(engine)
    with engine.begin() as c:
        level = c.execute(
            text(
                "SELECT field_permission_rule_permission_level "
                "FROM field_permission_rules "
                "WHERE field_permission_rule_identifier = 'FPR-001'"
            )
        ).scalar_one()
    assert level == "read_only"


def test_default_status_and_deployment_status():
    # Python-side defaults (applied by the ORM on insert): the four-status
    # propose-verify starter and the un-deployed deploy outcome (§4).
    assert FieldPermissionRule.field_permission_rule_status.default.arg == (
        "candidate"
    )
    assert (
        FieldPermissionRule.field_permission_rule_deployment_status.default.arg
        == "not_deployed"
    )


def test_identifier_format_check(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, ident="FPR-1")
    with pytest.raises(IntegrityError):
        _insert(engine, ident="RUL-001")
    with pytest.raises(IntegrityError):
        _insert(engine, ident="FPR-0001")


def test_permission_level_check(engine):
    for i, level in enumerate(("read_write", "read_only", "no_access")):
        # Distinct field per row so the (role, field) unique index is not the
        # constraint under test here.
        _insert(engine, ident=f"FPR-10{i}", field=f"FLD-10{i}", level=level)
    with pytest.raises(IntegrityError):
        _insert(engine, ident="FPR-200", level="write_only")
    with pytest.raises(IntegrityError):
        _insert(engine, ident="FPR-201", level="readonly")


def test_status_check(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, status="Open")
    with pytest.raises(IntegrityError):
        _insert(engine, status="active")


def test_deployment_status_check(engine):
    for i, deploy in enumerate(("not_deployed", "deployed", "drifted", "failed")):
        _insert(engine, ident=f"FPR-20{i}", field=f"FLD-20{i}", deploy=deploy)
    with pytest.raises(IntegrityError):
        _insert(engine, ident="FPR-300", deploy="present")
    with pytest.raises(IntegrityError):
        _insert(engine, ident="FPR-301", deploy="pending")


def test_duplicate_identifier_rejected_within_engagement(engine):
    _insert(engine)
    with pytest.raises(IntegrityError):
        _insert(engine)


def test_one_live_rule_per_role_field_pair(engine):
    # Invariant 6.3: at most one live rule per (engagement, role, field).
    _insert(engine, ident="FPR-001", role="ROL-001", field="FLD-001")
    with pytest.raises(IntegrityError):
        _insert(engine, ident="FPR-002", role="ROL-001", field="FLD-001")


def test_distinct_role_or_field_coexist(engine):
    # Same field, different role -> distinct cell, allowed.
    _insert(engine, ident="FPR-001", role="ROL-001", field="FLD-001")
    _insert(engine, ident="FPR-002", role="ROL-002", field="FLD-001")
    # Same role, different field -> distinct cell, allowed.
    _insert(engine, ident="FPR-003", role="ROL-001", field="FLD-002")
    with engine.begin() as c:
        n = c.execute(
            text("SELECT COUNT(*) FROM field_permission_rules")
        ).scalar_one()
    assert n == 3


def test_soft_deleted_rule_frees_the_pair(engine):
    # A soft-deleted rule no longer occupies the (role, field) cell, so a
    # replacement rule for the same pair may be inserted (partial unique index
    # excludes deleted rows).
    _insert(engine, ident="FPR-001", role="ROL-001", field="FLD-001")
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE field_permission_rules "
                "SET field_permission_rule_deleted_at = CURRENT_TIMESTAMP "
                "WHERE field_permission_rule_identifier = 'FPR-001'"
            )
        )
    _insert(engine, ident="FPR-002", role="ROL-001", field="FLD-001")
    with engine.begin() as c:
        n = c.execute(
            text(
                "SELECT COUNT(*) FROM field_permission_rules "
                "WHERE field_permission_rule_deleted_at IS NULL"
            )
        ).scalar_one()
    assert n == 1
