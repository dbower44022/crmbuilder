"""Vocabulary tests for the v0.8 Code Change Lifecycle additions.

Covers:
- the new ``commit`` entity type in ``ENTITY_TYPES``;
- the three new relationship kinds (``resolves``, ``addresses``,
  ``blocked_by``) plus the retirement of the legacy ``blocks`` kind;
- ``_kinds_for_pair`` source/target bindings for the new kinds.
"""

from __future__ import annotations

from crmbuilder_v2.access import vocab


def test_commit_entity_type_registered():
    assert "commit" in vocab.ENTITY_TYPES


def test_new_v0_8_relationship_kinds_registered():
    assert "resolves" in vocab.REFERENCE_RELATIONSHIPS
    assert "addresses" in vocab.REFERENCE_RELATIONSHIPS
    assert "blocked_by" in vocab.REFERENCE_RELATIONSHIPS


def test_legacy_blocks_kind_retired():
    assert "blocks" not in vocab.REFERENCE_RELATIONSHIPS


def test_kinds_for_pair_v0_8_bindings():
    kfp = vocab._kinds_for_pair
    # conversation -> planning_item admits both resolves and addresses
    pair = kfp("conversation", "planning_item")
    assert "resolves" in pair
    assert "addresses" in pair
    # work_ticket -> planning_item admits addresses (not resolves)
    pair = kfp("work_ticket", "planning_item")
    assert "addresses" in pair
    assert "resolves" not in pair
    # planning_item -> planning_item admits blocked_by
    pair = kfp("planning_item", "planning_item")
    assert "blocked_by" in pair


def test_blocks_no_longer_emitted_by_any_pair():
    """The legacy ``blocks`` kind must not appear in any pair's kinds."""
    for (s, t), kinds in vocab.RELATIONSHIP_RULES.items():
        assert "blocks" not in kinds, (
            f"`blocks` still appears in kinds for ({s}, {t}): {sorted(kinds)}"
        )


def test_risk_source_still_admits_affects():
    """Removing ``blocks`` from the risk clause must leave ``affects``."""
    assert "affects" in vocab._kinds_for_pair("risk", "planning_item")
    assert "affects" in vocab._kinds_for_pair("risk", "decision")


def test_commit_pair_admits_generic_kinds():
    """A (commit, X) pair admits the generic ``is_about`` and ``references``."""
    pair = vocab._kinds_for_pair("commit", "session")
    assert "is_about" in pair
    assert "references" in pair


def test_commit_same_type_admits_supersedes():
    """``supersedes`` is admitted for the rare (commit, commit) case."""
    assert "supersedes" in vocab._kinds_for_pair("commit", "commit")


def test_relationship_rules_covers_commit_pairs():
    """``RELATIONSHIP_RULES`` is precomputed; commit pairs must be present."""
    assert ("commit", "session") in vocab.RELATIONSHIP_RULES
    assert ("conversation", "commit") in vocab.RELATIONSHIP_RULES
    assert ("commit", "commit") in vocab.RELATIONSHIP_RULES
