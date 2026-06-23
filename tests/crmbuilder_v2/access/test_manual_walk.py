"""Manual-walk hardening tests — REQ-336 / DEC-661 (PI-296).

A manually-driven release (in-scope planning items delivered by hand, i.e.
``interactive``) must reach ``ready`` and beyond from its recorded review
evidence, without ADO decomposition. The fix exempts interactive in-scope
planning items from the planned-completely gate's decomposition requirement
(``releases._check_planned_completely``); an ADO item still requires its phase
plan. These exercise the gate predicate directly and walk a manual release
freeze → reconciliation → architecture_planning → ready end to end.

Scope (project/PI membership edges) is always built while the release is still
open, then the release is frozen — adding scope to a frozen release is rejected
by the freeze guard (the real scope-then-freeze flow).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    decomposition,
    planning_items,
    projects,
    references,
    release_signoffs,
    releases,
)
from crmbuilder_v2.access.repositories.releases import _check_planned_completely

_SUMMARY = (
    "A planning item used by the manual-walk hardening tests; it carries enough "
    "audience-facing text to satisfy the 200-800 character executive-summary "
    "requirement the planning_items repository enforces on create, so the tests can "
    "build a valid in-scope item and exercise the planned-completely gate and the "
    "manual release lane walk without tripping unrelated validation."
)


def _open_release(s) -> str:
    return releases.create_release(s, title="Manual release", description="d")[
        "release_identifier"
    ]


def _freeze(s, rel: str, *, status: str = "reconciliation") -> None:
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    row.release_frozen_at = datetime.now(UTC)
    s.flush()


def _add_pi(s, rel: str, *, execution_mode: str) -> str:
    """Attach a new PI to ``rel`` via a release-scoped project (release must be
    open)."""
    pi = planning_items.create(
        s,
        title="Manual-walk PI",
        item_type="pending_work",
        executive_summary=_SUMMARY,
        status="Draft",
        execution_mode=execution_mode,
    )["identifier"]
    prj = projects.create_project(
        s, name=f"Manual proj for {pi}", purpose="p", description="d"
    )["project_identifier"]
    references.create(
        s,
        source_type="project",
        source_id=prj,
        target_type="release",
        target_id=rel,
        relationship="project_belongs_to_release",
    )
    references.create(
        s,
        source_type="planning_item",
        source_id=pi,
        target_type="project",
        target_id=prj,
        relationship="planning_item_belongs_to_project",
    )
    return pi


# --- the gate predicate ----------------------------------------------------


def test_planned_completely_passes_for_interactive_only_release(v2_env):
    """An all-interactive (manually-delivered) release is planned-completely
    without any decomposition."""
    with session_scope() as s:
        rel = _open_release(s)
        _add_pi(s, rel, execution_mode="interactive")
        _freeze(s, rel)
        _check_planned_completely(s, rel)  # no raise


def test_planned_completely_rejects_undecomposed_ado_pi(v2_env):
    """An ADO in-scope item still requires its phase plan."""
    with session_scope() as s:
        rel = _open_release(s)
        _add_pi(s, rel, execution_mode="ado")
        _freeze(s, rel)
        with pytest.raises(ConflictError, match="not decomposed"):
            _check_planned_completely(s, rel)


def test_planned_completely_passes_for_decomposed_ado_pi(v2_env):
    with session_scope() as s:
        rel = _open_release(s)
        pi = _add_pi(s, rel, execution_mode="ado")
        decomposition.decompose_planning_item(s, pi)
        _freeze(s, rel)
        _check_planned_completely(s, rel)  # no raise


def test_planned_completely_mixed_interactive_and_decomposed_ado(v2_env):
    """A mixed release passes once its ADO item is decomposed; the interactive
    item is treated as already planned."""
    with session_scope() as s:
        rel = _open_release(s)
        _add_pi(s, rel, execution_mode="interactive")
        ado_pi = _add_pi(s, rel, execution_mode="ado")
        decomposition.decompose_planning_item(s, ado_pi)
        _freeze(s, rel)
        _check_planned_completely(s, rel)  # no raise


# --- full lane walk for a manual release -----------------------------------


def test_manual_release_walks_freeze_to_ready(v2_env):
    """A frozen, all-interactive release walks reconciliation →
    architecture_planning → ready from recorded review sign-offs alone — the
    planned-completely gate no longer blocks it (REQ-336)."""
    with session_scope() as s:
        rel = _open_release(s)
        _add_pi(s, rel, execution_mode="interactive")
        _freeze(s, rel)

        # reconciliation -> architecture_planning needs a fresh reconciliation sign-off
        release_signoffs.create_signoff(
            s, rel, stage="reconciliation", reviewer="doug", attestation="reconciled"
        )
        out = releases.transition(s, rel, "architecture_planning", actor="doug")
        assert out["release_status"] == "architecture_planning"

        # architecture_planning -> ready needs planned-completely (now passes for
        # the interactive item) + a fresh architecture_planning sign-off
        release_signoffs.create_signoff(
            s,
            rel,
            stage="architecture_planning",
            reviewer="doug",
            attestation="planned",
        )
        out = releases.transition(s, rel, "ready", actor="doug")
        assert out["release_status"] == "ready"
