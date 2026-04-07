"""Tests for automation.workflow.available — available work calculation."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.workflow.available import get_available_work


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


def _insert_work_item(conn, item_type, status="not_started", domain_id=None,
                       entity_id=None, process_id=None):
    cur = conn.execute(
        "INSERT INTO WorkItem (item_type, status, domain_id, entity_id, process_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (item_type, status, domain_id, entity_id, process_id),
    )
    conn.commit()
    return cur.lastrowid


class TestGetAvailableWork:
    """Tests for get_available_work()."""

    def test_empty_database(self, conn):
        assert get_available_work(conn) == []

    def test_only_ready_and_in_progress_returned(self, conn):
        _insert_work_item(conn, "master_prd", status="ready")
        _insert_work_item(conn, "business_object_discovery", status="not_started")
        _insert_work_item(conn, "crm_selection", status="complete")
        result = get_available_work(conn)
        assert len(result) == 1
        assert result[0]["item_type"] == "master_prd"

    def test_in_progress_before_ready(self, conn):
        _insert_work_item(conn, "master_prd", status="ready")
        _insert_work_item(conn, "business_object_discovery", status="in_progress")
        result = get_available_work(conn)
        assert result[0]["status"] == "in_progress"
        assert result[1]["status"] == "ready"

    def test_ordered_by_phase(self, conn):
        d1 = _insert_domain(conn, "D1", "D1", sort_order=1)
        _insert_work_item(conn, "yaml_generation", status="ready", domain_id=d1)
        _insert_work_item(conn, "entity_prd", status="ready", domain_id=d1)
        result = get_available_work(conn)
        # entity_prd is phase 2, yaml_generation is phase 8
        assert result[0]["phase"] == 2
        assert result[1]["phase"] == 8

    def test_ordered_by_domain_sort_order_within_phase(self, conn):
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        d2 = _insert_domain(conn, "Recruitment", "MR", sort_order=2)
        _insert_work_item(conn, "domain_overview", status="ready", domain_id=d2)
        _insert_work_item(conn, "domain_overview", status="ready", domain_id=d1)
        result = get_available_work(conn)
        assert result[0]["domain_sort_order"] == 1
        assert result[1]["domain_sort_order"] == 2

    def test_null_domain_sorts_last(self, conn):
        d1 = _insert_domain(conn, "D1", "D1", sort_order=1)
        _insert_work_item(conn, "master_prd", status="ready")  # no domain
        _insert_work_item(conn, "entity_prd", status="ready", domain_id=d1)
        result = get_available_work(conn)
        # Both are phase 1 and 2; master_prd (phase 1) < entity_prd (phase 2)
        assert result[0]["item_type"] == "master_prd"
        assert result[1]["item_type"] == "entity_prd"

    def test_service_domain_items_get_phase_4(self, conn):
        d1 = _insert_domain(conn, "Services", "SVC", sort_order=1, is_service=True)
        _insert_work_item(conn, "domain_overview", status="ready", domain_id=d1)
        result = get_available_work(conn)
        assert result[0]["phase"] == 4

    def test_non_service_domain_overview_gets_phase_3(self, conn):
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        _insert_work_item(conn, "domain_overview", status="ready", domain_id=d1)
        result = get_available_work(conn)
        assert result[0]["phase"] == 3

    def test_includes_domain_name(self, conn):
        d1 = _insert_domain(conn, "Mentoring", "MN", sort_order=1)
        _insert_work_item(conn, "domain_overview", status="ready", domain_id=d1)
        result = get_available_work(conn)
        assert result[0]["domain_name"] == "Mentoring"

    def test_cross_domain_null_domain_sorts_last_within_phase(self, conn):
        d1 = _insert_domain(conn, "D1", "D1", sort_order=1)
        # crm_selection has no domain, stakeholder_review has a domain
        # Both status=ready but different phases; test null sorting
        _insert_work_item(conn, "crm_selection", status="ready")
        _insert_work_item(conn, "stakeholder_review", status="ready", domain_id=d1)
        result = get_available_work(conn)
        # stakeholder_review is phase 7, crm_selection is phase 9
        assert result[0]["item_type"] == "stakeholder_review"
        assert result[1]["item_type"] == "crm_selection"
