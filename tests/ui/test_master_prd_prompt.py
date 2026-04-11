"""Tests for automation.core.master_prd_prompt."""

from __future__ import annotations

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


@pytest.fixture()
def guide_file(tmp_path):
    """Write a small fake interview guide and return its path."""
    guide = tmp_path / "interview-master-prd.md"
    guide.write_text("## Fake Guide\nAsk about goals.", encoding="utf-8")
    return guide


class TestBuildMasterPrdPrompt:
    def test_includes_client_name(self, client, guide_file):
        result = build_master_prd_prompt(client, guide_file)
        assert "Acme Corp" in result

    def test_includes_client_code(self, client, guide_file):
        result = build_master_prd_prompt(client, guide_file)
        assert "ACME" in result

    def test_includes_guide_body(self, client, guide_file):
        result = build_master_prd_prompt(client, guide_file)
        assert "## Fake Guide" in result
        assert "Ask about goals." in result

    def test_date_format(self, client, guide_file):
        result = build_master_prd_prompt(client, guide_file)
        assert re.search(r"\d{2}-\d{2}-\d{2} \d{2}:\d{2}", result)

    def test_no_product_names_instruction_present(self, client, guide_file):
        result = build_master_prd_prompt(client, guide_file)
        header = result.split("---")[0]
        assert "Do not mention specific product names" in header

    def test_raises_when_guide_missing(self, client, tmp_path):
        missing = tmp_path / "nonexistent.md"
        with pytest.raises(FileNotFoundError):
            build_master_prd_prompt(client, missing)


class TestSaveMasterPrdPrompt:
    def test_creates_prompts_folder(self, tmp_path):
        save_master_prd_prompt("text", str(tmp_path), "TEST")
        assert (tmp_path / "prompts").is_dir()

    def test_filename_includes_code(self, tmp_path):
        path = save_master_prd_prompt("text", str(tmp_path), "ACME")
        assert "ACME" in path.name

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
