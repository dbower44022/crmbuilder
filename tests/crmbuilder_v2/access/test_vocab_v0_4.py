"""Vocab additions for UI v0.4 slice A — foundation.

Covers the four new methodology entity types (``domain``, ``entity``,
``process``, ``crm_candidate``), the two new relationship kinds
(``entity_scopes_to_domain``, ``process_hands_off_to_process``), the
two new ``_kinds_for_pair`` rules, and the auto-recomputation of
``RELATIONSHIP_RULES`` at module load.
"""

from __future__ import annotations

from crmbuilder_v2.access.vocab import (
    ENTITY_TYPES,
    REFERENCE_RELATIONSHIPS,
    RELATIONSHIP_RULES,
    _kinds_for_pair,
)


def test_entity_types_contains_v0_4_additions():
    for new_type in ("domain", "entity", "process", "crm_candidate"):
        assert new_type in ENTITY_TYPES


def test_reference_relationships_contains_v0_4_additions():
    assert "entity_scopes_to_domain" in REFERENCE_RELATIONSHIPS
    assert "process_hands_off_to_process" in REFERENCE_RELATIONSHIPS


def test_kinds_for_entity_domain_pair():
    kinds = _kinds_for_pair("entity", "domain")
    assert "entity_scopes_to_domain" in kinds
    # The two universal kinds are always present.
    assert "is_about" in kinds
    assert "references" in kinds


def test_kinds_for_process_process_pair():
    kinds = _kinds_for_pair("process", "process")
    assert "process_hands_off_to_process" in kinds
    assert "is_about" in kinds
    assert "references" in kinds
    # Matched-type universal: source == target admits supersedes.
    assert "supersedes" in kinds


def test_entity_scopes_to_domain_is_directional():
    """The kind is valid entity -> domain only, not domain -> entity."""
    reverse = _kinds_for_pair("domain", "entity")
    assert "entity_scopes_to_domain" not in reverse


def test_domain_domain_pair_has_supersedes_no_methodology_kinds():
    kinds = _kinds_for_pair("domain", "domain")
    assert "supersedes" in kinds  # matched type
    assert "entity_scopes_to_domain" not in kinds
    assert "process_hands_off_to_process" not in kinds


def test_crm_candidate_session_pair_has_decided_in():
    """The universal decided_in rule applies to new entity types too."""
    kinds = _kinds_for_pair("crm_candidate", "session")
    assert "decided_in" in kinds


def test_relationship_rules_recomputed_for_entity_domain():
    assert RELATIONSHIP_RULES[("entity", "domain")] == _kinds_for_pair(
        "entity", "domain"
    )


def test_relationship_rules_recomputed_for_process_process():
    assert RELATIONSHIP_RULES[("process", "process")] == _kinds_for_pair(
        "process", "process"
    )


def test_relationship_rules_includes_new_entity_type_pairs():
    """New entity types participate in the auto-recomputation."""
    kinds = RELATIONSHIP_RULES[("crm_candidate", "decision")]
    assert "is_about" in kinds
    assert "references" in kinds


def test_relationship_rules_keys_cover_every_pair():
    """Every (source, target) pair over the expanded ENTITY_TYPES is keyed."""
    expected = {(s, t) for s in ENTITY_TYPES for t in ENTITY_TYPES}
    assert set(RELATIONSHIP_RULES.keys()) == expected
