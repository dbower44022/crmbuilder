"""Tests for automation.prompts.decisions_issues — inclusion rules."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.prompts.decisions_issues import get_decisions, get_open_issues


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed_domain(conn, name="Mentoring", code="MN"):
    cur = conn.execute(
        "INSERT INTO Domain (name, code) VALUES (?, ?)", (name, code),
    )
    conn.commit()
    return cur.lastrowid


def _seed_entity(conn, name="Contact", code="CON", primary_domain_id=None):
    cur = conn.execute(
        "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (?, ?, 'Base', 0, ?)",
        (name, code, primary_domain_id),
    )
    conn.commit()
    return cur.lastrowid


def _seed_process(conn, domain_id, name="Intake", code="INTAKE"):
    cur = conn.execute(
        "INSERT INTO Process (domain_id, name, code, sort_order) VALUES (?, ?, ?, 1)",
        (domain_id, name, code),
    )
    conn.commit()
    return cur.lastrowid


def _seed_decision(conn, identifier, title="Dec", status="locked", **scope):
    cols = "identifier, title, description, status"
    vals = "?, ?, ?, ?"
    params = [identifier, title, "desc", status]
    for k, v in scope.items():
        cols += f", {k}"
        vals += ", ?"
        params.append(v)
    cur = conn.execute(
        f"INSERT INTO Decision ({cols}) VALUES ({vals})", params,
    )
    conn.commit()
    return cur.lastrowid


def _seed_open_issue(conn, identifier, title="Issue", status="open", **scope):
    cols = "identifier, title, description, status"
    vals = "?, ?, ?, ?"
    params = [identifier, title, "desc", status]
    for k, v in scope.items():
        cols += f", {k}"
        vals += ", ?"
        params.append(v)
    cur = conn.execute(
        f"INSERT INTO OpenIssue ({cols}) VALUES ({vals})", params,
    )
    conn.commit()
    return cur.lastrowid


class TestMasterPrd:
    def test_returns_empty(self, conn):
        _seed_decision(conn, "DEC-001")
        assert get_decisions(conn, "master_prd", {}) == []
        assert get_open_issues(conn, "master_prd", {}) == []


class TestBusinessObjectDiscovery:
    def test_includes_global_only(self, conn):
        d1 = _seed_domain(conn)
        _seed_decision(conn, "DEC-G01")  # global
        _seed_decision(conn, "DEC-D01", domain_id=d1)  # domain-scoped
        results = get_decisions(conn, "business_object_discovery", {})
        ids = [r["identifier"] for r in results]
        assert "DEC-G01" in ids
        assert "DEC-D01" not in ids


class TestEntityPrd:
    def test_includes_global_entity_and_domain(self, conn):
        d1 = _seed_domain(conn)
        e1 = _seed_entity(conn, primary_domain_id=d1)
        _seed_decision(conn, "DEC-G01")  # global
        _seed_decision(conn, "DEC-E01", entity_id=e1)  # entity-scoped
        _seed_decision(conn, "DEC-D01", domain_id=d1)  # domain-scoped
        d2 = _seed_domain(conn, "Other", "OT")
        _seed_decision(conn, "DEC-D02", domain_id=d2)  # other domain
        wi = {"entity_id": e1, "domain_id": d1}
        results = get_decisions(conn, "entity_prd", wi)
        ids = [r["identifier"] for r in results]
        assert "DEC-G01" in ids
        assert "DEC-E01" in ids
        assert "DEC-D01" in ids
        assert "DEC-D02" not in ids


class TestDomainOverview:
    def test_includes_global_and_domain(self, conn):
        d1 = _seed_domain(conn)
        _seed_decision(conn, "DEC-G01")
        _seed_decision(conn, "DEC-D01", domain_id=d1)
        wi = {"domain_id": d1}
        results = get_decisions(conn, "domain_overview", wi)
        ids = [r["identifier"] for r in results]
        assert "DEC-G01" in ids
        assert "DEC-D01" in ids


class TestProcessDefinition:
    def test_includes_global_domain_process_entity(self, conn):
        d1 = _seed_domain(conn)
        e1 = _seed_entity(conn, primary_domain_id=d1)
        p1 = _seed_process(conn, d1)
        # Link entity to process
        conn.execute(
            "INSERT INTO ProcessEntity (process_id, entity_id, role) VALUES (?, ?, 'primary')",
            (p1, e1),
        )
        conn.commit()
        _seed_decision(conn, "DEC-G01")
        _seed_decision(conn, "DEC-D01", domain_id=d1)
        _seed_decision(conn, "DEC-P01", process_id=p1)
        _seed_decision(conn, "DEC-E01", entity_id=e1)
        wi = {"domain_id": d1, "process_id": p1}
        results = get_decisions(conn, "process_definition", wi)
        ids = [r["identifier"] for r in results]
        assert all(i in ids for i in ["DEC-G01", "DEC-D01", "DEC-P01", "DEC-E01"])


class TestDomainReconciliation:
    def test_includes_all_within_domain(self, conn):
        d1 = _seed_domain(conn)
        e1 = _seed_entity(conn, primary_domain_id=d1)
        p1 = _seed_process(conn, d1)
        _seed_decision(conn, "DEC-G01")
        _seed_decision(conn, "DEC-D01", domain_id=d1)
        _seed_decision(conn, "DEC-P01", process_id=p1)
        _seed_decision(conn, "DEC-E01", entity_id=e1)
        wi = {"domain_id": d1}
        results = get_decisions(conn, "domain_reconciliation", wi)
        ids = [r["identifier"] for r in results]
        assert all(i in ids for i in ["DEC-G01", "DEC-D01", "DEC-P01", "DEC-E01"])


class TestYamlGeneration:
    def test_uses_same_rules_as_domain_reconciliation(self, conn):
        d1 = _seed_domain(conn)
        _seed_decision(conn, "DEC-G01")
        _seed_decision(conn, "DEC-D01", domain_id=d1)
        wi = {"domain_id": d1}
        recon = get_decisions(conn, "domain_reconciliation", wi)
        yaml = get_decisions(conn, "yaml_generation", wi)
        assert [r["identifier"] for r in recon] == [r["identifier"] for r in yaml]


class TestCrmSelection:
    def test_includes_all(self, conn):
        d1 = _seed_domain(conn)
        _seed_decision(conn, "DEC-G01")
        _seed_decision(conn, "DEC-D01", domain_id=d1)
        results = get_decisions(conn, "crm_selection", {})
        assert len(results) == 2


class TestCrmDeployment:
    def test_includes_global(self, conn):
        d1 = _seed_domain(conn)
        _seed_decision(conn, "DEC-G01")
        _seed_decision(conn, "DEC-D01", domain_id=d1)
        results = get_decisions(conn, "crm_deployment", {})
        ids = [r["identifier"] for r in results]
        assert "DEC-G01" in ids
        assert "DEC-D01" not in ids


class TestOpenIssues:
    def test_filters_by_open_status(self, conn):
        _seed_open_issue(conn, "OI-001", status="open")
        _seed_open_issue(conn, "OI-002", status="resolved")
        results = get_open_issues(conn, "business_object_discovery", {})
        ids = [r["identifier"] for r in results]
        assert "OI-001" in ids
        assert "OI-002" not in ids


class TestDecisionStatus:
    def test_only_locked_decisions_included(self, conn):
        _seed_decision(conn, "DEC-001", status="locked")
        _seed_decision(conn, "DEC-002", status="proposed")
        results = get_decisions(conn, "business_object_discovery", {})
        ids = [r["identifier"] for r in results]
        assert "DEC-001" in ids
        assert "DEC-002" not in ids
