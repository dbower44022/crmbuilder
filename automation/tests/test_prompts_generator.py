"""Tests for automation.prompts.generator — PromptGenerator class."""

import pytest

from automation.db.migrations import run_client_migrations, run_master_migrations
from automation.prompts.generator import PromptGenerator
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
        ("Test Org", "TO", "A test org", "/tmp/test.db", "Overview narrative"),
    )
    c.commit()
    yield c
    c.close()


def _seed_domain(conn, name="Mentoring", code="MN", sort_order=1):
    cur = conn.execute(
        "INSERT INTO Domain (name, code, sort_order) VALUES (?, ?, ?)",
        (name, code, sort_order),
    )
    conn.commit()
    return cur.lastrowid


def _seed_entity(conn, name="Contact", code="CON", primary_domain_id=None):
    cur = conn.execute(
        "INSERT INTO Entity (name, code, entity_type, is_native, primary_domain_id) "
        "VALUES (?, ?, 'Person', 1, ?)",
        (name, code, primary_domain_id),
    )
    conn.commit()
    return cur.lastrowid


def _seed_process(conn, domain_id, name="Intake", code="MN-INTAKE", sort_order=1):
    cur = conn.execute(
        "INSERT INTO Process (domain_id, name, code, sort_order) VALUES (?, ?, ?, ?)",
        (domain_id, name, code, sort_order),
    )
    conn.commit()
    return cur.lastrowid


def _build_full_graph(conn):
    """Build a complete project graph up through BOD import."""
    d1 = _seed_domain(conn)
    e1 = _seed_entity(conn, primary_domain_id=d1)
    _seed_process(conn, d1)

    engine = WorkflowEngine(conn)
    master_id = engine.create_project()
    engine.start(master_id)
    engine.complete(master_id)
    engine.after_master_prd_import()

    bod_id = conn.execute(
        "SELECT id FROM WorkItem WHERE item_type = 'business_object_discovery'"
    ).fetchone()[0]
    engine.start(bod_id)
    engine.complete(bod_id)
    engine.after_business_object_discovery_import()

    return d1, e1


class TestPromptGeneratorEndToEnd:
    def test_generate_master_prd(self, conn, master_conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()

        gen = PromptGenerator(conn, master_conn)
        prompt = gen.generate(master_id)

        assert "Session Header" in prompt
        assert "Session Instructions" in prompt
        assert "Context" in prompt
        assert "Locked Decisions" in prompt
        assert "Open Issues" in prompt
        assert "Structured Output Specification" in prompt
        assert "master_prd" in prompt

    def test_generates_entity_prd_prompt(self, conn, master_conn):
        _build_full_graph(conn)
        ep_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'entity_prd' LIMIT 1"
        ).fetchone()[0]

        gen = PromptGenerator(conn, master_conn)
        prompt = gen.generate(ep_id)

        assert "entity_prd" in prompt
        assert "Entity Definition" in prompt  # phase name

    def test_ai_session_recorded(self, conn, master_conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()

        gen = PromptGenerator(conn, master_conn)
        gen.generate(master_id)

        sessions = conn.execute(
            "SELECT work_item_id, session_type, import_status, generated_prompt "
            "FROM AISession WHERE work_item_id = ?",
            (master_id,),
        ).fetchall()
        assert len(sessions) == 1
        assert sessions[0][0] == master_id
        assert sessions[0][1] == "initial"
        assert sessions[0][2] == "pending"
        assert len(sessions[0][3]) > 100  # prompt text present

    def test_revision_session(self, conn, master_conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()
        # First, create an initial session
        gen = PromptGenerator(conn, master_conn)
        gen.generate(master_id)

        # Complete and revise the work item
        engine.start(master_id)
        engine.complete(master_id)
        engine.revise(master_id)

        prompt = gen.generate(
            master_id, session_type="revision",
            revision_reason="Scope change needed",
        )
        assert "revision" in prompt
        assert "Scope change needed" in prompt
        assert "REVISION SESSION" in prompt

    def test_clarification_session(self, conn, master_conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()
        # Create initial session with structured output
        gen = PromptGenerator(conn, master_conn)
        gen.generate(master_id)

        prompt = gen.generate(
            master_id, session_type="clarification",
            clarification_topic="Why was domain X excluded?",
        )
        assert "clarification" in prompt
        assert "Why was domain X excluded?" in prompt
        assert "CLARIFICATION SESSION" in prompt


class TestPromptGeneratorValidation:
    def test_not_found_raises(self, conn):
        gen = PromptGenerator(conn)
        with pytest.raises(ValueError, match="not found"):
            gen.generate(999)

    def test_wrong_status_raises(self, conn, master_conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()
        engine.start(master_id)
        engine.complete(master_id)  # now 'complete'

        gen = PromptGenerator(conn, master_conn)
        with pytest.raises(ValueError, match="status is 'complete'"):
            gen.generate(master_id)

    def test_non_promptable_type_raises(self, conn):
        # Insert a stakeholder_review work item manually
        d1 = _seed_domain(conn)
        wi_id = conn.execute(
            "INSERT INTO WorkItem (item_type, status, domain_id) "
            "VALUES ('stakeholder_review', 'ready', ?)",
            (d1,),
        ).lastrowid
        conn.commit()

        gen = PromptGenerator(conn)
        with pytest.raises(ValueError, match="does not require a prompt"):
            gen.generate(wi_id)

    def test_revision_without_reason_raises(self, conn, master_conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()
        gen = PromptGenerator(conn, master_conn)
        with pytest.raises(ValueError, match="revision_reason is required"):
            gen.generate(master_id, session_type="revision")

    def test_clarification_without_topic_raises(self, conn, master_conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()
        gen = PromptGenerator(conn, master_conn)
        with pytest.raises(ValueError, match="clarification_topic is required"):
            gen.generate(master_id, session_type="clarification")


class TestIsPromptable:
    def test_promptable_types(self, conn):
        gen = PromptGenerator(conn)
        assert gen.is_promptable("master_prd") is True
        assert gen.is_promptable("entity_prd") is True
        assert gen.is_promptable("crm_selection") is True

    def test_non_promptable_types(self, conn):
        gen = PromptGenerator(conn)
        assert gen.is_promptable("stakeholder_review") is False
        assert gen.is_promptable("crm_configuration") is False
        assert gen.is_promptable("verification") is False


class TestPromptContent:
    def test_prompt_contains_phase_info(self, conn, master_conn):
        engine = WorkflowEngine(conn)
        master_id = engine.create_project()
        gen = PromptGenerator(conn, master_conn)
        prompt = gen.generate(master_id)
        assert "Phase" in prompt
        assert "Master PRD" in prompt

    def test_prompt_for_domain_overview(self, conn, master_conn):
        _build_full_graph(conn)
        # Complete all entity PRDs to make domain overview ready
        ep_rows = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'entity_prd'"
        ).fetchall()
        engine = WorkflowEngine(conn)
        for (ep_id,) in ep_rows:
            engine.start(ep_id)
            engine.complete(ep_id)

        do_id = conn.execute(
            "SELECT id FROM WorkItem WHERE item_type = 'domain_overview' LIMIT 1"
        ).fetchone()[0]
        gen = PromptGenerator(conn, master_conn)
        prompt = gen.generate(do_id)
        assert "domain_overview" in prompt
        assert "Domain Overview" in prompt
