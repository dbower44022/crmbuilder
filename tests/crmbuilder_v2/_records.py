"""Create the real records a test's references name (PI-502).

A reference may only name records that exist (REQ-596), so a test that wants a
reference between, say, a session and a decision first creates both. This
module creates the smallest valid record of the common types under an explicit
identifier, and does nothing when the record is already there, so a test can
call ``ensure(s, "session", "SES-001")`` without caring whether an earlier
helper made it.
"""

from __future__ import annotations

from crmbuilder_v2.access.reference_integrity import record_exists
from crmbuilder_v2.access.repositories import (
    conversations,
    decisions,
    deposit_events,
    planning_items,
    projects,
    requirement,
    sessions,
    topics,
)

SUMMARY = (
    "A record created only so a test's reference names something real; it "
    "carries no content of its own and stands in for whichever governed record "
    "the reference would name in practice, since a reference to a missing "
    "record is refused."
)

_PROJECT = "PRJ-900"


def _project(s) -> str:
    if not record_exists(s, "project", _PROJECT):
        projects.create_project(
            s, identifier=_PROJECT, name="Test records project",
            purpose="Holds sessions created for test references.", description="d",
        )
    return _PROJECT


def ensure(s, entity_type: str, identifier: str) -> str:
    """Create ``identifier`` as a minimal record of ``entity_type`` if absent."""
    if record_exists(s, entity_type, identifier):
        return identifier
    if entity_type == "decision":
        decisions.create(s, identifier=identifier, title=f"Decision {identifier}",
                         decision_date="2026-09-14", status="Active",
                         executive_summary=SUMMARY)
    elif entity_type == "session":
        sessions.create_session(
            s, identifier=identifier, title=f"Session {identifier}", description="d",
            medium="chat", executive_summary=SUMMARY,
            references=[{"source_type": "session", "source_id": identifier,
                         "target_type": "project", "target_id": _project(s),
                         "relationship": "session_belongs_to_project"}],
        )
    elif entity_type == "conversation":
        session_id = ensure(s, "session", "SES-900")
        conversations.create_conversation(
            s, identifier=identifier, title=f"Conversation {identifier}",
            purpose="p", description="d",
            references=[{"source_type": "conversation", "source_id": identifier,
                         "target_type": "session", "target_id": session_id,
                         "relationship": "conversation_belongs_to_session"}],
        )
    elif entity_type == "planning_item":
        planning_items.create(s, identifier=identifier, title=f"Item {identifier}",
                              item_type="pending_work", executive_summary=SUMMARY)
    elif entity_type == "requirement":
        requirement.create_requirement(
            s, identifier=identifier, name=f"Requirement {identifier}",
            description="The system does one testable thing.",
            acceptance_summary="The thing is observed.",
        )
    elif entity_type == "topic":
        topics.create(s, identifier=identifier, name=f"Topic {identifier}")
    elif entity_type == "deposit_event":
        deposit_events.create_deposit_event(
            s, identifier=identifier, title=f"Audit deposit {identifier}",
            description="Baseline deposit for a test.", kind="audit_deposit",
            outcome="success", records_summary={},
            apply_context={"source_system": "espocrm",
                           "source_instance": "https://crm.example.org",
                           "snapshot_at": "2026-06-11T18:00:00Z"},
            log_file_path="PRDs/product/crmbuilder-v2/deposit-event-logs/dep_test.log",
        )
    else:
        raise ValueError(f"ensure() does not create {entity_type!r} records")
    return identifier


#: The record types :func:`ensure` knows how to create.
CREATABLE = frozenset(
    {"decision", "session", "conversation", "planning_item", "requirement",
     "topic", "deposit_event"}
)


def ensure_ends(source_type: str, source_id: str, target_type: str, target_id: str) -> None:
    """For a test driving the REST API: create either end of a reference that is
    missing, when its type is one :func:`ensure` creates. Other types are left
    alone, so a test that means to name a missing record of those types still
    can."""
    from crmbuilder_v2.access.db import session_scope

    with session_scope() as s:
        for entity_type, identifier in ((source_type, source_id), (target_type, target_id)):
            if entity_type in CREATABLE:
                ensure(s, entity_type, identifier)
