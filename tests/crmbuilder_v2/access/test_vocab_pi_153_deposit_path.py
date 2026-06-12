"""Vocabulary tests for PI-153 / WTK-089 — `rejected` lifecycle + deposit-path provenance.

Covers the WTK-088 design spec D1 (the fourth truly-terminal ``rejected``
status across the seven status-bearing methodology entity types, with the
``rejected_by_decision`` rationale kind) and the WTK-089 design spec D1/D2
(the ``observed_in`` observation-provenance kind and the
``deposit_event_wrote_record`` target extension to the five baseline
capture types), plus the new ``DEPOSIT_EVENT_KINDS`` /
``BASELINE_CAPTURE_TYPES`` / ``EVIDENCE_SUBJECT_TYPES`` /
``CHANGE_LOG_ENTITY_TYPES`` vocabularies.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import vocab

_REJECTED = "rejected"

# (statuses set, transitions map) for the seven types per WTK-088 §3.1.
_LIFECYCLES = (
    (vocab.DOMAIN_STATUSES, vocab.DOMAIN_STATUS_TRANSITIONS),
    (vocab.ENTITY_STATUSES, vocab.ENTITY_STATUS_TRANSITIONS),
    (vocab.FIELD_STATUSES, vocab.FIELD_STATUS_TRANSITIONS),
    (vocab.PERSONA_STATUSES, vocab.PERSONA_STATUS_TRANSITIONS),
    (vocab.REQUIREMENT_STATUSES, vocab.REQUIREMENT_STATUS_TRANSITIONS),
    (vocab.MANUAL_CONFIG_STATUSES, vocab.MANUAL_CONFIG_STATUS_TRANSITIONS),
    (vocab.TEST_SPEC_STATUSES, vocab.TEST_SPEC_STATUS_TRANSITIONS),
)

_REJECTABLE_SOURCES = (
    "domain",
    "entity",
    "field",
    "persona",
    "requirement",
    "test_spec",
    "manual_config",
)


@pytest.mark.parametrize("statuses, transitions", _LIFECYCLES)
def test_rejected_in_all_seven_status_sets(statuses, transitions):
    assert _REJECTED in statuses
    assert _REJECTED in transitions


@pytest.mark.parametrize("statuses, transitions", _LIFECYCLES)
def test_rejected_is_truly_terminal(statuses, transitions):
    assert transitions[_REJECTED] == frozenset()


@pytest.mark.parametrize("statuses, transitions", _LIFECYCLES)
def test_rejected_reachable_from_candidate_and_deferred_only(statuses, transitions):
    sources = {s for s, succ in transitions.items() if _REJECTED in succ}
    assert sources == {"candidate", "deferred"}


@pytest.mark.parametrize("statuses, transitions", _LIFECYCLES)
def test_one_way_candidate_gate_preserved(statuses, transitions):
    # No status — including rejected — lists candidate as a successor.
    assert all("candidate" not in succ for succ in transitions.values())


def test_manual_config_completed_stays_terminal():
    assert vocab.MANUAL_CONFIG_STATUS_TRANSITIONS["completed"] == frozenset()


def test_rejected_by_decision_registered():
    assert "rejected_by_decision" in vocab.REFERENCE_RELATIONSHIPS


@pytest.mark.parametrize("source", _REJECTABLE_SOURCES)
def test_rejected_by_decision_admitted_for_seven_sources(source):
    assert "rejected_by_decision" in vocab.RELATIONSHIP_RULES[(source, "decision")]


def test_rejected_by_decision_does_not_leak():
    # process has no lifecycle status (WTK-088 §3.1 out-of-scope note);
    # non-decision targets never admit the kind.
    assert "rejected_by_decision" not in vocab._kinds_for_pair("process", "decision")
    assert "rejected_by_decision" not in vocab._kinds_for_pair("field", "session")
    assert "rejected_by_decision" not in vocab._kinds_for_pair("decision", "field")


def test_observed_in_registered():
    assert "observed_in" in vocab.REFERENCE_RELATIONSHIPS


@pytest.mark.parametrize("source", sorted(vocab.BASELINE_CAPTURE_TYPES))
def test_observed_in_admitted_for_capture_types(source):
    assert "observed_in" in vocab.RELATIONSHIP_RULES[(source, "deposit_event")]


def test_observed_in_does_not_leak():
    assert "observed_in" not in vocab._kinds_for_pair("decision", "deposit_event")
    assert "observed_in" not in vocab._kinds_for_pair("field", "close_out_payload")
    assert "observed_in" not in vocab._kinds_for_pair("deposit_event", "field")


@pytest.mark.parametrize("target", sorted(vocab.BASELINE_CAPTURE_TYPES))
def test_wrote_record_extended_to_capture_types(target):
    kinds = vocab.RELATIONSHIP_RULES[("deposit_event", target)]
    assert "deposit_event_wrote_record" in kinds


def test_wrote_record_close_out_targets_unchanged():
    for target in ("session", "decision", "planning_item", "commit"):
        kinds = vocab.RELATIONSHIP_RULES[("deposit_event", target)]
        assert "deposit_event_wrote_record" in kinds


def test_baseline_capture_types_are_the_five_phase_15_types():
    assert vocab.BASELINE_CAPTURE_TYPES == frozenset(
        {"entity", "field", "persona", "process", "manual_config"}
    )
    # Defined once so the observed_in clause and the evidence subject
    # vocabulary cannot drift (WTK-089 §3.2).
    assert vocab.EVIDENCE_SUBJECT_TYPES == vocab.BASELINE_CAPTURE_TYPES


def test_deposit_event_kinds():
    assert vocab.DEPOSIT_EVENT_KINDS == frozenset(
        {"close_out_apply", "audit_deposit"}
    )


def test_change_log_admits_utilization_evidence_outside_entity_types():
    assert "utilization_evidence" in vocab.CHANGE_LOG_ENTITY_TYPES
    assert "reference" in vocab.CHANGE_LOG_ENTITY_TYPES
    # Evidence is a mechanical table outside the refs discipline
    # (WTK-088 §4.2) — never a reference source/target type.
    assert "utilization_evidence" not in vocab.ENTITY_TYPES
