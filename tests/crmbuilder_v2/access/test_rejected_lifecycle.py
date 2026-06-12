"""Rejected-lifecycle repository enforcement tests (PI-153 / WTK-088 §3).

Covers the §5.2 invariants the repository layer owns: I3 (atomic edge +
flip / edge-first admission), I4 (edge locked while rejected), I5
(soft-delete round-trip preserves ``rejected``), plus the vocab-driven
I1/I2 arcs through the repository transition checks. The seven affected
types share one enforcement module (``_rejection.py``); ``field`` and
``domain`` exercise both patch styles, ``manual_config`` covers the
``completed`` deviation.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import (
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.repositories import (
    decisions,
    domain,
    field,
    manual_config,
    references,
)
from crmbuilder_v2.access.repositories import entity as entity_repo

_EXEC_SUMMARY = (
    "Test decision recording the rationale for dropping a baseline candidate "
    "during Phase 3 triage. The candidate was discovered by audit, reviewed "
    "with the stakeholder, and deliberately not carried forward into the "
    "confirmed inventory; this record is the durable answer to where it went "
    "and why, per the PI-153 rejected-lifecycle design."
)


def _make_decision(s) -> str:
    return decisions.create(
        s,
        title="Drop the dormant field",
        decision_date="2026-06-11",
        status="Active",
        executive_summary=_EXEC_SUMMARY,
    )["identifier"]


def _make_domain(s, name="Mentoring") -> str:
    return domain.create_domain(
        s, name=name, purpose="p", description="d"
    )["domain_identifier"]


def _make_entity_with_field(s) -> tuple[str, str]:
    ent = entity_repo.create_entity(s, name="Engagement", description="d")
    fld = field.create_field(
        s,
        field_belongs_to_entity_identifier=ent["entity_identifier"],
        name="Stage",
        description="d",
        type="enum",
    )
    return ent["entity_identifier"], fld["field_identifier"]


# ---------------------------------------------------------------------------
# I3 — transition requires the decision edge
# ---------------------------------------------------------------------------


def test_reject_without_key_or_edge_is_refused(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        domain.patch_domain(s, dom, status="rejected")
    assert exc.value.errors[0].code == "rejected_requires_decision_edge"


def test_atomic_key_path_flips_and_creates_edge(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
    with session_scope() as s:
        result = domain.patch_domain(
            s, dom, status="rejected", rejected_by_decision=dec
        )
    assert result["domain_status"] == "rejected"
    with session_scope() as s:
        edges = references.list_references(
            s,
            source_type="domain",
            source_id=dom,
            relationship_kind="rejected_by_decision",
        )
    assert [e["target_id"] for e in edges] == [dec]


def test_edge_first_path_admits_transition_without_key(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
        references.create(
            s,
            source_type="domain",
            source_id=dom,
            target_type="decision",
            target_id=dec,
            relationship="rejected_by_decision",
        )
    with session_scope() as s:
        result = domain.patch_domain(s, dom, status="rejected")
    assert result["domain_status"] == "rejected"


def test_atomic_key_with_unknown_decision_is_refused(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        domain.patch_domain(
            s, dom, status="rejected", rejected_by_decision="DEC-999"
        )
    assert exc.value.errors[0].code == "decision_not_found"


def test_key_outside_rejection_is_refused(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        domain.patch_domain(
            s, dom, status="confirmed", rejected_by_decision=dec
        )
    assert exc.value.errors[0].code == "invalid_usage"


def test_second_decision_attaches_while_rejected(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec1 = _make_decision(s)
        dec2 = _make_decision(s)
    with session_scope() as s:
        domain.patch_domain(s, dom, status="rejected", rejected_by_decision=dec1)
    with session_scope() as s:
        domain.patch_domain(s, dom, rejected_by_decision=dec2)
    with session_scope() as s:
        edges = references.list_references(
            s,
            source_type="domain",
            source_id=dom,
            relationship_kind="rejected_by_decision",
        )
    assert sorted(e["target_id"] for e in edges) == sorted([dec1, dec2])


# ---------------------------------------------------------------------------
# I1 / I2 — terminal arcs through the repository transition check
# ---------------------------------------------------------------------------


def test_confirmed_to_rejected_is_refused(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
        domain.patch_domain(s, dom, status="confirmed")
    with session_scope() as s, pytest.raises(StatusTransitionError):
        domain.patch_domain(
            s, dom, status="rejected", rejected_by_decision=dec
        )


def test_no_transition_out_of_rejected(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
        domain.patch_domain(s, dom, status="rejected", rejected_by_decision=dec)
    for target in ("candidate", "confirmed", "deferred"):
        with session_scope() as s, pytest.raises(StatusTransitionError):
            domain.patch_domain(s, dom, status=target)


def test_deferred_to_rejected_is_admitted(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
        domain.patch_domain(s, dom, status="deferred")
    with session_scope() as s:
        result = domain.patch_domain(
            s, dom, status="rejected", rejected_by_decision=dec
        )
    assert result["domain_status"] == "rejected"


def test_manual_config_completed_never_rejects(v2_env):
    with session_scope() as s:
        dec = _make_decision(s)
        mc = manual_config.create_manual_config(
            s,
            name="Recreate filter",
            category="saved_view",
            description="d",
            instructions="i",
            status="completed",
            completed_by="operator",
        )["manual_config_identifier"]
    with session_scope() as s, pytest.raises(StatusTransitionError):
        manual_config.patch_manual_config(
            s, mc, status="rejected", rejected_by_decision=dec
        )


def test_field_rejects_via_atomic_key(v2_env):
    with session_scope() as s:
        _, fld = _make_entity_with_field(s)
        dec = _make_decision(s)
    with session_scope() as s:
        result = field.patch_field(
            s, fld, status="rejected", rejected_by_decision=dec
        )
    assert result["field_status"] == "rejected"


# ---------------------------------------------------------------------------
# I4 — the supporting edge is locked while rejected
# ---------------------------------------------------------------------------


def test_edge_delete_refused_while_rejected(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
        domain.patch_domain(s, dom, status="rejected", rejected_by_decision=dec)
    with session_scope() as s, pytest.raises(UnprocessableError) as exc:
        references.delete(
            s,
            source_type="domain",
            source_id=dom,
            target_type="decision",
            target_id=dec,
            relationship="rejected_by_decision",
        )
    assert exc.value.errors[0].code == "rejected_edge_locked"


def test_edge_delete_permitted_when_not_rejected(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
        references.create(
            s,
            source_type="domain",
            source_id=dom,
            target_type="decision",
            target_id=dec,
            relationship="rejected_by_decision",
        )
    # The record never transitioned; the staged edge is deletable.
    with session_scope() as s:
        references.delete(
            s,
            source_type="domain",
            source_id=dom,
            target_type="decision",
            target_id=dec,
            relationship="rejected_by_decision",
        )


# ---------------------------------------------------------------------------
# I5 — soft-delete round-trip preserves rejected
# ---------------------------------------------------------------------------


def test_soft_delete_restore_preserves_rejected(v2_env):
    with session_scope() as s:
        dom = _make_domain(s)
        dec = _make_decision(s)
        domain.patch_domain(s, dom, status="rejected", rejected_by_decision=dec)
        domain.delete_domain(s, dom)
    with session_scope() as s:
        restored = domain.restore_domain(s, dom)
    assert restored["domain_status"] == "rejected"
