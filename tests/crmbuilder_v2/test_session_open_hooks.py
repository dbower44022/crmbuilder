"""REQ-575 / PI-488 — the two-hook session opening in Claude Code.

Pure tests against a fake caller: the session-start hook renders the
cross-cutting contract and the opening question and writes the marker; the
prompt-submission hook takes the first prompt as the opening answer, calls
the session-open operation, prints the phase rules and marks the session
opened; a second prompt does nothing; the pre-command check reads the
enforced rules from the marker; a store that cannot be reached leaves a
visible notice and the manual fallback; an older API falls back to the flat
audience query.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from crmbuilder_v2 import rule_check as rc
from crmbuilder_v2 import session_context as sc
from crmbuilder_v2 import session_open as so

CROSS = {
    "profile_id": "AGP-041",
    "advisory_rules": [{"identifier": "GVR-231", "body": "Record governance in real time."}],
    "enforced_ruleset": [
        {"identifier": "GVR-235", "enforcement": "enforced_with_override", "severity": "high",
         "body": "Always commit with an explicit pathspec.",
         "predicate": {"kind": "forbidden_command",
                       "pattern": r"\bgit\b(?:\s+-\S+)*\s+commit\b(?![^\n]*\s--\s)"}},
    ],
    "system_prompt": "SYSTEM ROLE — cross-cutting.",
    "version_stamp": "cc",
}
OPENING = {
    "question": "What do you want to do today?",
    "examples": ["Define new business processes", "Upgrade the platform to the latest version",
                 "Ask a question about the system or its records"],
    "catalogue": [],
    "cross_cutting": CROSS,
}
PREFS = [{"identifier": "PRF-001", "category": "interaction", "applies_to": "all", "body": "Just do the work."}]


def _opened(answer: str) -> dict:
    return {
        "session": {"session_identifier": "SES-410", "session_opening_answer": answer,
                    "session_kind_of_work": "PROC-013"},
        "kind_of_work": "PROC-013",
        "kind_of_work_name": "Define new business processes",
        "confirmation_line": "It sounds like you want to define new business processes; I will start with the Requirements Interviewer.",
        "first_line": "It sounds like you want to define new business processes; I will start with the Requirements Interviewer.",
        "follow_up_question": None,
        "segment": {"position": 1, "domain": "DOM-005", "profile": "AGP-039", "label": "Requirements Interviewer",
                    "status": "active"},
        "contract": {
            "profile_id": "AGP-039", "segment_profile_id": "AGP-039", "cross_cutting_profile_id": "AGP-041",
            "system_prompt": "SYSTEM ROLE — you are the Requirements Interviewer.\n\n"
                             "CROSS-CUTTING RULES — these apply in every phase segment.\n\nSYSTEM ROLE — cross-cutting.",
            "advisory_rules": [{"identifier": "GVR-194", "body": "Inferences require positive support."},
                               {"identifier": "GVR-231", "body": "Record governance in real time."}],
            "enforced_ruleset": CROSS["enforced_ruleset"] + [
                {"identifier": "GVR-240", "enforcement": "enforced", "severity": "high",
                 "body": "Production deploy is human-only.",
                 "predicate": {"kind": "forbidden_command", "pattern": r"rsync\b[^\n]*138\.197\.72\.15"}}],
            "version_stamp": "seg+cc",
        },
        "planning_item": None,
    }


class FakeStore:
    def __init__(self, *, opening_available=True, open_fails=False):
        self.calls: list[tuple[str, str, dict | None]] = []
        self.opening_available = opening_available
        self.open_fails = open_fails

    def fetch(self, path: str) -> list[dict]:
        if path.startswith("/preferences"):
            return [dict(p) for p in PREFS]
        if path.startswith("/governance-rules"):
            return [{"identifier": "GVR-900", "body": "flat rule", "applies_to": "claude_code",
                     "enforcement": "advisory", "status": "active"}]
        raise AssertionError(path)

    def call(self, method: str, path: str, body: dict | None):
        self.calls.append((method, path, body))
        if path == sc.OPENING_PATH:
            if not self.opening_available:
                raise RuntimeError("HTTP 404 session 'opening' not found")
            return json.loads(json.dumps(OPENING))
        if path == so.OPEN_PATH:
            if self.open_fails:
                raise ConnectionError("dns failed")
            if not body["opening_answer"]:
                return {"session": {"session_identifier": "SES-411", "session_opening_answer": None},
                        "kind_of_work": None, "confirmation_line": None,
                        "first_line": "No kind of work was chosen for this session; only the cross-cutting rules are loaded.",
                        "follow_up_question": None, "segment": None, "contract": dict(CROSS), "planning_item": None}
            if "birthday" in body["opening_answer"]:
                return {"session": {"session_identifier": "SES-412", "session_opening_answer": body["opening_answer"]},
                        "kind_of_work": None, "confirmation_line": None,
                        "first_line": "No kind of work was chosen for this session; only the cross-cutting rules are loaded.",
                        "follow_up_question": "I could not match that. What would you like done by the end of this session?",
                        "segment": None, "contract": dict(CROSS),
                        "planning_item": {"identifier": "PI-500", "title": "Catalogue miss: birthday cards"}}
            return _opened(body["opening_answer"])
        raise AssertionError((method, path))


def _start(tmp_path: Path, store: FakeStore, session_id="abc-123") -> str:
    return sc.build_context(tmp_path, fetch=store.fetch, call=store.call, session_id=session_id)


# --- session start ---------------------------------------------------------------


def test_session_start_renders_cross_cutting_and_question_and_writes_marker(tmp_path: Path):
    store = FakeStore()
    text = _start(tmp_path, store)
    assert "## Cross-cutting rules (2)" in text
    assert "**GVR-231**" in text and "**GVR-235** [enforced_with_override · severity high]" in text
    assert "What do you want to do today?" in text
    assert "Define new business processes; Upgrade the platform" in text
    assert "**PRF-001**" in text
    assert "GVR-900" not in text  # the flat audience query was not used
    marker = sc.read_marker(tmp_path, "abc-123")
    assert marker["opened"] is False and marker["session_identifier"] is None
    assert marker["cross_cutting_rule_ids"] == ["GVR-231", "GVR-235"]
    assert marker["contract"]["enforced_ruleset"][0]["predicate"]["kind"] == "forbidden_command"
    assert (tmp_path / sc.SNAPSHOT_FILE).read_text(encoding="utf-8") == text


def test_session_start_falls_back_to_flat_rules_on_older_api(tmp_path: Path, capsys):
    store = FakeStore(opening_available=False)
    text = _start(tmp_path, store)
    assert "**GVR-900**" in text and "## Governance rules (1)" in text
    assert sc.read_marker(tmp_path, "abc-123") is None
    assert "opening unavailable" in capsys.readouterr().err


def test_session_start_without_session_id_writes_no_marker(tmp_path: Path):
    store = FakeStore()
    text = _start(tmp_path, store, session_id=None)
    assert "What do you want to do today?" in text
    assert not (tmp_path / sc.MARKER_DIR).exists()


# --- the opening answer ----------------------------------------------------------


def test_extract_opening_answer_prefers_marked_line_then_first_line():
    assert so.extract_opening_answer("define new business processes") == "define new business processes"
    pasted = "# CLAUDE-CODE-PROMPT: Step 3\n\nOpening answer: add a field to the intake screen\n\nOperating mode: DETAIL"
    assert so.extract_opening_answer(pasted) == "add a field to the intake screen"
    assert so.extract_opening_answer("## Heading line\nsecond") == "Heading line"
    assert so.extract_opening_answer("- upgrade the platform\n") == "upgrade the platform"
    assert so.extract_opening_answer("   \n\n") == ""
    assert len(so.extract_opening_answer("x" * 1000)) == so.MAX_ANSWER_CHARS


# --- prompt submission -----------------------------------------------------------


def test_first_prompt_opens_the_session_and_prints_phase_rules(tmp_path: Path):
    store = FakeStore()
    _start(tmp_path, store)
    text = so.open_from_prompt(tmp_path, "abc-123", "define new business processes", call=store.call)
    assert "# Session opened — SES-410" in text
    assert "I will start with the Requirements Interviewer." in text
    assert "SYSTEM ROLE — you are the Requirements Interviewer." in text
    assert "SYSTEM ROLE — cross-cutting." not in text  # already in context
    assert "**GVR-194**" in text and "**GVR-240**" in text
    assert "**GVR-231**" not in text and "**GVR-235**" not in text  # cross-cutting, already shown
    assert "Rules for this segment (2 beyond the cross-cutting set)" in text
    assert "advance_session_segment" in text
    body = next(b for m, p, b in store.calls if p == so.OPEN_PATH)
    assert body["opening_answer"] == "define new business processes"
    assert body["medium"] == "claude_code"
    assert body["medium_metadata"]["claude_session_id"] == "abc-123"
    marker = sc.read_marker(tmp_path, "abc-123")
    assert marker["opened"] is True and marker["session_identifier"] == "SES-410"
    assert marker["kind_of_work"] == "PROC-013"
    assert {r["identifier"] for r in marker["contract"]["enforced_ruleset"]} == {"GVR-235", "GVR-240"}


def test_second_prompt_does_nothing(tmp_path: Path):
    store = FakeStore()
    _start(tmp_path, store)
    so.open_from_prompt(tmp_path, "abc-123", "define new business processes", call=store.call)
    n = len(store.calls)
    assert so.open_from_prompt(tmp_path, "abc-123", "now do the next thing", call=store.call) == ""
    assert len(store.calls) == n


def test_unrecognised_answer_prints_follow_up_question_and_miss(tmp_path: Path):
    store = FakeStore()
    _start(tmp_path, store)
    text = so.open_from_prompt(tmp_path, "abc-123", "send birthday cards", call=store.call)
    assert "ask the user this one question in their own words" in text
    assert "What would you like done by the end of this session?" in text
    assert "planning item PI-500" in text
    assert "Rules for this segment (0 beyond the cross-cutting set)" in text


def test_empty_prompt_opens_without_answer(tmp_path: Path):
    store = FakeStore()
    _start(tmp_path, store)
    text = so.open_from_prompt(tmp_path, "abc-123", "   ", call=store.call)
    assert "SES-411" in text and "No kind of work was chosen" in text


def test_unreachable_store_leaves_notice_and_manual_fallback(tmp_path: Path):
    store = FakeStore(open_fails=True)
    _start(tmp_path, store)
    text = so.open_from_prompt(tmp_path, "abc-123", "define new business processes", call=store.call)
    assert text.startswith("> **SESSION NOT OPENED")
    assert "ConnectionError: dns failed" in text and "open_session" in text
    marker = sc.read_marker(tmp_path, "abc-123")
    assert marker["opened"] is False and marker["open_failed_at"]
    # The next prompt is not mistaken for the answer.
    assert so.open_from_prompt(tmp_path, "abc-123", "second prompt", call=store.call) == ""


def test_resumed_session_renders_stored_contract_not_question(tmp_path: Path):
    store = FakeStore()
    _start(tmp_path, store)
    so.open_from_prompt(tmp_path, "abc-123", "define new business processes", call=store.call)
    text = _start(tmp_path, store)
    assert "resumed session SES-410" in text
    assert "What do you want to do today?" not in text
    assert "**GVR-194**" in text and "**GVR-235**" in text
    assert "## Rules in force (4)" in text


# --- the pre-command check -------------------------------------------------------------


def test_rule_check_reads_enforced_rules_from_the_contract(tmp_path: Path):
    store = FakeStore()
    _start(tmp_path, store)
    rules, source = rc.load_rules(tmp_path, session_id="abc-123")
    assert source == "contract" and [r["identifier"] for r in rules] == ["GVR-235"]
    assert [r["identifier"] for r, _ in rc.evaluate('git commit -m "x"', rules)] == ["GVR-235"]
    so.open_from_prompt(tmp_path, "abc-123", "define new business processes", call=store.call)
    rules, source = rc.load_rules(tmp_path, session_id="abc-123")
    assert source == "contract" and [r["identifier"] for r in rules] == ["GVR-235", "GVR-240"]
    assert [r["identifier"] for r, _ in rc.evaluate("rsync -a . root@138.197.72.15:/opt", rules)] == ["GVR-240"]


def test_rule_check_without_marker_uses_store_or_snapshot(tmp_path: Path):
    snapshot = tmp_path / rc.SNAPSHOT_FILE
    snapshot.parent.mkdir(parents=True)
    snapshot.write_text(json.dumps({"fetched_at": datetime.now(UTC).timestamp(),
                                    "rules": [{"identifier": "GVR-001", "enforcement": "enforced"}]}))
    rules, source = rc.load_rules(tmp_path, session_id="no-marker")
    assert source == "snapshot" and rules[0]["identifier"] == "GVR-001"


# --- entry points ------------------------------------------------------------------------


def test_main_never_fails(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.delenv("CRMBUILDER_V2_API_BASE_URL", raising=False)
    monkeypatch.delenv("CRMBUILDER_V2_API_TOKEN", raising=False)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(json.dumps({"session_id": "s1", "prompt": "hello"})))
    assert so.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "SESSION NOT OPENED" in out
    marker = sc.read_marker(tmp_path, "s1")
    assert marker["open_failed_at"] and marker["opening_answer"] == "hello"


# --- REQ-594: what the user sees -------------------------------------------------------


def _run_main(tmp_path: Path, monkeypatch, capsys, store: FakeStore, prompt: str) -> dict:
    monkeypatch.setattr(so, "make_caller", lambda *a, **k: store.call)
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(
        json.dumps({"session_id": "abc-123", "prompt": prompt})))
    assert so.main([str(tmp_path)]) == 0
    return json.loads(capsys.readouterr().out)


def test_hook_shows_the_confirmation_line_to_the_user(tmp_path: Path, monkeypatch, capsys):
    store = FakeStore()
    _start(tmp_path, store)
    out = _run_main(tmp_path, monkeypatch, capsys, store, "define new business processes")
    assert out["systemMessage"] == (
        "Session SES-410 opened. It sounds like you want to define new business processes; "
        "I will start with the Requirements Interviewer."
    )
    context = out["hookSpecificOutput"]["additionalContext"]
    assert out["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "# Session opened — SES-410" in context and "**GVR-240**" in context


def test_hook_shows_the_follow_up_question_to_the_user(tmp_path: Path, monkeypatch, capsys):
    store = FakeStore()
    _start(tmp_path, store)
    out = _run_main(tmp_path, monkeypatch, capsys, store, "send birthday cards")
    assert "What would you like done by the end of this session?" in out["systemMessage"]
    assert "ask the user this one question" in out["hookSpecificOutput"]["additionalContext"]


def test_hook_shows_the_could_not_open_notice_to_the_user(tmp_path: Path, monkeypatch, capsys):
    store = FakeStore(open_fails=True)
    _start(tmp_path, store)
    out = _run_main(tmp_path, monkeypatch, capsys, store, "define new business processes")
    assert out["systemMessage"].startswith("Session not opened:")
    assert "ConnectionError: dns failed" in out["systemMessage"]
    assert "open_session" in out["systemMessage"]
    assert out["hookSpecificOutput"]["additionalContext"].startswith("> **SESSION NOT OPENED")


def test_hook_passes_the_restatement_instruction_to_the_model(tmp_path: Path):
    store = FakeStore()
    _start(tmp_path, store)
    original = store.call

    def with_instruction(method, path, body):
        result = original(method, path, body)
        if path == so.OPEN_PATH and result.get("confirmation_line"):
            result["contract"]["first_reply_instruction"] = (
                f"Begin your first reply with: \"{result['confirmation_line']}\""
            )
        return result

    text = so.open_from_prompt(tmp_path, "abc-123", "define new business processes", call=with_instruction)
    assert 'Begin your first reply with: "It sounds like' in text


def test_a_later_prompt_prints_nothing(tmp_path: Path, monkeypatch, capsys):
    store = FakeStore()
    _start(tmp_path, store)
    _run_main(tmp_path, monkeypatch, capsys, store, "define new business processes")
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(
        json.dumps({"session_id": "abc-123", "prompt": "next"})))
    assert so.main([str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""
