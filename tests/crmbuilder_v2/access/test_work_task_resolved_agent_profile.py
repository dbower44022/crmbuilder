"""PI-302 (Phase 5b) — work_task_resolved_agent_profile stamp + area backstop.

Proves the stamp round-trips through the access repo (create / read-back / default
null / patch set + clear), the scoping path carries it, and the write-time area
backstop rejects a stamp whose profile is a different area, not active, or missing —
while accepting a same-area active profile.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import (
    agent_profiles,
    decomposition,
    planning_items,
    scoping,
    work_tasks,
)

_EXEC = "ADO PI-302 stamp test executive summary, comfortably over the floor. " * 5


def _profile(s, *, area="storage", tier="developer", status="active"):
    return agent_profiles.create(
        s, area=area, tier=tier, description="Specialist.", status=status,
        scope="system",
    )["identifier"]


# --- round-trip -------------------------------------------------------------


def test_stamp_round_trips_on_create(v2_env):
    with session_scope() as s:
        agp = _profile(s, area="storage")
        r = work_tasks.create_work_task(
            s, title="t", area="storage", resolved_agent_profile=agp
        )
        assert r["work_task_resolved_agent_profile"] == agp
        assert work_tasks.get_work_task(
            s, r["work_task_identifier"]
        )["work_task_resolved_agent_profile"] == agp


def test_stamp_defaults_to_null(v2_env):
    with session_scope() as s:
        r = work_tasks.create_work_task(s, title="t", area="storage")
        assert r["work_task_resolved_agent_profile"] is None


def test_patch_sets_and_clears_the_stamp(v2_env):
    with session_scope() as s:
        agp = _profile(s, area="api")
        work_tasks.create_work_task(
            s, title="t", area="api", identifier="WTK-300"
        )
    with session_scope() as s:
        r = work_tasks.patch_work_task(s, "WTK-300", resolved_agent_profile=agp)
        assert r["work_task_resolved_agent_profile"] == agp
    with session_scope() as s:
        r = work_tasks.patch_work_task(s, "WTK-300", resolved_agent_profile=None)
        assert r["work_task_resolved_agent_profile"] is None


# --- the area backstop ------------------------------------------------------


def test_same_area_active_profile_accepted(v2_env):
    with session_scope() as s:
        agp = _profile(s, area="ui", status="active")
        r = work_tasks.create_work_task(
            s, title="t", area="ui", resolved_agent_profile=agp
        )
        assert r["work_task_resolved_agent_profile"] == agp


def test_different_area_profile_rejected(v2_env):
    with session_scope() as s:
        agp = _profile(s, area="storage")
        with pytest.raises(UnprocessableError):
            work_tasks.create_work_task(
                s, title="t", area="api", resolved_agent_profile=agp
            )


def test_inactive_profile_rejected(v2_env):
    with session_scope() as s:
        agp = _profile(s, area="storage", status="retired")
        with pytest.raises(UnprocessableError):
            work_tasks.create_work_task(
                s, title="t", area="storage", resolved_agent_profile=agp
            )


def test_nonexistent_profile_rejected(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            work_tasks.create_work_task(
                s, title="t", area="storage", resolved_agent_profile="AGP-999"
            )


def test_patch_to_mismatched_area_rejected_but_null_clears(v2_env):
    with session_scope() as s:
        agp = _profile(s, area="storage")
        work_tasks.create_work_task(
            s, title="t", area="api", identifier="WTK-301"
        )
    with session_scope() as s, pytest.raises(UnprocessableError):
        work_tasks.patch_work_task(s, "WTK-301", resolved_agent_profile=agp)
    # NULL is always allowed even when the task carries no stamp.
    with session_scope() as s:
        r = work_tasks.patch_work_task(s, "WTK-301", resolved_agent_profile=None)
        assert r["work_task_resolved_agent_profile"] is None


# --- scoping path -----------------------------------------------------------


def _decomposed_pi(s, ident="PI-830"):
    planning_items.create(
        s, identifier=ident, title="Ship feature", item_type="pending_work",
        status="Draft", executive_summary=_EXEC,
    )
    return decomposition.decompose_planning_item(s, ident)


def test_scope_path_carries_and_validates_the_stamp(v2_env):
    with session_scope() as s:
        agp = _profile(s, area="access")
        ws = _decomposed_pi(s)
        arch = ws[0]["workstream_identifier"]
        result = scoping.scope_workstream(s, arch, [
            {"title": "Build access gate", "area": "access",
             "resolved_agent_profile": agp},
        ])
        assert result["work_tasks"][0]["work_task_resolved_agent_profile"] == agp


def test_scope_path_rejects_a_mismatched_stamp(v2_env):
    with session_scope() as s:
        agp = _profile(s, area="storage")
        ws = _decomposed_pi(s, ident="PI-831")
        arch = ws[0]["workstream_identifier"]
        with pytest.raises(UnprocessableError):
            scoping.scope_workstream(s, arch, [
                {"title": "Build access gate", "area": "access",
                 "resolved_agent_profile": agp},
            ])
