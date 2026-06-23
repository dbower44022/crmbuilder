"""Release-scoped development gate tests — REQ-323 / REQ-324 (PI-288).

The gate rejects developing a planning item that is not in a frozen release's
scope, and is flag-controlled (``release_scoped_gate_enabled``, default off).
These exercise the predicate, the ``assert_developable`` gate, and its two wired
surfaces: ``planning_items.update`` (In Progress / Resolved) and
``decomposition.decompose_planning_item``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access import release_gate
from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import (
    decomposition,
    planning_items,
    projects,
    references,
    releases,
)
from crmbuilder_v2.config import reset_settings_cache

_SUMMARY = (
    "A planning item used by the release-scoped development-gate tests; it carries "
    "enough audience-facing text to satisfy the 200-800 character executive-summary "
    "requirement the planning_items repository enforces on create, so the gate tests "
    "can build a valid planning item and exercise the frozen-release scope check end "
    "to end without tripping unrelated validation."
)

# Statuses that are NOT yet frozen (pre-freeze) — used to decide whether the
# scaffolding stamps release_frozen_at.
_PRE_FREEZE = frozenset({"preliminary_planning", "development_planning"})


def _enable_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRMBUILDER_V2_RELEASE_SCOPED_GATE_ENABLED", "true")
    reset_settings_cache()


def _set_release_status(s, rel: str, status: str) -> None:
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    if status not in _PRE_FREEZE and status not in {"cancelled", "superseded"}:
        row.release_frozen_at = datetime.now(UTC)
    s.flush()


def _make_pi(s, *, execution_mode: str = "ado") -> str:
    return planning_items.create(
        s,
        title="Gate test PI",
        item_type="pending_work",
        executive_summary=_SUMMARY,
        status="Draft",
        execution_mode=execution_mode,
    )["identifier"]


def _scope_pi_into_release(s, pi: str, *, release_status: str) -> str:
    """Attach ``pi`` to a release-scoped project in a release set to
    ``release_status``; returns the release identifier."""
    rel = releases.create_release(s, title="Gate release", description="d")[
        "release_identifier"
    ]
    prj = projects.create_project(
        s, name="Gate project", purpose="p", description="d"
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
    _set_release_status(s, rel, release_status)
    return rel


# --- the predicate + assert_developable ------------------------------------


def test_gate_off_is_noop_even_when_unreleased(v2_env):
    """Default (flag off): the gate never fires, even for an unreleased PI."""
    with session_scope() as s:
        pi = _make_pi(s)
        assert release_gate.in_frozen_release_scope(s, pi) is False
        # No raise — flag is off by default.
        release_gate.assert_developable(s, pi, action="decomposed")


def test_gate_on_rejects_unreleased_pi(v2_env, monkeypatch):
    with session_scope() as s:
        pi = _make_pi(s)
        _enable_gate(monkeypatch)
        with pytest.raises(ConflictError, match="not in a frozen release"):
            release_gate.assert_developable(s, pi, action="decomposed")


def test_gate_on_rejects_pre_freeze_release(v2_env, monkeypatch):
    with session_scope() as s:
        pi = _make_pi(s)
        _scope_pi_into_release(s, pi, release_status="development_planning")
        _enable_gate(monkeypatch)
        assert release_gate.in_frozen_release_scope(s, pi) is False
        with pytest.raises(ConflictError):
            release_gate.assert_developable(s, pi, action="decomposed")


@pytest.mark.parametrize("status", ["reconciliation", "architecture_planning", "ready", "development"])
def test_gate_on_allows_frozen_release(v2_env, monkeypatch, status):
    with session_scope() as s:
        pi = _make_pi(s)
        _scope_pi_into_release(s, pi, release_status=status)
        _enable_gate(monkeypatch)
        assert release_gate.in_frozen_release_scope(s, pi) is True
        # No raise — the release is frozen.
        release_gate.assert_developable(s, pi, action="decomposed")


@pytest.mark.parametrize("status", ["shipped", "cancelled", "superseded"])
def test_gate_on_rejects_terminal_release(v2_env, monkeypatch, status):
    """A shipped/cancelled/superseded release is not a developable scope."""
    with session_scope() as s:
        pi = _make_pi(s)
        _scope_pi_into_release(s, pi, release_status=status)
        _enable_gate(monkeypatch)
        assert release_gate.in_frozen_release_scope(s, pi) is False
        with pytest.raises(ConflictError):
            release_gate.assert_developable(s, pi, action="decomposed")


# --- wired surface: planning_items.update ----------------------------------


def test_update_to_in_progress_gated_when_unreleased(v2_env, monkeypatch):
    with session_scope() as s:
        pi = _make_pi(s)
        _enable_gate(monkeypatch)
        with pytest.raises(ConflictError, match="moved to In Progress"):
            planning_items.update(s, pi, status="In Progress")


def test_update_to_in_progress_allowed_in_frozen_release(v2_env, monkeypatch):
    with session_scope() as s:
        pi = _make_pi(s)
        _scope_pi_into_release(s, pi, release_status="reconciliation")
        _enable_gate(monkeypatch)
        out = planning_items.update(s, pi, status="In Progress")
        assert out["status"] == "In Progress"


def test_update_to_resolved_gated_when_unreleased(v2_env, monkeypatch):
    with session_scope() as s:
        pi = _make_pi(s)
        _enable_gate(monkeypatch)
        with pytest.raises(ConflictError, match="resolved"):
            planning_items.update(s, pi, status="Resolved")


def test_update_non_dev_status_not_gated(v2_env, monkeypatch):
    """Transitions to non-development states (e.g. Ready) are never gated."""
    with session_scope() as s:
        pi = _make_pi(s)
        _enable_gate(monkeypatch)
        out = planning_items.update(s, pi, status="Ready")
        assert out["status"] == "Ready"


def test_update_off_flag_no_regression(v2_env):
    """With the flag off (default), In Progress works as before."""
    with session_scope() as s:
        pi = _make_pi(s)
        out = planning_items.update(s, pi, status="In Progress")
        assert out["status"] == "In Progress"


# --- wired surface: decomposition ------------------------------------------


def test_decompose_gated_when_unreleased(v2_env, monkeypatch):
    with session_scope() as s:
        pi = _make_pi(s, execution_mode="ado")
        _enable_gate(monkeypatch)
        with pytest.raises(ConflictError, match="not in a frozen release"):
            decomposition.decompose_planning_item(s, pi)


def test_decompose_allowed_in_frozen_release(v2_env, monkeypatch):
    with session_scope() as s:
        pi = _make_pi(s, execution_mode="ado")
        _scope_pi_into_release(s, pi, release_status="reconciliation")
        _enable_gate(monkeypatch)
        created = decomposition.decompose_planning_item(s, pi)
        assert created  # phase workstreams created, gate passed
