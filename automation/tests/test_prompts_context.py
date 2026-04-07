"""Tests for automation.prompts.context — context assembly per work item type."""

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.prompts.context import assemble_context


@pytest.fixture()
def conn(tmp_path):
    """Create a client database and return an open connection."""
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


@pytest.fixture()
def master_conn(tmp_path):
    """Create a master database with a Client row."""
    db_path = tmp_path / "master.db"
    c = run_master_migrations(str(db_path))
    c.execute(
        "INSERT INTO Client (name, code, description, database_path, "
        "organization_overview, crm_platform) VALUES (?, ?, ?, ?, ?, ?)",
        ("Test Org", "TO", "A test organization", "/tmp/test.db",
         "Test org overview narrative", "EspoCRM"),
    )
    c.commit()
    yield c
    c.close()


def _seed_domain(conn, name="Mentoring", code="MN", sort_order=1, is_service=False,
                  parent_domain_id=None):
    cur = conn.execute(
        "INSERT INTO Domain (name, code, sort_order, is_service, parent_domain_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, code, sort_order, is_service, parent_domain_id),
    )
    conn.commit()
    return cur.lastrowid


def _seed_entity(conn, name="Contact", code="CON", entity_type="Person",
                  is_native=True, primary_domain_id=None):
    cur = conn.execute(
        "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, code, entity_type, is_native, primary_domain_id),
    )
    conn.commit()
    return cur.lastrowid


def _seed_process(conn, domain_id, name="Intake", code="MN-INTAKE", sort_order=1):
    cur = conn.execute(
        "INSERT INTO Process (domain_id, name, code, sort_order) VALUES (?, ?, ?, ?)",
        (domain_id, name, code, sort_order),
    )
    conn.commit()
    return cur.lastrowid


def _seed_work_item(conn, item_type, status="ready", domain_id=None,
                     entity_id=None, process_id=None):
    cur = conn.execute(
        "INSERT INTO WorkItem (item_type, status, domain_id, entity_id, process_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (item_type, status, domain_id, entity_id, process_id),
    )
    conn.commit()
    return cur.lastrowid


def _seed_persona(conn, name="Admin", code="ADM"):
    cur = conn.execute(
        "INSERT INTO Persona (name, code, description) VALUES (?, ?, ?)",
        (name, code, "Test persona"),
    )
    conn.commit()
    return cur.lastrowid


class TestAssembleMasterPrd:
    def test_includes_client_info(self, conn, master_conn):
        wid = _seed_work_item(conn, "master_prd")
        ctx = assemble_context(conn, wid, "master_prd", master_conn)
        assert len(ctx["subsections"]) >= 1
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Client Information" in labels

    def test_without_master_conn(self, conn):
        wid = _seed_work_item(conn, "master_prd")
        ctx = assemble_context(conn, wid, "master_prd")
        assert ctx["subsections"] == []


class TestAssembleBusinessObjectDiscovery:
    def test_includes_expected_subsections(self, conn, master_conn):
        d1 = _seed_domain(conn)
        _seed_process(conn, d1)
        _seed_persona(conn)
        wid = _seed_work_item(conn, "business_object_discovery")
        ctx = assemble_context(conn, wid, "business_object_discovery", master_conn)
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Organization Overview" in labels
        assert "Domains" in labels
        assert "Processes" in labels
        assert "Personas" in labels


class TestAssembleEntityPrd:
    def test_includes_target_entity_data(self, conn):
        d1 = _seed_domain(conn)
        e1 = _seed_entity(conn, primary_domain_id=d1)
        wid = _seed_work_item(conn, "entity_prd", entity_id=e1, domain_id=d1)
        ctx = assemble_context(conn, wid, "entity_prd")
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Domains" in labels
        assert "Entity Inventory" in labels
        assert "Target Entity Participation" in labels


class TestAssembleDomainOverview:
    def test_includes_domain_data(self, conn, master_conn):
        d1 = _seed_domain(conn)
        _seed_entity(conn, primary_domain_id=d1)
        _seed_process(conn, d1)
        _seed_persona(conn)
        wid = _seed_work_item(conn, "domain_overview", domain_id=d1)
        ctx = assemble_context(conn, wid, "domain_overview", master_conn)
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Organization Overview" in labels
        assert "Target Domain" in labels
        assert "Domain Processes" in labels
        assert "Personas" in labels
        assert "Domain Entities" in labels

    def test_sub_domain_includes_parent(self, conn, master_conn):
        parent = _seed_domain(conn, "Parent", "PAR", sort_order=1)
        conn.execute(
            "UPDATE Domain SET domain_overview_text = 'parent overview' WHERE id = ?",
            (parent,),
        )
        conn.commit()
        child = _seed_domain(conn, "Child", "CHI", sort_order=2, parent_domain_id=parent)
        wid = _seed_work_item(conn, "domain_overview", domain_id=child)
        ctx = assemble_context(conn, wid, "domain_overview", master_conn)
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Parent Domain" in labels


class TestAssembleProcessDefinition:
    def test_includes_domain_overview_text(self, conn):
        d1 = _seed_domain(conn)
        conn.execute(
            "UPDATE Domain SET domain_overview_text = 'Mentoring overview' WHERE id = ?",
            (d1,),
        )
        conn.commit()
        p1 = _seed_process(conn, d1)
        wid = _seed_work_item(conn, "process_definition", domain_id=d1, process_id=p1)
        ctx = assemble_context(conn, wid, "process_definition")
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Domain Overview" in labels
        assert "Personas" in labels
        assert "Domain Entities" in labels


class TestAssembleDomainReconciliation:
    def test_includes_processes_and_entities(self, conn):
        d1 = _seed_domain(conn)
        conn.execute(
            "UPDATE Domain SET domain_overview_text = 'overview' WHERE id = ?",
            (d1,),
        )
        conn.commit()
        _seed_process(conn, d1)
        _seed_entity(conn, primary_domain_id=d1)
        wid = _seed_work_item(conn, "domain_reconciliation", domain_id=d1)
        ctx = assemble_context(conn, wid, "domain_reconciliation")
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Domain Overview" in labels
        assert "Domain Processes" in labels
        assert "Domain Entities" in labels


class TestAssembleYamlGeneration:
    def test_includes_reconciliation_and_entities(self, conn):
        d1 = _seed_domain(conn)
        conn.execute(
            "UPDATE Domain SET domain_reconciliation_text = 'recon text' WHERE id = ?",
            (d1,),
        )
        conn.commit()
        _seed_entity(conn, primary_domain_id=d1)
        wid = _seed_work_item(conn, "yaml_generation", domain_id=d1)
        ctx = assemble_context(conn, wid, "yaml_generation")
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Domain Reconciliation" in labels
        assert "Domain Entities with Layout" in labels
        assert "Requirements" in labels


class TestAssembleCrmSelection:
    def test_broadest_scope(self, conn, master_conn):
        d1 = _seed_domain(conn)
        _seed_entity(conn, primary_domain_id=d1)
        wid = _seed_work_item(conn, "crm_selection")
        ctx = assemble_context(conn, wid, "crm_selection", master_conn)
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Organization Overview" in labels
        assert "Domains" in labels
        assert "All Entities" in labels
        assert "All Requirements" in labels


class TestAssembleCrmDeployment:
    def test_includes_scale_and_platform(self, conn, master_conn):
        _seed_entity(conn, is_native=False)
        wid = _seed_work_item(conn, "crm_deployment")
        ctx = assemble_context(conn, wid, "crm_deployment", master_conn)
        labels = [s["label"] for s in ctx["subsections"]]
        assert "Organization Overview" in labels
        assert "CRM Platform" in labels
        assert "Scale Summary" in labels
        scale = next(s for s in ctx["subsections"] if s["label"] == "Scale Summary")
        assert scale["content"]["entity_count"] >= 1


class TestNonPromptableTypes:
    @pytest.mark.parametrize("item_type", [
        "stakeholder_review", "crm_configuration", "verification",
    ])
    def test_raises_for_non_promptable(self, conn, item_type):
        with pytest.raises(ValueError, match="does not produce prompts"):
            assemble_context(conn, 1, item_type)
