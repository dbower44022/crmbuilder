"""Tests for automation.importer.conflicts — conflict detection."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.conflicts import detect_conflicts
from automation.importer.proposed import ProposedBatch, ProposedRecord


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    c.execute("INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'complete')")
    c.execute(
        "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (1, 'initial', 'p', 'imported', CURRENT_TIMESTAMP)"
    )
    c.execute("INSERT INTO Domain (name, code, sort_order) VALUES ('Mentoring', 'MN', 1)")
    c.execute(
        "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
        "VALUES ('Contact', 'CON', 'Person', 1, 1)"
    )
    c.execute(
        "INSERT INTO Field (entity_id, name, label, field_type) "
        "VALUES (1, 'contactType', 'Contact Type', 'enum')"
    )
    c.execute(
        "INSERT INTO Persona (name, code, description) VALUES ('Mentor', 'MNT', 'A mentor')"
    )
    c.commit()
    yield c
    c.close()


def _rec(table, values, action="create", target_id=None, batch_id=None, intra_refs=None):
    return ProposedRecord(
        table_name=table, action=action, target_id=target_id,
        values=values, source_payload_path=f"test.{table}",
        batch_id=batch_id, intra_batch_refs=intra_refs or {},
    )


def _batch(records):
    return ProposedBatch(
        records=records, ai_session_id=1, work_item_id=1,
        session_type="initial",
    )


class TestIdentifierUniqueness:
    def test_duplicate_domain_code(self, conn):
        rec = _rec("Domain", {"name": "Test", "code": "MN"})
        detect_conflicts(conn, _batch([rec]))
        errors = [c for c in rec.conflicts if c.conflict_type == "identifier_uniqueness"]
        assert len(errors) >= 1
        assert errors[0].severity == "error"

    def test_no_conflict_new_code(self, conn):
        rec = _rec("Domain", {"name": "Education", "code": "ED"})
        detect_conflicts(conn, _batch([rec]))
        errors = [c for c in rec.conflicts if c.conflict_type == "identifier_uniqueness"]
        assert len(errors) == 0


class TestTypeMismatches:
    def test_field_type_change_info(self, conn):
        rec = _rec("Field", {"field_type": "text"}, action="update", target_id=1)
        detect_conflicts(conn, _batch([rec]))
        type_conflicts = [c for c in rec.conflicts if c.conflict_type == "type_mismatch"]
        assert len(type_conflicts) == 1
        assert type_conflicts[0].severity == "info"

    def test_field_create_same_name_different_type(self, conn):
        rec = _rec("Field", {
            "name": "contactType", "field_type": "varchar", "entity_id": 1,
        })
        detect_conflicts(conn, _batch([rec]))
        type_conflicts = [c for c in rec.conflicts if c.conflict_type == "type_mismatch"]
        assert len(type_conflicts) == 1
        assert type_conflicts[0].severity == "error"

    def test_no_type_mismatch_same_type(self, conn):
        rec = _rec("Field", {"field_type": "enum"}, action="update", target_id=1)
        detect_conflicts(conn, _batch([rec]))
        type_conflicts = [c for c in rec.conflicts if c.conflict_type == "type_mismatch"]
        assert len(type_conflicts) == 0


class TestReferentialIntegrity:
    def test_missing_fk_entity(self, conn):
        rec = _rec("Field", {
            "entity_id": 999, "name": "test", "label": "Test",
            "field_type": "varchar",
        })
        detect_conflicts(conn, _batch([rec]))
        ref_conflicts = [c for c in rec.conflicts
                         if c.conflict_type == "referential_integrity"]
        assert any(c.severity == "error" for c in ref_conflicts)

    def test_valid_fk_entity(self, conn):
        rec = _rec("Field", {
            "entity_id": 1, "name": "test", "label": "Test",
            "field_type": "varchar",
        })
        detect_conflicts(conn, _batch([rec]))
        ref_errors = [c for c in rec.conflicts
                      if c.conflict_type == "referential_integrity"
                      and c.severity == "error"]
        assert len(ref_errors) == 0

    def test_intra_batch_ref_info(self, conn):
        entity_rec = _rec("Entity", {
            "name": "Account", "code": "ACC", "entity_type": "Company",
            "is_native": False,
        }, batch_id="batch:entity:ACC")
        field_rec = _rec("Field", {
            "name": "test", "label": "Test", "field_type": "varchar",
        }, intra_refs={"entity_id": "batch:entity:ACC"})
        detect_conflicts(conn, _batch([entity_rec, field_rec]))
        ref_infos = [c for c in field_rec.conflicts
                     if c.conflict_type == "referential_integrity"
                     and c.severity == "info"]
        assert len(ref_infos) >= 1


class TestDuplicateDetection:
    def test_similar_name_warning(self, conn):
        rec = _rec("Persona", {"name": "Volunteer Mentor", "code": "VMNT"})
        detect_conflicts(conn, _batch([rec]))
        dup_conflicts = [c for c in rec.conflicts
                         if c.conflict_type == "duplicate_detection"]
        assert len(dup_conflicts) >= 1
        assert dup_conflicts[0].severity == "warning"

    def test_no_duplicate_different_name(self, conn):
        rec = _rec("Persona", {"name": "Administrator", "code": "ADM"})
        detect_conflicts(conn, _batch([rec]))
        dup_conflicts = [c for c in rec.conflicts
                         if c.conflict_type == "duplicate_detection"]
        assert len(dup_conflicts) == 0


class TestOrphanedUpdates:
    def test_orphaned_update_error(self, conn):
        rec = _rec("Domain", {"name": "Updated"}, action="update", target_id=999)
        detect_conflicts(conn, _batch([rec]))
        orphan_conflicts = [c for c in rec.conflicts
                            if c.conflict_type == "orphaned_update"]
        assert len(orphan_conflicts) == 1
        assert orphan_conflicts[0].severity == "error"

    def test_valid_update_no_orphan(self, conn):
        rec = _rec("Domain", {"name": "Updated"}, action="update", target_id=1)
        detect_conflicts(conn, _batch([rec]))
        orphan_conflicts = [c for c in rec.conflicts
                            if c.conflict_type == "orphaned_update"]
        assert len(orphan_conflicts) == 0


class TestSeverityAssignment:
    def test_error_severity_for_identifier_dup(self, conn):
        rec = _rec("Domain", {"name": "Dup", "code": "MN"})
        detect_conflicts(conn, _batch([rec]))
        id_conflicts = [c for c in rec.conflicts
                        if c.conflict_type == "identifier_uniqueness"]
        assert all(c.severity == "error" for c in id_conflicts)

    def test_warning_severity_for_format(self, conn):
        rec = _rec("Domain", {"name": "Test", "code": "mn"})
        detect_conflicts(conn, _batch([rec]))
        fmt_conflicts = [c for c in rec.conflicts
                         if c.conflict_type == "format_violation"]
        assert all(c.severity == "warning" for c in fmt_conflicts)

    def test_info_severity_for_type_change(self, conn):
        rec = _rec("Field", {"field_type": "text"}, action="update", target_id=1)
        detect_conflicts(conn, _batch([rec]))
        type_conflicts = [c for c in rec.conflicts
                          if c.conflict_type == "type_mismatch"]
        assert all(c.severity == "info" for c in type_conflicts)
