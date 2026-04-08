"""Tests for automation.impact.batch — batch processing."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.impact.batch import process_batch, process_batch_precommit


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed_with_changes(conn):
    """Create a populated database with ChangeLog entries."""
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
        "VALUES (1, 1, 'status', 'Status', 'enum')"
    )
    conn.execute(
        "INSERT INTO Field (id, entity_id, name, label, field_type) "
        "VALUES (2, 1, 'priority', 'Priority', 'enum')"
    )
    conn.execute(
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Intake', 'TST-INTAKE', 1)"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, usage) "
        "VALUES (1, 1, 1, 'evaluated')"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, usage) "
        "VALUES (2, 1, 2, 'displayed')"
    )
    # ChangeLog — two field updates in same session
    conn.execute(
        "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
        "change_type, field_name, old_value, new_value, changed_at) "
        "VALUES (1, 1, 'Field', 1, 'update', 'field_type', 'varchar', 'enum', '2025-01-01')"
    )
    conn.execute(
        "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
        "change_type, field_name, old_value, new_value, changed_at) "
        "VALUES (2, 1, 'Field', 2, 'update', 'label', 'Old', 'New', '2025-01-01')"
    )
    # An insert ChangeLog (should be filtered out)
    conn.execute(
        "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
        "change_type, changed_at) "
        "VALUES (3, 1, 'Field', 3, 'insert', '2025-01-01')"
    )
    conn.commit()


class TestProcessBatch:

    def test_processes_updates(self, conn):
        _seed_with_changes(conn)
        result = process_batch(conn, [1, 2])
        assert len(result) > 0
        # ChangeImpact rows should be in database
        count = conn.execute("SELECT COUNT(*) FROM ChangeImpact").fetchone()[0]
        assert count > 0

    def test_skips_inserts(self, conn):
        _seed_with_changes(conn)
        result = process_batch(conn, [3])  # insert only
        assert len(result) == 0

    def test_empty_list(self, conn):
        assert process_batch(conn, []) == []

    def test_deduplication_applied(self, conn):
        """When two field changes affect the same ProcessField, only one impact."""
        _seed_with_changes(conn)
        # Both fields are on the same entity — if they share a downstream
        # target, it should be deduplicated
        process_batch(conn, [1, 2])
        # Check database for dedup
        rows = conn.execute(
            "SELECT affected_table, affected_record_id, COUNT(*) "
            "FROM ChangeImpact GROUP BY affected_table, affected_record_id "
            "HAVING COUNT(*) > 1"
        ).fetchall()
        # No duplicates should exist
        assert len(rows) == 0

    def test_multi_field_update_same_record(self, conn):
        """Two ChangeLog entries updating different fields of the SAME record."""
        _seed_with_changes(conn)
        # Add a second ChangeLog for field 1, different column
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (4, 1, 'Field', 1, 'update', 'label', 'Old', 'New', '2025-01-01')"
        )
        conn.commit()
        result = process_batch(conn, [1, 4])
        # Both should trace the same record → same results
        assert len(result) > 0

    def test_query_consolidation(self, conn):
        """Batch consolidation reduces SQL queries vs individual."""
        _seed_with_changes(conn)
        # Add more fields for batch
        for i in range(3, 8):
            conn.execute(
                "INSERT INTO Field (id, entity_id, name, label, field_type) "
                f"VALUES ({i}, 1, 'f{i}', 'F{i}', 'varchar')"
            )
            conn.execute(
                "INSERT INTO ProcessField (process_id, field_id, usage) "
                f"VALUES (1, {i}, 'collected')"
            )
            conn.execute(
                "INSERT INTO ChangeLog (session_id, table_name, record_id, "
                "change_type, field_name, old_value, new_value, changed_at) "
                f"VALUES (1, 'Field', {i}, 'update', 'label', 'o', 'n', '2025-01-01')"
            )
        conn.commit()

        cl_ids = [r[0] for r in conn.execute(
            "SELECT id FROM ChangeLog WHERE change_type = 'update'"
        ).fetchall()]

        query_count = {"n": 0}

        def counter(sql):
            if sql.startswith("SELECT"):
                query_count["n"] += 1

        conn.set_trace_callback(counter)
        process_batch(conn, cl_ids)
        batch_queries = query_count["n"]
        conn.set_trace_callback(None)

        # With 7 field changes, consolidated should use fewer queries
        # than 7 * 6 individual queries = 42
        assert batch_queries < 42, f"Used {batch_queries} queries (expected < 42)"


class TestProcessBatchPrecommit:

    def test_does_not_write(self, conn):
        _seed_with_changes(conn)
        result = process_batch_precommit(conn, [1, 2])
        assert len(result) > 0
        # No ChangeImpact rows should be in database
        count = conn.execute("SELECT COUNT(*) FROM ChangeImpact").fetchone()[0]
        assert count == 0

    def test_returns_candidates(self, conn):
        _seed_with_changes(conn)
        result = process_batch_precommit(conn, [1])
        assert len(result) > 0
        assert result[0].affected_table is not None
