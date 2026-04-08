"""Tests for automation.ui.work_item.work_item_logic — pure Python work item data assembly."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.ui.work_item.work_item_logic import (
    ACTIONS,
    get_available_actions,
    load_dependencies,
    load_documents,
    load_impacts,
    load_sessions,
    load_work_item,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _create_master_prd(conn, status="not_started"):
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) VALUES (1, 'master_prd', ?)",
        (status,),
    )
    conn.commit()


class TestGetAvailableActions:

    def test_all_actions_present(self):
        result = get_available_actions("ready")
        for action in ACTIONS:
            assert action in result

    def test_ready_can_start(self):
        result = get_available_actions("ready")
        assert result["start_work"] is None

    def test_ready_cannot_complete(self):
        result = get_available_actions("ready")
        assert result["mark_complete"] is not None

    def test_in_progress_can_complete(self):
        result = get_available_actions("in_progress")
        assert result["mark_complete"] is None

    def test_in_progress_cannot_start(self):
        result = get_available_actions("in_progress")
        assert result["start_work"] is not None

    def test_complete_can_reopen(self):
        result = get_available_actions("complete")
        assert result["reopen_for_revision"] is None

    def test_complete_cannot_start(self):
        result = get_available_actions("complete")
        assert result["start_work"] is not None

    def test_blocked_can_unblock(self):
        result = get_available_actions("blocked")
        assert result["unblock"] is None

    def test_blocked_cannot_start(self):
        result = get_available_actions("blocked")
        assert result["start_work"] is not None

    def test_not_started_limited_actions(self):
        result = get_available_actions("not_started")
        assert result["start_work"] is not None
        assert result["mark_complete"] is not None
        assert result["view_impact_analysis"] is None  # Always available

    def test_view_impact_always_available(self):
        for status in ("not_started", "ready", "in_progress", "complete", "blocked"):
            result = get_available_actions(status)
            assert result["view_impact_analysis"] is None

    def test_generate_prompt_ready_or_in_progress(self):
        assert get_available_actions("ready")["generate_prompt"] is None
        assert get_available_actions("in_progress")["generate_prompt"] is None
        assert get_available_actions("complete")["generate_prompt"] is not None

    def test_run_import_only_in_progress(self):
        assert get_available_actions("in_progress")["run_import"] is None
        assert get_available_actions("ready")["run_import"] is not None

    def test_generate_document_in_progress_or_complete(self):
        assert get_available_actions("in_progress")["generate_document"] is None
        assert get_available_actions("complete")["generate_document"] is None
        assert get_available_actions("ready")["generate_document"] is not None

    def test_block_from_ready_or_in_progress(self):
        assert get_available_actions("ready")["block"] is None
        assert get_available_actions("in_progress")["block"] is None
        assert get_available_actions("complete")["block"] is not None

    def test_unavailable_action_has_explanation(self):
        result = get_available_actions("not_started")
        for _action, reason in result.items():
            if reason is not None:
                assert len(reason) > 10  # Non-trivial explanation
                assert "not_started" in reason


class TestLoadWorkItem:

    def test_load_basic(self, conn):
        _create_master_prd(conn)
        item = load_work_item(conn, 1)
        assert item is not None
        assert item.item_type == "master_prd"
        assert item.phase == 1
        assert item.phase_name == "Master PRD"

    def test_not_found(self, conn):
        assert load_work_item(conn, 999) is None

    def test_with_domain(self, conn):
        conn.execute(
            "INSERT INTO Domain (id, name, code, sort_order) VALUES (1, 'Sales', 'SAL', 1)"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status, domain_id) "
            "VALUES (1, 'domain_overview', 'ready', 1)"
        )
        conn.commit()
        item = load_work_item(conn, 1)
        assert item.domain_name == "Sales"

    def test_with_entity(self, conn):
        conn.execute(
            "INSERT INTO Entity (id, name, code, entity_type, is_native) "
            "VALUES (1, 'Contact', 'CONTACT', 'Person', 0)"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status, entity_id) "
            "VALUES (1, 'entity_prd', 'not_started', 1)"
        )
        conn.commit()
        item = load_work_item(conn, 1)
        assert item.entity_name == "Contact"


class TestLoadDependencies:

    def test_upstream_and_downstream(self, conn):
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) VALUES (1, 'master_prd', 'complete')"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) "
            "VALUES (2, 'business_object_discovery', 'ready')"
        )
        conn.execute(
            "INSERT INTO Dependency (work_item_id, depends_on_id) VALUES (2, 1)"
        )
        conn.commit()

        # From item 2's perspective: item 1 is upstream
        deps = load_dependencies(conn, 2)
        upstream = [d for d in deps if d.direction == "upstream"]
        assert len(upstream) == 1
        assert upstream[0].work_item_id == 1

        # From item 1's perspective: item 2 is downstream
        deps = load_dependencies(conn, 1)
        downstream = [d for d in deps if d.direction == "downstream"]
        assert len(downstream) == 1
        assert downstream[0].work_item_id == 2

    def test_no_dependencies(self, conn):
        _create_master_prd(conn)
        deps = load_dependencies(conn, 1)
        assert deps == []


class TestLoadSessions:

    def test_loads_sessions(self, conn):
        _create_master_prd(conn, status="in_progress")
        conn.execute(
            "INSERT INTO AISession (id, work_item_id, session_type, generated_prompt, "
            "import_status, started_at) "
            "VALUES (1, 1, 'initial', 'Generate the Master PRD', 'pending', '2025-01-01')"
        )
        conn.commit()
        sessions = load_sessions(conn, 1)
        assert len(sessions) == 1
        assert sessions[0].session_type == "initial"
        assert sessions[0].generated_prompt == "Generate the Master PRD"

    def test_no_sessions(self, conn):
        _create_master_prd(conn)
        sessions = load_sessions(conn, 1)
        assert sessions == []


class TestLoadDocuments:

    def test_loads_documents(self, conn):
        _create_master_prd(conn, status="complete")
        conn.execute(
            "INSERT INTO GenerationLog (work_item_id, document_type, file_path, "
            "generated_at, generation_mode) "
            "VALUES (1, 'master_prd', '/docs/master.docx', '2025-01-15', 'final')"
        )
        conn.commit()
        docs = load_documents(conn, 1)
        assert len(docs) == 1
        assert docs[0].document_type == "master_prd"
        assert docs[0].file_path == "/docs/master.docx"

    def test_no_documents(self, conn):
        _create_master_prd(conn)
        docs = load_documents(conn, 1)
        assert docs == []


class TestLoadImpacts:

    def test_loads_impacts(self, conn):
        _create_master_prd(conn, status="in_progress")
        conn.execute(
            "INSERT INTO AISession (id, work_item_id, session_type, generated_prompt, "
            "import_status, started_at) "
            "VALUES (1, 1, 'initial', 'p', 'imported', '2025-01-01')"
        )
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, changed_at) VALUES (1, 1, 'Field', 1, 'insert', '2025-01-01')"
        )
        conn.execute(
            "INSERT INTO ChangeImpact (id, change_log_id, affected_table, "
            "affected_record_id, impact_description, requires_review) "
            "VALUES (1, 1, 'ProcessField', 10, 'Field type changed', 1)"
        )
        conn.commit()
        impacts = load_impacts(conn, 1)
        assert len(impacts) == 1
        assert impacts[0].affected_table == "ProcessField"
        assert impacts[0].requires_review is True
        assert impacts[0].action_required is False

    def test_no_impacts(self, conn):
        _create_master_prd(conn)
        impacts = load_impacts(conn, 1)
        assert impacts == []
