"""Tests for automation.workflow.domain_overview — Domain Overview output."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.workflow.domain_overview import save_domain_overview_text


@pytest.fixture()
def conn(tmp_path):
    """Create a client database and return an open connection."""
    db_path = tmp_path / "test.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _insert_domain(conn, name, code):
    cur = conn.execute(
        "INSERT INTO Domain (name, code) VALUES (?, ?)", (name, code)
    )
    conn.commit()
    return cur.lastrowid


class TestSaveDomainOverviewText:
    """Tests for save_domain_overview_text()."""

    def test_writes_text_to_domain(self, conn):
        did = _insert_domain(conn, "Mentoring", "MN")
        save_domain_overview_text(conn, did, "Overview of Mentoring domain")
        row = conn.execute(
            "SELECT domain_overview_text FROM Domain WHERE id = ?", (did,)
        ).fetchone()
        assert row[0] == "Overview of Mentoring domain"

    def test_overwrites_existing_text(self, conn):
        did = _insert_domain(conn, "Mentoring", "MN")
        save_domain_overview_text(conn, did, "First version")
        save_domain_overview_text(conn, did, "Second version")
        row = conn.execute(
            "SELECT domain_overview_text FROM Domain WHERE id = ?", (did,)
        ).fetchone()
        assert row[0] == "Second version"

    def test_updates_updated_at(self, conn):
        did = _insert_domain(conn, "Mentoring", "MN")
        save_domain_overview_text(conn, did, "New text")
        after = conn.execute(
            "SELECT updated_at FROM Domain WHERE id = ?", (did,)
        ).fetchone()[0]
        assert after is not None

    def test_domain_not_found_raises(self, conn):
        with pytest.raises(ValueError, match="Domain 999 not found"):
            save_domain_overview_text(conn, 999, "Some text")

    def test_writes_to_correct_domain(self, conn):
        d1 = _insert_domain(conn, "Mentoring", "MN")
        d2 = _insert_domain(conn, "Recruitment", "MR")
        save_domain_overview_text(conn, d1, "Mentoring overview")
        # d2 should be unaffected
        row = conn.execute(
            "SELECT domain_overview_text FROM Domain WHERE id = ?", (d2,)
        ).fetchone()
        assert row[0] is None

    def test_handles_long_text(self, conn):
        did = _insert_domain(conn, "Mentoring", "MN")
        long_text = "x" * 100_000
        save_domain_overview_text(conn, did, long_text)
        row = conn.execute(
            "SELECT domain_overview_text FROM Domain WHERE id = ?", (did,)
        ).fetchone()
        assert len(row[0]) == 100_000
