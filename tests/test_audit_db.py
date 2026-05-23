"""Tests for ``espo_impl.core.audit_db`` record insertion.

Focus: the multiEnum-default bug where ``props["default"]`` arrived as a
Python list and broke SQLite parameter binding (param 6 of the Field
INSERT). Also covers the secondary fix that makes ``FieldOption.is_default``
honour the multiple-value case.
"""

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from automation.db.client_schema import get_client_schema_sql
from espo_impl.core.audit_db import (
    _serialize_default,
    insert_audit_records,
)
from espo_impl.core.audit_manager import (
    AuditReport,
    EntityAuditResult,
    FieldAuditResult,
)
from espo_impl.core.audit_utils import EntityClass

# ---------------------------------------------------------------------------
# _serialize_default
# ---------------------------------------------------------------------------

def test_serialize_default_passes_scalars_through():
    assert _serialize_default(None) is None
    assert _serialize_default("Active") == "Active"
    assert _serialize_default(42) == 42
    assert _serialize_default(True) is True


def test_serialize_default_jsonifies_list():
    assert _serialize_default(["Active", "Pending"]) == '["Active", "Pending"]'


def test_serialize_default_jsonifies_dict():
    assert _serialize_default({"x": 1}) == '{"x": 1}'


# ---------------------------------------------------------------------------
# insert_audit_records with a multiEnum field
# ---------------------------------------------------------------------------

@pytest.fixture
def client_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    for stmt in get_client_schema_sql():
        conn.execute(stmt)
    conn.commit()
    yield conn
    conn.close()


def _multi_enum_report() -> AuditReport:
    """Build the smallest report that triggers the original bug."""
    field = FieldAuditResult(
        yaml_name="statuses",
        api_name="cStatuses",
        field_type="multiEnum",
        label="Statuses",
        properties={
            "options": ["Active", "Pending", "Closed"],
            "default": ["Active", "Pending"],
        },
    )
    entity = EntityAuditResult(
        yaml_name="MentorProfile",
        espo_name="CMentorProfile",
        entity_class=EntityClass.CUSTOM,
        entity_type="Base",
        label_singular="Mentor Profile",
        label_plural="Mentor Profiles",
        fields=[field],
    )
    return AuditReport(
        source_url="https://example.test",
        source_name="cbm-test",
        timestamp=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        output_dir="",
        entities=[entity],
    )


def test_insert_records_handles_multienum_default(client_db):
    report = _multi_enum_report()

    inserted = insert_audit_records(client_db, report)

    # 1 entity + 1 field + 3 options = 5 records (no relationships, no layouts).
    assert inserted == 5

    row = client_db.execute(
        "SELECT field_type, default_value FROM Field WHERE name = 'statuses'"
    ).fetchone()
    assert row is not None
    assert row[0] == "multiEnum"
    # Stored as JSON; round-trip recovers the original list.
    assert json.loads(row[1]) == ["Active", "Pending"]


def test_field_option_is_default_flags_multienum_values(client_db):
    report = _multi_enum_report()
    insert_audit_records(client_db, report)

    options = dict(client_db.execute(
        "SELECT value, is_default FROM FieldOption "
        "JOIN Field ON FieldOption.field_id = Field.id "
        "WHERE Field.name = 'statuses'"
    ).fetchall())

    assert options == {"Active": 1, "Pending": 1, "Closed": 0}


def test_scalar_enum_default_lands_as_text(client_db):
    field = FieldAuditResult(
        yaml_name="status",
        api_name="cStatus",
        field_type="enum",
        label="Status",
        properties={
            "options": ["Active", "Closed"],
            "default": "Active",
        },
    )
    entity = EntityAuditResult(
        yaml_name="MentorProfile",
        espo_name="CMentorProfile",
        entity_class=EntityClass.CUSTOM,
        entity_type="Base",
        label_singular="Mentor Profile",
        label_plural="Mentor Profiles",
        fields=[field],
    )
    report = AuditReport(
        source_url="https://example.test",
        source_name="cbm-test",
        timestamp="2026-05-23T04:49:53Z",
        output_dir="",
        entities=[entity],
    )

    insert_audit_records(client_db, report)

    row = client_db.execute(
        "SELECT default_value FROM Field WHERE name = 'status'"
    ).fetchone()
    assert row[0] == "Active"

    options = dict(client_db.execute(
        "SELECT value, is_default FROM FieldOption "
        "JOIN Field ON FieldOption.field_id = Field.id "
        "WHERE Field.name = 'status'"
    ).fetchall())
    assert options == {"Active": 1, "Closed": 0}
