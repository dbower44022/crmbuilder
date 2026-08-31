"""REQ-540 / PI-437 — the session-start context hook.

Pure tests against a fake fetcher: audience selection, rendering, the snapshot
refresh on success, and the two fallback shapes (snapshot present / absent).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2 import session_context as sc

RULES = [
    {"identifier": "GVR-005", "body": "Reuse helpers.", "enforcement": "advisory",
     "rule_type": None, "severity": None, "status": "active"},
    {"identifier": "GVR-235", "body": "Always commit with an explicit pathspec.",
     "enforcement": "advisory", "rule_type": "commit_hygiene", "severity": "high",
     "status": "active"},
    {"identifier": "GVR-229", "body": "Every code commit carries a Governed-By trailer.",
     "enforcement": "enforced_with_override", "rule_type": "commit_governance",
     "severity": "high", "status": "active"},
]
EDGES = [
    {"source_type": "agent_profile", "source_id": "AGP-002",
     "target_type": "governance_rule", "target_id": "GVR-005"},
    {"source_type": "lesson", "source_id": "LSN-021",
     "target_type": "governance_rule", "target_id": "GVR-229"},
]
PREFS = [
    {"identifier": "PRF-006", "category": "ui", "applies_to": "ui", "body": "No gray buttons."},
    {"identifier": "PRF-001", "category": "interaction", "applies_to": "all",
     "body": "Do not ask 'shall I proceed?'."},
    {"identifier": "PRF-003", "category": "interaction", "applies_to": "claude_code",
     "body": "One step at a time."},
]


def fake_fetch(path: str) -> list[dict]:
    if path.startswith("/governance-rules"):
        return [dict(r) for r in RULES]
    if path.startswith("/references"):
        return [dict(e) for e in EDGES]
    if path.startswith("/preferences"):
        return [dict(p) for p in PREFS]
    raise AssertionError(path)


def test_session_rules_exclude_profile_bound_rules_and_sort():
    selected = sc.select_session_rules(fake_fetch)
    assert [r["identifier"] for r in selected] == ["GVR-229", "GVR-235"]


def test_applies_to_field_wins_when_present():
    def fetch(path: str) -> list[dict]:
        if path.startswith("/governance-rules"):
            return [
                {"identifier": "GVR-900", "body": "agent only", "applies_to": "ado_agent"},
                {"identifier": "GVR-901", "body": "session", "applies_to": "claude_code"},
                {"identifier": "GVR-902", "body": "everyone", "applies_to": "all"},
            ]
        raise AssertionError("no binding lookup needed when applies_to is present")

    assert [r["identifier"] for r in sc.select_session_rules(fetch)] == ["GVR-901", "GVR-902"]


def test_preferences_filtered_to_session_audiences():
    assert [p["identifier"] for p in sc.select_preferences(fake_fetch)] == [
        "PRF-001", "PRF-003"
    ]


def test_render_names_every_rule_and_preference():
    text = sc.render(
        sc.select_session_rules(fake_fetch),
        sc.select_preferences(fake_fetch),
        "ENG-001",
        datetime(2026, 8, 31, 1, 2, tzinfo=UTC),
    )
    assert "ENG-001" in text and "2026-08-31 01:02 UTC" in text
    assert "## Governance rules (2)" in text
    assert "**GVR-229** [enforced_with_override · commit_governance · severity high]" in text
    assert "**GVR-235**" in text and "GVR-005" not in text
    assert "## Preferences (2)" in text and "PRF-006" not in text
    assert "TOP-013" in text


def test_build_context_writes_snapshot(tmp_path: Path):
    text = sc.build_context(tmp_path, fetch=fake_fetch)
    snapshot = tmp_path / sc.SNAPSHOT_FILE
    assert snapshot.read_text(encoding="utf-8") == text
    assert "GVR-235" in text


def test_fallback_uses_snapshot_with_banner(tmp_path: Path):
    sc.build_context(tmp_path, fetch=fake_fetch)
    text = sc.fallback_context(tmp_path, ConnectionError("dns failed"))
    assert text.startswith("> **SNAPSHOT — the V2 store was unreachable")
    assert "ConnectionError: dns failed" in text
    assert "GVR-235" in text


def test_fallback_without_snapshot_points_at_claude_md_core(tmp_path: Path):
    text = sc.fallback_context(tmp_path, RuntimeError("no token"))
    assert "NO SESSION CONTEXT" in text and "Session bootstrap" in text


def test_main_never_fails_and_prints_fallback(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv("CRMBUILDER_V2_API_BASE_URL", raising=False)
    monkeypatch.delenv("CRMBUILDER_V2_API_TOKEN", raising=False)
    assert sc.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "NO SESSION CONTEXT" in out


def test_load_env_file_parses_quotes_and_comments(tmp_path: Path):
    env = tmp_path / "x.env"
    env.write_text("# c\nCRMBUILDER_V2_API_BASE_URL='https://api.example'\nTOKEN=\"abc\"\n\n")
    assert sc.load_env_file(env) == {
        "CRMBUILDER_V2_API_BASE_URL": "https://api.example",
        "TOKEN": "abc",
    }


@pytest.mark.parametrize("path", ["/governance-rules?x", "/preferences?x"])
def test_fetcher_surfaces_envelope_errors(monkeypatch, path):
    class Resp:
        def __init__(self, payload):
            self._p = payload

        def read(self):
            import json
            return json.dumps(self._p).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        sc.urllib.request, "urlopen",
        lambda req, timeout: Resp({"data": None, "errors": [{"code": "unauthorized"}]}),
    )
    fetch = sc.make_fetcher("https://api.example", "tok", "ENG-001")
    with pytest.raises(RuntimeError, match="unauthorized"):
        fetch(path)
