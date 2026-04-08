"""Tests for automation.docgen.paths — output path resolution."""

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.docgen import DocumentType
from automation.docgen.paths import get_client_short_name, resolve_output_path


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
    c.execute("INSERT INTO Client (name, code, database_path) VALUES ('Test Org', 'TO', '/tmp/test.db')")
    c.commit()
    yield c
    c.close()


def _seed_basic(conn):
    """Seed minimum required data for path resolution tests."""
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) VALUES (1, 'master_prd', 'complete')"
    )
    conn.execute(
        "INSERT INTO Domain (id, name, code, sort_order) VALUES (1, 'Mentoring', 'MN', 1)"
    )
    conn.execute(
        "INSERT INTO Entity (id, name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (1, 'Contact', 'CONTACT', 'Person', 0, 1)"
    )
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Client Intake', 'MN-INTAKE', 1)"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status) "
        "VALUES (2, 'entity_prd', 1, 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, domain_id, status) "
        "VALUES (3, 'domain_overview', 1, 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, process_id, status) "
        "VALUES (4, 'process_definition', 1, 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, domain_id, status) "
        "VALUES (5, 'domain_reconciliation', 1, 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, domain_id, status) "
        "VALUES (6, 'yaml_generation', 1, 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) "
        "VALUES (7, 'business_object_discovery', 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) "
        "VALUES (8, 'crm_selection', 'complete')"
    )
    # ProcessEntity for YAML entity resolution
    conn.execute(
        "INSERT INTO ProcessEntity (process_id, entity_id, role) "
        "VALUES (1, 1, 'primary')"
    )
    conn.commit()


class TestGetClientShortName:

    def test_with_code(self, master_conn):
        assert get_client_short_name(master_conn) == "TO"

    def test_no_master_conn(self):
        assert get_client_short_name(None) == "client"


class TestResolveOutputPath:

    def test_master_prd(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        path = resolve_output_path(DocumentType.MASTER_PRD, conn, 1, tmp_path, master_conn)
        assert path.name == "TO-Master-PRD.docx"
        assert "PRDs" in str(path)

    def test_entity_inventory(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        path = resolve_output_path(DocumentType.ENTITY_INVENTORY, conn, 7, tmp_path, master_conn)
        assert path.name == "TO-Entity-Inventory.docx"

    def test_entity_prd(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        path = resolve_output_path(DocumentType.ENTITY_PRD, conn, 2, tmp_path, master_conn)
        assert path.name == "Contact-Entity-PRD.docx"
        assert "entities" in str(path)

    def test_domain_overview(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        path = resolve_output_path(DocumentType.DOMAIN_OVERVIEW, conn, 3, tmp_path, master_conn)
        assert "MN" in str(path)
        assert "Domain-Overview-Mentoring" in path.name

    def test_process_document(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        path = resolve_output_path(DocumentType.PROCESS_DOCUMENT, conn, 4, tmp_path, master_conn)
        assert path.name == "MN-INTAKE.docx"
        assert "MN" in str(path)

    def test_domain_prd(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        path = resolve_output_path(DocumentType.DOMAIN_PRD, conn, 5, tmp_path, master_conn)
        assert "Domain-PRD-Mentoring" in path.name

    def test_yaml_returns_list(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        paths = resolve_output_path(DocumentType.YAML_PROGRAM_FILES, conn, 6, tmp_path, master_conn)
        assert isinstance(paths, list)
        assert len(paths) >= 1
        assert paths[0].suffix == ".yaml"
        assert "programs" in str(paths[0])

    def test_crm_evaluation(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        path = resolve_output_path(DocumentType.CRM_EVALUATION_REPORT, conn, 8, tmp_path, master_conn)
        assert path.name == "TO-CRM-Evaluation-Report.docx"

    def test_subdomain_nesting(self, conn, master_conn, tmp_path):
        _seed_basic(conn)
        conn.execute(
            "INSERT INTO Domain (id, name, code, sort_order, parent_domain_id) "
            "VALUES (2, 'SubDomain', 'MN-SUB', 2, 1)"
        )
        conn.execute(
            "INSERT INTO Process (id, domain_id, name, code, sort_order) "
            "VALUES (2, 2, 'Sub Process', 'MN-SUB-PROC', 1)"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, process_id, status) "
            "VALUES (10, 'process_definition', 2, 'complete')"
        )
        conn.commit()
        path = resolve_output_path(DocumentType.PROCESS_DOCUMENT, conn, 10, tmp_path, master_conn)
        assert "MN" in str(path)
        assert "MN-SUB" in str(path)
        assert path.name == "MN-SUB-PROC.docx"

    def test_invalid_work_item(self, conn, tmp_path):
        _seed_basic(conn)
        with pytest.raises(ValueError, match="not found"):
            resolve_output_path(DocumentType.MASTER_PRD, conn, 999, tmp_path)
