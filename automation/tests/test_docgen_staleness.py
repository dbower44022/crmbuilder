"""Tests for automation.docgen.staleness — document staleness detection.

Uses GenerationLog.generated_at as the baseline (not WorkItem.completed_at).
"""

import pytest

from automation.db.migrations import run_client_migrations
from automation.docgen.generation_log import record as record_generation
from automation.docgen.staleness import get_stale_documents
from automation.impact.changeimpact import CandidateImpact, write_change_impacts


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed(conn):
    """Seed database for staleness tests."""
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status, completed_at) "
        "VALUES (1, 'master_prd', 'complete', '2025-01-01 00:00:00')"
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
        "VALUES (1, 1, 'status', 'Status', 'enum')"
    )
    conn.execute(
        "INSERT INTO Persona (id, name, code) VALUES (1, 'Admin', 'ADM')"
    )
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status, completed_at) "
        "VALUES (2, 'entity_prd', 1, 'complete', '2025-06-01 00:00:00')"
    )
    conn.commit()


class TestGetStaleDocuments:

    def test_no_generation_log_means_not_stale(self, conn):
        """Work item with no GenerationLog entry is not stale — just ungenerated."""
        _seed(conn)
        stale = get_stale_documents(conn)
        assert len(stale) == 0

    def test_stale_when_change_after_generation(self, conn):
        """A document is stale when ChangeLog post-dates GenerationLog."""
        _seed(conn)
        # Record a generation
        record_generation(conn, 2, "entity_prd", "path.docx", "final", "hash1")

        # ChangeLog entry after generation
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (1, 1, 'Field', 1, 'update', 'label', 'old', 'new', '2099-01-01 00:00:00')"
        )
        conn.commit()
        write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "field changed", True),
        ])

        stale = get_stale_documents(conn)
        wi_ids = {s.work_item_id for s in stale}
        assert 2 in wi_ids

    def test_not_stale_after_regeneration(self, conn):
        """Regeneration clears staleness because GenerationLog.generated_at updates."""
        _seed(conn)
        # First generation
        record_generation(conn, 2, "entity_prd", "path.docx", "final", "hash1")

        # ChangeLog in between
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (1, 1, 'Field', 1, 'update', 'label', 'old', 'new', '2025-06-15 00:00:00')"
        )
        conn.commit()
        write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "field changed", True),
        ])

        # Regeneration (with a later timestamp — record() uses datetime.now)
        # Since record() uses current time which is > the ChangeLog entry,
        # the document should be current after regeneration.
        record_generation(conn, 2, "entity_prd", "path.docx", "final", "hash2")

        stale = get_stale_documents(conn)
        # The latest generation is now() which is after the ChangeLog entry
        assert len(stale) == 0

    def test_uses_generation_log_not_completed_at(self, conn):
        """Staleness uses GenerationLog.generated_at, NOT WorkItem.completed_at."""
        _seed(conn)
        # Record a generation for work item 1 (master_prd)
        record_generation(conn, 1, "master_prd", "path.docx", "final", "hash1")

        # ChangeLog for Persona (owned by master_prd)
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (1, 1, 'Persona', 1, 'update', 'name', 'old', 'new', '2099-01-01 00:00:00')"
        )
        conn.commit()
        write_change_impacts(conn, [
            CandidateImpact(1, "Persona", 1, "persona changed", True),
        ])

        stale = get_stale_documents(conn)
        wi_ids = {s.work_item_id for s in stale}
        assert 1 in wi_ids

    def test_stale_document_has_change_summary(self, conn):
        _seed(conn)
        record_generation(conn, 2, "entity_prd", "path.docx", "final", "hash1")

        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (1, 1, 'Field', 1, 'update', 'label', 'old', 'new', '2099-01-01 00:00:00')"
        )
        conn.commit()
        write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "field changed", True),
        ])

        stale = get_stale_documents(conn)
        assert len(stale) == 1
        assert stale[0].change_count > 0
        assert stale[0].change_summary != ""
