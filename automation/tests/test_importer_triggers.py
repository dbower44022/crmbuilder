"""Tests for automation.importer.triggers — downstream trigger sequence."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.importer.commit import CommitResult
from automation.importer.triggers import TriggerResult, run_triggers
from automation.workflow.engine import WorkflowEngine


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _commit_result(import_status="imported", has_updates=False):
    return CommitResult(
        created_count=1, updated_count=0, rejected_count=0,
        total_proposed=1, created_ids={}, import_status=import_status,
        has_updates=has_updates,
    )


def _setup_master_prd(conn):
    """Set up a project with master_prd in_progress."""
    engine = WorkflowEngine(conn)
    wi_id = engine.create_project()
    engine.start(wi_id)
    # Create AISession
    conn.execute(
        "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (?, 'initial', 'p', 'pending', CURRENT_TIMESTAMP)",
        (wi_id,),
    )
    conn.commit()
    return wi_id


def _setup_bod(conn):
    """Set up a project through BOD in_progress."""
    engine = WorkflowEngine(conn)
    wi_id = engine.create_project()
    engine.start(wi_id)
    engine.complete(wi_id)
    engine.after_master_prd_import()

    bod_id = conn.execute(
        "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
    ).fetchone()[0]
    engine.start(bod_id)

    conn.execute(
        "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (?, 'initial', 'p', 'pending', CURRENT_TIMESTAMP)",
        (bod_id,),
    )
    conn.commit()
    return bod_id


class TestGraphConstruction:
    def test_master_prd_expands_graph(self, conn):
        wi_id = _setup_master_prd(conn)
        result = run_triggers(
            conn, 1, _commit_result(), wi_id, "master_prd", "initial",
        )
        assert result.graph_constructed is True
        # BOD work item should exist now
        bod = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()
        assert bod is not None

    def test_bod_expands_graph(self, conn):
        # Need domains, entities, processes for BOD graph expansion
        conn.execute("INSERT INTO Domain (name, code, sort_order) VALUES ('MN', 'MN', 1)")
        conn.execute(
            "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
            "VALUES ('Contact', 'CON', 'Person', 1, 1)"
        )
        conn.execute(
            "INSERT INTO Process (domain_id, name, code, sort_order) "
            "VALUES (1, 'Intake', 'MN-INTAKE', 1)"
        )
        conn.commit()

        bod_id = _setup_bod(conn)
        result = run_triggers(
            conn, 1, _commit_result(), bod_id, "business_object_discovery", "initial",
        )
        assert result.graph_constructed is True
        # Entity PRD work item should exist
        entity_prd = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'entity_prd'"
        ).fetchone()
        assert entity_prd is not None

    def test_no_graph_for_other_types(self, conn):
        wi_id = _setup_master_prd(conn)
        result = run_triggers(
            conn, 1, _commit_result(), wi_id, "entity_prd", "initial",
        )
        assert result.graph_constructed is False


class TestWorkItemCompletion:
    def test_full_import_completes_work_item(self, conn):
        wi_id = _setup_master_prd(conn)
        result = run_triggers(
            conn, 1, _commit_result(), wi_id, "master_prd", "initial",
        )
        assert result.work_item_completed is True
        engine = WorkflowEngine(conn)
        assert engine.get_status(wi_id) == "complete"

    def test_partial_import_does_not_complete(self, conn):
        wi_id = _setup_master_prd(conn)
        result = run_triggers(
            conn, 1, _commit_result(import_status="partial"),
            wi_id, "master_prd", "initial",
        )
        assert result.work_item_completed is False
        engine = WorkflowEngine(conn)
        assert engine.get_status(wi_id) == "in_progress"

    def test_clarification_does_not_complete(self, conn):
        wi_id = _setup_master_prd(conn)
        # First complete normally
        engine = WorkflowEngine(conn)
        engine.complete(wi_id)
        assert engine.get_status(wi_id) == "complete"

        # Clarification should not change status
        result = run_triggers(
            conn, 1, _commit_result(), wi_id, "master_prd", "clarification",
        )
        assert result.work_item_completed is False
        assert engine.get_status(wi_id) == "complete"


class TestTriggerFailureIsolation:
    def test_trigger_failure_does_not_affect_committed_data(self, conn):
        """Verify that if triggers fail, committed data stays."""
        # Create a domain in the DB (simulating committed data)
        conn.execute(
            "INSERT INTO Domain (name, code, sort_order, is_service) "
            "VALUES ('Test', 'TST', 1, 0)"
        )
        conn.commit()

        # Run triggers with a nonexistent work item — should fail gracefully
        result = run_triggers(
            conn, 1, _commit_result(), 999, "master_prd", "initial",
        )
        assert result.has_errors

        # Domain should still exist
        row = conn.execute("SELECT id FROM Domain WHERE code = 'TST'").fetchone()
        assert row is not None


class TestImpactAnalysisDeferral:
    def test_impact_analysis_queued_for_updates(self, conn):
        wi_id = _setup_master_prd(conn)
        result = run_triggers(
            conn, 1, _commit_result(has_updates=True),
            wi_id, "master_prd", "initial",
        )
        assert result.impact_analysis_queued is True

        # Check the marker on AISession
        session = conn.execute(
            "SELECT notes FROM AISession WHERE id = 1"
        ).fetchone()
        assert session is not None
        assert "IMPACT_ANALYSIS_NEEDED" in (session[0] or "")

    def test_no_impact_analysis_for_creates_only(self, conn):
        wi_id = _setup_master_prd(conn)
        result = run_triggers(
            conn, 1, _commit_result(has_updates=False),
            wi_id, "master_prd", "initial",
        )
        assert result.impact_analysis_queued is False


class TestTriggerResult:
    def test_no_errors(self):
        result = TriggerResult()
        assert not result.has_errors

    def test_has_errors(self):
        result = TriggerResult(errors=["Something failed"])
        assert result.has_errors
