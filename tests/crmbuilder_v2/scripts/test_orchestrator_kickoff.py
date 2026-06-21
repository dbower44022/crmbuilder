"""Kickoff-rendering tests for the orchestrator driver (PI-081 / PI-082)."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_MOD = _ROOT / "crmbuilder-v2" / "scripts" / "orchestrator" / "kickoff.py"
_spec = importlib.util.spec_from_file_location("orch_kickoff", _MOD)
kickoff = importlib.util.module_from_spec(_spec)
sys.modules["orch_kickoff"] = kickoff
_spec.loader.exec_module(kickoff)

_TEMPLATE = (
    _ROOT
    / "PRDs"
    / "product"
    / "NEW-Master PRDs"
    / "Agent PRDs"
    / "Archive"
    / "orchestrator"
    / "child-agent-kickoff-template.md"
)


def test_render_substitutes_markers():
    out = kickoff.render_kickoff("hi {{name}}", {"name": "PI"})
    assert out == "hi PI"


def test_render_missing_placeholder_raises():
    with pytest.raises(KeyError):
        kickoff.render_kickoff("hi {{name}}", {})


def test_strip_contract_comment_removes_leading_comment():
    text = "<!--\ndocs {{x}}\n-->\nbody {{y}}"
    stripped = kickoff.strip_contract_comment(text)
    assert "docs" not in stripped
    assert "body {{y}}" in stripped


def test_planning_items_block_inlines_details():
    block = kickoff.render_planning_items_block(
        [
            {
                "identifier": "PI-077",
                "title": "Claim fields",
                "area": ["storage", "api"],
                "executive_summary": "exec",
                "description": "full description here",
            }
        ]
    )
    assert "PI-077" in block
    assert "Claim fields" in block
    assert "storage, api" in block
    assert "full description here" in block


def test_real_template_renders_with_no_leftover_markers():
    body = kickoff.strip_contract_comment(_TEMPLATE.read_text(encoding="utf-8"))
    keys = set(re.findall(r"\{\{([a-z_]+)\}\}", body))
    assert keys, "template should contain placeholders outside the contract comment"
    subs = {k: f"<{k}>" for k in keys}
    out = kickoff.render_kickoff(body, subs)
    assert "{{" not in out and "}}" not in out
