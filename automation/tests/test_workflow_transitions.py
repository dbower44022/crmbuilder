"""Tests for automation.workflow.transitions — status transitions and side effects."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.workflow.transitions import (
    UPSTREAM_REVISION_PREFIX,
    complete,
    revise,
    start,
)


@pytest.fixture()
def conn(tmp_path):
    """Create a client database and return an open connection."""
    db_path = tmp_path / "test.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _insert_work_item(conn, item_type="master_prd", status="not_started",
                       domain_id=None, entity_id=None, process_id=None):
    cur = conn.execute(
        "INSERT INTO WorkItem (item_type, status, domain_id, entity_id, process_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (item_type, status, domain_id, entity_id, process_id),
    )
    conn.commit()
    return cur.lastrowid


def _insert_dependency(conn, work_item_id, depends_on_id):
    conn.execute(
        "INSERT INTO Dependency (work_item_id, depends_on_id) VALUES (?, ?)",
        (work_item_id, depends_on_id),
    )
    conn.commit()


def _get_status(conn, wid):
    return conn.execute(
        "SELECT status FROM WorkItem WHERE id = ?", (wid,)
    ).fetchone()[0]


def _get_work_item(conn, wid):
    row = conn.execute(
        "SELECT status, blocked_reason, status_before_blocked, started_at, completed_at "
        "FROM WorkItem WHERE id = ?",
        (wid,),
    ).fetchone()
    return {
        "status": row[0], "blocked_reason": row[1],
        "status_before_blocked": row[2],
        "started_at": row[3], "completed_at": row[4],
    }


class TestStart:
    """Tests for start() — ready → in_progress."""

    def test_ready_to_in_progress(self, conn):
        wid = _insert_work_item(conn, status="ready")
        start(conn, wid)
        assert _get_status(conn, wid) == "in_progress"

    def test_sets_started_at(self, conn):
        wid = _insert_work_item(conn, status="ready")
        start(conn, wid)
        wi = _get_work_item(conn, wid)
        assert wi["started_at"] is not None

    def test_rejects_not_started(self, conn):
        wid = _insert_work_item(conn, status="not_started")
        with pytest.raises(ValueError, match="expected 'ready'"):
            start(conn, wid)

    def test_rejects_in_progress(self, conn):
        wid = _insert_work_item(conn, status="in_progress")
        with pytest.raises(ValueError, match="expected 'ready'"):
            start(conn, wid)

    def test_rejects_complete(self, conn):
        wid = _insert_work_item(conn, status="complete")
        with pytest.raises(ValueError, match="expected 'ready'"):
            start(conn, wid)

    def test_not_found(self, conn):
        with pytest.raises(ValueError, match="not found"):
            start(conn, 999)


class TestComplete:
    """Tests for complete() — in_progress → complete."""

    def test_in_progress_to_complete(self, conn):
        wid = _insert_work_item(conn, status="in_progress")
        complete(conn, wid)
        assert _get_status(conn, wid) == "complete"

    def test_sets_completed_at(self, conn):
        wid = _insert_work_item(conn, status="in_progress")
        complete(conn, wid)
        wi = _get_work_item(conn, wid)
        assert wi["completed_at"] is not None

    def test_downstream_recalculation(self, conn):
        upstream = _insert_work_item(conn, status="in_progress")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="not_started",
        )
        _insert_dependency(conn, downstream, upstream)
        transitioned = complete(conn, upstream)
        assert downstream in transitioned
        assert _get_status(conn, downstream) == "ready"

    def test_downstream_stays_not_started_with_other_deps(self, conn):
        up1 = _insert_work_item(conn, status="in_progress")
        up2 = _insert_work_item(conn, item_type="business_object_discovery", status="not_started")
        downstream = _insert_work_item(
            conn, item_type="entity_prd", status="not_started",
        )
        _insert_dependency(conn, downstream, up1)
        _insert_dependency(conn, downstream, up2)
        complete(conn, up1)
        assert _get_status(conn, downstream) == "not_started"

    def test_rejects_ready(self, conn):
        wid = _insert_work_item(conn, status="ready")
        with pytest.raises(ValueError, match="expected 'in_progress'"):
            complete(conn, wid)

    def test_rejects_not_started(self, conn):
        wid = _insert_work_item(conn, status="not_started")
        with pytest.raises(ValueError, match="expected 'in_progress'"):
            complete(conn, wid)

    def test_not_found(self, conn):
        with pytest.raises(ValueError, match="not found"):
            complete(conn, 999)


class TestRevise:
    """Tests for revise() — complete → in_progress with cascade."""

    def test_complete_to_in_progress(self, conn):
        wid = _insert_work_item(conn, status="complete")
        revise(conn, wid)
        assert _get_status(conn, wid) == "in_progress"

    def test_clears_completed_at(self, conn):
        wid = _insert_work_item(conn, status="complete")
        revise(conn, wid)
        wi = _get_work_item(conn, wid)
        assert wi["completed_at"] is None

    def test_ready_downstream_becomes_not_started(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="ready",
        )
        _insert_dependency(conn, downstream, upstream)
        affected = revise(conn, upstream)
        assert downstream in affected
        assert _get_status(conn, downstream) == "not_started"

    def test_in_progress_downstream_becomes_blocked(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="in_progress",
        )
        _insert_dependency(conn, downstream, upstream)
        affected = revise(conn, upstream)
        assert downstream in affected
        wi = _get_work_item(conn, downstream)
        assert wi["status"] == "blocked"
        assert wi["status_before_blocked"] == "in_progress"
        assert wi["blocked_reason"].startswith(UPSTREAM_REVISION_PREFIX)

    def test_complete_downstream_becomes_blocked(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="complete",
        )
        _insert_dependency(conn, downstream, upstream)
        affected = revise(conn, upstream)
        assert downstream in affected
        wi = _get_work_item(conn, downstream)
        assert wi["status"] == "blocked"
        assert wi["status_before_blocked"] == "complete"

    def test_not_started_downstream_unaffected(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="not_started",
        )
        _insert_dependency(conn, downstream, upstream)
        affected = revise(conn, upstream)
        assert downstream not in affected
        assert _get_status(conn, downstream) == "not_started"

    def test_already_blocked_downstream_unaffected(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        # Manually block the downstream for a different reason
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="blocked",
        )
        conn.execute(
            "UPDATE WorkItem SET blocked_reason = 'manual reason', "
            "status_before_blocked = 'ready' WHERE id = ?",
            (downstream,),
        )
        conn.commit()
        _insert_dependency(conn, downstream, upstream)
        affected = revise(conn, upstream)
        assert downstream not in affected
        assert _get_status(conn, downstream) == "blocked"
        # blocked_reason unchanged
        wi = _get_work_item(conn, downstream)
        assert wi["blocked_reason"] == "manual reason"

    def test_transitive_cascade(self, conn):
        """Revision cascades through multi-level dependencies."""
        a = _insert_work_item(conn, status="complete")
        b = _insert_work_item(conn, item_type="business_object_discovery", status="complete")
        c = _insert_work_item(conn, item_type="entity_prd", status="ready")
        _insert_dependency(conn, b, a)
        _insert_dependency(conn, c, b)
        affected = revise(conn, a)
        assert b in affected
        assert c in affected
        assert _get_status(conn, b) == "blocked"
        # c was ready, so it becomes not_started
        assert _get_status(conn, c) == "not_started"

    def test_blocked_reason_format(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="in_progress",
        )
        _insert_dependency(conn, downstream, upstream)
        revise(conn, upstream)
        wi = _get_work_item(conn, downstream)
        reason = wi["blocked_reason"]
        assert reason.startswith(UPSTREAM_REVISION_PREFIX)
        assert f"Work Item #{upstream}" in reason
        assert "master_prd" in reason

    def test_rejects_non_complete(self, conn):
        wid = _insert_work_item(conn, status="in_progress")
        with pytest.raises(ValueError, match="expected 'complete'"):
            revise(conn, wid)

    def test_not_found(self, conn):
        with pytest.raises(ValueError, match="not found"):
            revise(conn, 999)


class TestCompleteAfterRevision:
    """Test that completing a revised item unblocks downstream."""

    def test_unblocks_downstream_after_revision_completes(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="in_progress",
        )
        _insert_dependency(conn, downstream, upstream)

        # Revise upstream — downstream becomes blocked
        revise(conn, upstream)
        assert _get_status(conn, downstream) == "blocked"

        # Complete the revised upstream
        transitioned = complete(conn, upstream)
        assert downstream in transitioned
        # Should restore to status_before_blocked (in_progress)
        assert _get_status(conn, downstream) == "in_progress"

    def test_unblocks_to_not_started_when_other_deps_incomplete(self, conn):
        up1 = _insert_work_item(conn, status="complete")
        up2 = _insert_work_item(conn, item_type="business_object_discovery", status="not_started")
        downstream = _insert_work_item(
            conn, item_type="entity_prd", status="in_progress",
        )
        _insert_dependency(conn, downstream, up1)
        _insert_dependency(conn, downstream, up2)

        revise(conn, up1)
        assert _get_status(conn, downstream) == "blocked"

        complete(conn, up1)
        # up2 is still not complete, so downstream goes to not_started
        assert _get_status(conn, downstream) == "not_started"
