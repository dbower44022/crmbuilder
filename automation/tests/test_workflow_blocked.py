"""Tests for automation.workflow.blocked — blocked state handling."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.workflow.blocked import block, is_automatic_block, unblock
from automation.workflow.transitions import UPSTREAM_REVISION_PREFIX, complete, revise


@pytest.fixture()
def conn(tmp_path):
    """Create a client database and return an open connection."""
    db_path = tmp_path / "test.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _insert_work_item(conn, item_type="master_prd", status="not_started",
                       domain_id=None):
    cur = conn.execute(
        "INSERT INTO WorkItem (item_type, status, domain_id) VALUES (?, ?, ?)",
        (item_type, status, domain_id),
    )
    conn.commit()
    return cur.lastrowid


def _insert_dependency(conn, work_item_id, depends_on_id):
    conn.execute(
        "INSERT INTO Dependency (work_item_id, depends_on_id) VALUES (?, ?)",
        (work_item_id, depends_on_id),
    )
    conn.commit()


def _get_work_item(conn, wid):
    row = conn.execute(
        "SELECT status, blocked_reason, status_before_blocked "
        "FROM WorkItem WHERE id = ?",
        (wid,),
    ).fetchone()
    return {
        "status": row[0], "blocked_reason": row[1],
        "status_before_blocked": row[2],
    }


class TestIsAutomaticBlock:
    """Tests for is_automatic_block()."""

    def test_automatic_reason(self):
        reason = f"{UPSTREAM_REVISION_PREFIX}master_prd — Test (Work Item #1)"
        assert is_automatic_block(reason) is True

    def test_manual_reason(self):
        assert is_automatic_block("Waiting for stakeholder") is False

    def test_none_reason(self):
        assert is_automatic_block(None) is False


class TestBlock:
    """Tests for block() — manual blocking."""

    def test_block_ready_item(self, conn):
        wid = _insert_work_item(conn, status="ready")
        block(conn, wid, "Waiting for stakeholder")
        wi = _get_work_item(conn, wid)
        assert wi["status"] == "blocked"
        assert wi["blocked_reason"] == "Waiting for stakeholder"
        assert wi["status_before_blocked"] == "ready"

    def test_block_in_progress_item(self, conn):
        wid = _insert_work_item(conn, status="in_progress")
        block(conn, wid, "Vendor decision pending")
        wi = _get_work_item(conn, wid)
        assert wi["status"] == "blocked"
        assert wi["status_before_blocked"] == "in_progress"

    def test_block_complete_item(self, conn):
        wid = _insert_work_item(conn, status="complete")
        block(conn, wid, "Need to revisit")
        wi = _get_work_item(conn, wid)
        assert wi["status"] == "blocked"
        assert wi["status_before_blocked"] == "complete"

    def test_cannot_block_not_started(self, conn):
        wid = _insert_work_item(conn, status="not_started")
        with pytest.raises(ValueError, match="not_started"):
            block(conn, wid, "Some reason")

    def test_cannot_block_already_blocked(self, conn):
        wid = _insert_work_item(conn, status="ready")
        block(conn, wid, "First reason")
        with pytest.raises(ValueError, match="already blocked"):
            block(conn, wid, "Second reason")

    def test_not_found(self, conn):
        with pytest.raises(ValueError, match="not found"):
            block(conn, 999, "Some reason")


class TestUnblock:
    """Tests for unblock() — manual unblocking."""

    def test_unblock_restores_status(self, conn):
        wid = _insert_work_item(conn, status="ready")
        block(conn, wid, "Waiting for stakeholder")
        unblock(conn, wid)
        wi = _get_work_item(conn, wid)
        assert wi["status"] == "ready"
        assert wi["blocked_reason"] is None
        assert wi["status_before_blocked"] is None

    def test_unblock_restores_in_progress(self, conn):
        wid = _insert_work_item(conn, status="in_progress")
        block(conn, wid, "Paused")
        unblock(conn, wid)
        assert _get_work_item(conn, wid)["status"] == "in_progress"

    def test_unblock_to_not_started_when_deps_incomplete(self, conn):
        upstream = _insert_work_item(conn, status="not_started")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="in_progress",
        )
        _insert_dependency(conn, downstream, upstream)
        block(conn, downstream, "Paused")
        unblock(conn, downstream)
        # Upstream is not complete, so downstream can't be in_progress
        assert _get_work_item(conn, downstream)["status"] == "not_started"

    def test_cannot_unblock_non_blocked(self, conn):
        wid = _insert_work_item(conn, status="ready")
        with pytest.raises(ValueError, match="expected 'blocked'"):
            unblock(conn, wid)

    def test_not_found(self, conn):
        with pytest.raises(ValueError, match="not found"):
            unblock(conn, 999)


class TestAutomaticBlockUnblock:
    """End-to-end tests for automatic blocking via revision and unblocking."""

    def test_revision_blocks_then_completion_unblocks(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="in_progress",
        )
        _insert_dependency(conn, downstream, upstream)

        # Revise upstream — downstream blocked
        revise(conn, upstream)
        wi = _get_work_item(conn, downstream)
        assert wi["status"] == "blocked"
        assert is_automatic_block(wi["blocked_reason"])
        assert wi["status_before_blocked"] == "in_progress"

        # Complete upstream — downstream unblocked
        complete(conn, upstream)
        wi = _get_work_item(conn, downstream)
        assert wi["status"] == "in_progress"
        assert wi["blocked_reason"] is None
        assert wi["status_before_blocked"] is None

    def test_automatic_block_preserves_complete_status(self, conn):
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="complete",
        )
        _insert_dependency(conn, downstream, upstream)

        revise(conn, upstream)
        wi = _get_work_item(conn, downstream)
        assert wi["status_before_blocked"] == "complete"

        # Complete upstream — downstream restored to complete
        complete(conn, upstream)
        assert _get_work_item(conn, downstream)["status"] == "complete"

    def test_manual_block_survives_upstream_revision(self, conn):
        """A manually blocked item is not affected by upstream revision."""
        upstream = _insert_work_item(conn, status="complete")
        downstream = _insert_work_item(
            conn, item_type="business_object_discovery", status="in_progress",
        )
        _insert_dependency(conn, downstream, upstream)

        # Manually block downstream first
        block(conn, downstream, "Manual hold")

        # Revise upstream — downstream already blocked, unaffected
        revise(conn, upstream)
        wi = _get_work_item(conn, downstream)
        assert wi["status"] == "blocked"
        assert wi["blocked_reason"] == "Manual hold"
