"""Tests for automation.ui.dashboard.dashboard_logic — pure Python dashboard data assembly."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.ui.dashboard.dashboard_logic import (
    WorkItemRow,
    build_phase_groups,
    build_work_queue,
    compute_summary,
    filter_items,
    get_unique_domains,
    has_incomplete_upstream,
    load_all_work_items,
)


def _make_item(**kwargs) -> WorkItemRow:
    """Build a WorkItemRow with defaults."""
    defaults = {
        "id": 1, "item_type": "master_prd", "status": "not_started",
        "phase": 1, "phase_name": "Master PRD",
        "domain_id": None, "domain_name": None, "domain_sort_order": None,
        "entity_id": None, "entity_name": None,
        "process_id": None, "process_name": None,
        "blocked_reason": None, "started_at": None, "completed_at": None,
    }
    defaults.update(kwargs)
    return WorkItemRow(**defaults)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


class TestComputeSummary:

    def test_empty_items(self):
        s = compute_summary("Test", [])
        assert s.total == 0
        assert s.not_started == 0
        assert s.client_name == "Test"

    def test_counts_by_status(self):
        items = [
            _make_item(id=1, status="not_started"),
            _make_item(id=2, status="ready"),
            _make_item(id=3, status="in_progress"),
            _make_item(id=4, status="complete"),
            _make_item(id=5, status="blocked"),
            _make_item(id=6, status="complete"),
        ]
        s = compute_summary("Acme", items)
        assert s.total == 6
        assert s.not_started == 1
        assert s.ready == 1
        assert s.in_progress == 1
        assert s.complete == 2
        assert s.blocked == 1


class TestBuildWorkQueue:

    def test_filters_to_actionable(self):
        items = [
            _make_item(id=1, status="in_progress", phase=1),
            _make_item(id=2, status="ready", phase=1),
            _make_item(id=3, status="not_started", phase=1),
            _make_item(id=4, status="complete", phase=1),
            _make_item(id=5, status="blocked", phase=1),
        ]
        queue = build_work_queue(items)
        assert len(queue) == 2
        statuses = [i.status for i in queue]
        assert "not_started" not in statuses
        assert "complete" not in statuses
        assert "blocked" not in statuses

    def test_in_progress_before_ready(self):
        items = [
            _make_item(id=1, status="ready", phase=1),
            _make_item(id=2, status="in_progress", phase=2),
        ]
        queue = build_work_queue(items)
        assert queue[0].status == "in_progress"
        assert queue[1].status == "ready"

    def test_sorted_by_phase(self):
        items = [
            _make_item(id=1, status="ready", phase=5),
            _make_item(id=2, status="ready", phase=2),
            _make_item(id=3, status="ready", phase=1),
        ]
        queue = build_work_queue(items)
        phases = [i.phase for i in queue]
        assert phases == [1, 2, 5]

    def test_sorted_by_domain_sort_order(self):
        items = [
            _make_item(id=1, status="ready", phase=5, domain_sort_order=3),
            _make_item(id=2, status="ready", phase=5, domain_sort_order=1),
            _make_item(id=3, status="ready", phase=5, domain_sort_order=2),
        ]
        queue = build_work_queue(items)
        orders = [i.domain_sort_order for i in queue]
        assert orders == [1, 2, 3]

    def test_null_domain_sort_order_last(self):
        items = [
            _make_item(id=1, status="ready", phase=1, domain_sort_order=None),
            _make_item(id=2, status="ready", phase=1, domain_sort_order=1),
        ]
        queue = build_work_queue(items)
        assert queue[0].id == 2
        assert queue[1].id == 1


class TestBuildPhaseGroups:

    def test_groups_by_phase(self):
        items = [
            _make_item(id=1, phase=1, phase_name="Master PRD"),
            _make_item(id=2, phase=2, phase_name="Entity Definition"),
            _make_item(id=3, phase=2, phase_name="Entity Definition"),
        ]
        groups = build_phase_groups(items)
        assert len(groups) == 2
        assert groups[0].phase == 1
        assert len(groups[0].items) == 1
        assert groups[1].phase == 2
        assert len(groups[1].items) == 2

    def test_completion_counts(self):
        items = [
            _make_item(id=1, phase=1, status="complete"),
            _make_item(id=2, phase=1, status="in_progress"),
            _make_item(id=3, phase=1, status="complete"),
        ]
        groups = build_phase_groups(items)
        assert groups[0].complete_count == 2
        assert groups[0].total_count == 3

    def test_sorted_by_phase(self):
        items = [
            _make_item(id=1, phase=5),
            _make_item(id=2, phase=1),
            _make_item(id=3, phase=3),
        ]
        groups = build_phase_groups(items)
        phases = [g.phase for g in groups]
        assert phases == [1, 3, 5]


class TestFilterItems:

    def test_no_filters(self):
        items = [_make_item(id=1), _make_item(id=2)]
        assert len(filter_items(items)) == 2

    def test_filter_by_domain(self):
        items = [
            _make_item(id=1, domain_name="Sales"),
            _make_item(id=2, domain_name="HR"),
            _make_item(id=3, domain_name="Sales"),
        ]
        result = filter_items(items, domain_filter="Sales")
        assert len(result) == 2
        assert all(i.domain_name == "Sales" for i in result)

    def test_filter_by_phase(self):
        items = [
            _make_item(id=1, phase=1),
            _make_item(id=2, phase=2),
        ]
        result = filter_items(items, phase_filter=1)
        assert len(result) == 1
        assert result[0].phase == 1

    def test_filter_by_status(self):
        items = [
            _make_item(id=1, status="ready"),
            _make_item(id=2, status="complete"),
        ]
        result = filter_items(items, status_filter="ready")
        assert len(result) == 1

    def test_combined_filters(self):
        items = [
            _make_item(id=1, domain_name="Sales", phase=1, status="ready"),
            _make_item(id=2, domain_name="Sales", phase=2, status="ready"),
            _make_item(id=3, domain_name="HR", phase=1, status="ready"),
        ]
        result = filter_items(items, domain_filter="Sales", phase_filter=1)
        assert len(result) == 1
        assert result[0].id == 1


class TestGetUniqueDomains:

    def test_unique_sorted(self):
        items = [
            _make_item(id=1, domain_name="Zebra"),
            _make_item(id=2, domain_name="Alpha"),
            _make_item(id=3, domain_name="Zebra"),
            _make_item(id=4, domain_name=None),
        ]
        domains = get_unique_domains(items)
        assert domains == ["Alpha", "Zebra"]


class TestLoadAllWorkItems:

    def test_loads_items(self, conn):
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) "
            "VALUES (1, 'master_prd', 'not_started')"
        )
        conn.commit()
        items = load_all_work_items(conn)
        assert len(items) == 1
        assert items[0].item_type == "master_prd"
        assert items[0].phase == 1
        assert items[0].phase_name == "Master PRD"

    def test_loads_with_domain(self, conn):
        conn.execute(
            "INSERT INTO Domain (id, name, code, sort_order) "
            "VALUES (1, 'Sales', 'SAL', 1)"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status, domain_id) "
            "VALUES (1, 'domain_overview', 'ready', 1)"
        )
        conn.commit()
        items = load_all_work_items(conn)
        assert items[0].domain_name == "Sales"
        assert items[0].domain_sort_order == 1

    def test_loads_with_entity(self, conn):
        conn.execute(
            "INSERT INTO Entity (id, name, code, entity_type, is_native) "
            "VALUES (1, 'Contact', 'CONTACT', 'Person', 0)"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status, entity_id) "
            "VALUES (1, 'entity_prd', 'not_started', 1)"
        )
        conn.commit()
        items = load_all_work_items(conn)
        assert items[0].entity_name == "Contact"

    def test_loads_with_process(self, conn):
        conn.execute(
            "INSERT INTO Domain (id, name, code, sort_order) "
            "VALUES (1, 'Sales', 'SAL', 1)"
        )
        conn.execute(
            "INSERT INTO Process (id, domain_id, name, code, sort_order) "
            "VALUES (1, 1, 'Lead Intake', 'LI', 1)"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status, domain_id, process_id) "
            "VALUES (1, 'process_definition', 'not_started', 1, 1)"
        )
        conn.commit()
        items = load_all_work_items(conn)
        assert items[0].process_name == "Lead Intake"


class TestHasIncompleteUpstream:

    def test_no_dependencies(self, conn):
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) "
            "VALUES (1, 'master_prd', 'ready')"
        )
        conn.commit()
        assert has_incomplete_upstream(conn, 1) is False

    def test_all_complete(self, conn):
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) "
            "VALUES (1, 'master_prd', 'complete')"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) "
            "VALUES (2, 'business_object_discovery', 'ready')"
        )
        conn.execute(
            "INSERT INTO Dependency (work_item_id, depends_on_id) "
            "VALUES (2, 1)"
        )
        conn.commit()
        assert has_incomplete_upstream(conn, 2) is False

    def test_some_incomplete(self, conn):
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) "
            "VALUES (1, 'master_prd', 'in_progress')"
        )
        conn.execute(
            "INSERT INTO WorkItem (id, item_type, status) "
            "VALUES (2, 'business_object_discovery', 'not_started')"
        )
        conn.execute(
            "INSERT INTO Dependency (work_item_id, depends_on_id) "
            "VALUES (2, 1)"
        )
        conn.commit()
        assert has_incomplete_upstream(conn, 2) is True
