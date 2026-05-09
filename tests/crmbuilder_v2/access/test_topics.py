"""Topics repository tests."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ValidationError
from crmbuilder_v2.access.repositories import topics


def test_topic_hierarchy(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOPIC-001", name="Schema design")
        topics.create(
            s, identifier="TOPIC-002", name="References table", parent_topic="TOPIC-001"
        )
    with session_scope() as s:
        child = topics.get(s, "TOPIC-002")
    assert child["parent_topic_identifier"] == "TOPIC-001"


def test_unknown_parent(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        topics.create(s, identifier="TOPIC-X", name="x", parent_topic="TOPIC-NONE")


def test_update(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOPIC-001", name="Foo")
    with session_scope() as s:
        topics.update(s, "TOPIC-001", description="more")
    with session_scope() as s:
        assert topics.get(s, "TOPIC-001")["description"] == "more"


def test_update_parent_topic_set(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOPIC-001", name="Parent A")
        topics.create(s, identifier="TOPIC-002", name="Parent B")
        topics.create(s, identifier="TOPIC-003", name="Child", parent_topic="TOPIC-001")
    with session_scope() as s:
        topics.update(s, "TOPIC-003", parent_topic="TOPIC-002")
    with session_scope() as s:
        assert topics.get(s, "TOPIC-003")["parent_topic_identifier"] == "TOPIC-002"


def test_update_parent_topic_clear_with_empty_string(v2_env):
    """Empty-string parent_topic clears the FK (re-parents to root).

    Parallel to v0.1 slice H's supersedes='' clearing fix on decisions.
    """
    with session_scope() as s:
        topics.create(s, identifier="TOPIC-001", name="Parent")
        topics.create(s, identifier="TOPIC-002", name="Child", parent_topic="TOPIC-001")
    with session_scope() as s:
        topics.update(s, "TOPIC-002", parent_topic="")
    with session_scope() as s:
        assert topics.get(s, "TOPIC-002")["parent_topic_identifier"] is None


def test_update_parent_topic_none_does_not_touch(v2_env):
    """parent_topic=None means 'do not touch' (existing behavior)."""
    with session_scope() as s:
        topics.create(s, identifier="TOPIC-001", name="Parent")
        topics.create(s, identifier="TOPIC-002", name="Child", parent_topic="TOPIC-001")
    with session_scope() as s:
        topics.update(s, "TOPIC-002", description="changed", parent_topic=None)
    with session_scope() as s:
        topic = topics.get(s, "TOPIC-002")
        assert topic["parent_topic_identifier"] == "TOPIC-001"
        assert topic["description"] == "changed"


def test_update_parent_topic_unknown_raises(v2_env):
    with session_scope() as s:
        topics.create(s, identifier="TOPIC-001", name="A")
    with session_scope() as s, pytest.raises(ValidationError):
        topics.update(s, "TOPIC-001", parent_topic="TOPIC-NONEXISTENT")
