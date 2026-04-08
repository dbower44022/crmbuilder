"""Tests for automation.impact.staleness — document staleness detection."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.impact.changeimpact import CandidateImpact, write_change_impacts
from automation.impact.staleness import get_stale_work_items


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


def _seed(conn):
    """Seed database for staleness tests."""
    # Entity and field
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, status) VALUES (1, 'master_prd', 'complete')"
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
        "INSERT INTO Process (id, domain_id, name, code, sort_order) "
        "VALUES (1, 1, 'Intake', 'TST-INTAKE', 1)"
    )
    conn.execute(
        "INSERT INTO ProcessField (id, process_id, field_id, usage) "
        "VALUES (1, 1, 1, 'collected')"
    )

    # Entity PRD work item — completed at 2025-06-01
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, entity_id, status, completed_at) "
        "VALUES (2, 'entity_prd', 1, 'complete', '2025-06-01 00:00:00')"
    )
    # Process definition work item — completed at 2025-07-01
    conn.execute(
        "INSERT INTO WorkItem (id, item_type, process_id, status, completed_at) "
        "VALUES (3, 'process_definition', 1, 'complete', '2025-07-01 00:00:00')"
    )

    conn.commit()


class TestGetStaleWorkItems:

    def test_stale_when_change_after_completion(self, conn):
        _seed(conn)
        # ChangeLog after entity_prd completion
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (1, 1, 'Field', 1, 'update', 'label', 'old', 'new', '2025-08-01 00:00:00')"
        )
        conn.commit()
        # Create ChangeImpact pointing to Field 1
        write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "field changed", True)
        ])

        stale = get_stale_work_items(conn)
        wi_ids = {s.work_item_id for s in stale}
        assert 2 in wi_ids  # entity_prd

    def test_not_stale_when_change_before_completion(self, conn):
        _seed(conn)
        # ChangeLog BEFORE entity_prd completion
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (1, 1, 'Field', 1, 'update', 'label', 'old', 'new', '2025-05-01 00:00:00')"
        )
        conn.commit()
        write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "field changed", True)
        ])

        stale = get_stale_work_items(conn)
        wi_ids = {s.work_item_id for s in stale}
        assert 2 not in wi_ids

    def test_no_changelog_not_stale(self, conn):
        _seed(conn)
        stale = get_stale_work_items(conn)
        assert len(stale) == 0

    def test_process_definition_staleness(self, conn):
        _seed(conn)
        # ChangeLog affecting ProcessField after process completion
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, old_value, new_value, changed_at) "
            "VALUES (1, 1, 'Field', 1, 'update', 'label', 'o', 'n', '2025-08-01 00:00:00')"
        )
        conn.commit()
        write_change_impacts(conn, [
            CandidateImpact(1, "ProcessField", 1, "pf changed", True)
        ])

        stale = get_stale_work_items(conn)
        wi_ids = {s.work_item_id for s in stale}
        assert 3 in wi_ids  # process_definition

    def test_incomplete_work_item_not_reported(self, conn):
        _seed(conn)
        # Set entity_prd to in_progress
        conn.execute("UPDATE WorkItem SET status = 'in_progress', completed_at = NULL WHERE id = 2")
        conn.commit()

        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, changed_at) VALUES (1, 1, 'Field', 1, 'update', '2025-08-01')"
        )
        conn.commit()
        write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "field changed", True)
        ])

        stale = get_stale_work_items(conn)
        wi_ids = {s.work_item_id for s in stale}
        assert 2 not in wi_ids

    def test_stale_count_and_latest(self, conn):
        _seed(conn)
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, changed_at) "
            "VALUES (1, 1, 'Field', 1, 'update', 'label', '2025-08-01 00:00:00')"
        )
        conn.execute(
            "INSERT INTO ChangeLog (id, session_id, table_name, record_id, "
            "change_type, field_name, changed_at) "
            "VALUES (2, 1, 'Field', 1, 'update', 'field_type', '2025-09-01 00:00:00')"
        )
        conn.commit()
        write_change_impacts(conn, [
            CandidateImpact(1, "Field", 1, "change 1", True),
            CandidateImpact(2, "Field", 1, "change 2", True),
        ])

        stale = get_stale_work_items(conn)
        entity_stale = [s for s in stale if s.work_item_id == 2]
        assert len(entity_stale) == 1
        assert entity_stale[0].stale_change_count == 2
        assert entity_stale[0].latest_change_at == "2025-09-01 00:00:00"
