"""Topics repository tests."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import topics


def test_topic_hierarchy(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOP-001", name="Schema design")
        topics.create(
            s, identifier="TOP-002", name="References table", parent_topic="TOP-001"
        )
    with session_scope() as s:
        child = topics.get(s, "TOP-002")
    assert child["parent_topic_identifier"] == "TOP-001"


def test_unknown_parent(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        topics.create(s, identifier="TOPIC-X", name="x", parent_topic="TOPIC-NONE")


def test_update(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOP-001", name="Foo")
    with session_scope() as s:
        topics.update(s, "TOP-001", description="more")
    with session_scope() as s:
        assert topics.get(s, "TOP-001")["description"] == "more"


def test_update_parent_topic_set(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOP-001", name="Parent A")
        topics.create(s, identifier="TOP-002", name="Parent B")
        topics.create(s, identifier="TOP-003", name="Child", parent_topic="TOP-001")
    with session_scope() as s:
        topics.update(s, "TOP-003", parent_topic="TOP-002")
    with session_scope() as s:
        assert topics.get(s, "TOP-003")["parent_topic_identifier"] == "TOP-002"


def test_update_parent_topic_clear_with_empty_string(v2_env):
    """Empty-string parent_topic clears the FK (re-parents to root).

    Parallel to v0.1 slice H's supersedes='' clearing fix on decisions.
    """
    with session_scope() as s:
        topics.create(s, identifier="TOP-001", name="Parent")
        topics.create(s, identifier="TOP-002", name="Child", parent_topic="TOP-001")
    with session_scope() as s:
        topics.update(s, "TOP-002", parent_topic="")
    with session_scope() as s:
        assert topics.get(s, "TOP-002")["parent_topic_identifier"] is None


def test_update_parent_topic_none_does_not_touch(v2_env):
    """parent_topic=None means 'do not touch' (existing behavior)."""
    with session_scope() as s:
        topics.create(s, identifier="TOP-001", name="Parent")
        topics.create(s, identifier="TOP-002", name="Child", parent_topic="TOP-001")
    with session_scope() as s:
        topics.update(s, "TOP-002", description="changed", parent_topic=None)
    with session_scope() as s:
        topic = topics.get(s, "TOP-002")
        assert topic["parent_topic_identifier"] == "TOP-001"
        assert topic["description"] == "changed"


def test_update_parent_topic_unknown_raises(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOP-001", name="A")
    with session_scope() as s, pytest.raises(ValidationError):
        topics.update(s, "TOP-001", parent_topic="TOPIC-NONEXISTENT")


# ---------------------------------------------------------------------------
# PI-002 — identifier is server-assigned when omitted (option C of SES-010)
# ---------------------------------------------------------------------------


def test_create_with_omitted_identifier_assigns_next(v2_env):
    with session_scope() as s:
        row = topics.create(s, name="Auto")
    assert row["identifier"] == "TOP-001"
    with session_scope() as s:
        row2 = topics.create(s, name="Auto2")
    assert row2["identifier"] == "TOP-002"


def test_create_with_supplied_identifier_uses_it(v2_env):
    with session_scope() as s:
        row = topics.create(s, identifier="TOP-042", name="Explicit")
    assert row["identifier"] == "TOP-042"


def test_create_with_invalid_identifier_format_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        topics.create(s, identifier="TOP-1", name="Bad")


def test_create_with_empty_string_identifier_rejected(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        topics.create(s, identifier="", name="Bad")


def test_create_explicit_duplicate_identifier_raises_conflict(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOP-001", name="First")
    with session_scope() as s, pytest.raises(ConflictError):
        topics.create(s, identifier="TOP-001", name="Second")


def test_autoassign_retries_on_identifier_collision(v2_env, monkeypatch):
    with session_scope() as s:
        topics.create(s, identifier="TOP-001", name="First")
    monkeypatch.setattr(topics, "compute_next_identifier", lambda _s: "TOP-001")
    with session_scope() as s:
        row = topics.create(s, name="Second")
    assert row["identifier"] == "TOP-002"
