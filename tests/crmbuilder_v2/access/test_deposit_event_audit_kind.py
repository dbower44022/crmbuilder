"""Audit-kind deposit_event repository tests (WTK-089 §4.2–4.3, D3).

The ``close_out_apply`` behavior is covered by ``test_deposit_event.py``
and unchanged; these tests pin the kind-conditional rules the
``audit_deposit`` kind adds: parent edge forbidden (I4), no lazy
payload, required ``apply_context`` keys (I6), wrote_record edges to
methodology capture targets, and the ``kind`` list filter.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.models import CloseOutPayload
from crmbuilder_v2.access.repositories import deposit_events
from crmbuilder_v2.access.repositories.entity import create_entity
from sqlalchemy import func, select

_AUDIT_CONTEXT = {
    "source_system": "espocrm",
    "source_instance": "https://crm.example.org",
    "snapshot_at": "2026-06-11T18:00:00Z",
}


def _create_audit_event(s, **overrides):
    kwargs = {
        "title": "Audit deposit: espocrm @ crm.example.org",
        "description": "Phase 1.5 baseline deposit.",
        "kind": "audit_deposit",
        "outcome": "success",
        "records_summary": {},
        "apply_context": dict(_AUDIT_CONTEXT),
        "log_file_path": "PRDs/product/crmbuilder-v2/deposit-event-logs/dep_test.log",
    }
    kwargs.update(overrides)
    return deposit_events.create_deposit_event(s, **kwargs)


def test_audit_deposit_without_parent_edge_succeeds(v2_env):
    with session_scope() as s:
        event = _create_audit_event(s)
    assert event["deposit_event_kind"] == "audit_deposit"
    # No lazy payload was manufactured.
    with session_scope() as s:
        assert (
            s.scalar(
                select(
                    func.count(CloseOutPayload.close_out_payload_identifier)
                )
            )
            == 0
        )


def test_audit_deposit_with_parent_edge_is_refused(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _create_audit_event(
            s,
            references=[
                {
                    "relationship": "deposit_event_applies_close_out_payload",
                    "target_type": "close_out_payload",
                    "target_id": "COP-001",
                }
            ],
        )
    assert (
        exc.value.errors[0].code
        == "deposit_event_audit_kind_forbids_close_out_payload_edge"
    )


def test_audit_deposit_requires_apply_context_keys(v2_env):
    for missing in ("source_system", "source_instance", "snapshot_at"):
        context = dict(_AUDIT_CONTEXT)
        del context[missing]
        with session_scope() as s, pytest.raises(UnprocessableError):
            _create_audit_event(s, apply_context=context)
    with session_scope() as s, pytest.raises(UnprocessableError):
        _create_audit_event(
            s, apply_context=dict(_AUDIT_CONTEXT, snapshot_at="not-a-date")
        )


def test_close_out_apply_still_requires_parent_edge(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        _create_audit_event(s, kind="close_out_apply")
    assert (
        exc.value.errors[0].code
        == "deposit_event_requires_applies_close_out_payload_edge"
    )


def test_wrote_record_targets_methodology_records(v2_env):
    with session_scope() as s:
        ent = create_entity(s, name="Engagement", description="d")
        event = _create_audit_event(
            s,
            records_summary={"entities": 1},
            references=[
                {
                    "relationship": "deposit_event_wrote_record",
                    "target_type": "entity",
                    "target_id": ent["entity_identifier"],
                }
            ],
        )
    assert event["deposit_event_records_summary"] == {"entities": 1}


def test_kind_filter_on_list(v2_env):
    with session_scope() as s:
        _create_audit_event(s)
    with session_scope() as s:
        audits = deposit_events.list_deposit_events(s, kind="audit_deposit")
        applies = deposit_events.list_deposit_events(s, kind="close_out_apply")
    assert len(audits) == 1
    assert applies == []
