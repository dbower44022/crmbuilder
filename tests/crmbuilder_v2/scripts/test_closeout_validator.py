"""Tests for the PI-090 close-out-payload pre-flight validator.

``closeout_validator.py`` lives at ``crmbuilder-v2/scripts/`` which isn't on
the package import path, so it's loaded by file path the same way
``test_apply_close_out.py`` loads the apply script.

The shape checks (1-9) run offline (``api_base=None``); the identifier-head
check (10) is driven by a fake ``head_fetcher`` so no live API is needed.
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

# Load the validator by file path.
_VALIDATOR_PATH = (
    Path(__file__).resolve().parents[3]
    / "crmbuilder-v2"
    / "scripts"
    / "closeout_validator.py"
)
_spec = importlib.util.spec_from_file_location("closeout_validator", _VALIDATOR_PATH)
cv = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cv)

# A real applied payload, used as a known-good template.
_REAL_PAYLOAD_PATH = (
    Path(__file__).resolve().parents[3]
    / "PRDs"
    / "product"
    / "crmbuilder-v2"
    / "close-out-payloads"
    / "ses_107.json"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _errors(violations) -> list:
    return [v for v in violations if v.severity == cv.SEVERITY_ERROR]


def _warnings(violations) -> list:
    return [v for v in violations if v.severity == cv.SEVERITY_WARNING]


def _check_names(violations) -> set:
    return {v.check_name for v in violations}


def _valid_payload() -> dict:
    """A minimal-but-complete, valid post-PI-073 payload.

    All ten sections present; valid session/conversation blocks with the
    mandatory conversation_belongs_to_session edge; one Active decision with
    its decided_in→conversation edge; one pending_work PI; one work_ticket
    with a file path.
    """
    return {
        "label": "Valid test payload",
        "session": {
            "session_identifier": "SES-500",
            "session_title": "Valid test session",
            "session_description": "A complete, valid post-PI-073 session.",
            "session_medium": "chat",
            "session_status": "complete",
            "references": [
                {
                    "source_type": "session",
                    "source_id": "SES-500",
                    "target_type": "workstream",
                    "target_id": "WS-012",
                    "relationship": "session_belongs_to_workstream",
                }
            ],
        },
        "conversation": {
            "conversation_identifier": "CNV-500",
            "conversation_title": "Valid test conversation",
            "conversation_status": "complete",
            "references": [
                {
                    "source_type": "conversation",
                    "source_id": "CNV-500",
                    "target_type": "session",
                    "target_id": "SES-500",
                    "relationship": "conversation_belongs_to_session",
                }
            ],
        },
        "work_tickets": [
            {
                "work_ticket_identifier": "WT-500",
                "work_ticket_title": "Test WT",
                "work_ticket_description": "d",
                "work_ticket_file_path": "PRDs/test/foo.md",
                "work_ticket_kind": "kickoff_prompt",
                "work_ticket_status": "drafted",
            }
        ],
        "planning_items": [
            {
                "identifier": "PI-500",
                "title": "Test PI",
                "description": "d",
                "item_type": "pending_work",
                "status": "Open",
            }
        ],
        "commits": [],
        "decisions": [
            {
                "identifier": "DEC-500",
                "title": "Test decision",
                "decision_date": "2026-05-27",
                "status": "Active",
            }
        ],
        "references": [
            {
                "source_type": "decision",
                "source_id": "DEC-500",
                "target_type": "conversation",
                "target_id": "CNV-500",
                "relationship": "decided_in",
            }
        ],
        "resolves_planning_items": [],
        "addresses_planning_items": [{"planning_item_identifier": "PI-500"}],
    }


# ---------------------------------------------------------------------------
# Fully-valid payloads pass clean
# ---------------------------------------------------------------------------


def test_constructed_valid_payload_passes_offline():
    violations = cv.validate_payload(_valid_payload(), api_base=None)
    assert _errors(violations) == [], cv.format_report(violations)


def test_real_ses107_payload_passes_offline():
    """A real applied payload (ses_107.json) has zero error-severity
    violations — the validator doesn't reject clean payloads."""
    payload = json.loads(_REAL_PAYLOAD_PATH.read_text())
    violations = cv.validate_payload(payload, api_base=None)
    assert _errors(violations) == [], cv.format_report(violations)


# ---------------------------------------------------------------------------
# Check 1 — required sections
# ---------------------------------------------------------------------------


def test_required_sections_all_present_passes():
    assert cv.check_required_sections(_valid_payload()) == []


def test_required_sections_missing_key_is_error():
    payload = _valid_payload()
    del payload["decisions"]
    violations = cv.check_required_sections(payload)
    assert len(_errors(violations)) == 1
    assert "decisions" in violations[0].message


def test_required_sections_empty_arrays_ok():
    payload = _valid_payload()
    payload["work_tickets"] = []
    payload["decisions"] = []
    payload["references"] = []
    assert cv.check_required_sections(payload) == []


# ---------------------------------------------------------------------------
# Check 2 — session block shape + medium vocab (SES-101 case)
# ---------------------------------------------------------------------------


def test_session_block_valid_passes():
    assert cv.check_session_block(_valid_payload()) == []


def test_session_medium_claude_code_rejected_ses101_case():
    payload = _valid_payload()
    payload["session"]["session_medium"] = "claude_code"
    violations = cv.check_session_block(payload)
    assert len(_errors(violations)) == 1
    assert "claude_code" in violations[0].message
    assert "SES-101" in violations[0].message


def test_session_bad_identifier_rejected():
    payload = _valid_payload()
    payload["session"]["session_identifier"] = "SESSION-1"
    violations = cv.check_session_block(payload)
    assert any("session_identifier" in v.message for v in _errors(violations))


def test_session_missing_required_field_rejected():
    payload = _valid_payload()
    payload["session"]["session_description"] = ""
    violations = cv.check_session_block(payload)
    assert any("session_description" in v.message for v in _errors(violations))


# ---------------------------------------------------------------------------
# Check 3 — conversation block shape + parentage edge
# ---------------------------------------------------------------------------


def test_conversation_block_valid_passes():
    assert cv.check_conversation_block(_valid_payload()) == []


def test_conversation_bad_identifier_rejected():
    payload = _valid_payload()
    payload["conversation"]["conversation_identifier"] = "CONV-500"
    violations = cv.check_conversation_block(payload)
    assert any("conversation_identifier" in v.message for v in _errors(violations))


def test_conversation_missing_belongs_to_session_edge_rejected():
    payload = _valid_payload()
    payload["conversation"]["references"] = []
    violations = cv.check_conversation_block(payload)
    assert any(
        "conversation_belongs_to_session" in v.message for v in _errors(violations)
    )


def test_conversation_belongs_to_session_edge_in_top_level_refs_ok():
    """The membership edge counts whether it's inline in the conversation
    block OR in the top-level references[]."""
    payload = _valid_payload()
    edge = payload["conversation"]["references"].pop()
    payload["references"].append(edge)
    assert cv.check_conversation_block(payload) == []


# ---------------------------------------------------------------------------
# Check 4 — decision status enum (Final → SES-067)
# ---------------------------------------------------------------------------


def test_decision_status_active_passes():
    assert cv.check_decision_status(_valid_payload()) == []


def test_decision_status_final_rejected_with_ses067():
    payload = _valid_payload()
    payload["decisions"][0]["status"] = "Final"
    violations = cv.check_decision_status(payload)
    assert len(_errors(violations)) == 1
    assert "Final" in violations[0].message
    assert "SES-067" in violations[0].message


def test_decision_status_unknown_rejected():
    payload = _valid_payload()
    payload["decisions"][0]["status"] = "Approved"
    violations = cv.check_decision_status(payload)
    assert len(_errors(violations)) == 1
    assert "Approved" in violations[0].message


def test_decision_status_all_valid_enum_values_pass():
    for status in ("Active", "Superseded", "Withdrawn", "Deleted"):
        payload = _valid_payload()
        payload["decisions"][0]["status"] = status
        assert cv.check_decision_status(payload) == [], status


# ---------------------------------------------------------------------------
# Check 5 — decision back-reference (decided_in → CONVERSATION)
# ---------------------------------------------------------------------------


def test_decision_back_reference_present_passes():
    assert cv.check_decision_back_reference(_valid_payload()) == []


def test_decision_missing_decided_in_conversation_rejected():
    payload = _valid_payload()
    payload["references"] = []
    violations = cv.check_decision_back_reference(payload)
    assert len(_errors(violations)) == 1
    assert "decided_in" in violations[0].message
    assert "conversation" in violations[0].message.lower()


def test_decision_decided_in_targeting_session_is_rejected():
    """Post-PI-073, decided_in must target a conversation, not a session —
    an edge targeting the session does NOT satisfy the check."""
    payload = _valid_payload()
    payload["references"] = [
        {
            "source_type": "decision",
            "source_id": "DEC-500",
            "target_type": "session",
            "target_id": "SES-500",
            "relationship": "decided_in",
        }
    ]
    violations = cv.check_decision_back_reference(payload)
    assert len(_errors(violations)) == 1


def test_no_decisions_no_back_reference_violations():
    payload = _valid_payload()
    payload["decisions"] = []
    payload["references"] = []
    assert cv.check_decision_back_reference(payload) == []


# ---------------------------------------------------------------------------
# Check 6 — PI item_type
# ---------------------------------------------------------------------------


def test_planning_item_pending_work_passes():
    assert cv.check_planning_item_type(_valid_payload()) == []


def test_planning_item_wrong_type_rejected():
    payload = _valid_payload()
    payload["planning_items"][0]["item_type"] = "open_question"
    violations = cv.check_planning_item_type(payload)
    assert len(_errors(violations)) == 1
    assert "pending_work" in violations[0].message


def test_planning_item_missing_type_rejected():
    payload = _valid_payload()
    del payload["planning_items"][0]["item_type"]
    violations = cv.check_planning_item_type(payload)
    assert len(_errors(violations)) == 1


# ---------------------------------------------------------------------------
# Check 7 — work_ticket file path
# ---------------------------------------------------------------------------


def test_work_ticket_file_path_present_passes():
    assert cv.check_work_ticket_file_path(_valid_payload()) == []


def test_work_ticket_missing_file_path_rejected():
    payload = _valid_payload()
    del payload["work_tickets"][0]["work_ticket_file_path"]
    violations = cv.check_work_ticket_file_path(payload)
    assert len(_errors(violations)) == 1
    assert "work_ticket_file_path" in violations[0].message


def test_work_ticket_empty_file_path_rejected():
    payload = _valid_payload()
    payload["work_tickets"][0]["work_ticket_file_path"] = "  "
    violations = cv.check_work_ticket_file_path(payload)
    assert len(_errors(violations)) == 1


def test_work_ticket_placeholder_path_ok():
    payload = _valid_payload()
    payload["work_tickets"][0]["work_ticket_file_path"] = "n/a"
    assert cv.check_work_ticket_file_path(payload) == []


# ---------------------------------------------------------------------------
# Check 8 — reference field key (relationship vs relationship_kind)
# ---------------------------------------------------------------------------


def test_reference_field_key_valid_passes():
    assert cv.check_reference_field_key(_valid_payload()) == []


def test_reference_relationship_kind_mistake_rejected():
    payload = _valid_payload()
    payload["references"][0].pop("relationship")
    payload["references"][0]["relationship_kind"] = "decided_in"
    violations = cv.check_reference_field_key(payload)
    assert len(_errors(violations)) == 1
    assert "relationship_kind" in violations[0].message


def test_reference_missing_relationship_rejected():
    payload = _valid_payload()
    payload["references"][0].pop("relationship")
    violations = cv.check_reference_field_key(payload)
    assert len(_errors(violations)) == 1


def test_resolves_pi_missing_identifier_key_rejected():
    payload = _valid_payload()
    payload["resolves_planning_items"] = [{"pi": "PI-500"}]
    violations = cv.check_reference_field_key(payload)
    assert any("planning_item_identifier" in v.message for v in _errors(violations))


# ---------------------------------------------------------------------------
# Check 9 — executive_summary length (PI-074 rule)
# ---------------------------------------------------------------------------


def test_exec_summary_absent_passes():
    payload = _valid_payload()
    # No executive_summary anywhere.
    assert cv.check_executive_summary_length(payload) == []


def test_exec_summary_null_passes():
    payload = _valid_payload()
    payload["session"]["session_executive_summary"] = None
    payload["decisions"][0]["executive_summary"] = None
    assert cv.check_executive_summary_length(payload) == []


def test_exec_summary_150_chars_rejected():
    payload = _valid_payload()
    payload["session"]["session_executive_summary"] = "x" * 150
    violations = cv.check_executive_summary_length(payload)
    assert len(_errors(violations)) == 1
    assert "200-800" in violations[0].message
    assert "150" in violations[0].message


def test_exec_summary_400_chars_passes():
    payload = _valid_payload()
    payload["session"]["session_executive_summary"] = "x" * 400
    assert cv.check_executive_summary_length(payload) == []


def test_exec_summary_too_long_rejected():
    payload = _valid_payload()
    payload["decisions"][0]["executive_summary"] = "y" * 801
    violations = cv.check_executive_summary_length(payload)
    assert len(_errors(violations)) == 1


def test_exec_summary_boundaries_inclusive():
    payload = _valid_payload()
    payload["session"]["session_executive_summary"] = "a" * 200
    assert cv.check_executive_summary_length(payload) == []
    payload["session"]["session_executive_summary"] = "a" * 800
    assert cv.check_executive_summary_length(payload) == []


# ---------------------------------------------------------------------------
# Check 10 — identifier-head conflicts (WARNING, not error)
# ---------------------------------------------------------------------------


def _fake_head_fetcher(heads: dict[str, str]):
    """Build a head_fetcher mapping endpoint paths to next-identifier strings."""

    def fetch(endpoint: str):
        return heads.get(endpoint)

    return fetch


def test_identifier_head_at_or_below_head_warns_not_errors():
    payload = _valid_payload()  # SES-500, CNV-500, DEC-500, PI-500, WT-500
    # Heads are well past the payload identifiers → re-apply situation.
    fetcher = _fake_head_fetcher(
        {
            "/sessions/next-identifier": "SES-600",
            "/conversations/next-identifier": "CNV-600",
            "/decisions/next-identifier": "DEC-600",
            "/planning-items/next-identifier": "PI-600",
            "/work-tickets/next-identifier": "WT-600",
        }
    )
    violations = cv.check_identifier_heads(payload, head_fetcher=fetcher)
    assert _errors(violations) == []
    warns = _warnings(violations)
    assert len(warns) == 5
    assert all(v.check_name == "identifier_heads" for v in warns)


def test_identifier_head_above_head_no_warning():
    payload = _valid_payload()
    # Heads are at the payload identifiers' slots → these are the next-to-be
    # assigned, i.e. payload number == head means "not yet created"; only
    # strictly-below warns.
    fetcher = _fake_head_fetcher(
        {
            "/sessions/next-identifier": "SES-500",
            "/conversations/next-identifier": "CNV-500",
            "/decisions/next-identifier": "DEC-500",
            "/planning-items/next-identifier": "PI-500",
            "/work-tickets/next-identifier": "WT-500",
        }
    )
    violations = cv.check_identifier_heads(payload, head_fetcher=fetcher)
    assert violations == []


def test_identifier_head_unreachable_degrades_to_no_warning():
    payload = _valid_payload()
    # Fetcher returns None for everything (API unreachable).
    violations = cv.check_identifier_heads(
        payload, head_fetcher=lambda endpoint: None
    )
    assert violations == []


def test_head_check_via_validate_payload_is_warning_only():
    """End-to-end: a re-apply payload (identifiers below head) produces only
    warnings through validate_payload, never errors."""
    payload = _valid_payload()
    fetcher = _fake_head_fetcher(
        {
            "/sessions/next-identifier": "SES-999",
            "/conversations/next-identifier": "CNV-999",
            "/decisions/next-identifier": "DEC-999",
            "/planning-items/next-identifier": "PI-999",
            "/work-tickets/next-identifier": "WT-999",
        }
    )
    violations = cv.validate_payload(payload, head_fetcher=fetcher)
    assert _errors(violations) == []
    assert len(_warnings(violations)) == 5


# ---------------------------------------------------------------------------
# Offline mode: head check skipped, shape checks still run
# ---------------------------------------------------------------------------


def test_offline_mode_skips_head_check_runs_shape_checks():
    payload = _valid_payload()
    # Valid payload, offline → zero violations (head check skipped, no shape
    # errors).
    assert cv.validate_payload(payload, api_base=None) == []

    # Break a shape check; offline still catches it (no API needed).
    payload["session"]["session_medium"] = "claude_code"
    violations = cv.validate_payload(payload, api_base=None)
    errs = _errors(violations)
    assert len(errs) == 1
    assert errs[0].check_name == "session_block"
    # And no head-check warnings were produced offline.
    assert _warnings(violations) == []


# ---------------------------------------------------------------------------
# Aggregate behavior + report formatting
# ---------------------------------------------------------------------------


def test_multiple_violations_aggregate_across_checks():
    payload = _valid_payload()
    payload["session"]["session_medium"] = "claude_code"  # check 2
    payload["decisions"][0]["status"] = "Final"  # check 4
    payload["planning_items"][0]["item_type"] = "open_question"  # check 6
    violations = cv.validate_payload(payload, api_base=None)
    names = _check_names(violations)
    assert "session_block" in names
    assert "decision_status" in names
    assert "planning_item_type" in names


def test_format_report_groups_by_severity():
    payload = _valid_payload()
    payload["decisions"][0]["status"] = "Final"  # one error
    fetcher = _fake_head_fetcher({"/sessions/next-identifier": "SES-999"})
    violations = cv.validate_payload(payload, head_fetcher=fetcher)
    report = cv.format_report(violations)
    assert "[ERROR]" in report
    assert "[WARN]" in report
    # Errors appear before warnings.
    assert report.index("[ERROR]") < report.index("[WARN]")


def test_valid_payload_template_is_actually_valid_offline():
    """Guard: the _valid_payload() fixture must itself be clean, otherwise
    the negative tests above are testing against a poisoned baseline."""
    payload = copy.deepcopy(_valid_payload())
    assert cv.validate_payload(payload, api_base=None) == []
