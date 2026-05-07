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
