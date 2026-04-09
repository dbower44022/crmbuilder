"""Integration test: WorkflowEngine queries on populated CBM data."""

from __future__ import annotations

from automation.workflow.engine import WorkflowEngine


class TestCBMWorkflow:

    def test_get_available_work(self, cbm_client_conn):
        engine = WorkflowEngine(cbm_client_conn)
        available = engine.get_available_work()
        # Should have some available work items
        assert isinstance(available, list)

    def test_master_prd_is_phase_1(self, cbm_client_conn):
        engine = WorkflowEngine(cbm_client_conn)
        wi = cbm_client_conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'master_prd'"
        ).fetchone()
        assert wi is not None
        phase = engine.get_phase_for(wi[0])
        assert phase == 1

    def test_business_object_discovery_is_phase_2(self, cbm_client_conn):
        engine = WorkflowEngine(cbm_client_conn)
        wi = cbm_client_conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()
        assert wi is not None
        phase = engine.get_phase_for(wi[0])
        assert phase == 2

    def test_dependency_graph_structure(self, cbm_client_conn):
        # business_object_discovery should depend on master_prd
        row = cbm_client_conn.execute(
            "SELECT d.depends_on_id "
            "FROM Dependency d "
            "JOIN WorkItem wi ON d.work_item_id = wi.id "
            "WHERE wi.item_type = 'business_object_discovery'"
        ).fetchone()
        assert row is not None
        dep_type = cbm_client_conn.execute(
            "SELECT item_type FROM WorkItem WHERE id = ?", (row[0],)
        ).fetchone()
        assert dep_type[0] == "master_prd"
