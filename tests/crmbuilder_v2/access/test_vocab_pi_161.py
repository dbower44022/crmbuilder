"""Vocabulary tests for PI-161 — the `service` methodology entity.

Covers the WTK-132 design spec's vocab surface
(methodology-schema-specs/service.md §10): the standard four-status
lifecycle, the two edge kinds with their pair rules (process → service,
service → entity), the deliberate absence of `service_scopes_to_domain`
(§3.3.2), the entity-type registration, and the `rejected_by_decision`
source-set extension to the ninth status-bearing type.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import vocab

_CONSUMES = "process_consumes_service"
_OWNS = "service_owns_entity"


def test_statuses_are_the_standard_four():
    assert vocab.SERVICE_STATUSES == frozenset(
        {"candidate", "confirmed", "deferred", "rejected"}
    )


def test_transitions_mirror_the_methodology_lifecycle():
    # Same map as domain/entity/field/persona — no per-type variation (§3.4.1).
    assert vocab.SERVICE_STATUS_TRANSITIONS == vocab.PERSONA_STATUS_TRANSITIONS
    assert vocab.SERVICE_STATUS_TRANSITIONS["rejected"] == frozenset()
    # One-way propose-verify gate: no status lists candidate as a successor.
    assert all(
        "candidate" not in succ
        for succ in vocab.SERVICE_STATUS_TRANSITIONS.values()
    )
    # confirmed cannot reach rejected directly (two-step demotion via deferred).
    assert "rejected" not in vocab.SERVICE_STATUS_TRANSITIONS["confirmed"]


def test_edge_kinds_registered():
    assert _CONSUMES in vocab.REFERENCE_RELATIONSHIPS
    assert _OWNS in vocab.REFERENCE_RELATIONSHIPS


def test_entity_type_registered():
    assert "service" in vocab.ENTITY_TYPES
    assert "service" in vocab.CHANGE_LOG_ENTITY_TYPES


def test_process_consumes_service_pair_rule():
    # The process is the source (the actor doing the consuming, §3.3.1).
    kinds = vocab.RELATIONSHIP_RULES[("process", "service")]
    assert _CONSUMES in kinds
    # Direction matters: the inverse pair does not admit the kind.
    assert _CONSUMES not in vocab.RELATIONSHIP_RULES[("service", "process")]


def test_service_owns_entity_pair_rule():
    kinds = vocab.RELATIONSHIP_RULES[("service", "entity")]
    assert _OWNS in kinds
    assert _OWNS not in vocab.RELATIONSHIP_RULES[("entity", "service")]


def test_no_service_scopes_to_domain_kind():
    # §3.3.2: a cross-domain service is not domain-bound — its coverage is
    # derived from consuming processes, never asserted via a scoping edge.
    assert "service_scopes_to_domain" not in vocab.REFERENCE_RELATIONSHIPS
    assert "service_scopes_to_domain" not in vocab._kinds_for_pair(
        "service", "domain"
    )


def test_edge_kinds_do_not_leak_to_other_sources():
    assert _CONSUMES not in vocab._kinds_for_pair("process", "entity")
    assert _OWNS not in vocab._kinds_for_pair("service", "field")
    assert _CONSUMES not in vocab._kinds_for_pair("service", "service")


def test_rejected_by_decision_extended_to_service():
    # §10: the rejected terminal requires the rationale edge, so the source
    # set grows to include the ninth status-bearing type.
    assert "rejected_by_decision" in vocab.RELATIONSHIP_RULES[
        ("service", "decision")
    ]
    assert "rejected_by_decision" not in vocab._kinds_for_pair(
        "service", "session"
    )


def test_generic_kinds_still_apply():
    kinds = vocab.RELATIONSHIP_RULES[("service", "service")]
    assert "is_about" in kinds
    assert "references" in kinds
    assert "supersedes" in kinds


@pytest.mark.parametrize("target", ["field", "process", "decision", "persona"])
def test_service_does_not_own_non_entity_targets(target):
    assert _OWNS not in vocab.RELATIONSHIP_RULES[("service", target)]
