"""Storage-layer tests for the ``migration_mappings`` table (WTK-106).

Exercises the schema-boundary CHECK constraints the WTK-104 design spec
puts on the table itself (migration_mapping.md §3.2 + invariant I11) via
raw SQL against a ``create_all`` SQLite store — repository-layer
validation (edge cardinality, rule-list schema, keep/split shapes) is a
sibling Work Task and is deliberately not covered here.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from crmbuilder_v2.access.models import Base, MigrationMapping
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

_INSERT = text(
    "INSERT INTO migration_mappings "
    "(engagement_id, migration_mapping_identifier, migration_mapping_level, "
    "migration_mapping_disposition, migration_mapping_source_system_label, "
    "migration_mapping_source_entity_name, "
    "migration_mapping_source_attribute_name, "
    "migration_mapping_transform_rules, migration_mapping_status, "
    "migration_mapping_created_at, migration_mapping_updated_at) "
    "VALUES (:eng, :ident, :level, :disposition, :label, :entity, :attr, "
    ":rules, :status, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
)

_ROW = {
    "eng": "ENG-001",
    "ident": "MIG-001",
    "level": "field",
    "disposition": "transform",
    "label": "espocrm @ crm.cbmentors.org",
    "entity": "Contact",
    "attr": "cContactType",
    "rules": None,
    "status": "confirmed",
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


def test_models_define_migration_mappings_table():
    assert "migration_mappings" in Base.metadata.tables
    assert MigrationMapping.__tablename__ == "migration_mappings"


def test_field_level_row_round_trips_with_rules(engine):
    rules = [
        {
            "rule_kind": "enum_value_map",
            "value_map": {"Mentor Candidate": "candidate"},
            "unmapped_policy": "error",
        }
    ]
    _insert(engine, rules=json.dumps(rules))
    with engine.begin() as c:
        stored = c.execute(
            text(
                "SELECT migration_mapping_transform_rules "
                "FROM migration_mappings "
                "WHERE migration_mapping_identifier = 'MIG-001'"
            )
        ).scalar_one()
    assert json.loads(stored) == rules


def test_entity_level_row_with_null_attribute(engine):
    _insert(engine, ident="MIG-002", level="entity", attr=None)


def test_identifier_format_check(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, ident="MIG-1")
    with pytest.raises(IntegrityError):
        _insert(engine, ident="MAP-001")


def test_status_check(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, status="Open")


def test_level_check(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, level="persona")


def test_disposition_check(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, disposition="drop")


def test_i11_field_level_requires_attribute(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, level="field", attr=None)


def test_i11_entity_level_forbids_attribute(engine):
    with pytest.raises(IntegrityError):
        _insert(engine, level="entity", attr="cContactType")


def test_duplicate_identifier_rejected_within_engagement(engine):
    _insert(engine)
    with pytest.raises(IntegrityError):
        _insert(engine)
