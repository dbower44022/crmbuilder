"""PI-462 vocab tests — the ``withdraws`` reference kind (REQ-560 / DEC-1034)
and the ``claude_code`` session medium (REQ-561 / DEC-1035)."""

from __future__ import annotations

from crmbuilder_v2.access.vocab import (
    REFERENCE_RELATIONSHIPS,
    RELATIONSHIP_RULES,
    SESSION_MEDIUMS,
    _kinds_for_pair,
    kinds_for_source,
    target_types_for,
)


def test_withdraws_is_a_reference_kind():
    assert "withdraws" in REFERENCE_RELATIONSHIPS


def test_withdraws_runs_from_a_decision_only():
    for (source, _target), kinds in RELATIONSHIP_RULES.items():
        if "withdraws" in kinds:
            assert source == "decision"
    assert "withdraws" not in kinds_for_source("requirement")
    assert "withdraws" not in kinds_for_source("session")


def test_withdraws_targets_the_governed_record_types():
    targets = target_types_for("decision", "withdraws")
    assert {"decision", "requirement", "planning_item"} <= targets
    # Communication and mechanical types are not withdrawn by decision.
    assert not targets & {"session", "conversation", "commit", "deposit_event"}


def test_withdraws_unlike_supersedes_crosses_types():
    assert "withdraws" in _kinds_for_pair("decision", "requirement")
    assert "supersedes" not in _kinds_for_pair("decision", "requirement")
    assert {"withdraws", "supersedes"} <= _kinds_for_pair("decision", "decision")


def test_claude_code_is_a_session_medium():
    assert "claude_code" in SESSION_MEDIUMS
    # The pre-existing seven remain.
    assert {"chat", "email", "phone", "zoom", "in_person", "slack", "other"} <= (
        SESSION_MEDIUMS
    )
