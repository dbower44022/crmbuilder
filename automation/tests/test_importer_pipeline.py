"""Tests for automation.importer.pipeline — ImportProcessor end-to-end."""

import json

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.importer.parser import ParserError
from automation.importer.pipeline import ImportProcessor
from automation.workflow.engine import WorkflowEngine


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


@pytest.fixture()
def master_conn(tmp_path):
    db_path = tmp_path / "master.db"
    c = run_master_migrations(str(db_path))
    c.execute(
        "INSERT INTO Client (name, code, description, database_path, "
        "organization_overview) VALUES (?, ?, ?, ?, ?)",
        ("Test Org", "TO", "A test org", "/tmp/test.db", "Old overview"),
    )
    c.commit()
    yield c
    c.close()


def _setup_master_prd_ready(conn):
    """Create a project and return the master_prd work item id with a pending session."""
    engine = WorkflowEngine(conn)
    wi_id = engine.create_project()
    engine.start(wi_id)

    # Generate a prompt (creates AISession)
    conn.execute(
        "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
        "import_status, started_at) VALUES (?, 'initial', 'Generated prompt', "
        "'pending', CURRENT_TIMESTAMP)",
        (wi_id,),
    )
    conn.commit()
    return wi_id


def _master_prd_json(work_item_id=1):
    """Build a complete master_prd JSON envelope."""
    return json.dumps({
        "output_version": "1.0",
        "work_item_type": "master_prd",
        "work_item_id": work_item_id,
        "session_type": "initial",
        "payload": {
            "organization_overview": "Test organization overview",
            "personas": [
                {"name": "Mentor", "identifier": "MNT",
                 "description": "A volunteer mentor"},
                {"name": "Admin", "identifier": "ADM",
                 "description": "Program administrator"},
            ],
            "domains": [
                {"name": "Mentoring", "code": "MN",
                 "description": "Mentoring domain", "sort_order": 1},
            ],
            "processes": [
                {"name": "Intake", "code": "MN-INTAKE",
                 "description": "Intake process", "sort_order": 1,
                 "tier": "core", "domain_code": "MN"},
            ],
        },
        "decisions": [],
        "open_issues": [],
    })


# ===========================================================================
# Stage 1: Receive
# ===========================================================================

class TestReceive:
    def test_receive_stores_raw_output(self, conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn)
        session_id = proc.receive(wi_id, "raw json text")

        row = conn.execute(
            "SELECT raw_output FROM AISession WHERE id = ?", (session_id,)
        ).fetchone()
        assert row[0] == "raw json text"

    def test_receive_no_pending_session(self, conn):
        proc = ImportProcessor(conn)
        with pytest.raises(ValueError, match="No pending AISession"):
            proc.receive(999, "text")

    def test_receive_empty_text(self, conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn)
        with pytest.raises(ValueError, match="empty"):
            proc.receive(wi_id, "")

    def test_receive_picks_most_recent_pending(self, conn):
        wi_id = _setup_master_prd_ready(conn)
        # Create another pending session
        conn.execute(
            "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
            "import_status, started_at) VALUES (?, 'revision', 'Prompt 2', "
            "'pending', CURRENT_TIMESTAMP)",
            (wi_id,),
        )
        conn.commit()

        proc = ImportProcessor(conn)
        session_id = proc.receive(wi_id, "text")
        # Should pick the higher id (most recent)
        assert session_id == 2


# ===========================================================================
# Stage 2: Parse
# ===========================================================================

class TestParse:
    def test_parse_stores_structured_output(self, conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn)
        raw = _master_prd_json(wi_id)
        session_id = proc.receive(wi_id, raw)
        envelope = proc.parse(session_id)

        assert envelope["work_item_type"] == "master_prd"

        row = conn.execute(
            "SELECT structured_output FROM AISession WHERE id = ?", (session_id,)
        ).fetchone()
        assert row[0] is not None
        parsed = json.loads(row[0])
        assert parsed["work_item_type"] == "master_prd"

    def test_parse_fails_on_bad_json(self, conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn)
        session_id = proc.receive(wi_id, "{bad json")

        with pytest.raises(ParserError):
            proc.parse(session_id)

    def test_parse_no_raw_output(self, conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn)
        # Don't call receive, directly try to parse
        session_id = conn.execute(
            "SELECT id FROM AISession WHERE work_item_id = ?", (wi_id,)
        ).fetchone()[0]

        with pytest.raises(ValueError, match="no raw_output"):
            proc.parse(session_id)


# ===========================================================================
# Stage 3: Map
# ===========================================================================

class TestMap:
    def test_map_produces_records(self, conn, master_conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn, master_conn)
        raw = _master_prd_json(wi_id)
        session_id = proc.receive(wi_id, raw)
        proc.parse(session_id)
        batch = proc.map(session_id)

        assert len(batch.records) > 0
        tables = {r.table_name for r in batch.records}
        assert "Domain" in tables
        assert "Persona" in tables
        assert "Process" in tables


# ===========================================================================
# Stage 4: Detect Conflicts
# ===========================================================================

class TestDetectConflicts:
    def test_no_conflicts_on_clean_import(self, conn, master_conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn, master_conn)
        raw = _master_prd_json(wi_id)
        session_id = proc.receive(wi_id, raw)
        proc.parse(session_id)
        batch = proc.map(session_id)
        batch = proc.detect_conflicts(batch)

        errors = [r for r in batch.records if r.has_errors]
        assert len(errors) == 0


# ===========================================================================
# Stage 6: Commit
# ===========================================================================

class TestCommit:
    def test_commit_creates_records(self, conn, master_conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn, master_conn)
        raw = _master_prd_json(wi_id)
        session_id = proc.receive(wi_id, raw)
        proc.parse(session_id)
        batch = proc.map(session_id)
        batch = proc.detect_conflicts(batch)
        result = proc.commit(session_id, batch)

        assert result.import_status == "imported"
        assert result.created_count > 0

        # Verify records in database
        domains = conn.execute("SELECT code FROM Domain").fetchall()
        assert len(domains) >= 1

    def test_commit_partial(self, conn, master_conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn, master_conn)
        raw = _master_prd_json(wi_id)
        session_id = proc.receive(wi_id, raw)
        proc.parse(session_id)
        batch = proc.map(session_id)

        # Only accept first record
        accepted = {batch.records[0].source_payload_path}
        result = proc.commit(session_id, batch, accepted)

        assert result.import_status == "partial"


# ===========================================================================
# Full end-to-end
# ===========================================================================

class TestFullImport:
    def test_run_full_import(self, conn, master_conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn, master_conn)
        raw = _master_prd_json(wi_id)

        result = proc.run_full_import(wi_id, raw)

        assert result.commit_result.import_status == "imported"
        assert result.trigger_result.work_item_completed is True

        # Verify AISession lifecycle
        session = conn.execute(
            "SELECT import_status, completed_at, raw_output, structured_output "
            "FROM AISession WHERE id = ?", (result.ai_session_id,)
        ).fetchone()
        assert session[0] == "imported"
        assert session[1] is not None  # completed_at
        assert session[2] is not None  # raw_output
        assert session[3] is not None  # structured_output

        # Verify work item completed
        engine = WorkflowEngine(conn)
        assert engine.get_status(wi_id) == "complete"

        # Verify database records exist
        domains = conn.execute("SELECT code FROM Domain").fetchall()
        assert len(domains) >= 1
        personas = conn.execute("SELECT code FROM Persona").fetchall()
        assert len(personas) >= 2

        # Verify ChangeLog entries
        logs = conn.execute("SELECT COUNT(*) FROM ChangeLog").fetchone()
        assert logs[0] > 0

        # Verify Client update in master db
        client = master_conn.execute(
            "SELECT organization_overview FROM Client WHERE id = 1"
        ).fetchone()
        assert client[0] == "Test organization overview"

    def test_run_full_import_reject_all(self, conn, master_conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn, master_conn)
        raw = _master_prd_json(wi_id)

        result = proc.run_full_import(wi_id, raw, accept_all=False)
        assert result.commit_result.import_status == "rejected"

        # Work item should stay in_progress
        engine = WorkflowEngine(conn)
        assert engine.get_status(wi_id) == "in_progress"

    def test_graph_expands_after_master_prd(self, conn, master_conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn, master_conn)
        raw = _master_prd_json(wi_id)

        result = proc.run_full_import(wi_id, raw)
        assert result.trigger_result.graph_constructed is True

        # BOD should exist
        bod = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
        ).fetchone()
        assert bod is not None


class TestAISessionLifecycle:
    def test_no_pending_session_raises(self, conn):
        proc = ImportProcessor(conn)
        with pytest.raises(ValueError, match="No pending AISession"):
            proc.receive(999, "text")

    def test_receive_does_not_create_new_session(self, conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn)

        count_before = conn.execute("SELECT COUNT(*) FROM AISession").fetchone()[0]
        proc.receive(wi_id, "text")
        count_after = conn.execute("SELECT COUNT(*) FROM AISession").fetchone()[0]

        assert count_after == count_before  # No new row created

    def test_session_updated_through_stages(self, conn, master_conn):
        wi_id = _setup_master_prd_ready(conn)
        proc = ImportProcessor(conn, master_conn)
        raw = _master_prd_json(wi_id)

        # Stage 1
        session_id = proc.receive(wi_id, raw)
        session = conn.execute(
            "SELECT raw_output, structured_output, import_status "
            "FROM AISession WHERE id = ?", (session_id,)
        ).fetchone()
        assert session[0] is not None   # raw_output set
        assert session[1] is None       # structured_output not yet
        assert session[2] == "pending"  # still pending

        # Stage 2
        proc.parse(session_id)
        session = conn.execute(
            "SELECT structured_output, import_status "
            "FROM AISession WHERE id = ?", (session_id,)
        ).fetchone()
        assert session[0] is not None  # structured_output set
        assert session[1] == "pending"  # still pending

        # Stages 3-4
        batch = proc.map(session_id)
        batch = proc.detect_conflicts(batch)

        # Stage 6
        proc.commit(session_id, batch)
        session = conn.execute(
            "SELECT import_status, completed_at "
            "FROM AISession WHERE id = ?", (session_id,)
        ).fetchone()
        assert session[0] == "imported"
        assert session[1] is not None


class TestNonPromptableType:
    def test_non_promptable_type_raises(self, conn):
        # Create a stakeholder_review work item
        conn.execute(
            "INSERT INTO WorkItem (item_type, status) "
            "VALUES ('stakeholder_review', 'in_progress')"
        )
        conn.execute(
            "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
            "import_status, started_at, raw_output) VALUES (1, 'initial', 'p', "
            "'pending', CURRENT_TIMESTAMP, '{}')"
        )
        conn.commit()

        proc = ImportProcessor(conn)
        with pytest.raises(ValueError, match="not importable"):
            proc.parse(1)
