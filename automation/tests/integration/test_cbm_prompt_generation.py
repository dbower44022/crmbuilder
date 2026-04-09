"""Integration test: PromptGenerator end-to-end with CBM data."""

from __future__ import annotations

import pytest

from automation.workflow.engine import WorkflowEngine


class TestCBMPromptGeneration:

    def test_generate_prompt_for_revision(self, cbm_client_conn, cbm_master_conn):
        """Reopen a completed entity_prd work item, generate a revision prompt."""
        engine = WorkflowEngine(cbm_client_conn)

        # Find a completed entity_prd work item
        wi = cbm_client_conn.execute(
            "SELECT id, status FROM WorkItem WHERE item_type = 'entity_prd' AND status = 'complete'"
        ).fetchone()
        if wi is None:
            pytest.skip("No completed entity_prd work item available")

        wi_id = wi[0]

        # Reopen for revision
        engine.revise(wi_id)
        assert engine.get_status(wi_id) == "in_progress"

        # Generate a revision prompt
        from automation.prompts.generator import PromptGenerator
        gen = PromptGenerator(cbm_client_conn, master_conn=cbm_master_conn)
        prompt = gen.generate(wi_id, session_type="revision", revision_reason="Integration test")

        assert len(prompt) > 100
        # Prompt should contain expected sections
        assert "Session" in prompt or "session" in prompt

        # AISession should be recorded
        row = cbm_client_conn.execute(
            "SELECT id, session_type, generated_prompt FROM AISession "
            "WHERE work_item_id = ? AND session_type = 'revision' "
            "ORDER BY id DESC LIMIT 1",
            (wi_id,),
        ).fetchone()
        assert row is not None
        assert len(row[2]) > 100

    def test_promptable_types(self, cbm_client_conn, cbm_master_conn):
        """Verify prompt generation can be called for supported types."""
        from automation.prompts.generator import PromptGenerator
        gen = PromptGenerator(cbm_client_conn, master_conn=cbm_master_conn)

        # These should all be promptable
        for item_type in ("master_prd", "entity_prd", "process_definition"):
            assert gen.is_promptable(item_type)
