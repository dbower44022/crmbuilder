"""Tests for automation.workflow.status — status calculation logic."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.workflow.status import calculate_status, recalculate_downstream


@pytest.fixture()
def conn(tmp_path):
    """Create a client database and return an open connection."""
    db_path = tmp_path / "test.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _insert_work_item(conn, item_type="master_prd", status="not_started"):
    """Insert a WorkItem and return its id."""
    cur = conn.execute(
        "INSERT INTO WorkItem (item_type, status) VALUES (?, ?)",
        (item_type, status),
    )
    conn.commit()
    return cur.lastrowid


def _insert_dependency(conn, work_item_id, depends_on_id):
    """Insert a Dependency row."""
    conn.execute(
        "INSERT INTO Dependency (work_item_id, depends_on_id) VALUES (?, ?)",
        (work_item_id, depends_on_id),
    )
    conn.commit()


class TestCalculateStatus:
    """Tests for calculate_status()."""

    def test_no_dependencies_returns_ready(self, conn):
        wid = _insert_work_item(conn)
        assert calculate_status(conn, wid) == "ready"

    def test_all_deps_complete_returns_ready(self, conn):
        dep1 = _insert_work_item(conn, status="complete")
        dep2 = _insert_work_item(conn, status="complete")
        item = _insert_work_item(conn, item_type="business_object_discovery")
        _insert_dependency(conn, item, dep1)
        _insert_dependency(conn, item, dep2)
        assert calculate_status(conn, item) == "ready"

    def test_some_deps_incomplete_returns_not_started(self, conn):
        dep1 = _insert_work_item(conn, status="complete")
        dep2 = _insert_work_item(conn, status="in_progress")
        item = _insert_work_item(conn, item_type="business_object_discovery")
        _insert_dependency(conn, item, dep1)
        _insert_dependency(conn, item, dep2)
        assert calculate_status(conn, item) == "not_started"

    def test_single_incomplete_dep(self, conn):
        dep = _insert_work_item(conn, status="not_started")
        item = _insert_work_item(conn, item_type="business_object_discovery")
        _insert_dependency(conn, item, dep)
        assert calculate_status(conn, item) == "not_started"

    def test_blocked_dep_counts_as_incomplete(self, conn):
        dep = _insert_work_item(conn, status="blocked")
        item = _insert_work_item(conn, item_type="business_object_discovery")
        _insert_dependency(conn, item, dep)
        assert calculate_status(conn, item) == "not_started"


class TestRecalculateDownstream:
    """Tests for recalculate_downstream()."""

    def test_downstream_transitions_to_ready(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="not_started",
        )
        _insert_dependency(conn, downstream, upstream)
        transitioned = recalculate_downstream(conn, upstream)
        assert downstream in transitioned
        row = conn.execute(
            "SELECT status FROM WorkItem WHERE id = ?", (downstream,)
        ).fetchone()
        assert row[0] == "ready"

    def test_downstream_stays_not_started_if_other_deps_incomplete(self, conn):
        upstream1 = _insert_work_item(conn, status="complete")
        upstream2 = _insert_work_item(conn, status="in_progress")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="not_started",
        )
        _insert_dependency(conn, downstream, upstream1)
        _insert_dependency(conn, downstream, upstream2)
        transitioned = recalculate_downstream(conn, upstream1)
        assert transitioned == []
        row = conn.execute(
            "SELECT status FROM WorkItem WHERE id = ?", (downstream,)
        ).fetchone()
        assert row[0] == "not_started"

    def test_only_not_started_items_are_recalculated(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        # An in_progress downstream should not be touched
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="in_progress",
        )
        _insert_dependency(conn, downstream, upstream)
        transitioned = recalculate_downstream(conn, upstream)
        assert transitioned == []
        row = conn.execute(
            "SELECT status FROM WorkItem WHERE id = ?", (downstream,)
        ).fetchone()
        assert row[0] == "in_progress"

    def test_multiple_downstream_items(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        d1 = _insert_work_item(conn, item_type="entity_prd", status="not_started")
        d2 = _insert_work_item(conn, item_type="entity_prd", status="not_started")
        _insert_dependency(conn, d1, upstream)
        _insert_dependency(conn, d2, upstream)
        transitioned = recalculate_downstream(conn, upstream)
        assert set(transitioned) == {d1, d2}
