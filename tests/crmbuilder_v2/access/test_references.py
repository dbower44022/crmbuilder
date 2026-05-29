"""References repository tests (DEC-006 universal pattern)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.repositories import (
    conversations as cr,
    planning_items as pi,
    references,
    sessions as se,
    workstreams as ws,
)

# A 200-800 character audience-facing executive summary, required on
# planning_items (PI-102) and sessions (PI-073/PI-075).
_EXEC_SUMMARY = (
    "This planning item reconciles stale test fixtures with the current "
    "governance schema so the suite validates real behavior; it carries no "
    "production code change and exists purely to keep the regression net "
    "aligned with the PI-073 and PI-102 data-model decisions now in effect."
)


def _add(s, **kw):
    return references.create(
        s,
        source_type="session",
        source_id="SES-001",
        target_type="decision",
        target_id="DEC-001",
        relationship="decided_in",
        **kw,
    )


def test_create_and_list_from(v2_env):
    with session_scope() as s:
        _add(s)
    with session_scope() as s:
        rows = references.list_from(s, source_type="session", source_id="SES-001")
    assert len(rows) == 1
    assert rows[0]["target_id"] == "DEC-001"
    assert rows[0]["relationship"] == "decided_in"


def test_unknown_relationship_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        references.create(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-001",
            relationship="vibes_with",
        )


def test_unknown_entity_type_rejected(v2_env):
    with session_scope() as s, pytest.raises(ValidationError):
        references.create(
            s,
            source_type="alien",
            source_id="A",
            target_type="decision",
            target_id="DEC-001",
            relationship="is_about",
        )


def test_duplicate_reference_rejected(v2_env):
    with session_scope() as s:
        _add(s)
    with session_scope() as s, pytest.raises(ConflictError):
        _add(s)


def test_list_to_and_touching(v2_env):
    with session_scope() as s:
        _add(s)
        references.create(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-002",
            relationship="decided_in",
        )
        references.create(
            s,
            source_type="decision",
            source_id="DEC-001",
            target_type="topic",
            target_id="TOPIC-001",
            relationship="is_about",
        )
    with session_scope() as s:
        to_dec1 = references.list_to(s, target_type="decision", target_id="DEC-001")
        touching = references.list_touching(
            s, entity_type="decision", entity_id="DEC-001"
        )
    assert len(to_dec1) == 1
    assert len(touching["as_source"]) == 1
    assert len(touching["as_target"]) == 1


def test_delete(v2_env):
    with session_scope() as s:
        _add(s)
    with session_scope() as s:
        references.delete(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-001",
            relationship="decided_in",
        )
    with session_scope() as s, pytest.raises(NotFoundError):
        references.delete(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-001",
            relationship="decided_in",
        )


def test_upsert_idempotent(v2_env):
    with session_scope() as s:
        first = _add(s)
    with session_scope() as s:
        second = references.upsert(
            s,
            source_type="session",
            source_id="SES-001",
            target_type="decision",
            target_id="DEC-001",
            relationship="decided_in",
        )
    assert first["id"] == second["id"]


def test_delete_by_id_removes_row(v2_env):
    with session_scope() as s:
        created = _add(s)
    ref_id = created["id"]
    with session_scope() as s:
        before = references.delete_by_id(s, ref_id)
    assert before["id"] == ref_id
    with session_scope() as s, pytest.raises(NotFoundError):
        references.get(s, ref_id)


def test_delete_by_id_unknown_id_raises(v2_env):
    with session_scope() as s, pytest.raises(NotFoundError):
        references.delete_by_id(s, 999_999)


class TestResolvesStatusFlip:
    """PI-030 slice A: POST /references with relationship=resolves flips
    target planning_item status to Resolved in the same transaction."""

    @staticmethod
    def _conv(s, identifier="CNV-991"):
        """Create a conversation linked into the redesigned governance
        hierarchy (PI-073): workstream <- session <- conversation.

        A conversation requires exactly one outbound
        ``conversation_belongs_to_session`` edge, and the parent session
        requires exactly one outbound ``session_belongs_to_workstream``
        edge. Build that chain so the conversation create validates.
        """
        wid = ws.create_workstream(
            s, name="WS " + identifier, purpose="p", description="d"
        )["workstream_identifier"]
        # Derive an explicit session identifier from the conversation's
        # numeric suffix (e.g. CNV-991 -> SES-991) so the membership edge
        # can name its source before the row is persisted.
        ses_id = "SES-" + identifier.split("-", 1)[1]
        se.create_session(
            s,
            title="Session " + identifier,
            description="d",
            medium="chat",
            executive_summary=_EXEC_SUMMARY,
            identifier=ses_id,
            references=[{
                "source_type": "session", "source_id": ses_id,
                "target_type": "workstream", "target_id": wid,
                "relationship": "session_belongs_to_workstream",
            }],
        )
        return cr.create_conversation(
            s, title="Conv " + identifier, purpose="p", description="d",
            identifier=identifier,
            references=[{
                "source_type": "conversation", "source_id": identifier,
                "target_type": "session", "target_id": ses_id,
                "relationship": "conversation_belongs_to_session",
            }],
        )["conversation_identifier"]

    @staticmethod
    def _pi(s, identifier="PI-991", status="Open"):
        return pi.create(
            s,
            identifier=identifier,
            title="Test PI " + identifier,
            item_type="pending_work",
            description="",
            status=status,
            executive_summary=_EXEC_SUMMARY,
        )["identifier"]

    def test_resolves_flips_open_to_resolved(self, v2_env):
        """Happy path: Open planning_item -> Resolved on resolves edge."""
        with session_scope() as s:
            conv_id = self._conv(s, "CNV-991")
            pi_id = self._pi(s, "PI-991", status="Open")
        with session_scope() as s:
            references.create(
                s,
                source_type="conversation",
                source_id=conv_id,
                target_type="planning_item",
                target_id=pi_id,
                relationship="resolves",
            )
        with session_scope() as s:
            row = pi.get(s, pi_id)
        assert row["status"] == "Resolved"

    def test_resolves_idempotent_on_already_resolved(self, v2_env):
        """Resolved -> Resolved: no-op update; reference still created."""
        with session_scope() as s:
            conv_id = self._conv(s, "CNV-992")
            pi_id = self._pi(s, "PI-992", status="Resolved")
        with session_scope() as s:
            created = references.create(
                s,
                source_type="conversation",
                source_id=conv_id,
                target_type="planning_item",
                target_id=pi_id,
                relationship="resolves",
            )
        with session_scope() as s:
            row = pi.get(s, pi_id)
        assert created["relationship"] == "resolves"
        assert row["status"] == "Resolved"

    def test_duplicate_resolves_edge_returns_409(self, v2_env):
        """Second resolves edge with same source/target/kind raises
        ConflictError; planning_item status remains Resolved."""
        with session_scope() as s:
            conv_id = self._conv(s, "CNV-993")
            pi_id = self._pi(s, "PI-993", status="Open")
        with session_scope() as s:
            references.create(
                s,
                source_type="conversation",
                source_id=conv_id,
                target_type="planning_item",
                target_id=pi_id,
                relationship="resolves",
            )
        with session_scope() as s, pytest.raises(ConflictError):
            references.create(
                s,
                source_type="conversation",
                source_id=conv_id,
                target_type="planning_item",
                target_id=pi_id,
                relationship="resolves",
            )
        with session_scope() as s:
            row = pi.get(s, pi_id)
        assert row["status"] == "Resolved"

    def test_non_resolves_kind_does_not_flip(self, v2_env):
        """An is_about edge from a conversation to a planning_item does
        NOT change the planning_item's status; the flip is gated on the
        relationship kind, not on the target type."""
        with session_scope() as s:
            conv_id = self._conv(s, "CNV-994")
            pi_id = self._pi(s, "PI-994", status="Open")
        with session_scope() as s:
            references.create(
                s,
                source_type="conversation",
                source_id=conv_id,
                target_type="planning_item",
                target_id=pi_id,
                relationship="is_about",
            )
        with session_scope() as s:
            row = pi.get(s, pi_id)
        assert row["status"] == "Open"
