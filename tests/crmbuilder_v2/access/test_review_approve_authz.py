"""WTK-177 / REQ-251 — reviewer authorization for requirement approval.

The reviewer capability is the ``approve`` permission: granted to ``owner`` and
``editor``, withheld from ``viewer`` and the agent tiers, and enforced at the
top of :func:`crmbuilder_v2.access.review.approve_requirements` (a no-op when
auth is off, ``PermissionDenied`` → 403 otherwise).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import rbac, review
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.engagement_scope import (
    reset_active_engagement,
    set_active_engagement,
)
from crmbuilder_v2.access.principal_scope import (
    DEFAULT_OWNER,
    Principal,
    reset_active_principal,
    set_active_principal,
)
from crmbuilder_v2.access.repositories import requirement as _requirement


def _auth(monkeypatch, enabled: bool) -> None:
    class _S:
        principal_auth_enabled = enabled

    monkeypatch.setattr(rbac, "get_settings", lambda: _S())


def _principal(role: str) -> Principal:
    return Principal(
        principal_id="PRN-100",
        kind="human",
        roles=frozenset({role}),
        roles_by_engagement={"ENG-001": frozenset({role})},
        allowed_engagements=frozenset({"ENG-001"}),
    )


def test_approve_permission_granted_to_reviewer_roles_only():
    # The reviewer persona (owner / editor) holds ``approve``; viewer and the
    # agent tiers do not — confirming a requirement is a human review.
    assert rbac.has_permission(DEFAULT_OWNER, "ENG-001", "approve")
    assert rbac.has_permission(_principal("editor"), "ENG-001", "approve")
    assert not rbac.has_permission(_principal("viewer"), "ENG-001", "approve")
    assert not rbac.has_permission(
        _principal("area_specialist"), "ENG-001", "approve"
    )


def test_approve_requirements_denied_without_approve_permission(v2_env, monkeypatch):
    _auth(monkeypatch, True)
    eng = set_active_engagement("ENG-001")
    prn = set_active_principal(_principal("viewer"))
    try:
        with session_scope() as s, pytest.raises(rbac.PermissionDenied) as exc:
            review.approve_requirements(
                s,
                requirement_identifiers=["REQ-999"],
                reviewer="Doug",
                decision_date="2026-06-18",
            )
        assert exc.value.permission == "approve"
    finally:
        reset_active_principal(prn)
        reset_active_engagement(eng)


def _candidate(s, name: str = "A candidate awaiting review") -> str:
    return _requirement.create_requirement(
        s,
        name=name,
        description="A requirement to exercise the approval gate.",
        acceptance_summary="Approving it records a governed decision.",
        origin="human_defined",
    )["requirement_identifier"]


def test_approve_requirements_allows_authorized_reviewer_past_gate(
    v2_env, monkeypatch
):
    # An editor clears the authorization gate and reaches the per-requirement
    # approval logic; a candidate with no provenance/topic then fails the
    # confirmation gates (a non-None gate reason, no decision recorded) — proving
    # the authorization gate did not block the authorized reviewer.
    _auth(monkeypatch, True)
    eng = set_active_engagement("ENG-001")
    prn = set_active_principal(_principal("editor"))
    try:
        with session_scope() as s:
            rid = _candidate(s)
            result = review.approve_requirements(
                s,
                requirement_identifiers=[rid],
                reviewer="Doug",
                decision_date="2026-06-18",
            )
    finally:
        reset_active_principal(prn)
        reset_active_engagement(eng)
    assert result[0]["identifier"] == rid
    assert result[0]["outcome"] == "failed"
    assert result[0]["decision_identifier"] is None
    assert result[0]["reason"]  # the gate's own reason, not an authz denial


def test_approve_requirements_gate_is_noop_when_auth_off(v2_env, monkeypatch):
    # Auth off (the default-owner localhost flow): no active principal, the gate
    # passes and the per-requirement approval logic runs.
    _auth(monkeypatch, False)
    with session_scope() as s:
        rid = _candidate(s)
        result = review.approve_requirements(
            s,
            requirement_identifiers=[rid],
            reviewer="Doug",
            decision_date="2026-06-18",
        )
    assert result[0]["identifier"] == rid
    assert result[0]["outcome"] == "failed"


# ---------------------------------------------------------------------------
# WTK-180 / REQ-251 — reviewer authorization enforcement coverage.
#
# WTK-177 wired the gate and proved the happy/denied paths for one role each;
# these close the enforcement gaps: *every* agent tier (not only one) lacks the
# capability, an anonymous request (auth on, no principal) is denied, denial
# actually prevents confirmation rather than merely raising, a denied principal
# blocks the whole batch (no partial approval), and the capability is
# engagement-scoped — reviewer rights on one engagement do not carry to another.
# ---------------------------------------------------------------------------


def test_approve_permission_denied_to_every_agent_tier():
    # Confirming a requirement is a human review, not an agent action: none of
    # the four ADO agent tiers holds ``approve`` — only the reviewer persona.
    for tier in ("orchestrator", "pi_lead", "phase_specialist", "area_specialist"):
        assert not rbac.has_permission(_principal(tier), "ENG-001", "approve"), tier


def test_approve_requirements_denied_for_anonymous_principal(v2_env, monkeypatch):
    # Auth on with no active principal at all: the gate denies the anonymous
    # request rather than falling open.
    _auth(monkeypatch, True)
    eng = set_active_engagement("ENG-001")
    prn = set_active_principal(None)
    try:
        with session_scope() as s, pytest.raises(rbac.PermissionDenied) as exc:
            review.approve_requirements(
                s,
                requirement_identifiers=["REQ-999"],
                reviewer="Doug",
                decision_date="2026-06-18",
            )
        assert exc.value.permission == "approve"
    finally:
        reset_active_principal(prn)
        reset_active_engagement(eng)


def test_unauthorized_approval_leaves_requirement_unconfirmed(v2_env, monkeypatch):
    # The gate is enforcement, not advice: a denied attempt confirms nothing —
    # the candidate stays a candidate (no governed approving decision is run).
    _auth(monkeypatch, True)
    eng = set_active_engagement("ENG-001")
    prn = set_active_principal(_principal("viewer"))
    try:
        with session_scope() as s:
            rid = _candidate(s)
            with pytest.raises(rbac.PermissionDenied):
                review.approve_requirements(
                    s,
                    requirement_identifiers=[rid],
                    reviewer="Doug",
                    decision_date="2026-06-18",
                )
            assert (
                _requirement.get_requirement(s, rid)["requirement_status"]
                == "candidate"
            )
    finally:
        reset_active_principal(prn)
        reset_active_engagement(eng)


def test_unauthorized_approval_blocks_entire_batch(v2_env, monkeypatch):
    # The gate sits above the per-requirement loop, so an unauthorized principal
    # approves none of a multi-requirement batch — there is no partial approval.
    _auth(monkeypatch, True)
    eng = set_active_engagement("ENG-001")
    prn = set_active_principal(_principal("viewer"))
    try:
        with session_scope() as s:
            rids = [
                _candidate(s, "First batch candidate"),
                _candidate(s, "Second batch candidate"),
            ]
            with pytest.raises(rbac.PermissionDenied):
                review.approve_requirements(
                    s,
                    requirement_identifiers=rids,
                    reviewer="Doug",
                    decision_date="2026-06-18",
                )
            for rid in rids:
                assert (
                    _requirement.get_requirement(s, rid)["requirement_status"]
                    == "candidate"
                )
    finally:
        reset_active_principal(prn)
        reset_active_engagement(eng)


def test_approve_capability_is_engagement_scoped(v2_env, monkeypatch):
    # Reviewer rights are per-engagement: an editor on ENG-002 holds ``approve``
    # there but is denied on the active ENG-001.
    _auth(monkeypatch, True)
    other_eng_editor = Principal(
        principal_id="PRN-200",
        kind="human",
        roles=frozenset({"editor"}),
        roles_by_engagement={"ENG-002": frozenset({"editor"})},
        allowed_engagements=frozenset({"ENG-002"}),
    )
    eng = set_active_engagement("ENG-001")
    prn = set_active_principal(other_eng_editor)
    try:
        assert rbac.has_permission(other_eng_editor, "ENG-002", "approve")
        assert not rbac.has_permission(other_eng_editor, "ENG-001", "approve")
        with session_scope() as s, pytest.raises(rbac.PermissionDenied) as exc:
            review.approve_requirements(
                s,
                requirement_identifiers=["REQ-999"],
                reviewer="Doug",
                decision_date="2026-06-18",
            )
        assert exc.value.permission == "approve"
    finally:
        reset_active_principal(prn)
        reset_active_engagement(eng)
