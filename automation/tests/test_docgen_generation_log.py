"""Tests for automation.docgen.generation_log — GenerationLog recording."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.docgen.generation_log import (
    GenerationLogEntry,
    get_latest_for_work_item,
    record,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    # Seed a work item
    c.execute(
        "INSERT INTO WorkItem (id, item_type, status) VALUES (1, 'master_prd', 'complete')"
    )
    c.commit()
    yield c
    c.close()


class TestRecord:

    def test_records_final_generation(self, conn):
        log_id = record(conn, 1, "master_prd", "PRDs/TO-Master-PRD.docx", "final", "abc123")
        assert log_id > 0

        row = conn.execute(
            "SELECT work_item_id, document_type, file_path, generation_mode, git_commit_hash "
            "FROM GenerationLog WHERE id = ?",
            (log_id,),
        ).fetchone()
        assert row[0] == 1
        assert row[1] == "master_prd"
        assert row[2] == "PRDs/TO-Master-PRD.docx"
        assert row[3] == "final"
        assert row[4] == "abc123"

    def test_records_without_git_hash(self, conn):
        log_id = record(conn, 1, "master_prd", "PRDs/TO-Master-PRD.docx", "final", None)
        assert log_id > 0

        row = conn.execute(
            "SELECT git_commit_hash FROM GenerationLog WHERE id = ?",
            (log_id,),
        ).fetchone()
        assert row[0] is None


class TestGetLatestForWorkItem:

    def test_returns_latest_final(self, conn):
        record(conn, 1, "master_prd", "path1.docx", "final", "hash1")
        record(conn, 1, "master_prd", "path2.docx", "final", "hash2")

        latest = get_latest_for_work_item(conn, 1, mode="final")
        assert latest is not None
        assert isinstance(latest, GenerationLogEntry)
        assert latest.git_commit_hash == "hash2"

    def test_returns_none_when_no_entries(self, conn):
        latest = get_latest_for_work_item(conn, 999, mode="final")
        assert latest is None

    def test_filters_by_mode(self, conn):
        record(conn, 1, "master_prd", "path.docx", "final", "hash1")

        latest_draft = get_latest_for_work_item(conn, 1, mode="draft")
        assert latest_draft is None

        latest_final = get_latest_for_work_item(conn, 1, mode="final")
        assert latest_final is not None
