"""Tests for ``espo_impl.core.audit_db`` record insertion.

Focus: the multiEnum-default bug where ``props["default"]`` arrived as a
Python list and broke SQLite parameter binding (param 6 of the Field
INSERT). Also covers the secondary fix that makes ``FieldOption.is_default``
honour the multiple-value case.

audit-v1.2 Prompt H adds coverage of ``_insert_team`` / ``_insert_role``
and the full ``insert_audit_records`` flow with teams + roles.
"""

import json
import sqlite3
from datetime import UTC, datetime

import pytest

from automation.db.client_schema import get_client_schema_sql
from automation.db.migrations import _client_v5, _client_v15
from espo_impl.core.audit_db import (
    _insert_role,
    _insert_team,
    _serialize_default,
    insert_audit_records,
)
from espo_impl.core.audit_manager import (
    AuditReport,
    EntityAuditResult,
    FieldAuditResult,
    RoleAuditResult,
    TeamAuditResult,
)
from espo_impl.core.audit_utils import EntityClass
from espo_impl.core.models import ScopeAccess, SystemPermissions

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


# ---------------------------------------------------------------------------
# Role / Team insertion (audit-v1.2 Prompt H)
# ---------------------------------------------------------------------------

@pytest.fixture
def security_db():
    """Client DB with ConfigurationRun (v5) and Role/Team (v15) applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    for stmt in get_client_schema_sql():
        conn.execute(stmt)
    _client_v5(conn)
    _client_v15(conn)
    conn.commit()
    yield conn
    conn.close()


def _make_instance(conn: sqlite3.Connection) -> int:
    cursor = conn.execute(
        "INSERT INTO Instance (name, code, environment) "
        "VALUES ('Test', 'TEST', 'test')"
    )
    return cursor.lastrowid


def test_insert_team_creates_row(security_db):
    instance_id = _make_instance(security_db)
    team = TeamAuditResult(name="Mentors", description="Volunteer mentors")

    inserted = _insert_team(security_db, team, instance_id)

    assert inserted is True
    row = security_db.execute(
        "SELECT instance_id, name, description FROM Team WHERE name = 'Mentors'"
    ).fetchone()
    assert row == (instance_id, "Mentors", "Volunteer mentors")


def test_insert_team_skips_duplicate(security_db):
    instance_id = _make_instance(security_db)
    team = TeamAuditResult(name="Mentors", description="Volunteer mentors")

    assert _insert_team(security_db, team, instance_id) is True
    assert _insert_team(security_db, team, instance_id) is False

    count = security_db.execute(
        "SELECT COUNT(*) FROM Team WHERE name = 'Mentors'"
    ).fetchone()[0]
    assert count == 1


def test_insert_role_creates_row_with_json_blobs(security_db):
    instance_id = _make_instance(security_db)
    role = RoleAuditResult(
        name="MentorRole",
        description="Mentor permissions",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="team", edit="own",
                delete="no", stream="team",
            ),
        },
        system_permissions=SystemPermissions(
            assignment_permission="team",
            user_permission="team",
            export=True,
            mass_update=False,
            portal=False,
        ),
    )

    inserted = _insert_role(security_db, role, instance_id)

    assert inserted is True
    row = security_db.execute(
        "SELECT name, description, scope_access_json, system_permissions_json "
        "FROM Role WHERE name = 'MentorRole'"
    ).fetchone()
    assert row[0] == "MentorRole"
    assert row[1] == "Mentor permissions"

    scope_payload = json.loads(row[2])
    assert "Engagement" in scope_payload
    assert scope_payload["Engagement"]["create"] is True
    assert scope_payload["Engagement"]["read"] == "team"

    perms_payload = json.loads(row[3])
    assert perms_payload["assignment_permission"] == "team"
    assert perms_payload["export"] is True


def test_insert_role_system_permissions_none_stores_null(security_db):
    instance_id = _make_instance(security_db)
    role = RoleAuditResult(name="NoPerms", system_permissions=None)

    assert _insert_role(security_db, role, instance_id) is True

    row = security_db.execute(
        "SELECT system_permissions_json FROM Role WHERE name = 'NoPerms'"
    ).fetchone()
    assert row[0] is None


def test_insert_audit_records_includes_role_and_team_counts(security_db):
    instance_id = _make_instance(security_db)
    field = FieldAuditResult(
        yaml_name="status",
        api_name="cStatus",
        field_type="enum",
        label="Status",
        properties={"options": ["A", "B"], "default": "A"},
    )
    entity = EntityAuditResult(
        yaml_name="Engagement",
        espo_name="CEngagement",
        entity_class=EntityClass.CUSTOM,
        entity_type="Base",
        label_singular="Engagement",
        label_plural="Engagements",
        fields=[field],
    )
    team = TeamAuditResult(name="Admins", description="Admin team")
    role = RoleAuditResult(
        name="AdminRole",
        scope_access={
            "Engagement": ScopeAccess(
                create=True, read="all", edit="all",
                delete="all", stream="all",
            ),
        },
        system_permissions=SystemPermissions(
            assignment_permission="all",
            user_permission="all",
            export=True,
            mass_update=True,
            portal=False,
        ),
    )
    report = AuditReport(
        source_url="https://example.test",
        source_name="audit-test",
        timestamp=datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        output_dir="",
        entities=[entity],
        teams=[team],
        roles=[role],
    )

    total = insert_audit_records(security_db, report, instance_id=instance_id)

    # 1 entity + 1 field + 2 options + 1 team + 1 role + 1 ConfigurationRun
    assert total == 7

    assert security_db.execute(
        "SELECT COUNT(*) FROM Team WHERE instance_id = ?", (instance_id,),
    ).fetchone()[0] == 1
    assert security_db.execute(
        "SELECT COUNT(*) FROM Role WHERE instance_id = ?", (instance_id,),
    ).fetchone()[0] == 1


def test_insert_audit_records_skips_security_without_instance_id(security_db):
    """Without an instance_id, security rows have nowhere to FK to and
    are not inserted (matches the ConfigurationRun gate)."""
    team = TeamAuditResult(name="Mentors")
    role = RoleAuditResult(name="MentorRole")
    report = AuditReport(
        source_url="https://example.test",
        source_name="audit-test",
        timestamp="2026-05-24T07:30:00Z",
        output_dir="",
        teams=[team],
        roles=[role],
    )

    total = insert_audit_records(security_db, report, instance_id=None)

    assert total == 0
    assert security_db.execute("SELECT COUNT(*) FROM Team").fetchone()[0] == 0
    assert security_db.execute("SELECT COUNT(*) FROM Role").fetchone()[0] == 0
