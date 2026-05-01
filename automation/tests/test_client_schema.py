"""Tests for client database schema.

Covers all 25 tables across Requirements, Cross-Reference, Management,
Audit, and Layout layers. Tests verify constraints: NOT NULL, UNIQUE,
FOREIGN KEY, and CHECK constraints on enumerated TEXT columns.
"""

import sqlite3
from datetime import datetime

import pytest

from automation.db.client_schema import SCHEMA_VERSION_TABLE, get_client_schema_sql


@pytest.fixture()
def client_db(tmp_path):
    """Create a client database with the full schema applied."""
    db_path = tmp_path / "client.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(SCHEMA_VERSION_TABLE)
    for stmt in get_client_schema_sql():
        conn.execute(stmt)
    conn.commit()
    yield conn
    conn.close()


def _insert_work_item(conn, item_type="master_prd",
                       status="not_started", **kwargs):
    """Helper to insert a WorkItem and return its id."""
    cols = "item_type, status"
    vals = "?, ?"
    params = [item_type, status]
    for k, v in kwargs.items():
        cols += f", {k}"
        vals += ", ?"
        params.append(v)
    cur = conn.execute(
        f"INSERT INTO WorkItem ({cols}) VALUES ({vals})", params
    )
    conn.commit()
    return cur.lastrowid


def _insert_ai_session(conn, work_item_id, **kwargs):
    """Helper to insert an AISession and return its id."""
    defaults = {
        "session_type": "initial",
        "generated_prompt": "Test prompt",
        "import_status": "pending",
        "started_at": datetime.now().isoformat(),
    }
    defaults.update(kwargs)
    cur = conn.execute(
        "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (?, ?, ?, ?, ?)",
        (work_item_id, defaults["session_type"], defaults["generated_prompt"],
         defaults["import_status"], defaults["started_at"]),
    )
    conn.commit()
    return cur.lastrowid


def _insert_domain(conn, name="Mentoring", code="MN", **kwargs):
    """Helper to insert a Domain and return its id."""
    cur = conn.execute(
        "INSERT INTO Domain (name, code) VALUES (?, ?)", (name, code)
    )
    conn.commit()
    return cur.lastrowid


def _insert_entity(conn, name="Contact", code="CON", entity_type="Person",
                    is_native=True, **kwargs):
    """Helper to insert an Entity and return its id."""
    cur = conn.execute(
        "INSERT INTO Entity (name, code, entity_type, is_native) "
        "VALUES (?, ?, ?, ?)",
        (name, code, entity_type, is_native),
    )
    conn.commit()
    return cur.lastrowid


def _insert_field(conn, entity_id, name="mentorStatus", label="Mentor Status",
                   field_type="enum", **kwargs):
    """Helper to insert a Field and return its id."""
    cur = conn.execute(
        "INSERT INTO Field (entity_id, name, label, field_type) "
        "VALUES (?, ?, ?, ?)",
        (entity_id, name, label, field_type),
    )
    conn.commit()
    return cur.lastrowid


def _insert_process(conn, domain_id, name="Client Intake", code="MN-INTAKE",
                     sort_order=1, **kwargs):
    """Helper to insert a Process and return its id."""
    cur = conn.execute(
        "INSERT INTO Process (domain_id, name, code, sort_order) "
        "VALUES (?, ?, ?, ?)",
        (domain_id, name, code, sort_order),
    )
    conn.commit()
    return cur.lastrowid


def _insert_persona(conn, name="Volunteer Mentor", code="MENTOR"):
    """Helper to insert a Persona and return its id."""
    cur = conn.execute(
        "INSERT INTO Persona (name, code) VALUES (?, ?)", (name, code)
    )
    conn.commit()
    return cur.lastrowid


# ===== Requirements Layer =====


class TestDomainTable:
    def test_create_domain(self, client_db):
        _insert_domain(client_db)
        row = client_db.execute(
            "SELECT name, code FROM Domain WHERE code = 'MN'"
        ).fetchone()
        assert row == ("Mentoring", "MN")

    def test_name_not_null(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute("INSERT INTO Domain (code) VALUES ('MN')")

    def test_code_not_null(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute("INSERT INTO Domain (name) VALUES ('Test')")

    def test_code_unique(self, client_db):
        _insert_domain(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Domain (name, code) VALUES ('Other', 'MN')"
            )

    def test_parent_domain_fk(self, client_db):
        parent_id = _insert_domain(client_db, "Parent", "PAR")
        client_db.execute(
            "INSERT INTO Domain (name, code, parent_domain_id) "
            "VALUES ('Child', 'CHD', ?)",
            (parent_id,),
        )
        client_db.commit()

    def test_parent_domain_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Domain (name, code, parent_domain_id) "
                "VALUES ('Child', 'CHD', 9999)"
            )

    def test_is_service_default(self, client_db):
        _insert_domain(client_db)
        row = client_db.execute(
            "SELECT is_service FROM Domain WHERE code = 'MN'"
        ).fetchone()
        assert row[0] == 0

    def test_can_drop(self, client_db):
        client_db.execute("PRAGMA foreign_keys = OFF")
        client_db.execute("DROP TABLE Domain")


class TestEntityTable:
    def test_create_entity(self, client_db):
        _insert_entity(client_db)
        row = client_db.execute(
            "SELECT name, entity_type, is_native FROM Entity WHERE code = 'CON'"
        ).fetchone()
        assert row == ("Contact", "Person", 1)

    def test_entity_type_check(self, client_db):
        for valid in ("Base", "Person", "Company", "Event"):
            client_db.execute(
                "INSERT INTO Entity (name, code, entity_type, is_native) "
                "VALUES (?, ?, ?, ?)",
                (f"E_{valid}", f"E{valid[:2].upper()}", valid, False),
            )
        client_db.commit()

    def test_entity_type_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Entity (name, code, entity_type, is_native) "
                "VALUES ('Bad', 'BAD', 'Invalid', 0)"
            )

    def test_code_unique(self, client_db):
        _insert_entity(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_entity(client_db, "Other", "CON", "Base", False)

    def test_primary_domain_fk(self, client_db):
        domain_id = _insert_domain(client_db)
        client_db.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
            "VALUES ('Dues', 'DUE', 'Base', 0, ?)",
            (domain_id,),
        )
        client_db.commit()

    def test_primary_domain_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
                "VALUES ('Dues', 'DUE', 'Base', 0, 9999)"
            )


class TestFieldTable:
    def test_create_field(self, client_db):
        eid = _insert_entity(client_db)
        _insert_field(client_db, eid)
        row = client_db.execute(
            "SELECT name, field_type FROM Field WHERE entity_id = ?", (eid,)
        ).fetchone()
        assert row == ("mentorStatus", "enum")

    def test_entity_id_not_null(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Field (name, label, field_type) "
                "VALUES ('test', 'Test', 'varchar')"
            )

    def test_entity_id_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Field (entity_id, name, label, field_type) "
                "VALUES (9999, 'test', 'Test', 'varchar')"
            )

    def test_field_type_check_all_valid(self, client_db):
        eid = _insert_entity(client_db)
        valid_types = [
            "varchar", "text", "wysiwyg", "bool", "int", "float",
            "date", "datetime", "currency", "url", "email", "phone",
            "enum", "multiEnum",
        ]
        for i, ft in enumerate(valid_types):
            client_db.execute(
                "INSERT INTO Field (entity_id, name, label, field_type) "
                "VALUES (?, ?, ?, ?)",
                (eid, f"f{i}", f"Field {i}", ft),
            )
        client_db.commit()

    def test_field_type_check_rejects_invalid(self, client_db):
        eid = _insert_entity(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Field (entity_id, name, label, field_type) "
                "VALUES (?, 'bad', 'Bad', 'invalid_type')",
                (eid,),
            )

    def test_is_native_default(self, client_db):
        eid = _insert_entity(client_db)
        _insert_field(client_db, eid)
        row = client_db.execute(
            "SELECT is_native FROM Field WHERE entity_id = ?", (eid,)
        ).fetchone()
        assert row[0] == 0

    def test_boolean_defaults(self, client_db):
        eid = _insert_entity(client_db)
        _insert_field(client_db, eid)
        row = client_db.execute(
            "SELECT is_required, read_only, audited, is_sorted, display_as_label "
            "FROM Field WHERE entity_id = ?",
            (eid,),
        ).fetchone()
        assert row == (0, 0, 0, 0, 0)


class TestFieldOptionTable:
    def test_create_option(self, client_db):
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        client_db.execute(
            "INSERT INTO FieldOption (field_id, value, label) "
            "VALUES (?, 'Active', 'Active')",
            (fid,),
        )
        client_db.commit()

    def test_field_id_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO FieldOption (field_id, value, label) "
                "VALUES (9999, 'Active', 'Active')"
            )

    def test_style_check_valid(self, client_db):
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        for i, style in enumerate(
            ["default", "primary", "success", "danger", "warning", "info"]
        ):
            client_db.execute(
                "INSERT INTO FieldOption (field_id, value, label, style) "
                "VALUES (?, ?, ?, ?)",
                (fid, f"val{i}", f"Label{i}", style),
            )
        client_db.commit()

    def test_style_check_rejects_invalid(self, client_db):
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO FieldOption (field_id, value, label, style) "
                "VALUES (?, 'v', 'L', 'neon')",
                (fid,),
            )

    def test_style_null_allowed(self, client_db):
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        client_db.execute(
            "INSERT INTO FieldOption (field_id, value, label, style) "
            "VALUES (?, 'v', 'L', NULL)",
            (fid,),
        )
        client_db.commit()


class TestRelationshipTable:
    def test_create_relationship(self, client_db):
        e1 = _insert_entity(client_db, "Contact", "CON", "Person", True)
        e2 = _insert_entity(client_db, "Dues", "DUE", "Base", False)
        client_db.execute(
            "INSERT INTO Relationship (name, description, entity_id, "
            "entity_foreign_id, link_type, link, link_foreign, label, "
            "label_foreign) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("duesToMentor", "Dues owed by mentor", e1, e2,
             "oneToMany", "dues", "mentor", "Dues", "Mentor"),
        )
        client_db.commit()

    def test_link_type_check(self, client_db):
        e1 = _insert_entity(client_db, "A", "A", "Base", False)
        e2 = _insert_entity(client_db, "B", "B", "Base", False)
        for lt in ("oneToMany", "manyToOne", "manyToMany"):
            client_db.execute(
                "INSERT INTO Relationship (name, description, entity_id, "
                "entity_foreign_id, link_type, link, link_foreign, label, "
                "label_foreign) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"r_{lt}", "desc", e1, e2, lt, f"l_{lt}", f"lf_{lt}",
                 "Lab", "LabF"),
            )
        client_db.commit()

    def test_link_type_check_rejects_invalid(self, client_db):
        e1 = _insert_entity(client_db, "A", "A", "Base", False)
        e2 = _insert_entity(client_db, "B", "B", "Base", False)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Relationship (name, description, entity_id, "
                "entity_foreign_id, link_type, link, link_foreign, label, "
                "label_foreign) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("bad", "desc", e1, e2, "badType", "l", "lf", "L", "LF"),
            )

    def test_entity_fk_rejects_invalid(self, client_db):
        e1 = _insert_entity(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Relationship (name, description, entity_id, "
                "entity_foreign_id, link_type, link, link_foreign, label, "
                "label_foreign) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                ("bad", "desc", e1, 9999, "oneToMany", "l", "lf", "L", "LF"),
            )


class TestPersonaTable:
    def test_create_persona(self, client_db):
        _insert_persona(client_db)
        row = client_db.execute(
            "SELECT name, code FROM Persona WHERE code = 'MENTOR'"
        ).fetchone()
        assert row == ("Volunteer Mentor", "MENTOR")

    def test_code_unique(self, client_db):
        _insert_persona(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_persona(client_db, "Other Mentor", "MENTOR")

    def test_entity_field_fks(self, client_db):
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        client_db.execute(
            "INSERT INTO Persona (name, code, persona_entity_id, "
            "persona_field_id, persona_field_value) "
            "VALUES ('Mentor', 'MTR', ?, ?, 'Mentor')",
            (eid, fid),
        )
        client_db.commit()

    def test_entity_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Persona (name, code, persona_entity_id) "
                "VALUES ('Bad', 'BAD', 9999)"
            )


class TestBusinessObjectTable:
    def test_create_business_object(self, client_db):
        client_db.execute(
            "INSERT INTO BusinessObject (name, status) "
            "VALUES ('Prospect', 'unclassified')"
        )
        client_db.commit()

    def test_status_check(self, client_db):
        for status in ("unclassified", "classified", "excluded"):
            client_db.execute(
                "INSERT INTO BusinessObject (name, status) VALUES (?, ?)",
                (f"BO_{status}", status),
            )
        client_db.commit()

    def test_status_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO BusinessObject (name, status) "
                "VALUES ('Bad', 'invalid')"
            )

    def test_resolution_check(self, client_db):
        valid_resolutions = [
            "entity", "process", "persona", "field_value",
            "lifecycle_state", "relationship",
        ]
        for res in valid_resolutions:
            client_db.execute(
                "INSERT INTO BusinessObject (name, status, resolution) "
                "VALUES (?, 'classified', ?)",
                (f"BO_{res}", res),
            )
        client_db.commit()

    def test_resolution_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO BusinessObject (name, status, resolution) "
                "VALUES ('Bad', 'classified', 'invalid_res')"
            )

    def test_resolution_null_allowed(self, client_db):
        client_db.execute(
            "INSERT INTO BusinessObject (name, status, resolution) "
            "VALUES ('Unclass', 'unclassified', NULL)"
        )
        client_db.commit()


class TestProcessTable:
    def test_create_process(self, client_db):
        did = _insert_domain(client_db)
        _insert_process(client_db, did)
        row = client_db.execute(
            "SELECT name, code FROM Process WHERE code = 'MN-INTAKE'"
        ).fetchone()
        assert row == ("Client Intake", "MN-INTAKE")

    def test_domain_id_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Process (domain_id, name, code, sort_order) "
                "VALUES (9999, 'Bad', 'BAD', 1)"
            )

    def test_code_unique(self, client_db):
        did = _insert_domain(client_db)
        _insert_process(client_db, did)
        with pytest.raises(sqlite3.IntegrityError):
            _insert_process(client_db, did, "Other", "MN-INTAKE", 2)

    def test_tier_check(self, client_db):
        did = _insert_domain(client_db)
        for i, tier in enumerate(["core", "important", "enhancement"]):
            client_db.execute(
                "INSERT INTO Process (domain_id, name, code, sort_order, tier) "
                "VALUES (?, ?, ?, ?, ?)",
                (did, f"P{i}", f"MN-P{i}", i + 1, tier),
            )
        client_db.commit()

    def test_tier_check_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Process (domain_id, name, code, sort_order, tier) "
                "VALUES (?, 'Bad', 'BAD', 1, 'critical')",
                (did,),
            )

    def test_tier_null_allowed(self, client_db):
        did = _insert_domain(client_db)
        client_db.execute(
            "INSERT INTO Process (domain_id, name, code, sort_order, tier) "
            "VALUES (?, 'P', 'MN-P', 1, NULL)",
            (did,),
        )
        client_db.commit()


class TestProcessStepTable:
    def test_create_step(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        client_db.execute(
            "INSERT INTO ProcessStep (process_id, name, step_type, sort_order) "
            "VALUES (?, 'Submit Form', 'action', 1)",
            (pid,),
        )
        client_db.commit()

    def test_step_type_check(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        for i, st in enumerate(["action", "decision", "system", "notification"]):
            client_db.execute(
                "INSERT INTO ProcessStep (process_id, name, step_type, sort_order) "
                "VALUES (?, ?, ?, ?)",
                (pid, f"Step{i}", st, i + 1),
            )
        client_db.commit()

    def test_step_type_check_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessStep (process_id, name, step_type, sort_order) "
                "VALUES (?, 'Bad', 'invalid', 1)",
                (pid,),
            )

    def test_process_id_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessStep (process_id, name, step_type, sort_order) "
                "VALUES (9999, 'Bad', 'action', 1)"
            )


class TestRequirementTable:
    def test_create_requirement(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        client_db.execute(
            "INSERT INTO Requirement (identifier, process_id, description, status) "
            "VALUES ('MN-INTAKE-REQ-001', ?, 'Must track intake', 'proposed')",
            (pid,),
        )
        client_db.commit()

    def test_identifier_unique(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        client_db.execute(
            "INSERT INTO Requirement (identifier, process_id, description, status) "
            "VALUES ('REQ-001', ?, 'First', 'proposed')",
            (pid,),
        )
        client_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Requirement (identifier, process_id, description, status) "
                "VALUES ('REQ-001', ?, 'Second', 'proposed')",
                (pid,),
            )

    def test_status_check(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        for i, status in enumerate(["proposed", "approved", "deferred", "removed"]):
            client_db.execute(
                "INSERT INTO Requirement (identifier, process_id, description, status) "
                "VALUES (?, ?, ?, ?)",
                (f"REQ-{i:03d}", pid, f"Req {i}", status),
            )
        client_db.commit()

    def test_status_check_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Requirement (identifier, process_id, description, status) "
                "VALUES ('REQ-BAD', ?, 'Bad', 'invalid')",
                (pid,),
            )

    def test_priority_check(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        for i, pri in enumerate(["must", "should", "may"]):
            client_db.execute(
                "INSERT INTO Requirement (identifier, process_id, description, "
                "status, priority) VALUES (?, ?, ?, 'proposed', ?)",
                (f"REQ-P{i}", pid, f"Req {i}", pri),
            )
        client_db.commit()

    def test_priority_check_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Requirement (identifier, process_id, description, "
                "status, priority) VALUES ('REQ-BAD', ?, 'Bad', 'proposed', 'critical')",
                (pid,),
            )


# ===== Cross-Reference Layer =====


class TestProcessEntityTable:
    def test_create_cross_ref(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        eid = _insert_entity(client_db)
        client_db.execute(
            "INSERT INTO ProcessEntity (process_id, entity_id, role) "
            "VALUES (?, ?, 'primary')",
            (pid, eid),
        )
        client_db.commit()

    def test_role_check(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        eid = _insert_entity(client_db)
        for role in ("primary", "referenced", "created", "updated"):
            client_db.execute(
                "INSERT INTO ProcessEntity (process_id, entity_id, role) "
                "VALUES (?, ?, ?)",
                (pid, eid, role),
            )
        client_db.commit()

    def test_role_check_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        eid = _insert_entity(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessEntity (process_id, entity_id, role) "
                "VALUES (?, ?, 'invalid')",
                (pid, eid),
            )

    def test_process_fk_rejects_invalid(self, client_db):
        eid = _insert_entity(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessEntity (process_id, entity_id, role) "
                "VALUES (9999, ?, 'primary')",
                (eid,),
            )

    def test_entity_fk_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessEntity (process_id, entity_id, role) "
                "VALUES (?, 9999, 'primary')",
                (pid,),
            )


class TestProcessFieldTable:
    def test_create_cross_ref(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        client_db.execute(
            "INSERT INTO ProcessField (process_id, field_id, usage) "
            "VALUES (?, ?, 'collected')",
            (pid, fid),
        )
        client_db.commit()

    def test_usage_check(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        for usage in ("collected", "displayed", "updated", "evaluated",
                       "filtered", "calculated"):
            client_db.execute(
                "INSERT INTO ProcessField (process_id, field_id, usage) "
                "VALUES (?, ?, ?)",
                (pid, fid, usage),
            )
        client_db.commit()

    def test_usage_check_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessField (process_id, field_id, usage) "
                "VALUES (?, ?, 'invalid')",
                (pid, fid),
            )

    def test_field_fk_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessField (process_id, field_id, usage) "
                "VALUES (?, 9999, 'collected')",
                (pid,),
            )


class TestProcessPersonaTable:
    def test_create_cross_ref(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        persona_id = _insert_persona(client_db)
        client_db.execute(
            "INSERT INTO ProcessPersona (process_id, persona_id, role) "
            "VALUES (?, ?, 'performer')",
            (pid, persona_id),
        )
        client_db.commit()

    def test_role_check(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        persona_id = _insert_persona(client_db)
        for role in ("initiator", "performer", "approver", "recipient", "observer"):
            client_db.execute(
                "INSERT INTO ProcessPersona (process_id, persona_id, role) "
                "VALUES (?, ?, ?)",
                (pid, persona_id, role),
            )
        client_db.commit()

    def test_role_check_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        persona_id = _insert_persona(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessPersona (process_id, persona_id, role) "
                "VALUES (?, ?, 'invalid')",
                (pid, persona_id),
            )

    def test_persona_fk_rejects_invalid(self, client_db):
        did = _insert_domain(client_db)
        pid = _insert_process(client_db, did)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ProcessPersona (process_id, persona_id, role) "
                "VALUES (?, 9999, 'performer')",
                (pid,),
            )


# ===== Management Layer =====


class TestDecisionTable:
    def test_create_decision(self, client_db):
        wi_id = _insert_work_item(client_db)
        sess_id = _insert_ai_session(client_db, wi_id)
        client_db.execute(
            "INSERT INTO Decision (identifier, title, description, status, "
            "created_by_session_id) VALUES ('DEC-001', 'Test', 'Rationale', "
            "'proposed', ?)",
            (sess_id,),
        )
        client_db.commit()

    def test_identifier_unique(self, client_db):
        client_db.execute(
            "INSERT INTO Decision (identifier, title, description, status) "
            "VALUES ('DEC-001', 'A', 'B', 'proposed')"
        )
        client_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Decision (identifier, title, description, status) "
                "VALUES ('DEC-001', 'C', 'D', 'proposed')"
            )

    def test_status_check(self, client_db):
        for i, status in enumerate(["proposed", "locked", "superseded"]):
            client_db.execute(
                "INSERT INTO Decision (identifier, title, description, status) "
                "VALUES (?, ?, 'desc', ?)",
                (f"DEC-{i:03d}", f"Title {i}", status),
            )
        client_db.commit()

    def test_status_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Decision (identifier, title, description, status) "
                "VALUES ('DEC-BAD', 'T', 'D', 'invalid')"
            )

    def test_scope_fks(self, client_db):
        did = _insert_domain(client_db)
        eid = _insert_entity(client_db)
        client_db.execute(
            "INSERT INTO Decision (identifier, title, description, status, "
            "domain_id, entity_id) VALUES ('DEC-001', 'T', 'D', 'proposed', ?, ?)",
            (did, eid),
        )
        client_db.commit()

    def test_superseded_by_fk(self, client_db):
        client_db.execute(
            "INSERT INTO Decision (identifier, title, description, status) "
            "VALUES ('DEC-001', 'Old', 'D', 'proposed')"
        )
        client_db.commit()
        old_id = client_db.execute(
            "SELECT id FROM Decision WHERE identifier = 'DEC-001'"
        ).fetchone()[0]
        client_db.execute(
            "INSERT INTO Decision (identifier, title, description, status) "
            "VALUES ('DEC-002', 'New', 'D', 'proposed')"
        )
        client_db.commit()
        new_id = client_db.execute(
            "SELECT id FROM Decision WHERE identifier = 'DEC-002'"
        ).fetchone()[0]
        client_db.execute(
            "UPDATE Decision SET status = 'superseded', superseded_by_id = ? "
            "WHERE id = ?",
            (new_id, old_id),
        )
        client_db.commit()


class TestOpenIssueTable:
    def test_create_open_issue(self, client_db):
        client_db.execute(
            "INSERT INTO OpenIssue (identifier, title, description, status) "
            "VALUES ('ISS-001', 'Test issue', 'Details', 'open')"
        )
        client_db.commit()

    def test_identifier_unique(self, client_db):
        client_db.execute(
            "INSERT INTO OpenIssue (identifier, title, description, status) "
            "VALUES ('ISS-001', 'A', 'B', 'open')"
        )
        client_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO OpenIssue (identifier, title, description, status) "
                "VALUES ('ISS-001', 'C', 'D', 'open')"
            )

    def test_status_check(self, client_db):
        for i, status in enumerate(["open", "resolved", "deferred"]):
            client_db.execute(
                "INSERT INTO OpenIssue (identifier, title, description, status) "
                "VALUES (?, ?, 'desc', ?)",
                (f"ISS-{i:03d}", f"Title {i}", status),
            )
        client_db.commit()

    def test_status_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO OpenIssue (identifier, title, description, status) "
                "VALUES ('ISS-BAD', 'T', 'D', 'invalid')"
            )

    def test_priority_check(self, client_db):
        for i, pri in enumerate(["high", "medium", "low"]):
            client_db.execute(
                "INSERT INTO OpenIssue (identifier, title, description, status, priority) "
                "VALUES (?, ?, 'desc', 'open', ?)",
                (f"ISS-P{i}", f"Title {i}", pri),
            )
        client_db.commit()

    def test_priority_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO OpenIssue (identifier, title, description, status, priority) "
                "VALUES ('ISS-BAD', 'T', 'D', 'open', 'critical')"
            )

    def test_priority_null_allowed(self, client_db):
        client_db.execute(
            "INSERT INTO OpenIssue (identifier, title, description, status, priority) "
            "VALUES ('ISS-N', 'T', 'D', 'open', NULL)"
        )
        client_db.commit()


class TestWorkItemTable:
    def test_create_work_item(self, client_db):
        wi_id = _insert_work_item(client_db)
        row = client_db.execute(
            "SELECT item_type, status FROM WorkItem WHERE id = ?",
            (wi_id,),
        ).fetchone()
        assert row == ("master_prd", "not_started")

    def test_item_type_check_all_valid(self, client_db):
        valid_types = [
            "master_prd", "business_object_discovery", "entity_prd",
            "domain_overview", "process_definition", "domain_reconciliation",
            "stakeholder_review", "yaml_generation", "crm_selection",
            "crm_deployment", "crm_configuration", "verification",
        ]
        for it in valid_types:
            _insert_work_item(client_db, item_type=it)

    def test_item_type_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            _insert_work_item(client_db, item_type="invalid_type")

    def test_status_check(self, client_db):
        for status in ("not_started", "ready", "in_progress", "complete", "blocked"):
            _insert_work_item(client_db, status=status)

    def test_status_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            _insert_work_item(client_db, status="invalid")

    def test_status_before_blocked_check(self, client_db):
        for sbb in ("not_started", "ready", "in_progress", "complete"):
            client_db.execute(
                "INSERT INTO WorkItem (item_type, status, "
                "status_before_blocked) VALUES ('master_prd', "
                "'blocked', ?)",
                (sbb,),
            )
        client_db.commit()

    def test_status_before_blocked_null_allowed(self, client_db):
        client_db.execute(
            "INSERT INTO WorkItem (item_type, status, "
            "status_before_blocked) VALUES ('master_prd', "
            "'not_started', NULL)"
        )
        client_db.commit()

    def test_status_before_blocked_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO WorkItem (item_type, status, "
                "status_before_blocked) VALUES ('master_prd', "
                "'blocked', 'invalid')"
            )

    def test_domain_fk(self, client_db):
        did = _insert_domain(client_db)
        _insert_work_item(
            client_db, item_type="domain_overview",
            domain_id=did,
        )

    def test_domain_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            _insert_work_item(
                client_db, item_type="domain_overview",
                domain_id=9999,
            )


class TestDependencyTable:
    def test_create_dependency(self, client_db):
        wi1 = _insert_work_item(client_db)
        wi2 = _insert_work_item(
            client_db, item_type="business_object_discovery",
        )
        client_db.execute(
            "INSERT INTO Dependency (work_item_id, depends_on_id) VALUES (?, ?)",
            (wi2, wi1),
        )
        client_db.commit()

    def test_unique_constraint(self, client_db):
        wi1 = _insert_work_item(client_db)
        wi2 = _insert_work_item(
            client_db, item_type="business_object_discovery",
        )
        client_db.execute(
            "INSERT INTO Dependency (work_item_id, depends_on_id) VALUES (?, ?)",
            (wi2, wi1),
        )
        client_db.commit()
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Dependency (work_item_id, depends_on_id) "
                "VALUES (?, ?)",
                (wi2, wi1),
            )

    def test_work_item_fk_rejects_invalid(self, client_db):
        wi1 = _insert_work_item(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Dependency (work_item_id, depends_on_id) "
                "VALUES (9999, ?)",
                (wi1,),
            )

    def test_depends_on_fk_rejects_invalid(self, client_db):
        wi1 = _insert_work_item(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO Dependency (work_item_id, depends_on_id) "
                "VALUES (?, 9999)",
                (wi1,),
            )


# ===== Audit Layer =====


class TestAISessionTable:
    def test_create_session(self, client_db):
        wi_id = _insert_work_item(client_db)
        sess_id = _insert_ai_session(client_db, wi_id)
        assert sess_id is not None

    def test_session_type_check(self, client_db):
        wi_id = _insert_work_item(client_db)
        for st in ("initial", "revision", "clarification"):
            _insert_ai_session(client_db, wi_id, session_type=st)

    def test_session_type_check_rejects_invalid(self, client_db):
        wi_id = _insert_work_item(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO AISession (work_item_id, session_type, "
                "generated_prompt, import_status, started_at) "
                "VALUES (?, 'invalid', 'prompt', 'pending', ?)",
                (wi_id, datetime.now().isoformat()),
            )

    def test_import_status_check(self, client_db):
        wi_id = _insert_work_item(client_db)
        for status in ("pending", "imported", "partial", "rejected"):
            _insert_ai_session(client_db, wi_id, import_status=status)

    def test_import_status_check_rejects_invalid(self, client_db):
        wi_id = _insert_work_item(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO AISession (work_item_id, session_type, "
                "generated_prompt, import_status, started_at) "
                "VALUES (?, 'initial', 'prompt', 'invalid', ?)",
                (wi_id, datetime.now().isoformat()),
            )

    def test_work_item_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO AISession (work_item_id, session_type, "
                "generated_prompt, import_status, started_at) "
                "VALUES (9999, 'initial', 'prompt', 'pending', ?)",
                (datetime.now().isoformat(),),
            )


class TestChangeLogTable:
    def test_create_change_log(self, client_db):
        client_db.execute(
            "INSERT INTO ChangeLog (table_name, record_id, change_type, "
            "changed_at) VALUES ('field', 1, 'insert', ?)",
            (datetime.now().isoformat(),),
        )
        client_db.commit()

    def test_change_type_check(self, client_db):
        for ct in ("insert", "update", "delete"):
            client_db.execute(
                "INSERT INTO ChangeLog (table_name, record_id, change_type, "
                "changed_at) VALUES ('entity', 1, ?, ?)",
                (ct, datetime.now().isoformat()),
            )
        client_db.commit()

    def test_change_type_check_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ChangeLog (table_name, record_id, change_type, "
                "changed_at) VALUES ('entity', 1, 'invalid', ?)",
                (datetime.now().isoformat(),),
            )

    def test_session_id_nullable(self, client_db):
        client_db.execute(
            "INSERT INTO ChangeLog (session_id, table_name, record_id, "
            "change_type, changed_at) VALUES (NULL, 'entity', 1, 'update', ?)",
            (datetime.now().isoformat(),),
        )
        client_db.commit()


class TestChangeImpactTable:
    def test_create_change_impact(self, client_db):
        client_db.execute(
            "INSERT INTO ChangeLog (table_name, record_id, change_type, "
            "changed_at) VALUES ('field', 1, 'update', ?)",
            (datetime.now().isoformat(),),
        )
        client_db.commit()
        cl_id = client_db.execute(
            "SELECT id FROM ChangeLog LIMIT 1"
        ).fetchone()[0]
        client_db.execute(
            "INSERT INTO ChangeImpact (change_log_id, affected_table, "
            "affected_record_id) VALUES (?, 'process', 5)",
            (cl_id,),
        )
        client_db.commit()

    def test_change_log_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ChangeImpact (change_log_id, affected_table, "
                "affected_record_id) VALUES (9999, 'process', 5)"
            )

    def test_defaults(self, client_db):
        client_db.execute(
            "INSERT INTO ChangeLog (table_name, record_id, change_type, "
            "changed_at) VALUES ('field', 1, 'update', ?)",
            (datetime.now().isoformat(),),
        )
        client_db.commit()
        cl_id = client_db.execute("SELECT id FROM ChangeLog LIMIT 1").fetchone()[0]
        client_db.execute(
            "INSERT INTO ChangeImpact (change_log_id, affected_table, "
            "affected_record_id) VALUES (?, 'process', 5)",
            (cl_id,),
        )
        client_db.commit()
        row = client_db.execute(
            "SELECT requires_review, reviewed FROM ChangeImpact LIMIT 1"
        ).fetchone()
        assert row == (1, 0)


class TestGenerationLogTable:
    def test_create_generation_log(self, client_db):
        wi_id = _insert_work_item(client_db)
        client_db.execute(
            "INSERT INTO GenerationLog (work_item_id, document_type, "
            "file_path, generated_at, generation_mode) "
            "VALUES (?, 'master_prd', 'docs/master.docx', ?, 'final')",
            (wi_id, datetime.now().isoformat()),
        )
        client_db.commit()

    def test_document_type_check(self, client_db):
        wi_id = _insert_work_item(client_db)
        valid_types = [
            "master_prd", "entity_inventory", "entity_prd", "domain_overview",
            "process_document", "domain_prd", "yaml_program_files",
            "crm_evaluation_report",
        ]
        for dt in valid_types:
            client_db.execute(
                "INSERT INTO GenerationLog (work_item_id, document_type, "
                "file_path, generated_at, generation_mode) "
                "VALUES (?, ?, ?, ?, 'final')",
                (wi_id, dt, f"docs/{dt}.docx", datetime.now().isoformat()),
            )
        client_db.commit()

    def test_document_type_check_rejects_invalid(self, client_db):
        wi_id = _insert_work_item(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO GenerationLog (work_item_id, document_type, "
                "file_path, generated_at, generation_mode) "
                "VALUES (?, 'invalid', 'x.docx', ?, 'final')",
                (wi_id, datetime.now().isoformat()),
            )

    def test_generation_mode_check(self, client_db):
        wi_id = _insert_work_item(client_db)
        for mode in ("final", "draft"):
            client_db.execute(
                "INSERT INTO GenerationLog (work_item_id, document_type, "
                "file_path, generated_at, generation_mode) "
                "VALUES (?, 'master_prd', ?, ?, ?)",
                (wi_id, f"docs/{mode}.docx", datetime.now().isoformat(), mode),
            )
        client_db.commit()

    def test_generation_mode_check_rejects_invalid(self, client_db):
        wi_id = _insert_work_item(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO GenerationLog (work_item_id, document_type, "
                "file_path, generated_at, generation_mode) "
                "VALUES (?, 'master_prd', 'x.docx', ?, 'invalid')",
                (wi_id, datetime.now().isoformat()),
            )

    def test_work_item_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO GenerationLog (work_item_id, document_type, "
                "file_path, generated_at, generation_mode) "
                "VALUES (9999, 'master_prd', 'x.docx', ?, 'final')",
                (datetime.now().isoformat(),),
            )


# ===== Layout Layer =====


class TestLayoutPanelTable:
    def test_create_panel(self, client_db):
        eid = _insert_entity(client_db)
        client_db.execute(
            "INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode) "
            "VALUES (?, 'Overview', 1, 'rows')",
            (eid,),
        )
        client_db.commit()

    def test_layout_mode_check(self, client_db):
        eid = _insert_entity(client_db)
        for mode in ("rows", "tabs"):
            client_db.execute(
                "INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode) "
                "VALUES (?, ?, 1, ?)",
                (eid, f"Panel_{mode}", mode),
            )
        client_db.commit()

    def test_layout_mode_check_rejects_invalid(self, client_db):
        eid = _insert_entity(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode) "
                "VALUES (?, 'Bad', 1, 'invalid')",
                (eid,),
            )

    def test_style_check(self, client_db):
        eid = _insert_entity(client_db)
        for i, style in enumerate(
            ["default", "primary", "success", "danger", "warning", "info"]
        ):
            client_db.execute(
                "INSERT INTO LayoutPanel (entity_id, label, sort_order, "
                "layout_mode, style) VALUES (?, ?, ?, 'rows', ?)",
                (eid, f"Panel_{i}", i + 1, style),
            )
        client_db.commit()

    def test_style_check_rejects_invalid(self, client_db):
        eid = _insert_entity(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO LayoutPanel (entity_id, label, sort_order, "
                "layout_mode, style) VALUES (?, 'Bad', 1, 'rows', 'neon')",
                (eid,),
            )

    def test_entity_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode) "
                "VALUES (9999, 'Bad', 1, 'rows')"
            )


class TestLayoutRowTable:
    def _make_panel(self, client_db):
        eid = _insert_entity(client_db)
        client_db.execute(
            "INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode) "
            "VALUES (?, 'Test', 1, 'rows')",
            (eid,),
        )
        client_db.commit()
        panel_id = client_db.execute(
            "SELECT id FROM LayoutPanel LIMIT 1"
        ).fetchone()[0]
        fid1 = _insert_field(client_db, eid, "f1", "Field 1", "varchar")
        fid2 = _insert_field(client_db, eid, "f2", "Field 2", "varchar")
        return panel_id, eid, fid1, fid2

    def test_create_row_two_fields(self, client_db):
        panel_id, eid, fid1, fid2 = self._make_panel(client_db)
        client_db.execute(
            "INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id, "
            "cell_2_field_id) VALUES (?, 1, ?, ?)",
            (panel_id, fid1, fid2),
        )
        client_db.commit()

    def test_create_row_one_field(self, client_db):
        panel_id, eid, fid1, fid2 = self._make_panel(client_db)
        client_db.execute(
            "INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id) "
            "VALUES (?, 1, ?)",
            (panel_id, fid1),
        )
        client_db.commit()

    def test_at_least_one_cell_check_rejects_both_null(self, client_db):
        panel_id, eid, fid1, fid2 = self._make_panel(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id, "
                "cell_2_field_id) VALUES (?, 1, NULL, NULL)",
                (panel_id,),
            )

    def test_panel_fk_rejects_invalid(self, client_db):
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id) "
                "VALUES (9999, 1, ?)",
                (fid,),
            )

    def test_field_fk_rejects_invalid(self, client_db):
        panel_id, eid, fid1, fid2 = self._make_panel(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id) "
                "VALUES (?, 1, 9999)",
                (panel_id,),
            )


class TestLayoutTabTable:
    def test_create_tab(self, client_db):
        eid = _insert_entity(client_db)
        client_db.execute(
            "INSERT INTO LayoutPanel (entity_id, label, sort_order, layout_mode) "
            "VALUES (?, 'Tabs', 1, 'tabs')",
            (eid,),
        )
        client_db.commit()
        panel_id = client_db.execute(
            "SELECT id FROM LayoutPanel LIMIT 1"
        ).fetchone()[0]
        client_db.execute(
            "INSERT INTO LayoutTab (panel_id, label, category, sort_order) "
            "VALUES (?, 'Status', 'status', 1)",
            (panel_id,),
        )
        client_db.commit()

    def test_panel_fk_rejects_invalid(self, client_db):
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO LayoutTab (panel_id, label, category, sort_order) "
                "VALUES (9999, 'Bad', 'bad', 1)"
            )


class TestListColumnTable:
    def test_create_list_column(self, client_db):
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        client_db.execute(
            "INSERT INTO ListColumn (entity_id, field_id, sort_order) "
            "VALUES (?, ?, 1)",
            (eid, fid),
        )
        client_db.commit()

    def test_entity_fk_rejects_invalid(self, client_db):
        eid = _insert_entity(client_db)
        fid = _insert_field(client_db, eid)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ListColumn (entity_id, field_id, sort_order) "
                "VALUES (9999, ?, 1)",
                (fid,),
            )

    def test_field_fk_rejects_invalid(self, client_db):
        eid = _insert_entity(client_db)
        with pytest.raises(sqlite3.IntegrityError):
            client_db.execute(
                "INSERT INTO ListColumn (entity_id, field_id, sort_order) "
                "VALUES (?, 9999, 1)",
                (eid,),
            )


# ===== Cross-cutting =====


class TestAllTablesExist:
    """Verify every expected table exists in the schema."""

    EXPECTED_TABLES = sorted([
        "Domain", "Entity", "Field", "FieldOption", "Relationship",
        "Persona", "BusinessObject", "Process", "ProcessStep", "Requirement",
        "ProcessEntity", "ProcessField", "ProcessPersona",
        "Decision", "OpenIssue", "WorkItem", "Dependency",
        "AISession", "ChangeLog", "ChangeImpact", "GenerationLog",
        "LayoutPanel", "LayoutRow", "LayoutTab", "ListColumn",
        "Instance", "DeploymentRun",
        "InstanceDeployConfig",
    ])

    def test_all_tables_present(self, client_db):
        rows = client_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'schema_version' "
            "ORDER BY name"
        ).fetchall()
        actual = sorted(r[0] for r in rows)
        assert actual == self.EXPECTED_TABLES

    def test_table_count(self, client_db):
        rows = client_db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'schema_version'"
        ).fetchone()
        assert rows[0] == 28
