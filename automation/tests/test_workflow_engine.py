"""Integration tests for automation.workflow.engine — WorkflowEngine class."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.workflow.engine import WorkflowEngine


@pytest.fixture()
def conn(tmp_path):
    """Create a client database and return an open connection."""
    db_path = tmp_path / "test.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _insert_domain(conn, name, code, sort_order=None, is_service=False):
    cur = conn.execute(
        "INSERT INTO Domain (name, code, sort_order, is_service) VALUES (?, ?, ?, ?)",
        (name, code, sort_order, is_service),
    )
    conn.commit()
    return cur.lastrowid


def _insert_entity(conn, name, code, entity_type="Base", is_native=False,
                    primary_domain_id=None):
    cur = conn.execute(
        "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, code, entity_type, is_native, primary_domain_id),
    )
    conn.commit()
    return cur.lastrowid


def _insert_process(conn, domain_id, name, code, sort_order):
    cur = conn.execute(
        "INSERT INTO Process (domain_id, name, code, sort_order) VALUES (?, ?, ?, ?)",
        (domain_id, name, code, sort_order),
    )
    conn.commit()
    return cur.lastrowid


class TestWorkflowEngineEndToEnd:
    """Full lifecycle integration test through the WorkflowEngine API."""

    def test_full_lifecycle(self, conn):
        """Exercise the complete project lifecycle:
        create → import master PRD → import BOD → start → complete →
        verify downstream ready → revise upstream → verify blocked →
        complete upstream → verify unblocked.
        """
        engine = WorkflowEngine(conn)

        # 1. Create project
        master_id = engine.create_project()
        assert engine.get_status(master_id) == "ready"
        assert engine.get_phase_for(master_id) == 1

        # 2. Start and complete master PRD
        engine.start(master_id)
        assert engine.get_status(master_id) == "in_progress"
        engine.complete(master_id)
        assert engine.get_status(master_id) == "complete"

        # 3. Import master PRD results — creates BOD
        engine.after_master_prd_import()
        bod_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()[0]
        assert engine.get_status(bod_id) == "ready"

        # 4. Start and complete BOD
        engine.start(bod_id)
        engine.complete(bod_id)

        # 5. Set up domains, entities, processes, then import BOD
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        e1 = _insert_entity(conn, "Contact", "CON", primary_domain_id=d1)
        _insert_process(conn, d1, "Intake", "MN-INTAKE", 1)
        engine.after_business_object_discovery_import()

        # 6. Entity PRDs should be ready
        ep_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'entity_prd' AND entity_id = ?",
            (e1,),
        ).fetchone()[0]
        assert engine.get_status(ep_id) == "ready"
        assert engine.get_phase_for(ep_id) == 2

        # 7. Available work should show entity PRDs
        available = engine.get_available_work()
        assert any(w["id"] == ep_id for w in available)

        # 8. Start and complete entity PRD
        engine.start(ep_id)
        assert engine.get_status(ep_id) == "in_progress"
        engine.complete(ep_id)
        assert engine.get_status(ep_id) == "complete"

        # 9. Domain overview should now be ready (BOD + entity_prd both complete)
        do_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_overview' AND domain_id = ?",
            (d1,),
        ).fetchone()[0]
        assert engine.get_status(do_id) == "ready"
        assert engine.get_phase_for(do_id) == 3

        # 10. Revise entity PRD — domain overview should go back to not_started
        engine.revise(ep_id)
        assert engine.get_status(ep_id) == "in_progress"
        assert engine.get_status(do_id) == "not_started"

        # 11. Complete entity PRD again — domain overview should become ready
        engine.complete(ep_id)
        assert engine.get_status(do_id) == "ready"

    def test_block_and_unblock(self, conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()
        engine.start(master_id)

        # Block it
        engine.block(master_id, "Waiting for stakeholder")
        assert engine.get_status(master_id) == "blocked"

        # Unblock it
        engine.unblock(master_id)
        assert engine.get_status(master_id) == "in_progress"

    def test_revision_cascade_with_blocked_unblock(self, conn):
        """Revise an upstream item, verify cascade blocks, then complete
        and verify unblock."""
        engine = WorkflowEngine(conn)

        # Build full graph
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        _insert_entity(conn, "Contact", "CON", primary_domain_id=d1)
        _insert_process(conn, d1, "Intake", "MN-INTAKE", 1)

        master_id = engine.create_project()
        engine.start(master_id)
        engine.complete(master_id)
        engine.after_master_prd_import()

        bod_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()[0]
        engine.start(bod_id)
        engine.complete(bod_id)
        engine.after_business_object_discovery_import()

        # Complete entity_prd and domain_overview
        ep_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'entity_prd'"
        ).fetchone()[0]
        engine.start(ep_id)
        engine.complete(ep_id)

        do_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_overview' AND domain_id = ?",
            (d1,),
        ).fetchone()[0]
        engine.start(do_id)
        engine.complete(do_id)

        # Process definition should be ready
        pd_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'process_definition' AND domain_id = ?",
            (d1,),
        ).fetchone()[0]
        assert engine.get_status(pd_id) == "ready"

        # Start process definition
        engine.start(pd_id)
        assert engine.get_status(pd_id) == "in_progress"

        # Revise domain overview — process definition becomes blocked
        engine.revise(do_id)
        assert engine.get_status(pd_id) == "blocked"

        # Complete domain overview — process definition unblocks
        engine.complete(do_id)
        assert engine.get_status(pd_id) == "in_progress"

    def test_service_domain_phase(self, conn):
        """Service domain items are reported as phase 4."""
        engine = WorkflowEngine(conn)
        d1 = _insert_domain(conn, "Services", "SVC", sort_order=1, is_service=True)
        _insert_entity(conn, "Contact", "CON", primary_domain_id=d1)
        _insert_process(conn, d1, "ServiceProc", "SVC-P1", 1)

        master_id = engine.create_project()
        engine.start(master_id)
        engine.complete(master_id)
        engine.after_master_prd_import()

        bod_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()[0]
        engine.start(bod_id)
        engine.complete(bod_id)
        engine.after_business_object_discovery_import()

        do_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_overview' AND domain_id = ?",
            (d1,),
        ).fetchone()[0]
        assert engine.get_phase_for(do_id) == 4

    def test_mid_project_add_entity(self, conn):
        engine = WorkflowEngine(conn)
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        _insert_entity(conn, "Contact", "CON", primary_domain_id=d1)
        _insert_process(conn, d1, "Intake", "MN-INTAKE", 1)

        master_id = engine.create_project()
        engine.start(master_id)
        engine.complete(master_id)
        engine.after_master_prd_import()
        bod_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()[0]
        engine.start(bod_id)
        engine.complete(bod_id)
        engine.after_business_object_discovery_import()

        # Add new entity
        e2 = _insert_entity(conn, "Mentor", "MEN", primary_domain_id=d1)
        new_ep = engine.add_entity(e2)
        assert engine.get_status(new_ep) == "ready"
        assert engine.get_phase_for(new_ep) == 2

    def test_mid_project_add_process(self, conn):
        engine = WorkflowEngine(conn)
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        _insert_entity(conn, "Contact", "CON", primary_domain_id=d1)
        _insert_process(conn, d1, "Intake", "MN-INTAKE", 1)

        master_id = engine.create_project()
        engine.start(master_id)
        engine.complete(master_id)
        engine.after_master_prd_import()
        bod_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()[0]
        engine.start(bod_id)
        engine.complete(bod_id)
        engine.after_business_object_discovery_import()

        # Add new process
        p2 = _insert_process(conn, d1, "Matching", "MN-MATCH", 2)
        new_pd = engine.add_process(p2)
        assert engine.get_phase_for(new_pd) == 5

    def test_mid_project_add_domain(self, conn):
        engine = WorkflowEngine(conn)
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        _insert_entity(conn, "Contact", "CON", primary_domain_id=d1)
        _insert_process(conn, d1, "Intake", "MN-INTAKE", 1)

        master_id = engine.create_project()
        engine.start(master_id)
        engine.complete(master_id)
        engine.after_master_prd_import()
        bod_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()[0]
        engine.start(bod_id)
        engine.complete(bod_id)
        engine.after_business_object_discovery_import()

        # Add new domain
        d2 = _insert_domain(conn, "Training", "TR", sort_order=2)
        created = engine.add_domain(d2)
        assert len(created) >= 4  # do, recon, sr, yg

    def test_save_domain_overview(self, conn):
        engine = WorkflowEngine(conn)
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        engine.save_domain_overview(d1, "Overview text for Mentoring domain")
        row = conn.execute(
            "SELECT domain_overview_text FROM Domain WHERE id = ?", (d1,)
        ).fetchone()
        assert row[0] == "Overview text for Mentoring domain"

    def test_get_status_not_found(self, conn):
        engine = WorkflowEngine(conn)
        with pytest.raises(ValueError, match="not found"):
            engine.get_status(999)

    def test_get_phase_for_not_found(self, conn):
        engine = WorkflowEngine(conn)
        with pytest.raises(ValueError, match="not found"):
            engine.get_phase_for(999)
