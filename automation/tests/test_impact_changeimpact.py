"""Tests for automation.impact.changeimpact — ChangeImpact record creation."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.impact.changeimpact import (
    CandidateImpact,
    build_candidates,
    write_change_impacts,
)
from automation.impact.queries import AffectedRecord


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _setup_changelog(conn):
    """Create minimal data for ChangeLog entries."""
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) VALUES (1, 'master_prd', 'in_progress')"
    )
    conn.execute(
        "INSERT INTO AISession (id, work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (1, 1, 'initial', 'p', 'imported', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO Domain (id, name, code, sort_order) VALUES (1, 'Test', 'TST', 1)"
    )
    conn.execute(
        "INSERT INTO Entity (id, name, code, entity_type, is_native) "
        "VALUES (1, 'Contact', 'CONTACT', 'Person', 0)"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type) "
        "VALUES (1, 1, 'testField', 'Test Field', 'varchar')"
    )
    conn.execute(
        "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
        "change_type, field_name, old_value, new_value, changed_at) "
        "VALUES (1, 1, 'Field', 1, 'update', 'field_type', 'varchar', 'text', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
        "change_type, field_name, old_value, new_value, changed_at) "
        "VALUES (2, 1, 'Field', 1, 'update', 'label', 'Old Label', 'New Label', '2025-01-01')"
    )
    conn.commit()


class TestBuildCandidates:

    def test_converts_affected_records(self):
        affected = [
            AffectedRecord("ProcessField", 10, "Process uses field", True),
            AffectedRecord("Decision", 20, "Decision scoped", False),
        ]
        candidates = build_candidates(1, affected)
        assert len(candidates) == 2
        assert candidates[0].change_log_id == 1
        assert candidates[0].affected_table == "ProcessField"
        assert candidates[0].requires_review is True
        assert candidates[1].requires_review is False


class TestWriteChangeImpacts:

    def test_writes_rows(self, conn):
        _setup_changelog(conn)
        candidates = [
            CandidateImpact(1, "ProcessField", 10, "Impact desc 1", True),
            CandidateImpact(1, "Decision", 20, "Impact desc 2", False),
        ]
        ids = write_change_impacts(conn, candidates)
        assert len(ids) == 2

        rows = conn.execute("SELECT * FROM ChangeImpact").fetchall()
        assert len(rows) == 2

    def test_requires_review_persisted(self, conn):
        _setup_changelog(conn)
        candidates = [
            CandidateImpact(1, "ProcessField", 10, "desc", True),
            CandidateImpact(1, "Decision", 20, "desc", False),
        ]
        write_change_impacts(conn, candidates)

        rows = conn.execute(
            "SELECT affected_table, requires_review FROM ChangeImpact ORDER BY id"
        ).fetchall()
        assert rows[0] == ("ProcessField", 1)  # True
        assert rows[1] == ("Decision", 0)  # False

    def test_reviewed_default_false(self, conn):
        _setup_changelog(conn)
        candidates = [CandidateImpact(1, "Field", 1, "desc", True)]
        write_change_impacts(conn, candidates)

        row = conn.execute(
            "SELECT reviewed FROM ChangeImpact"
        ).fetchone()
        assert row[0] == 0  # False

    def test_empty_list_returns_empty(self, conn):
        ids = write_change_impacts(conn, [])
        assert ids == []

    def test_atomic_write(self, conn):
        """All rows are written in a single transaction."""
        _setup_changelog(conn)
        candidates = [
            CandidateImpact(1, "Field", 1, "desc1", True),
            CandidateImpact(1, "Field", 2, "desc2", True),
            CandidateImpact(1, "Field", 3, "desc3", True),
        ]
        ids = write_change_impacts(conn, candidates)
        assert len(ids) == 3

        count = conn.execute("SELECT COUNT(*) FROM ChangeImpact").fetchone()[0]
        assert count == 3

    def test_impact_description_stored(self, conn):
        _setup_changelog(conn)
        candidates = [
            CandidateImpact(1, "Field", 1, "Specific impact description here", True)
        ]
        write_change_impacts(conn, candidates)

        row = conn.execute(
            "SELECT impact_description FROM ChangeImpact"
        ).fetchone()
        assert row[0] == "Specific impact description here"
