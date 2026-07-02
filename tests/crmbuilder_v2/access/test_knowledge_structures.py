"""REL-039 / PI-357 — preference / lesson / reference_pointer repositories.

Covers CRUD + the system|engagement scope merge for the three knowledge-class
entities (REQ-416, DEC-891), the vocab-rejection paths, and the three new
``lesson_*`` provenance edges (which also proves the ``refs`` +
``change_log`` CHECK rebuilds admit the new entity types / relationship kinds).

v2_env seeds ENG-001 (the default active engagement) and is hermetic; when
``CRMBUILDER_V2_TEST_PG_URL`` is set it runs against Postgres, otherwise SQLite.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import (
    lessons,
    preferences,
    reference_pointers,
    references,
)

# --------------------------------------------------------------------------
# preference
# --------------------------------------------------------------------------


def test_preference_create_scopes_and_autoassign(v2_env):
    with session_scope() as s:
        sys_p = preferences.create(
            s, category="interaction", title="No confirmation",
            body="Execute autonomously.", applies_to="claude_code",
        )
        assert sys_p["identifier"] == "PRF-001"
        assert sys_p["scope"] == "system"
        assert sys_p["engagement_id"] is None
        assert sys_p["applies_to"] == "claude_code"

        eng_p = preferences.create(
            s, category="ui", title="Warm-orange secondary buttons",
            body="Use #FFA726.", scope="ENG-001",
        )
        assert eng_p["identifier"] == "PRF-002"
        assert eng_p["scope"] == "ENG-001"
        assert eng_p["applies_to"] == "all"  # default


def test_preference_rejects_bad_vocab_and_unknown_scope(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            preferences.create(s, category="bogus", title="x", body="y")
        with pytest.raises(UnprocessableError):
            preferences.create(
                s, category="interaction", title="x", body="y", applies_to="nope"
            )
        with pytest.raises(ValidationError):
            preferences.create(
                s, category="interaction", title="x", body="y", scope="ENG-999"
            )


def test_preference_explicit_identifier_and_conflict(v2_env):
    with session_scope() as s:
        preferences.create(
            s, identifier="PRF-050", category="workflow", title="a", body="b"
        )
        with pytest.raises(ConflictError):
            preferences.create(
                s, identifier="PRF-050", category="workflow", title="c", body="d"
            )
        with pytest.raises(UnprocessableError):
            preferences.create(
                s, identifier="BAD-1", category="workflow", title="c", body="d"
            )


def test_preference_list_update_delete(v2_env):
    with session_scope() as s:
        preferences.create(s, category="interaction", title="a", body="b")
        preferences.create(s, category="ui", title="c", body="d")
        assert len(preferences.list_all(s)) == 2
        assert len(preferences.list_all(s, category="ui")) == 1
        assert len(preferences.list_all(s, scope="system")) == 2

        updated = preferences.update(s, "PRF-001", status="retired", scope="ENG-001")
        assert updated["status"] == "retired"
        assert updated["scope"] == "ENG-001"
        with pytest.raises(ValidationError):
            preferences.update(s, "PRF-001", bogus_field="x")

        preferences.delete(s, "PRF-002")
        assert len(preferences.list_all(s)) == 1
        with pytest.raises(NotFoundError):
            preferences.get(s, "PRF-002")


# --------------------------------------------------------------------------
# lesson
# --------------------------------------------------------------------------


def test_lesson_create_and_signal(v2_env):
    with session_scope() as s:
        hazard = lessons.create(
            s, category="engineering", title="Rebuild change_log CHECK",
            body="Adding an entity type must rebuild the change_log CHECK.",
            signal="hazard",
        )
        assert hazard["identifier"] == "LSN-001"
        assert hazard["signal"] == "hazard"
        howto = lessons.create(
            s, category="deployment", title="Safe live migrate",
            body="Verify schema == head then alembic stamp head.", signal="howto",
        )
        assert howto["signal"] == "howto"
        assert lessons.list_all(s, signal="hazard") == [
            l for l in lessons.list_all(s) if l["signal"] == "hazard"
        ]


def test_lesson_rejects_bad_vocab(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            lessons.create(s, category="nope", title="x", body="y")
        with pytest.raises(UnprocessableError):
            lessons.create(s, category="process", title="x", body="y", signal="bad")


# --------------------------------------------------------------------------
# reference_pointer
# --------------------------------------------------------------------------


def test_reference_pointer_create_and_scope(v2_env):
    with session_scope() as s:
        rfp = reference_pointers.create(
            s, kind="server", title="CBM prod",
            target="crm.clevelandbusinessmentors.org",
            access_note="SSH root + ~/.ssh/id_ed25519 (key path only, never the key)",
            scope="ENG-001",
        )
        assert rfp["identifier"] == "RFP-001"
        assert rfp["scope"] == "ENG-001"
        assert rfp["kind"] == "server"
        sysrfp = reference_pointers.create(
            s, kind="doc", title="Agent PRDs", target="PRDs/.../Agent PRDs/Archive/",
        )
        assert sysrfp["scope"] == "system"
        assert len(reference_pointers.list_all(s, kind="server")) == 1


def test_reference_pointer_rejects_bad_kind(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            reference_pointers.create(s, kind="bogus", title="x", target="y")


# --------------------------------------------------------------------------
# lesson provenance edges — proves the refs + change_log CHECK rebuilds
# --------------------------------------------------------------------------


def test_lesson_derived_from_and_supersedes_edges(v2_env):
    with session_scope() as s:
        l1 = lessons.create(
            s, category="engineering", title="lesson 1", body="b1"
        )
        l2 = lessons.create(
            s, category="engineering", title="lesson 2 (corrects 1)", body="b2"
        )
        # lesson_derived_from -> decision (the DB record the memory was welded to)
        edge = references.create(
            s, source_type="lesson", source_id=l1["identifier"],
            target_type="decision", target_id="DEC-001",
            relationship="lesson_derived_from",
        )
        assert edge["relationship"] == "lesson_derived_from"
        # lesson_supersedes -> lesson (same-type)
        sup = references.create(
            s, source_type="lesson", source_id=l2["identifier"],
            target_type="lesson", target_id=l1["identifier"],
            relationship="lesson_supersedes",
        )
        assert sup["relationship"] == "lesson_supersedes"


def test_lesson_promoted_to_learning_edge_pair_valid(v2_env):
    from crmbuilder_v2.access.vocab import RELATIONSHIP_RULES

    assert "lesson_derived_from" in RELATIONSHIP_RULES[("lesson", "decision")]
    assert "lesson_derived_from" in RELATIONSHIP_RULES[("lesson", "planning_item")]
    assert "lesson_derived_from" in RELATIONSHIP_RULES[("lesson", "commit")]
    assert "lesson_supersedes" in RELATIONSHIP_RULES[("lesson", "lesson")]
    assert "lesson_promoted_to_learning" in RELATIONSHIP_RULES[("lesson", "learning")]
