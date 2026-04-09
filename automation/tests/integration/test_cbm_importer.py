"""Integration test: CBM importer correctness against fixture subset."""

from __future__ import annotations


class TestCBMImporterIntegration:

    def test_import_completes_without_fatal_errors(self, cbm_imported):
        assert not cbm_imported.errors, f"Fatal errors: {cbm_imported.errors}"

    def test_personas_imported(self, cbm_client_conn):
        rows = cbm_client_conn.execute("SELECT code FROM Persona ORDER BY code").fetchall()
        codes = {r[0] for r in rows}
        assert "MST-PER-001" in codes
        assert "MST-PER-003" in codes
        assert len(codes) >= 3

    def test_domains_imported(self, cbm_client_conn):
        rows = cbm_client_conn.execute("SELECT code FROM Domain ORDER BY code").fetchall()
        codes = {r[0] for r in rows}
        assert "MN" in codes
        assert "MR" in codes
        assert len(codes) >= 2

    def test_entities_imported(self, cbm_client_conn):
        rows = cbm_client_conn.execute("SELECT name FROM Entity ORDER BY name").fetchall()
        names = {r[0] for r in rows}
        assert "Contact" in names
        assert len(names) >= 2

    def test_fields_imported(self, cbm_client_conn):
        rows = cbm_client_conn.execute(
            "SELECT f.name FROM Field f "
            "JOIN Entity e ON f.entity_id = e.id "
            "WHERE e.name = 'Contact'"
        ).fetchall()
        field_names = {r[0] for r in rows}
        assert "contactType" in field_names
        assert len(field_names) >= 3

    def test_processes_imported(self, cbm_client_conn):
        rows = cbm_client_conn.execute("SELECT code FROM Process ORDER BY code").fetchall()
        codes = {r[0] for r in rows}
        assert "MN-INTAKE" in codes

    def test_process_steps_imported(self, cbm_client_conn):
        row = cbm_client_conn.execute(
            "SELECT COUNT(*) FROM ProcessStep ps "
            "JOIN Process p ON ps.process_id = p.id "
            "WHERE p.code = 'MN-INTAKE'"
        ).fetchone()
        assert row[0] >= 3

    def test_requirements_imported(self, cbm_client_conn):
        rows = cbm_client_conn.execute(
            "SELECT identifier FROM Requirement ORDER BY identifier"
        ).fetchall()
        ids = {r[0] for r in rows}
        assert "MN-INTAKE-REQ-001" in ids

    def test_decisions_imported(self, cbm_client_conn):
        rows = cbm_client_conn.execute(
            "SELECT identifier FROM Decision ORDER BY identifier"
        ).fetchall()
        ids = {r[0] for r in rows}
        assert "MN-DEC-001" in ids

    def test_work_items_created(self, cbm_client_conn):
        rows = cbm_client_conn.execute(
            "SELECT item_type, status FROM WorkItem"
        ).fetchall()
        assert len(rows) >= 3  # master_prd + business_object_discovery + at least 1 more
        types = {r[0] for r in rows}
        assert "master_prd" in types
        assert "business_object_discovery" in types

    def test_master_prd_work_item_complete(self, cbm_client_conn):
        row = cbm_client_conn.execute(
            "SELECT status, completed_at FROM WorkItem WHERE item_type = 'master_prd'"
        ).fetchone()
        assert row is not None
        assert row[0] == "complete"
        assert row[1] is not None

    def test_synthetic_sessions_created(self, cbm_client_conn):
        rows = cbm_client_conn.execute(
            "SELECT import_status, generated_prompt FROM AISession"
        ).fetchall()
        assert len(rows) >= 1
        for status, prompt in rows:
            assert status == "imported"
            assert "[CBM bootstrap import]" in prompt

    def test_client_record_in_master(self, cbm_master_conn):
        row = cbm_master_conn.execute(
            "SELECT name, code FROM Client WHERE code = 'CBM'"
        ).fetchone()
        assert row is not None
        assert row[0] == "Cleveland Business Mentors"

    def test_import_report_has_counts(self, cbm_imported):
        assert cbm_imported.total_parsed > 0
        assert cbm_imported.total_imported > 0
