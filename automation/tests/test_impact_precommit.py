"""Tests for automation.impact.precommit — pre-commit analysis."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.impact.precommit import ProposedImpact, analyze_proposed_change


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed(conn):
    """Seed database for pre-commit tests."""
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) VALUES (1, 'master_prd', 'complete')"
    )
    conn.execute(
        "INSERT INTO AISession (id, work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (1, 1, 'initial', 'p', 'imported', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO Domain (id, name, code, sort_order) VALUES (1, 'Test', 'TST', 1)"
    )
    conn.execute(
        "INSERT INTO Entity (id, name, code, entity_type, is_native) "
        "VALUES (1, 'Contact', 'CONTACT', 'Person', 0)"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type) "
        "VALUES (1, 1, 'status', 'Status', 'enum')"
    )
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Intake', 'TST-INTAKE', 1)"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, usage) "
        "VALUES (1, 1, 1, 'evaluated')"
    )
    conn.execute(
        "INSERT INTO LayoutPanel (id, entity_id, label, sort_order, layout_mode) "
        "VALUES (1, 1, 'Main', 1, 'rows')"
    )
    conn.execute(
        "INSERT INTO LayoutRow (id, panel_id, sort_order, cell_1_field_id) "
        "VALUES (1, 1, 1, 1)"
    )
    conn.commit()


class TestAnalyzeProposedChange:

    def test_update_returns_impacts(self, conn):
        _seed(conn)
        result = analyze_proposed_change(conn, "Field", 1, "update")
        assert len(result) > 0
        assert all(isinstance(r, ProposedImpact) for r in result)

    def test_delete_returns_impacts(self, conn):
        _seed(conn)
        result = analyze_proposed_change(conn, "Field", 1, "delete")
        assert len(result) > 0
        for r in result:
            assert "deletion" in r.impact_description

    def test_does_not_write_to_db(self, conn):
        _seed(conn)
        analyze_proposed_change(conn, "Field", 1, "update")
        count = conn.execute("SELECT COUNT(*) FROM ChangeImpact").fetchone()[0]
        assert count == 0

    def test_rationale_accepted(self, conn):
        _seed(conn)
        # Should not raise
        result = analyze_proposed_change(
            conn, "Field", 1, "update",
            rationale="Changing type per stakeholder request"
        )
        assert len(result) > 0

    def test_new_values_accepted(self, conn):
        _seed(conn)
        result = analyze_proposed_change(
            conn, "Field", 1, "update",
            new_values={"field_type": "text"},
        )
        assert len(result) > 0

    def test_insert_returns_empty(self, conn):
        _seed(conn)
        result = analyze_proposed_change(conn, "Field", 1, "insert")
        assert result == []

    def test_leaf_node_returns_empty(self, conn):
        _seed(conn)
        conn.execute(
            "INSERT INTO Decision (id, identifier, title, description, status) "
            "VALUES (1, 'DEC-001', 'Test', 'Test', 'proposed')"
        )
        conn.commit()
        result = analyze_proposed_change(conn, "Decision", 1, "update")
        assert result == []

    def test_unknown_table_returns_empty(self, conn):
        result = analyze_proposed_change(conn, "NonExistent", 1, "delete")
        assert result == []

    def test_entity_delete_transitive(self, conn):
        _seed(conn)
        result = analyze_proposed_change(conn, "Entity", 1, "delete")
        tables = {r.affected_table for r in result}
        # Should include transitive Field → ProcessField
        assert "Field" in tables
        assert "ProcessField" in tables
