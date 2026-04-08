"""Tests for automation.impact.engine — ImpactAnalysisEngine end-to-end."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.impact.engine import (
    AnalysisResult,
    ImpactAnalysisEngine,
    _remove_marker,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed_full(conn):
    """Seed a fully populated database simulating Step 12 output."""
    # Work items
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) "
        "VALUES (1, 'master_prd', 'complete')"
    )
    # AISession with IMPACT_ANALYSIS_NEEDED marker
    conn.execute(
        "INSERT INTO AISession (id, work_item_id, session_type, generated_prompt, "
        "import_status, notes, started_at, completed_at) "
        "VALUES (1, 1, 'initial', 'prompt', 'imported', "
        "'IMPACT_ANALYSIS_NEEDED', '2025-01-01', '2025-01-01')"
    )
    # Domain + Entity + Field
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
    # Process + ProcessField
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Intake', 'TST-INTAKE', 1)"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, usage) "
        "VALUES (1, 1, 1, 'evaluated')"
    )
    # Layout for field — so field update creates entity-scoped impacts
    conn.execute(
        "INSERT INTO LayoutPanel (id, entity_id, label, sort_order, layout_mode) "
        "VALUES (1, 1, 'Main', 1, 'rows')"
    )
    conn.execute(
        "INSERT INTO LayoutRow (id, panel_id, sort_order, cell_1_field_id) "
        "VALUES (1, 1, 1, 1)"
    )
    conn.execute(
        "INSERT INTO ListColumn (id, entity_id, field_id, sort_order) "
        "VALUES (1, 1, 1, 1)"
    )
    # ChangeLog — update entries from import
    conn.execute(
        "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
        "change_type, field_name, old_value, new_value, changed_at) "
        "VALUES (1, 1, 'Field', 1, 'update', 'field_type', 'varchar', 'enum', '2025-01-01')"
    )
    # Entity PRD work item
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status, completed_at) "
        "VALUES (2, 'entity_prd', 1, 'complete', '2024-12-01 00:00:00')"
    )
    # Process definition work item
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, process_id, status, completed_at) "
        "VALUES (3, 'process_definition', 1, 'complete', '2024-12-01 00:00:00')"
    )
    conn.commit()


class TestAnalyzeSession:

    def test_creates_impacts(self, conn):
        _seed_full(conn)
        engine = ImpactAnalysisEngine(conn)
        result = engine.analyze_session(1)
        assert isinstance(result, AnalysisResult)
        assert result.ai_session_id == 1
        assert result.change_log_count == 1
        assert result.impact_count > 0
        # ChangeImpact rows in database
        count = conn.execute("SELECT COUNT(*) FROM ChangeImpact").fetchone()[0]
        assert count > 0

    def test_no_changes_returns_zero(self, conn):
        _seed_full(conn)
        # Change the ChangeLog to insert (exempt)
        conn.execute("UPDATE ChangeLog SET change_type = 'insert' WHERE id = 1")
        conn.commit()
        engine = ImpactAnalysisEngine(conn)
        result = engine.analyze_session(1)
        assert result.impact_count == 0

    def test_review_counts(self, conn):
        _seed_full(conn)
        engine = ImpactAnalysisEngine(conn)
        result = engine.analyze_session(1)
        assert result.requires_review_count + result.informational_count == result.impact_count


class TestAnalyzePendingSessions:

    def test_processes_marker_and_clears(self, conn):
        _seed_full(conn)
        engine = ImpactAnalysisEngine(conn)
        results = engine.analyze_pending_sessions()
        assert len(results) == 1
        assert results[0].ai_session_id == 1
        assert results[0].impact_count > 0

        # Marker should be cleared
        notes = conn.execute(
            "SELECT notes FROM AISession WHERE id = 1"
        ).fetchone()[0]
        assert notes is None or "IMPACT_ANALYSIS_NEEDED" not in notes

    def test_preserves_other_notes(self, conn):
        _seed_full(conn)
        # Add other notes alongside marker
        conn.execute(
            "UPDATE AISession SET notes = 'some note | IMPACT_ANALYSIS_NEEDED' WHERE id = 1"
        )
        conn.commit()

        engine = ImpactAnalysisEngine(conn)
        engine.analyze_pending_sessions()

        notes = conn.execute(
            "SELECT notes FROM AISession WHERE id = 1"
        ).fetchone()[0]
        assert notes == "some note"

    def test_no_pending_returns_empty(self, conn):
        _seed_full(conn)
        # Clear the marker manually
        conn.execute("UPDATE AISession SET notes = NULL WHERE id = 1")
        conn.commit()
        engine = ImpactAnalysisEngine(conn)
        results = engine.analyze_pending_sessions()
        assert results == []

    def test_multiple_sessions(self, conn):
        _seed_full(conn)
        # Add second session with marker
        conn.execute(
            "INSERT INTO AISession (id, work_item_id, session_type, generated_prompt, "
            "import_status, notes, started_at) "
            "VALUES (2, 1, 'revision', 'p', 'imported', 'IMPACT_ANALYSIS_NEEDED', '2025-02-01')"
        )
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (2, 2, 'Field', 1, 'update', 'label', 'old', 'new', '2025-02-01')"
        )
        conn.commit()

        engine = ImpactAnalysisEngine(conn)
        results = engine.analyze_pending_sessions()
        assert len(results) == 2

        # Both markers cleared
        for sid in (1, 2):
            notes = conn.execute(
                "SELECT notes FROM AISession WHERE id = ?", (sid,)
            ).fetchone()[0]
            assert notes is None or "IMPACT_ANALYSIS_NEEDED" not in notes

    def test_marker_in_middle(self, conn):
        _seed_full(conn)
        conn.execute(
            "UPDATE AISession SET notes = "
            "'note a | IMPACT_ANALYSIS_NEEDED | note b' WHERE id = 1"
        )
        conn.commit()

        engine = ImpactAnalysisEngine(conn)
        engine.analyze_pending_sessions()

        notes = conn.execute(
            "SELECT notes FROM AISession WHERE id = 1"
        ).fetchone()[0]
        assert notes == "note a | note b"


class TestPreCommitAnalysis:

    def test_returns_proposed_impacts(self, conn):
        _seed_full(conn)
        engine = ImpactAnalysisEngine(conn)
        result = engine.analyze_proposed_change("Field", 1, "update")
        assert len(result) > 0

    def test_no_db_writes(self, conn):
        _seed_full(conn)
        engine = ImpactAnalysisEngine(conn)
        engine.analyze_proposed_change("Field", 1, "delete")
        count = conn.execute("SELECT COUNT(*) FROM ChangeImpact").fetchone()[0]
        assert count == 0


class TestWorkItemMapping:

    def test_maps_impacts_to_work_items(self, conn):
        _seed_full(conn)
        engine = ImpactAnalysisEngine(conn)
        engine.analyze_session(1)

        ci_ids = [
            r[0] for r in conn.execute("SELECT id FROM ChangeImpact").fetchall()
        ]
        if ci_ids:
            result = engine.get_affected_work_items(ci_ids)
            assert len(result) > 0


class TestStaleness:

    def test_detects_stale_work_items(self, conn):
        _seed_full(conn)
        engine = ImpactAnalysisEngine(conn)
        # Analyze session first to create ChangeImpact rows
        engine.analyze_session(1)

        stale = engine.get_stale_work_items()
        wi_ids = {s.work_item_id for s in stale}
        # entity_prd (id=2) completed 2024-12-01, change at 2025-01-01 → stale
        assert 2 in wi_ids


class TestRemoveMarker:

    def test_marker_alone(self):
        assert _remove_marker("IMPACT_ANALYSIS_NEEDED") is None

    def test_marker_at_end(self):
        assert _remove_marker("notes | IMPACT_ANALYSIS_NEEDED") == "notes"

    def test_marker_at_start(self):
        assert _remove_marker("IMPACT_ANALYSIS_NEEDED | notes") == "notes"

    def test_marker_in_middle(self):
        assert _remove_marker("a | IMPACT_ANALYSIS_NEEDED | b") == "a | b"

    def test_no_marker(self):
        assert _remove_marker("just notes") == "just notes"

    def test_none_input(self):
        assert _remove_marker(None) is None
