"""Tests for automation.ui.impact.impact_logic — pure Python impact display logic."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.ui.impact.impact_logic import (
    ImpactDisplayRow,
    compute_impact_summary,
    get_revision_eligibility,
    get_revision_reason,
    group_impacts_by_table,
    load_change_sets,
    load_flagged_work_items,
    load_impacts_for_change_set,
    load_impacts_for_work_item,
    mark_impact_reviewed,
    mark_impacts_reviewed_bulk,
    pop_revision_reason,
    store_revision_reason,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed_work_item(conn, wi_id=1, item_type="master_prd", status="in_progress"):
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) VALUES (?, ?, ?)",
        (wi_id, item_type, status),
    )
    conn.commit()


def _seed_session(conn, session_id=1, work_item_id=1, session_type="initial"):
    conn.execute(
        "INSERT INTO AISession (id, work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (?, ?, ?, 'test prompt', 'imported', "
        "CURRENT_TIMESTAMP)",
        (session_id, work_item_id, session_type),
    )
    conn.commit()


def _seed_changelog(conn, cl_id=1, session_id=1, table_name="Entity",
                    change_type="update", field_name="name"):
    conn.execute(
        "INSERT INTO ChangeLog (id, session_id, table_name, record_id, change_type, "
        "field_name, changed_at) VALUES (?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP)",
        (cl_id, session_id, table_name, change_type, field_name),
    )
    conn.commit()


def _seed_impact(conn, ci_id=1, cl_id=1, table="Entity", record_id=1,
                 requires_review=True, reviewed=False, action_required=False):
    conn.execute(
        "INSERT INTO ChangeImpact (id, change_log_id, affected_table, "
        "affected_record_id, impact_description, requires_review, reviewed, "
        "action_required) VALUES (?, ?, ?, ?, 'Test impact', ?, ?, ?)",
        (ci_id, cl_id, table, record_id,
         1 if requires_review else 0,
         1 if reviewed else 0,
         1 if action_required else 0),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Revision reason cache
# ---------------------------------------------------------------------------

class TestRevisionReasonCache:

    def test_store_and_get(self):
        store_revision_reason(999, "Field split required")
        assert get_revision_reason(999) == "Field split required"
        # Cleanup
        pop_revision_reason(999)

    def test_pop_removes(self):
        store_revision_reason(998, "Test reason")
        assert pop_revision_reason(998) == "Test reason"
        assert get_revision_reason(998) is None

    def test_get_missing(self):
        assert get_revision_reason(9999) is None

    def test_pop_missing(self):
        assert pop_revision_reason(9999) is None


# ---------------------------------------------------------------------------
# Grouping helpers
# ---------------------------------------------------------------------------

class TestGroupImpactsByTable:

    def _row(self, table="Entity", requires_review=True, **kwargs):
        defaults = {
            "id": 1, "change_log_id": 1, "affected_table": table,
            "affected_record_id": 1, "impact_description": "desc",
            "requires_review": requires_review, "reviewed": False,
            "reviewed_at": None, "action_required": False,
            "source_summary": "Updated Entity",
        }
        defaults.update(kwargs)
        return ImpactDisplayRow(**defaults)

    def test_empty(self):
        assert group_impacts_by_table([]) == {}

    def test_single_table(self):
        rows = [self._row(id=1), self._row(id=2, requires_review=False)]
        result = group_impacts_by_table(rows)
        assert "Entity" in result
        review_list, info_list = result["Entity"]
        assert len(review_list) == 1
        assert len(info_list) == 1

    def test_multiple_tables(self):
        rows = [
            self._row(id=1, table="Entity"),
            self._row(id=2, table="Field"),
            self._row(id=3, table="Entity", requires_review=False),
        ]
        result = group_impacts_by_table(rows)
        assert len(result) == 2
        assert len(result["Entity"][0]) == 1  # requires_review
        assert len(result["Entity"][1]) == 1  # informational
        assert len(result["Field"][0]) == 1


class TestComputeImpactSummary:

    def _row(self, requires_review=True, reviewed=False, **kwargs):
        defaults = {
            "id": 1, "change_log_id": 1, "affected_table": "Entity",
            "affected_record_id": 1, "impact_description": "desc",
            "requires_review": requires_review, "reviewed": reviewed,
            "reviewed_at": None, "action_required": False,
            "source_summary": "Updated Entity",
        }
        defaults.update(kwargs)
        return ImpactDisplayRow(**defaults)

    def test_empty(self):
        s = compute_impact_summary([])
        assert s.total == 0
        assert s.requires_review == 0

    def test_mixed(self):
        rows = [
            self._row(id=1, requires_review=True, reviewed=False),
            self._row(id=2, requires_review=True, reviewed=True),
            self._row(id=3, requires_review=False, reviewed=False),
        ]
        s = compute_impact_summary(rows)
        assert s.total == 3
        assert s.requires_review == 2
        assert s.informational == 1
        assert s.reviewed == 1


# ---------------------------------------------------------------------------
# Revision eligibility
# ---------------------------------------------------------------------------

class TestRevisionEligibility:

    def test_complete_eligible(self):
        eligible, reason = get_revision_eligibility("complete")
        assert eligible is True

    def test_in_progress_not_eligible(self):
        eligible, reason = get_revision_eligibility("in_progress")
        assert eligible is False
        assert "in_progress" in reason

    def test_blocked_not_eligible(self):
        eligible, reason = get_revision_eligibility("blocked")
        assert eligible is False

    def test_not_started_not_eligible(self):
        eligible, reason = get_revision_eligibility("not_started")
        assert eligible is False

    def test_ready_not_eligible(self):
        eligible, reason = get_revision_eligibility("ready")
        assert eligible is False


# ---------------------------------------------------------------------------
# Database queries
# ---------------------------------------------------------------------------

class TestLoadImpactsForWorkItem:

    def test_no_impacts(self, conn):
        _seed_work_item(conn)
        result = load_impacts_for_work_item(conn, 1)
        assert result == []

    def test_returns_impacts(self, conn):
        _seed_work_item(conn)
        _seed_session(conn)
        _seed_changelog(conn)
        _seed_impact(conn)
        result = load_impacts_for_work_item(conn, 1)
        assert len(result) == 1
        assert result[0].affected_table == "Entity"
        assert result[0].source_summary != ""


class TestLoadChangeSets:

    def test_empty(self, conn):
        result = load_change_sets(conn)
        assert result == []

    def test_groups_by_session(self, conn):
        _seed_work_item(conn)
        _seed_session(conn, session_id=1)
        _seed_changelog(conn, cl_id=1, session_id=1)
        _seed_changelog(conn, cl_id=2, session_id=1, field_name="code")
        _seed_impact(conn, ci_id=1, cl_id=1)
        _seed_impact(conn, ci_id=2, cl_id=2)
        result = load_change_sets(conn)
        assert len(result) == 1
        assert result[0].key == "session:1"
        assert result[0].unreviewed_count == 2

    def test_excludes_fully_reviewed(self, conn):
        _seed_work_item(conn)
        _seed_session(conn, session_id=1)
        _seed_changelog(conn, cl_id=1, session_id=1)
        _seed_impact(conn, ci_id=1, cl_id=1, reviewed=True)
        result = load_change_sets(conn)
        assert result == []


class TestLoadImpactsForChangeSet:

    def test_empty(self, conn):
        result = load_impacts_for_change_set(conn, [])
        assert result == []

    def test_returns_matching(self, conn):
        _seed_work_item(conn)
        _seed_session(conn)
        _seed_changelog(conn)
        _seed_impact(conn, ci_id=1, cl_id=1)
        _seed_impact(conn, ci_id=2, cl_id=1)
        result = load_impacts_for_change_set(conn, [1, 2])
        assert len(result) == 2


class TestMarkImpactReviewed:

    def test_marks_no_action(self, conn):
        _seed_work_item(conn)
        _seed_session(conn)
        _seed_changelog(conn)
        _seed_impact(conn, ci_id=1, cl_id=1)

        mark_impact_reviewed(conn, 1, action_required=False)

        row = conn.execute(
            "SELECT reviewed, action_required, reviewed_at FROM ChangeImpact WHERE id = 1"
        ).fetchone()
        assert row[0] == 1  # reviewed
        assert row[1] == 0  # not action_required
        assert row[2] is not None  # reviewed_at set

    def test_marks_action_required(self, conn):
        _seed_work_item(conn)
        _seed_session(conn)
        _seed_changelog(conn)
        _seed_impact(conn, ci_id=1, cl_id=1)

        mark_impact_reviewed(conn, 1, action_required=True)

        row = conn.execute(
            "SELECT reviewed, action_required FROM ChangeImpact WHERE id = 1"
        ).fetchone()
        assert row[0] == 1
        assert row[1] == 1


class TestMarkImpactsReviewedBulk:

    def test_bulk_marks(self, conn):
        _seed_work_item(conn)
        _seed_session(conn)
        _seed_changelog(conn, cl_id=1)
        _seed_changelog(conn, cl_id=2, field_name="code")
        _seed_impact(conn, ci_id=1, cl_id=1)
        _seed_impact(conn, ci_id=2, cl_id=2)

        mark_impacts_reviewed_bulk(conn, [1, 2], action_required=False)

        for cid in (1, 2):
            row = conn.execute(
                "SELECT reviewed FROM ChangeImpact WHERE id = ?", (cid,)
            ).fetchone()
            assert row[0] == 1

    def test_empty_list(self, conn):
        # Should not raise
        mark_impacts_reviewed_bulk(conn, [], action_required=False)


class TestLoadFlaggedWorkItems:

    def test_empty(self, conn):
        result = load_flagged_work_items(conn)
        assert result == []

    def test_returns_flagged(self, conn):
        _seed_work_item(conn, wi_id=1, item_type="master_prd", status="complete")
        _seed_session(conn)
        _seed_changelog(conn, table_name="Persona")
        # Persona maps to master_prd
        conn.execute(
            "INSERT INTO Persona (id, name, code) VALUES (1, 'Admin', 'ADM')"
        )
        conn.commit()
        _seed_impact(conn, ci_id=1, cl_id=1, table="Persona",
                     reviewed=True, action_required=True)

        result = load_flagged_work_items(conn)
        assert len(result) == 1
        assert result[0].work_item_id == 1
        assert result[0].eligible is True
        assert result[0].flagged_count == 1
