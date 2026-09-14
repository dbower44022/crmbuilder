"""Reference integrity — PI-502 (REQ-596, REQ-597, REQ-598; DEC-1081, DEC-1083).

A reference needs both of its records to exist before it is written or makes
any change to another record, and the stored references that already point at
a missing record are reported without being changed.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import reference_integrity as ri
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.models import Reference
from crmbuilder_v2.access.repositories import conversations as cr
from crmbuilder_v2.access.repositories import decisions, domain, references
from crmbuilder_v2.access.repositories import planning_items as pi
from crmbuilder_v2.access.repositories import projects as ws
from crmbuilder_v2.access.repositories import sessions as se
from crmbuilder_v2.access.repositories import work_tickets as wt
from crmbuilder_v2.access.vocab import REFERENCE_EXISTENCE_EXEMPT_TYPES
from sqlalchemy import select

_SUMMARY = (
    "A record that exists so the reference-integrity tests have something real "
    "to point at; it carries no content of its own and stands in for whichever "
    "governed record a reference would name in practice, so the tests exercise "
    "the existence check rather than any particular record type."
)


def _codes(exc_info) -> set[str]:
    return {e.code for e in exc_info.value.errors}


def _decision(s, title="A ruling") -> str:
    return decisions.create(
        s, title=title, decision_date="2026-09-14", status="Active",
        executive_summary=_SUMMARY,
    )["identifier"]


def _domain(s) -> str:
    return domain.create_domain(s, name="Domain", purpose="p", description="d")["domain_identifier"]


def _planning_item(s) -> str:
    return pi.create(s, title="Work", item_type="pending_work", executive_summary=_SUMMARY)["identifier"]


def _session_and_conversation(s):
    project = ws.create_project(s, name="Project", purpose="p", description="d")["project_identifier"]
    se.create_session(
        s, identifier="SES-001", title="Session", description="d", medium="chat",
        executive_summary=_SUMMARY,
        references=[{"source_type": "session", "source_id": "SES-001",
                     "target_type": "project", "target_id": project,
                     "relationship": "session_belongs_to_project"}],
    )
    cr.create_conversation(
        s, identifier="CNV-001", title="Conversation", purpose="p", description="d",
        references=[{"source_type": "conversation", "source_id": "CNV-001",
                     "target_type": "session", "target_id": "SES-001",
                     "relationship": "conversation_belongs_to_session"}],
    )
    return "SES-001", "CNV-001"


# --- REQ-596: both records must exist ------------------------------------------------


def test_reference_between_existing_records_is_accepted(v2_env):
    with session_scope() as s:
        dec = _decision(s)
        dom = _domain(s)
        edge = references.create(s, source_type="decision", source_id=dec,
                                 target_type="domain", target_id=dom, relationship="is_about")
    assert edge["relationship"] == "is_about"


def test_missing_source_is_refused_naming_the_source(v2_env):
    with session_scope() as s:
        dom = _domain(s)
        with pytest.raises(UnprocessableError) as exc:
            references.create(s, source_type="decision", source_id="DEC-999",
                              target_type="domain", target_id=dom, relationship="is_about")
    assert _codes(exc) == {"source_not_found"}
    assert "DEC-999" in exc.value.errors[0].message


def test_missing_target_is_refused_naming_the_target(v2_env):
    with session_scope() as s:
        dec = _decision(s)
        with pytest.raises(UnprocessableError) as exc:
            references.create(s, source_type="decision", source_id=dec,
                              target_type="domain", target_id="DOM-999", relationship="is_about")
    assert _codes(exc) == {"target_not_found"}


def test_both_missing_ends_are_reported_together(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError) as exc:
            references.create(s, source_type="decision", source_id="DEC-998",
                              target_type="domain", target_id="DOM-998", relationship="is_about")
    assert _codes(exc) == {"source_not_found", "target_not_found"}


def test_an_error_message_as_identifier_is_refused(v2_env):
    """The SES-411 case: an API error's text sent as the source identifier."""
    with session_scope() as s:
        item = _planning_item(s)
        with pytest.raises(UnprocessableError) as exc:
            references.create(
                s, source_type="conversation",
                source_id="[{'code': 'request_validation_error', 'field': 'body'}]",
                target_type="planning_item", target_id=item, relationship="resolves",
            )
    assert _codes(exc) == {"source_not_found"}


def test_a_soft_deleted_record_still_counts_as_existing(v2_env):
    with session_scope() as s:
        dec = _decision(s)
        dom = _domain(s)
        domain.delete_domain(s, dom)
        edge = references.create(s, source_type="decision", source_id=dec,
                                 target_type="domain", target_id=dom, relationship="is_about")
    assert edge["target_id"] == dom


def test_a_new_record_with_its_references_succeeds(v2_env):
    """A reference supplied with the record it starts from is checked after
    that record is written."""
    with session_scope() as s:
        ses, cnv = _session_and_conversation(s)
    with session_scope() as s:
        rows = s.scalars(select(Reference).where(Reference.source_id == cnv)).all()
    assert [(r.relationship_kind, r.target_id) for r in rows] == [
        ("conversation_belongs_to_session", ses)
    ]


def test_exempt_types_are_named_in_the_vocabulary_and_not_looked_up(v2_env):
    assert REFERENCE_EXISTENCE_EXEMPT_TYPES == {
        "charter", "status", "catalog_entity", "catalog_attribute",
        "mapping_candidate", "reference",
    }
    with session_scope() as s:
        dec = _decision(s)
        assert ri.record_exists(s, "catalog_entity", "12345") is None
        edge = references.create(s, source_type="decision", source_id=dec,
                                 target_type="catalog_entity", target_id="12345",
                                 relationship="is_about")
    assert edge["target_type"] == "catalog_entity"


# --- REQ-597: a change to another record waits for the check ------------------------


def test_resolves_from_a_missing_conversation_leaves_the_item_unchanged(v2_env):
    with session_scope() as s:
        item = _planning_item(s)
        with pytest.raises(UnprocessableError):
            references.create(s, source_type="conversation", source_id="CNV-404",
                              target_type="planning_item", target_id=item, relationship="resolves")
    with session_scope() as s:
        assert pi.get(s, item)["status"] == "Draft"


def test_consumption_from_a_missing_session_leaves_the_ticket_ready(v2_env):
    with session_scope() as s:
        wt.create_work_ticket(s, title="Ticket", description="d", kind="kickoff_prompt",
                              file_path="PRDs/t.md")
        wt.patch_work_ticket(s, "WT-001", status="ready")
        with pytest.raises(UnprocessableError):
            references.create(s, source_type="session", source_id="SES-404",
                              target_type="work_ticket", target_id="WT-001",
                              relationship="session_opens_against_work_ticket")
    with session_scope() as s:
        assert wt.get_work_ticket(s, "WT-001")["work_ticket_status"] == "ready"


def test_resolves_from_an_existing_conversation_still_resolves(v2_env):
    with session_scope() as s:
        _, cnv = _session_and_conversation(s)
        item = _planning_item(s)
        references.create(s, source_type="conversation", source_id=cnv,
                          target_type="planning_item", target_id=item, relationship="resolves")
    with session_scope() as s:
        assert pi.get(s, item)["status"] == "Resolved"


# --- REQ-598: the census ------------------------------------------------------------


def _snapshot(s) -> list[tuple]:
    return [
        (r.id, r.source_type, r.source_id, r.target_type, r.target_id, r.relationship_kind)
        for r in s.scalars(select(Reference).order_by(Reference.id)).all()
    ]


def test_census_lists_a_stored_reference_to_a_missing_record(v2_env):
    with session_scope() as s:
        dec = _decision(s)
        # Written the way the older writers wrote it: straight into the table,
        # past the check, as the seven production references were.
        s.add(Reference(source_type="decision", source_id=dec, target_type="domain",
                        target_id="DOM-404", relationship_kind="is_about",
                        reference_identifier="REF-0001"))
        s.add(Reference(source_type="workstream", source_id="__SELF__",
                        target_type="planning_item", target_id="PI-404",
                        relationship_kind="workstream_belongs_to_planning_item",
                        reference_identifier="REF-0002"))
        s.flush()
        before = _snapshot(s)
        found = ri.dangling_references(s)
        after = _snapshot(s)
    assert before == after
    assert [(f["reference_identifier"], f["missing"]) for f in found] == [
        ("REF-0001", ["target"]),
        ("REF-0002", ["source", "target"]),
    ]
    assert found[0]["relationship"] == "is_about" and found[0]["target_id"] == "DOM-404"


def test_census_of_a_clean_store_is_empty(v2_env):
    with session_scope() as s:
        dec = _decision(s)
        dom = _domain(s)
        references.create(s, source_type="decision", source_id=dec,
                          target_type="domain", target_id=dom, relationship="is_about")
        assert ri.dangling_references(s) == []
