"""Tests for automation.docgen.pipeline — 7-step rendering pipeline."""

import subprocess

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.docgen.pipeline import GenerationResult, run_pipeline


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
        "VALUES ('Test Org', 'TO', '/tmp/test.db', 'Overview text.', 'EspoCRM')"
    )
    c.commit()
    yield c
    c.close()


@pytest.fixture()
def project_folder(tmp_path):
    """Initialize a project folder with git."""
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
    """Seed minimum data for pipeline tests."""
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

    # Work items in various states
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status, completed_at) "
        "VALUES (1, 'master_prd', 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status, completed_at) "
        "VALUES (2, 'entity_prd', 1, 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, domain_id, status, completed_at) "
        "VALUES (3, 'domain_overview', 1, 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, process_id, status, completed_at) "
        "VALUES (4, 'process_definition', 1, 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, domain_id, status, completed_at) "
        "VALUES (5, 'domain_reconciliation', 1, 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, domain_id, status, completed_at) "
        "VALUES (6, 'yaml_generation', 1, 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status, completed_at) "
        "VALUES (7, 'business_object_discovery', 'complete', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status, completed_at) "
        "VALUES (8, 'crm_selection', 'complete', '2025-01-01')"
    )
    # Draft work item
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status, started_at) "
        "VALUES (10, 'entity_prd', 1, 'in_progress', '2025-01-01')"
    )
    conn.commit()


class TestPipeline:

    def test_invalid_mode(self, conn, project_folder):
        _seed(conn)
        with pytest.raises(ValueError, match="Invalid generation mode"):
            run_pipeline(conn, 1, mode="invalid", project_folder=project_folder)

    def test_final_requires_complete(self, conn, project_folder):
        _seed(conn)
        with pytest.raises(ValueError, match="complete"):
            run_pipeline(conn, 10, mode="final", project_folder=project_folder)

    def test_draft_requires_in_progress(self, conn, project_folder):
        _seed(conn)
        with pytest.raises(ValueError, match="in_progress"):
            run_pipeline(conn, 1, mode="draft", project_folder=project_folder)

    def test_non_generatable_type(self, conn, project_folder):
        _seed(conn)
        # stakeholder_review doesn't produce a document
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status, completed_at) "
            "VALUES (20, 'stakeholder_review', 'complete', '2025-01-01')"
        )
        conn.commit()
        with pytest.raises(ValueError, match="does not produce"):
            run_pipeline(conn, 20, mode="final", project_folder=project_folder)

    def test_master_prd_generation(self, conn, master_conn, project_folder):
        _seed(conn)
        result = run_pipeline(conn, 1, mode="final",
                              project_folder=project_folder, master_conn=master_conn)
        assert isinstance(result, GenerationResult)
        assert result.error is None
        assert result.file_path is not None
        assert result.file_path.endswith(".docx")
        # Check GenerationLog was recorded
        assert result.generation_log_id is not None

    def test_entity_prd_generation(self, conn, master_conn, project_folder):
        _seed(conn)
        result = run_pipeline(conn, 2, mode="final",
                              project_folder=project_folder, master_conn=master_conn)
        assert result.error is None
        assert result.file_path is not None

    def test_process_document_generation(self, conn, master_conn, project_folder):
        _seed(conn)
        result = run_pipeline(conn, 4, mode="final",
                              project_folder=project_folder, master_conn=master_conn)
        assert result.error is None
        assert result.file_path is not None

    def test_yaml_generation(self, conn, master_conn, project_folder):
        _seed(conn)
        result = run_pipeline(conn, 6, mode="final",
                              project_folder=project_folder, master_conn=master_conn)
        assert result.error is None
        assert result.file_paths is not None
        assert len(result.file_paths) >= 1

    def test_draft_generation_no_log(self, conn, master_conn, project_folder):
        _seed(conn)
        result = run_pipeline(conn, 10, mode="draft",
                              project_folder=project_folder, master_conn=master_conn)
        assert result.error is None
        assert result.generation_log_id is None

    def test_work_item_not_found(self, conn, project_folder):
        _seed(conn)
        with pytest.raises(ValueError, match="not found"):
            run_pipeline(conn, 999, mode="final", project_folder=project_folder)
