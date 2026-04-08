"""Tests for automation.impact.work_item_mapping."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.impact.changeimpact import CandidateImpact, write_change_impacts
from automation.impact.work_item_mapping import get_affected_work_items


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed(conn):
    """Seed database with work items, records, and ChangeImpact."""
    # Work items
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
        "INSERT INTO Entity (id, name, code, entity_type, is_native) "
        "VALUES (2, 'Account', 'ACCOUNT', 'Company', 1)"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type) "
        "VALUES (1, 1, 'testField', 'Test', 'varchar')"
    )
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Intake', 'TST-INTAKE', 1)"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, usage) "
        "VALUES (1, 1, 1, 'collected')"
    )
    conn.execute(
        "INSERT INTO Persona (id, name, code) VALUES (1, 'Admin', 'ADMIN')"
    )
    conn.execute(
        "INSERT INTO Relationship (id, name, description, entity_id, entity_foreign_id, "
        "link_type, link, link_foreign, label, label_foreign) "
        "VALUES (1, 'C-A', 'desc', 1, 2, 'manyToOne', 'a', 'c', 'A', 'C')"
    )
    conn.execute(
        "INSERT INTO LayoutPanel (id, entity_id, label, sort_order, layout_mode) "
        "VALUES (1, 1, 'Panel', 1, 'rows')"
    )
    conn.execute(
        "INSERT INTO LayoutRow (id, panel_id, sort_order, cell_1_field_id) "
        "VALUES (1, 1, 1, 1)"
    )

    # Work items for mapping
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status) "
        "VALUES (2, 'entity_prd', 1, 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status) "
        "VALUES (3, 'entity_prd', 2, 'complete')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, process_id, status) "
        "VALUES (4, 'process_definition', 1, 'in_progress')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, domain_id, status) "
        "VALUES (5, 'domain_overview', 1, 'complete')"
    )

    # ChangeLog
    conn.execute(
        "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
        "change_type, changed_at) VALUES (1, 1, 'Field', 1, 'update', '2025-01-01')"
    )
    conn.commit()


class TestWorkItemMapping:

    def test_field_maps_to_entity_prd(self, conn):
        _seed(conn)
        ci_ids = write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "field impact", True)
        ])
        result = get_affected_work_items(conn, ci_ids)
        assert len(result) == 1
        assert result[0].work_item_id == 2  # entity_prd for entity 1
        assert result[0].item_type == "entity_prd"

    def test_process_field_maps_to_process_definition(self, conn):
        _seed(conn)
        ci_ids = write_change_impacts(conn, [
            CandidateImpact(1, "ProcessField", 1, "pf impact", True)
        ])
        result = get_affected_work_items(conn, ci_ids)
        assert len(result) == 1
        assert result[0].work_item_id == 4
        assert result[0].item_type == "process_definition"

    def test_persona_maps_to_master_prd(self, conn):
        _seed(conn)
        ci_ids = write_change_impacts(conn, [
            CandidateImpact(1, "Persona", 1, "persona impact", True)
        ])
        result = get_affected_work_items(conn, ci_ids)
        assert len(result) == 1
        assert result[0].work_item_id == 1
        assert result[0].item_type == "master_prd"

    def test_domain_maps_to_domain_overview(self, conn):
        _seed(conn)
        ci_ids = write_change_impacts(conn, [
            CandidateImpact(1, "Domain", 1, "domain impact", True)
        ])
        result = get_affected_work_items(conn, ci_ids)
        assert len(result) == 1
        assert result[0].work_item_id == 5

    def test_relationship_maps_to_both_entities(self, conn):
        _seed(conn)
        ci_ids = write_change_impacts(conn, [
            CandidateImpact(1, "Relationship", 1, "rel impact", True)
        ])
        result = get_affected_work_items(conn, ci_ids)
        wi_ids = {r.work_item_id for r in result}
        assert 2 in wi_ids  # entity_prd for entity 1
        assert 3 in wi_ids  # entity_prd for entity 2

    def test_layout_row_maps_to_entity_prd(self, conn):
        _seed(conn)
        ci_ids = write_change_impacts(conn, [
            CandidateImpact(1, "LayoutRow", 1, "lr impact", True)
        ])
        result = get_affected_work_items(conn, ci_ids)
        assert len(result) == 1
        assert result[0].work_item_id == 2

    def test_grouping_multiple_impacts_same_wi(self, conn):
        _seed(conn)
        ci_ids = write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "field impact", True),
            CandidateImpact(1, "LayoutRow", 1, "layout impact", True),
        ])
        result = get_affected_work_items(conn, ci_ids)
        # Both map to entity_prd for entity 1
        assert len(result) == 1
        assert result[0].impact_count == 2
        assert len(result[0].impact_summaries) == 2

    def test_empty_input(self, conn):
        assert get_affected_work_items(conn, []) == []
