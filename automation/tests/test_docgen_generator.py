"""Tests for automation.docgen.generator — DocumentGenerator public API."""

import subprocess

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.docgen.generator import DocumentGenerator


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


@pytest.fixture()
def master_conn(tmp_path):
    db_path = tmp_path / "master.db"
    c = run_master_migrations(str(db_path))
    c.execute(
        "INSERT INTO Client (name, code, database_path, organization_overview, crm_platform) "
        "VALUES ('Test Org', 'TO', '/tmp/test.db', 'Overview.', 'EspoCRM')"
    )
    c.commit()
    yield c
    c.close()


@pytest.fixture()
def project_folder(tmp_path):
    pf = tmp_path / "project"
    pf.mkdir()
    subprocess.run(["git", "init"], cwd=str(pf), capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=str(pf), capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=str(pf), capture_output=True)
    (pf / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=str(pf), capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=str(pf), capture_output=True)
    return pf


def _seed(conn):
    conn.execute(
        "INSERT INTO Domain (id, name, code, sort_order, domain_overview_text, domain_reconciliation_text) "
        "VALUES (1, 'Mentoring', 'MN', 1, 'Overview', 'Reconciliation')"
    )
    conn.execute(
        "INSERT INTO Entity (id, name, code, entity_type, is_native, primary_domain_id, "
        "singular_label, plural_label) "
        "VALUES (1, 'Contact', 'CONTACT', 'Person', 0, 1, 'Contact', 'Contacts')"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type, is_native, sort_order) "
        "VALUES (1, 1, 'contactType', 'Contact Type', 'enum', 0, 1)"
    )
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Client Intake', 'MN-INTAKE', 1)"
    )
    conn.execute(
        "INSERT INTO ProcessEntity (process_id, entity_id, role) VALUES (1, 1, 'primary')"
    )
    conn.execute(
        "INSERT INTO Persona (id, name, code) VALUES (1, 'Admin', 'ADM')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status, completed_at) "
        "VALUES (1, 'master_prd', 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status, completed_at) "
        "VALUES (2, 'entity_prd', 1, 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, process_id, status, completed_at) "
        "VALUES (4, 'process_definition', 1, 'complete', '2025-01-01')"
    )
    conn.commit()


class TestDocumentGenerator:

    def test_generate_single(self, conn, master_conn, project_folder):
        _seed(conn)
        gen = DocumentGenerator(conn, master_conn, project_folder)
        result = gen.generate(1, mode="final")
        assert result.error is None
        assert result.file_path is not None

    def test_generate_batch(self, conn, master_conn, project_folder):
        _seed(conn)
        gen = DocumentGenerator(conn, master_conn, project_folder)
        results = gen.generate_batch([1, 2, 4], mode="final")
        assert len(results) == 3
        # Each should succeed
        for r in results:
            assert r.error is None

    def test_batch_continues_on_failure(self, conn, master_conn, project_folder):
        _seed(conn)
        gen = DocumentGenerator(conn, master_conn, project_folder)
        # Work item 999 doesn't exist; batch should continue
        results = gen.generate_batch([1, 999, 2], mode="final")
        assert len(results) == 3
        # First and last should succeed
        assert results[0].error is None
        assert results[1].error is not None
        assert results[2].error is None

    def test_get_stale_documents(self, conn, master_conn, project_folder):
        _seed(conn)
        gen = DocumentGenerator(conn, master_conn, project_folder)
        stale = gen.get_stale_documents()
        # With no GenerationLog entries, nothing is stale
        assert isinstance(stale, list)

    def test_push_no_remote(self, conn, master_conn, project_folder):
        _seed(conn)
        gen = DocumentGenerator(conn, master_conn, project_folder)
        result = gen.push()
        assert result is False  # No remote configured

    def test_push_no_project_folder(self, conn, master_conn):
        _seed(conn)
        gen = DocumentGenerator(conn, master_conn, project_folder=None)
        result = gen.push()
        assert result is False
