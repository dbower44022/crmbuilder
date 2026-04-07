"""Tests for automation.prompts.session_types — session type variations."""

import pytest

from automation.db.migrations import run_client_migrations
from automation.prompts.session_types import (
    build_session_header,
    get_prior_output_for_revision,
    get_session_instructions_preamble,
    validate_session_params,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "client.db"
    c = run_client_migrations(str(db_path))
    yield c
    c.close()


class TestBuildSessionHeader:
    def test_initial_header(self):
        header = build_session_header(
            "entity_prd", "Contact Entity PRD", "initial", 2, "Entity Definition",
        )
        assert "entity_prd" in header
        assert "Contact Entity PRD" in header
        assert "initial" in header
        assert "**Phase:** 2" in header
        assert "Entity Definition" in header

    def test_revision_header_includes_reason(self):
        header = build_session_header(
            "entity_prd", "Contact Entity PRD", "revision", 2, "Entity Definition",
            revision_reason="Stakeholder feedback on fields",
        )
        assert "revision" in header
        assert "Stakeholder feedback on fields" in header

    def test_clarification_header_includes_topic(self):
        header = build_session_header(
            "entity_prd", "Contact Entity PRD", "clarification", 2, "Entity Definition",
            clarification_topic="Why was contactType added?",
        )
        assert "clarification" in header
        assert "Why was contactType added?" in header

    def test_initial_no_revision_reason(self):
        header = build_session_header(
            "master_prd", "Master PRD", "initial", 1, "Master PRD",
        )
        assert "Revision Reason" not in header


class TestGetSessionInstructionsPreamble:
    def test_initial_returns_none(self):
        assert get_session_instructions_preamble("initial") is None

    def test_revision_returns_preamble(self):
        preamble = get_session_instructions_preamble("revision")
        assert preamble is not None
        assert "REVISION SESSION" in preamble
        assert "baseline" in preamble

    def test_clarification_returns_preamble(self):
        preamble = get_session_instructions_preamble("clarification")
        assert preamble is not None
        assert "CLARIFICATION SESSION" in preamble
        assert "follow-up" in preamble


class TestGetPriorOutput:
    def test_returns_most_recent_output(self, conn):
        from datetime import datetime
        wi_id = conn.execute(
            "INSERT INTO WorkItem (item_type, status) VALUES ('master_prd', 'complete')",
        ).lastrowid
        conn.execute(
            "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
            "import_status, started_at, structured_output) "
            "VALUES (?, 'initial', 'prompt', 'imported', ?, ?)",
            (wi_id, datetime.now().isoformat(), '{"payload": "first"}'),
        )
        conn.execute(
            "INSERT INTO AISession (work_item_id, session_type, generated_prompt, "
            "import_status, started_at, structured_output) "
            "VALUES (?, 'revision', 'prompt2', 'imported', ?, ?)",
            (wi_id, datetime.now().isoformat(), '{"payload": "second"}'),
        )
        conn.commit()
        result = get_prior_output_for_revision(conn, wi_id)
        assert result == '{"payload": "second"}'

    def test_returns_none_when_no_output(self, conn):
        assert get_prior_output_for_revision(conn, 999) is None


class TestValidateSessionParams:
    def test_initial_valid(self):
        validate_session_params("initial")

    def test_revision_requires_reason(self):
        with pytest.raises(ValueError, match="revision_reason is required"):
            validate_session_params("revision")

    def test_revision_with_reason_valid(self):
        validate_session_params("revision", revision_reason="Scope change")

    def test_clarification_requires_topic(self):
        with pytest.raises(ValueError, match="clarification_topic is required"):
            validate_session_params("clarification")

    def test_clarification_with_topic_valid(self):
        validate_session_params("clarification", clarification_topic="Why?")

    def test_invalid_session_type(self):
        with pytest.raises(ValueError, match="Invalid session_type"):
            validate_session_params("bogus")
