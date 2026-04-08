"""Tests for automation.docgen.queries — data query layer.

Tests all 8 query modules against a populated test database.
"""

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.docgen.queries import (
    crm_evaluation,
    domain_overview,
    domain_prd,
    entity_inventory,
    entity_prd,
    master_prd,
    process_document,
    yaml_program,
)


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
        "VALUES ('Test Org', 'TO', '/tmp/test.db', 'We are a test org.', 'EspoCRM')"
    )
    c.commit()
    yield c
    c.close()


def _seed_full(conn):
    """Seed a complete dataset for all query tests."""
    conn.execute(
        "INSERT INTO Domain (id, name, code, description, sort_order, domain_overview_text, domain_reconciliation_text) "
        "VALUES (1, 'Mentoring', 'MN', 'Mentoring domain', 1, 'Overview text here', 'Reconciliation text here')"
    )
    conn.execute(
        "INSERT INTO Entity (id, name, code, entity_type, is_native, primary_domain_id, "
        "singular_label, plural_label, description) "
        "VALUES (1, 'Contact', 'CONTACT', 'Person', 0, 1, 'Contact', 'Contacts', 'A person')"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type, is_required, is_native, sort_order, description) "
        "VALUES (1, 1, 'firstName', 'First Name', 'varchar', 1, 1, 1, 'First name of contact')"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type, is_required, is_native, sort_order, description) "
        "VALUES (2, 1, 'contactType', 'Contact Type', 'multiEnum', 1, 0, 2, 'Type discriminator')"
    )
    conn.execute(
        "INSERT INTO FieldOption (id, field_id, value, label, sort_order, is_default) "
        "VALUES (1, 2, 'Client', 'Client', 1, 0)"
    )
    conn.execute(
        "INSERT INTO FieldOption (id, field_id, value, label, sort_order, is_default) "
        "VALUES (2, 2, 'Mentor', 'Mentor', 2, 0)"
    )
    conn.execute(
        "INSERT INTO Persona (id, name, code, description) "
        "VALUES (1, 'Administrator', 'ADM', 'System admin')"
    )
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, description, triggers, "
        "completion_criteria, sort_order) "
        "VALUES (1, 1, 'Client Intake', 'MN-INTAKE', 'Intake process', "
        "'Form submission', 'Review complete', 1)"
    )
    conn.execute(
        "INSERT INTO ProcessStep (id, process_id, name, description, step_type, "
        "performer_persona_id, sort_order) "
        "VALUES (1, 1, 'Submit Form', 'Client submits form', 'action', 1, 1)"
    )
    conn.execute(
        "INSERT INTO Requirement (id, identifier, process_id, description, priority, status) "
        "VALUES (1, 'MN-INTAKE-REQ-001', 1, 'Accept submissions', 'must', 'approved')"
    )
    conn.execute(
        "INSERT INTO ProcessEntity (process_id, entity_id, role) VALUES (1, 1, 'primary')"
    )
    conn.execute(
        "INSERT INTO ProcessField (process_id, field_id, usage) VALUES (1, 1, 'collected')"
    )
    conn.execute(
        "INSERT INTO ProcessPersona (process_id, persona_id, role) VALUES (1, 1, 'performer')"
    )
    conn.execute(
        "INSERT INTO Decision (id, identifier, title, description, status, entity_id, domain_id, process_id) "
        "VALUES (1, 'DEC-001', 'Test Decision', 'A decision', 'locked', 1, 1, 1)"
    )
    conn.execute(
        "INSERT INTO OpenIssue (id, identifier, title, description, status, entity_id, domain_id, process_id) "
        "VALUES (1, 'ISS-001', 'Test Issue', 'An issue', 'open', 1, 1, 1)"
    )
    conn.execute(
        "INSERT INTO Relationship (id, name, description, entity_id, entity_foreign_id, "
        "link_type, link, link_foreign, label, label_foreign) "
        "VALUES (1, 'Contact-Account', 'Contact to Account', 1, 1, 'manyToMany', "
        "'accounts', 'contacts', 'Accounts', 'Contacts')"
    )
    conn.execute(
        "INSERT INTO BusinessObject (id, name, description, status, resolution, "
        "resolved_to_entity_id) "
        "VALUES (1, 'Mentor', 'A mentor person', 'classified', 'entity', 1)"
    )
    conn.execute(
        "INSERT INTO LayoutPanel (id, entity_id, label, sort_order, layout_mode) "
        "VALUES (1, 1, 'Overview', 1, 'rows')"
    )
    conn.execute(
        "INSERT INTO LayoutRow (panel_id, sort_order, cell_1_field_id, is_full_width) "
        "VALUES (1, 1, 1, 0)"
    )
    conn.execute(
        "INSERT INTO ListColumn (entity_id, field_id, sort_order) "
        "VALUES (1, 1, 1)"
    )

    # Work items
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
    conn.commit()


class TestMasterPrdQuery:
    def test_returns_data(self, conn, master_conn):
        _seed_full(conn)
        data = master_prd.query(conn, 1, master_conn)
        assert data["client_name"] == "Test Org"
        assert data["organization_overview"] == "We are a test org."
        assert len(data["personas"]) == 1
        assert len(data["domains"]) == 1
        assert data["domains"][0]["name"] == "Mentoring"


class TestEntityInventoryQuery:
    def test_returns_entities(self, conn, master_conn):
        _seed_full(conn)
        data = entity_inventory.query(conn, 7, master_conn)
        assert len(data["entities"]) >= 1
        assert data["entities"][0]["name"] == "Contact"
        assert len(data["business_objects"]) >= 1


class TestEntityPrdQuery:
    def test_returns_full_entity(self, conn, master_conn):
        _seed_full(conn)
        data = entity_prd.query(conn, 2, master_conn)
        assert data["entity"]["name"] == "Contact"
        assert len(data["native_fields"]) >= 1
        assert len(data["custom_fields"]) >= 1
        assert len(data["relationships"]) >= 1
        assert len(data["decisions"]) >= 1
        assert len(data["open_issues"]) >= 1
        assert len(data["layout_panels"]) >= 1

    def test_field_options_populated(self, conn, master_conn):
        _seed_full(conn)
        data = entity_prd.query(conn, 2, master_conn)
        enum_field = next(f for f in data["custom_fields"] if f["name"] == "contactType")
        assert len(enum_field["options"]) == 2


class TestDomainOverviewQuery:
    def test_returns_domain_data(self, conn, master_conn):
        _seed_full(conn)
        data = domain_overview.query(conn, 3, master_conn)
        assert data["domain"]["name"] == "Mentoring"
        assert data["domain_overview_text"] == "Overview text here"
        assert len(data["processes"]) >= 1
        assert len(data["personas"]) >= 1


class TestProcessDocumentQuery:
    def test_returns_process_data(self, conn, master_conn):
        _seed_full(conn)
        data = process_document.query(conn, 4, master_conn)
        assert data["process"]["name"] == "Client Intake"
        assert data["process"]["code"] == "MN-INTAKE"
        assert data["domain"]["name"] == "Mentoring"
        assert len(data["steps"]) >= 1
        assert len(data["requirements"]) >= 1
        assert len(data["personas"]) >= 1
        assert len(data["data_reference"]) >= 1


class TestDomainPrdQuery:
    def test_returns_reconciliation(self, conn, master_conn):
        _seed_full(conn)
        data = domain_prd.query(conn, 5, master_conn)
        assert data["domain"]["name"] == "Mentoring"
        assert data["reconciliation_text"] == "Reconciliation text here"
        assert len(data["processes"]) >= 1
        assert len(data["decisions"]) >= 1
        assert len(data["open_issues"]) >= 1


class TestYamlProgramQuery:
    def test_returns_entities(self, conn, master_conn):
        _seed_full(conn)
        data = yaml_program.query(conn, 6, master_conn)
        assert len(data["entities"]) >= 1
        entity = data["entities"][0]
        assert entity["name"] == "Contact"
        # Only custom fields (is_native = FALSE)
        for f in entity["fields"]:
            assert f.get("is_native") is not True


class TestCrmEvaluationQuery:
    def test_returns_platform(self, conn, master_conn):
        _seed_full(conn)
        data = crm_evaluation.query(conn, 8, master_conn)
        assert data["crm_platform"] == "EspoCRM"
        assert data["scale_summary"]["entity_count"] >= 1
        assert data["scale_summary"]["field_count"] >= 1
        assert data["requirements_summary"]["total"] >= 1

    def test_handles_missing_data(self, conn):
        """Gracefully handles no master connection."""
        _seed_full(conn)
        data = crm_evaluation.query(conn, 8, None)
        assert data["crm_platform"] is None
        assert data["scale_summary"]["entity_count"] >= 1
