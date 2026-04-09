"""Tests for automation.ui.documents.documents_logic and generation_logic — pure Python."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.ui.documents.documents_logic import (
    DocumentEntry,
    DocumentStatus,
    filter_stale,
    load_document_inventory,
    sort_entries,
)
from automation.ui.documents.generation_logic import (
    GenerationStage,
    GenerationState,
    advance_stage,
    cancel_generation,
    fail_generation,
    pause_for_warnings,
    record_batch_result,
    resume_after_warnings,
    set_result,
    start_batch,
    start_generation,
)


def _make_entry(**kwargs) -> DocumentEntry:
    """Build a DocumentEntry with defaults."""
    defaults = {
        "work_item_id": 1,
        "item_type": "master_prd",
        "document_type": "master_prd",
        "document_name": "Master PRD",
        "work_item_status": "complete",
        "document_status": DocumentStatus.NOT_GENERATED,
        "last_generated_at": None,
        "file_path": None,
        "git_commit_hash": None,
        "change_count": 0,
        "change_summary": "",
        "domain_name": None,
        "entity_name": None,
        "process_name": None,
    }
    defaults.update(kwargs)
    return DocumentEntry(**defaults)


# ---------------------------------------------------------------------------
# documents_logic tests
# ---------------------------------------------------------------------------


class TestSortEntries:

    def test_stale_first(self):
        entries = [
            _make_entry(work_item_id=1, document_status=DocumentStatus.CURRENT),
            _make_entry(work_item_id=2, document_status=DocumentStatus.STALE),
            _make_entry(work_item_id=3, document_status=DocumentStatus.NOT_GENERATED),
        ]
        sorted_entries = sort_entries(entries)
        assert sorted_entries[0].document_status == DocumentStatus.STALE
        assert sorted_entries[1].document_status == DocumentStatus.CURRENT
        assert sorted_entries[2].document_status == DocumentStatus.NOT_GENERATED

    def test_full_sort_order(self):
        entries = [
            _make_entry(work_item_id=1, document_status=DocumentStatus.NOT_GENERATED),
            _make_entry(work_item_id=2, document_status=DocumentStatus.DRAFT_ONLY),
            _make_entry(work_item_id=3, document_status=DocumentStatus.CURRENT),
            _make_entry(work_item_id=4, document_status=DocumentStatus.STALE),
        ]
        sorted_entries = sort_entries(entries)
        statuses = [e.document_status for e in sorted_entries]
        assert statuses == [
            DocumentStatus.STALE,
            DocumentStatus.CURRENT,
            DocumentStatus.DRAFT_ONLY,
            DocumentStatus.NOT_GENERATED,
        ]


class TestFilterStale:

    def test_returns_only_stale(self):
        entries = [
            _make_entry(work_item_id=1, document_status=DocumentStatus.STALE),
            _make_entry(work_item_id=2, document_status=DocumentStatus.CURRENT),
            _make_entry(work_item_id=3, document_status=DocumentStatus.STALE),
        ]
        result = filter_stale(entries)
        assert len(result) == 2
        assert all(e.document_status == DocumentStatus.STALE for e in result)

    def test_returns_empty_if_none_stale(self):
        entries = [
            _make_entry(document_status=DocumentStatus.CURRENT),
        ]
        assert filter_stale(entries) == []


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


class TestLoadDocumentInventory:

    def test_empty_database(self, conn):
        result = load_document_inventory(conn, [])
        assert result == []

    def test_loads_generatable_work_items(self, conn):
        # Insert a master_prd work item
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'not_started')"
        )
        conn.commit()
        result = load_document_inventory(conn, [])
        assert len(result) == 1
        assert result[0].item_type == "master_prd"
        assert result[0].document_status == DocumentStatus.NOT_GENERATED

    def test_excludes_non_generatable_types(self, conn):
        # crm_deployment is not generatable
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) VALUES ('crm_deployment', 'not_started')"
        )
        conn.commit()
        result = load_document_inventory(conn, [])
        assert len(result) == 0

    def test_scoped_to_work_item(self, conn):
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'complete')"
        )
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) VALUES ('entity_prd', 'in_progress')"
        )
        conn.commit()
        result = load_document_inventory(conn, [], scoped_work_item_id=1)
        assert len(result) == 1
        assert result[0].work_item_id == 1


# ---------------------------------------------------------------------------
# generation_logic tests
# ---------------------------------------------------------------------------


class TestGenerationProgress:

    def test_start_sets_running(self):
        p = start_generation("final")
        assert p.state == GenerationState.RUNNING
        assert p.current_stage == GenerationStage.QUERY
        assert p.completed_stages == []

    def test_advance_through_stages(self):
        p = start_generation("final")
        p = advance_stage(p)
        assert GenerationStage.QUERY in p.completed_stages
        assert p.current_stage == GenerationStage.VALIDATE

    def test_advance_to_completion(self):
        p = start_generation("final")
        for _ in range(6):
            p = advance_stage(p)
        assert p.state == GenerationState.COMPLETED
        assert p.current_stage is None

    def test_draft_skips_final_only_stages(self):
        p = start_generation("draft")
        assert len(p.applicable_stages) == 4
        assert GenerationStage.GIT_COMMIT not in p.applicable_stages
        assert GenerationStage.GENERATION_LOG not in p.applicable_stages

    def test_pause_for_warnings(self):
        p = start_generation("final")
        p = advance_stage(p)  # past QUERY
        p = pause_for_warnings(p, ["Warning 1"])
        assert p.state == GenerationState.PAUSED_WARNINGS
        assert p.warnings == ["Warning 1"]

    def test_resume_after_warnings(self):
        p = start_generation("final")
        p = advance_stage(p)
        p = pause_for_warnings(p, ["W"])
        p = resume_after_warnings(p)
        assert p.state == GenerationState.RUNNING
        assert GenerationStage.VALIDATE in p.completed_stages

    def test_cancel(self):
        p = start_generation("final")
        p = cancel_generation(p)
        assert p.state == GenerationState.CANCELLED
        assert p.is_done

    def test_fail(self):
        p = start_generation("final")
        p = fail_generation(p, "Something went wrong")
        assert p.state == GenerationState.FAILED
        assert p.error == "Something went wrong"
        assert p.is_done

    def test_set_result(self):
        p = start_generation("final")
        p = set_result(p, file_path="/out/test.docx", git_commit_hash="abc123")
        assert p.file_path == "/out/test.docx"
        assert p.git_commit_hash == "abc123"


class TestBatchProgress:

    def test_start_batch(self):
        b = start_batch([1, 2, 3])
        assert b.total == 3
        assert b.current_index == 0
        assert not b.is_done

    def test_record_success(self):
        b = start_batch([1, 2])
        b = record_batch_result(b, success=True)
        assert b.success_count == 1
        assert b.current_index == 1
        assert not b.is_done

    def test_record_failure(self):
        b = start_batch([1])
        b = record_batch_result(b, success=False)
        assert b.failure_count == 1
        assert b.is_done

    def test_record_skipped(self):
        b = start_batch([1, 2])
        b = record_batch_result(b, success=False, skipped=True)
        assert b.skipped_count == 1
        assert b.failure_count == 0
