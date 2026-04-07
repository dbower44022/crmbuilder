"""Tests for automation.importer.identifiers — identifier validation."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.identifiers import (
    check_uniqueness,
    validate_format,
    validate_process_code_prefix,
)
from automation.importer.proposed import ProposedBatch, ProposedRecord


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _rec(table, values, action="create", target_id=None, batch_id=None):
    return ProposedRecord(
        table_name=table, action=action, target_id=target_id,
        values=values, source_payload_path=f"test.{table}",
        batch_id=batch_id,
    )


def _batch(records):
    return ProposedBatch(
        records=records, ai_session_id=1, work_item_id=1,
        session_type="initial",
    )


# ===========================================================================
# Format validation
# ===========================================================================

class TestFormatValidation:
    def test_valid_domain_code(self):
        rec = _rec("Domain", {"code": "MN"})
        assert validate_format(rec) == []

    def test_valid_domain_code_4_chars(self):
        rec = _rec("Domain", {"code": "MENT"})
        assert validate_format(rec) == []

    def test_invalid_domain_code_lowercase(self):
        rec = _rec("Domain", {"code": "mn"})
        conflicts = validate_format(rec)
        assert len(conflicts) == 1
        assert conflicts[0].severity == "warning"
        assert conflicts[0].conflict_type == "format_violation"

    def test_invalid_domain_code_too_long(self):
        rec = _rec("Domain", {"code": "ABCDE"})
        conflicts = validate_format(rec)
        assert len(conflicts) == 1

    def test_valid_entity_code(self):
        rec = _rec("Entity", {"code": "CON"})
        assert validate_format(rec) == []

    def test_invalid_entity_code_numbers(self):
        rec = _rec("Entity", {"code": "CON1"})
        conflicts = validate_format(rec)
        assert len(conflicts) == 1

    def test_valid_persona_code(self):
        rec = _rec("Persona", {"code": "VOL"})
        assert validate_format(rec) == []

    def test_valid_process_code(self):
        rec = _rec("Process", {"code": "MN-INTAKE"})
        assert validate_format(rec) == []

    def test_invalid_process_code(self):
        rec = _rec("Process", {"code": "intake"})
        conflicts = validate_format(rec)
        assert len(conflicts) == 1

    def test_valid_requirement_id(self):
        rec = _rec("Requirement", {"identifier": "MN-INTAKE-REQ-001"})
        assert validate_format(rec) == []

    def test_invalid_requirement_id(self):
        rec = _rec("Requirement", {"identifier": "REQ-001"})
        conflicts = validate_format(rec)
        assert len(conflicts) == 1

    def test_valid_decision_id(self):
        rec = _rec("Decision", {"identifier": "MN-DEC-001"})
        assert validate_format(rec) == []

    def test_valid_open_issue_id(self):
        rec = _rec("OpenIssue", {"identifier": "MN-ISS-001"})
        assert validate_format(rec) == []

    def test_open_issue_oi_format(self):
        rec = _rec("OpenIssue", {"identifier": "MN-OI-001"})
        assert validate_format(rec) == []

    def test_no_identifier_column(self):
        """Tables without identifier columns return no conflicts."""
        rec = _rec("Field", {"name": "status"})
        assert validate_format(rec) == []

    def test_no_value_for_identifier(self):
        rec = _rec("Domain", {})
        assert validate_format(rec) == []


# ===========================================================================
# Process code prefix
# ===========================================================================

class TestProcessCodePrefix:
    def test_matching_prefix(self):
        rec = _rec("Process", {"code": "MN-INTAKE"})
        assert validate_process_code_prefix(rec, "MN") == []

    def test_mismatched_prefix(self):
        rec = _rec("Process", {"code": "ED-INTAKE"})
        conflicts = validate_process_code_prefix(rec, "MN")
        assert len(conflicts) == 1
        assert conflicts[0].severity == "warning"

    def test_no_domain_code(self):
        rec = _rec("Process", {"code": "MN-INTAKE"})
        assert validate_process_code_prefix(rec, None) == []

    def test_not_a_process(self):
        rec = _rec("Domain", {"code": "MN"})
        assert validate_process_code_prefix(rec, "MN") == []


# ===========================================================================
# Uniqueness
# ===========================================================================

class TestUniqueness:
    def test_no_conflict_empty_db(self, conn):
        rec = _rec("Domain", {"code": "MN"})
        batch = _batch([rec])
        assert check_uniqueness(conn, rec, batch) == []

    def test_conflict_existing_record(self, conn):
        # Seed a session for created_by_session_id FK
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'ready')"
        )
        conn.execute(
            "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
            "import_status, started_at) VALUES (1, 'initial', 'p', 'pending', "
            "CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO Domain (name, code, sort_order) VALUES ('Mentoring', 'MN', 1)"
        )
        conn.commit()

        rec = _rec("Domain", {"code": "MN"})
        batch = _batch([rec])
        conflicts = check_uniqueness(conn, rec, batch)
        assert len(conflicts) == 1
        assert conflicts[0].severity == "error"
        assert conflicts[0].conflict_type == "identifier_uniqueness"

    def test_update_excludes_self(self, conn):
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'ready')"
        )
        conn.execute(
            "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
            "import_status, started_at) VALUES (1, 'initial', 'p', 'pending', "
            "CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "INSERT INTO Domain (name, code, sort_order) VALUES ('Mentoring', 'MN', 1)"
        )
        conn.commit()

        rec = _rec("Domain", {"code": "MN", "name": "Updated"},
                    action="update", target_id=1)
        batch = _batch([rec])
        conflicts = check_uniqueness(conn, rec, batch)
        assert len(conflicts) == 0

    def test_intra_batch_conflict(self, conn):
        rec1 = _rec("Domain", {"code": "MN"})
        rec2 = _rec("Domain", {"code": "MN"})
        rec2.source_payload_path = "test.Domain[1]"
        batch = _batch([rec1, rec2])
        conflicts = check_uniqueness(conn, rec1, batch)
        assert len(conflicts) == 1
        assert "also proposed" in conflicts[0].message

    def test_table_without_id_column(self, conn):
        rec = _rec("Field", {"name": "status"})
        batch = _batch([rec])
        assert check_uniqueness(conn, rec, batch) == []
