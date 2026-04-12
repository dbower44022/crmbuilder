"""Tests for automation.core.master_prd_prompt."""

from __future__ import annotations

import json
import re
from unittest.mock import patch

import pytest

from automation.core.active_client_state import Client
from automation.core.master_prd_prompt import (
    build_master_prd_prompt,
    save_master_prd_prompt,
)


@pytest.fixture()
def client() -> Client:
    """Minimal Client for testing."""
    return Client(
        id=1,
        name="Acme Corp",
        code="ACME",
        description=None,
        project_folder="/tmp/acme",
    )


class TestBuildMasterPrdPrompt:
    def test_includes_client_name(self, client):
        result = build_master_prd_prompt(client)
        assert "Acme Corp" in result

    def test_includes_client_code(self, client):
        result = build_master_prd_prompt(client)
        assert "ACME" in result

    def test_includes_guide_body(self, client):
        result = build_master_prd_prompt(client)
        # The prompt-optimized guide content should be present
        assert "Organization Overview" in result
        assert "Personas" in result

    def test_date_format(self, client):
        result = build_master_prd_prompt(client)
        assert re.search(r"\d{2}-\d{2}-\d{2} \d{2}:\d{2}", result)

    def test_no_word_document_instruction(self, client):
        """The assembled prompt must not mention producing a Word document."""
        result = build_master_prd_prompt(client)
        assert "Word document" not in result

    def test_work_item_type_is_master_prd(self, client):
        """The assembled prompt contains the literal 'master_prd' as work_item_type."""
        result = build_master_prd_prompt(client)
        assert '"work_item_type": "master_prd"' in result

    def test_contains_all_seven_payload_keys(self, client):
        """The assembled prompt references all seven payload top-level keys."""
        result = build_master_prd_prompt(client)
        for key in [
            "organization_overview",
            "personas",
            "domains",
            "processes",
            "cross_domain_services",
            "system_scope",
            "interview_transcript",
        ]:
            assert key in result, f"Missing payload key '{key}' in prompt"

    def test_placeholder_client_name(self, client):
        result = build_master_prd_prompt(client)
        assert "{client_name}" not in result
        assert "Acme Corp" in result

    def test_placeholder_client_code(self, client):
        result = build_master_prd_prompt(client)
        assert "{client_code}" not in result
        assert "ACME" in result

    def test_placeholder_work_item_id_with_value(self, client):
        result = build_master_prd_prompt(client, work_item_id=42)
        assert "{work_item_id}" not in result
        assert "42" in result

    def test_placeholder_work_item_id_without_value(self, client):
        result = build_master_prd_prompt(client)
        assert "<work_item_id>" in result

    def test_placeholder_generated_at(self, client):
        result = build_master_prd_prompt(client)
        assert "{generated_at}" not in result

    def test_placeholder_session_type(self, client):
        result = build_master_prd_prompt(client, session_type="initial")
        # Template placeholder should be replaced
        assert "{session_type}" not in result
        assert "initial" in result

    def test_raises_when_template_missing(self, client, tmp_path):
        """FileNotFoundError when the template file does not exist."""
        with patch(
            "automation.core.master_prd_prompt._repo_root",
            return_value=tmp_path,
        ):
            with pytest.raises(FileNotFoundError):
                build_master_prd_prompt(client)

    def test_round_trip_json_schema_validation(self, client):
        """Extract the JSON example from the prompt, parse it, validate
        against the JSON Schema from Task 1.

        Proves the example in the prompt is valid against the schema
        the import processor will validate against in Section 11.2.
        """
        import jsonschema

        from automation.core.schemas.master_prd_payload import load_json_schema

        result = build_master_prd_prompt(client, work_item_id=1)

        # Find the payload JSON example block in the Structured Output
        # Specification — it's the second ```json block (the first is
        # the envelope, the second is the payload).
        json_blocks = re.findall(
            r"```json\s*\n(.*?)```", result, re.DOTALL,
        )
        assert len(json_blocks) >= 2, (
            f"Expected at least 2 JSON blocks, found {len(json_blocks)}"
        )

        # The payload example is the second JSON block
        payload_text = json_blocks[1].strip()

        # The example uses // comments which are not valid JSON.
        # Strip single-line comments.
        lines = []
        for line in payload_text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("//"):
                continue
            # Remove trailing // comments
            idx = line.find("//")
            if idx >= 0:
                line = line[:idx].rstrip().rstrip(",")
                # Re-add comma if the next non-blank line is not ] or }
                line = line.rstrip()
            lines.append(line)
        cleaned = "\n".join(lines)

        # The payload example uses placeholder strings, not real data,
        # so we validate the structure rather than exact content.
        # Parse the cleaned JSON.
        payload = json.loads(cleaned)

        schema = load_json_schema()
        jsonschema.validate(instance=payload, schema=schema)


class TestSaveMasterPrdPrompt:
    def test_creates_prompts_folder(self, tmp_path):
        save_master_prd_prompt("text", str(tmp_path), "TEST")
        assert (tmp_path / "prompts").is_dir()

    def test_filename_includes_code(self, tmp_path):
        path = save_master_prd_prompt("text", str(tmp_path), "ACME")
        assert "ACME" in path.name

    def test_filename_pattern(self, tmp_path):
        path = save_master_prd_prompt("text", str(tmp_path), "ACME")
        assert re.match(
            r"master-prd-prompt-ACME-\d{8}-\d{6}\.md", path.name,
        )

    def test_writes_content(self, tmp_path):
        content = "Full prompt text here."
        path = save_master_prd_prompt(content, str(tmp_path), "X")
        assert path.read_text(encoding="utf-8") == content

    def test_unique_filenames(self, tmp_path):
        from datetime import datetime

        times = iter(
            [
                datetime(2026, 1, 1, 12, 0, 0),
                datetime(2026, 1, 1, 12, 0, 1),
            ]
        )
        with patch(
            "automation.core.master_prd_prompt.datetime"
        ) as mock_dt:
            mock_dt.now.side_effect = lambda: next(times)
            mock_dt.strftime = datetime.strftime
            p1 = save_master_prd_prompt("a", str(tmp_path), "C")
            p2 = save_master_prd_prompt("b", str(tmp_path), "C")
        assert p1.name != p2.name
