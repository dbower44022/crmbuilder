"""Tests for automation.importer.commit — atomic commit with ChangeLog."""

import sqlite3

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.importer.commit import commit_batch
from automation.importer.proposed import ProposedBatch, ProposedRecord


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    # Create work item and AI session
    c.execute("INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'in_progress')")
    c.execute(
        "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (1, 'initial', 'prompt text', "
        "'pending', CURRENT_TIMESTAMP)"
    )
    c.commit()
    yield c
    c.close()


@pytest.fixture()
def master_conn(tmp_path):
    db_path = tmp_path / "master.db"
    c = run_master_migrations(str(db_path))
    c.execute(
        "INSERT INTO Client (name, code, description, database_path) "
        "VALUES ('Test', 'TST', 'Test org', '/tmp/test.db')"
    )
    c.commit()
    yield c
    c.close()


def _rec(table, values, action="create", target_id=None, batch_id=None, intra_refs=None):
    return ProposedRecord(
        table_name=table, action=action, target_id=target_id,
        values=values, source_payload_path=f"test.{table}",
        batch_id=batch_id, intra_batch_refs=intra_refs or {},
    )


def _batch(records, session_id=1):
    return ProposedBatch(
        records=records, ai_session_id=session_id, work_item_id=1,
        session_type="initial",
    )


class TestCommitCreate:
    def test_single_create(self, conn):
        rec = _rec("Domain", {
            "name": "Mentoring", "code": "MN", "sort_order": 1,
            "is_service": False, "created_by_session_id": 1,
        })
        result = commit_batch(conn, 1, _batch([rec]))
        assert result.created_count == 1
        assert result.import_status == "imported"

        # Verify record in database
        row = conn.execute("SELECT name, code FROM Domain WHERE code = 'MN'").fetchone()
        assert row is not None
        assert row[0] == "Mentoring"

    def test_changelog_entry_for_create(self, conn):
        rec = _rec("Domain", {
            "name": "Mentoring", "code": "MN", "sort_order": 1,
            "is_service": False, "created_by_session_id": 1,
        })
        commit_batch(conn, 1, _batch([rec]))

        logs = conn.execute(
            "SELECT table_name, change_type, session_id FROM ChangeLog"
        ).fetchall()
        assert len(logs) == 1
        assert logs[0][0] == "Domain"
        assert logs[0][1] == "insert"
        assert logs[0][2] == 1


class TestCommitUpdate:
    def test_single_update(self, conn):
        # Create a domain to update
        conn.execute(
            "INSERT INTO Domain (name, code, sort_order, is_service) "
            "VALUES ('Mentoring', 'MN', 1, 0)"
        )
        conn.commit()

        rec = _rec("Domain", {"name": "Updated Mentoring"},
                    action="update", target_id=1)
        result = commit_batch(conn, 1, _batch([rec]))
        assert result.updated_count == 1
        assert result.has_updates is True

        row = conn.execute("SELECT name FROM Domain WHERE id = 1").fetchone()
        assert row[0] == "Updated Mentoring"

    def test_changelog_entries_for_update(self, conn):
        conn.execute(
            "INSERT INTO Domain (name, code, sort_order, is_service) "
            "VALUES ('Mentoring', 'MN', 1, 0)"
        )
        conn.commit()

        rec = _rec("Domain", {"name": "Updated Mentoring"},
                    action="update", target_id=1)
        commit_batch(conn, 1, _batch([rec]))

        logs = conn.execute(
            "SELECT change_type, field_name, old_value, new_value FROM ChangeLog"
        ).fetchall()
        assert len(logs) >= 1
        update_logs = [entry for entry in logs if entry[0] == "update"]
        assert len(update_logs) >= 1
        name_log = [entry for entry in update_logs if entry[1] == "name"]
        assert len(name_log) == 1
        assert name_log[0][2] == "Mentoring"
        assert name_log[0][3] == "Updated Mentoring"


class TestIntraBatchResolution:
    def test_intra_batch_fk_resolved(self, conn):
        domain_rec = _rec("Domain", {
            "name": "Mentoring", "code": "MN", "sort_order": 1,
            "is_service": False, "created_by_session_id": 1,
        }, batch_id="batch:domain:MN")

        process_rec = _rec("Process", {
            "name": "Intake", "code": "MN-INTAKE", "sort_order": 1,
            "created_by_session_id": 1,
        }, intra_refs={"domain_id": "batch:domain:MN"})

        result = commit_batch(conn, 1, _batch([domain_rec, process_rec]))
        assert result.created_count == 2

        # Verify FK was resolved
        proc = conn.execute(
            "SELECT domain_id FROM Process WHERE code = 'MN-INTAKE'"
        ).fetchone()
        domain = conn.execute(
            "SELECT id FROM Domain WHERE code = 'MN'"
        ).fetchone()
        assert proc[0] == domain[0]


class TestAtomicRollback:
    def test_constraint_violation_rolls_back(self, conn):
        good_rec = _rec("Domain", {
            "name": "Good", "code": "GD", "sort_order": 1,
            "is_service": False, "created_by_session_id": 1,
        })
        # This will fail: process requires domain_id which is NOT NULL
        bad_rec = _rec("Process", {
            "name": "Bad", "code": "BAD", "sort_order": 1,
            "created_by_session_id": 1,
            # Missing domain_id — will cause NOT NULL constraint violation
        })

        with pytest.raises(sqlite3.IntegrityError):
            commit_batch(conn, 1, _batch([good_rec, bad_rec]))

        # Good domain should NOT exist because transaction rolled back
        row = conn.execute("SELECT id FROM Domain WHERE code = 'GD'").fetchone()
        assert row is None


class TestPartialImport:
    def test_partial_accept(self, conn):
        rec1 = _rec("Domain", {
            "name": "Mentoring", "code": "MN", "sort_order": 1,
            "is_service": False, "created_by_session_id": 1,
        })
        rec1.source_payload_path = "payload.domains[0]"
        rec2 = _rec("Domain", {
            "name": "Education", "code": "ED", "sort_order": 2,
            "is_service": False, "created_by_session_id": 1,
        })
        rec2.source_payload_path = "payload.domains[1]"

        result = commit_batch(
            conn, 1, _batch([rec1, rec2]),
            accepted_paths={"payload.domains[0]"},
        )
        assert result.created_count == 1
        assert result.rejected_count == 1
        assert result.import_status == "partial"

        # Only MN should exist
        rows = conn.execute("SELECT code FROM Domain").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "MN"

    def test_all_rejected(self, conn):
        rec = _rec("Domain", {
            "name": "Test", "code": "TST", "sort_order": 1,
            "is_service": False, "created_by_session_id": 1,
        })
        result = commit_batch(conn, 1, _batch([rec]), accepted_paths=set())
        assert result.import_status == "rejected"
        assert result.created_count == 0


class TestAISessionUpdate:
    def test_session_status_updated(self, conn):
        rec = _rec("Domain", {
            "name": "Mentoring", "code": "MN", "sort_order": 1,
            "is_service": False, "created_by_session_id": 1,
        })
        commit_batch(conn, 1, _batch([rec]))

        session = conn.execute(
            "SELECT import_status, completed_at FROM AISession WHERE id = 1"
        ).fetchone()
        assert session[0] == "imported"
        assert session[1] is not None

    def test_session_rejected_status(self, conn):
        rec = _rec("Domain", {
            "name": "Test", "code": "TST", "sort_order": 1,
            "is_service": False, "created_by_session_id": 1,
        })
        commit_batch(conn, 1, _batch([rec]), accepted_paths=set())

        session = conn.execute(
            "SELECT import_status FROM AISession WHERE id = 1"
        ).fetchone()
        assert session[0] == "rejected"


class TestClientUpdate:
    def test_client_update_in_master_db(self, conn, master_conn):
        rec = _rec("Client", {"organization_overview": "New overview"},
                    action="update", target_id=1)
        result = commit_batch(
            conn, 1, _batch([rec]), master_conn=master_conn,
        )
        assert result.updated_count == 1

        row = master_conn.execute(
            "SELECT organization_overview FROM Client WHERE id = 1"
        ).fetchone()
        assert row[0] == "New overview"
