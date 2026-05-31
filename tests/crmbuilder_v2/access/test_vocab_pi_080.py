"""Vocabulary tests for the PI-080 ``conversation_orchestrates_conversation`` kind.

Adds a third (conversation, conversation) edge alongside the existing
``conversation_follows_from`` and ``conversation_relates_to`` kinds, plus
the same-type ``supersedes`` admitted for every same-type pair. Used to
express the parent–child relationship between an orchestrator
conversation and the child agents' conversations it supervises.
"""

from __future__ import annotations

from crmbuilder_v2.access import vocab

_NEW_KIND = "conversation_orchestrates_conversation"


def test_new_relationship_kind_registered():
    assert _NEW_KIND in vocab.REFERENCE_RELATIONSHIPS


def test_kinds_for_pair_conversation_conversation_admits_new_kind():
    kinds = vocab._kinds_for_pair("conversation", "conversation")
    assert _NEW_KIND in kinds
    # The redesign's other two (conversation, conversation) kinds remain
    # admitted alongside; the new kind joins them rather than replacing.
    assert "conversation_follows_from" in kinds
    assert "conversation_relates_to" in kinds
    # Same-type supersession is still admitted via the generic clause.
    assert "supersedes" in kinds


def test_relationship_rules_conversation_pair_includes_new_kind():
    assert _NEW_KIND in vocab.RELATIONSHIP_RULES[("conversation", "conversation")]


def test_new_kind_does_not_leak_to_unrelated_pairs():
    # The kind is conversation→conversation only; other (conversation, X)
    # and (X, conversation) pairs must not pick it up.
    assert _NEW_KIND not in vocab._kinds_for_pair("conversation", "session")
    assert _NEW_KIND not in vocab._kinds_for_pair("conversation", "project")
    assert _NEW_KIND not in vocab._kinds_for_pair("session", "conversation")
    assert _NEW_KIND not in vocab._kinds_for_pair("session", "session")


def test_target_types_for_new_kind_is_conversation_only():
    targets = vocab.target_types_for("conversation", _NEW_KIND)
    assert targets == frozenset({"conversation"})
