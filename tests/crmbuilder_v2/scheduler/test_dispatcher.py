"""PI-122 runtime — dispatcher eligibility + profile-selection logic."""

from __future__ import annotations

from crmbuilder_v2.scheduler.dispatcher import (
    is_work_task_eligible,
    select_profile_id,
)


def _wt(status="Ready", claimed_by=None):
    return {"work_task_status": status, "work_task_claimed_by": claimed_by}


def test_eligible_ready_unclaimed_no_blockers():
    assert is_work_task_eligible(_wt(), []) is True


def test_not_eligible_when_not_ready():
    assert is_work_task_eligible(_wt(status="Planned"), []) is False
    assert is_work_task_eligible(_wt(status="In Progress"), []) is False


def test_not_eligible_when_claimed():
    assert is_work_task_eligible(_wt(claimed_by="AGP-002"), []) is False


def test_not_eligible_when_a_blocker_incomplete():
    assert is_work_task_eligible(_wt(), ["Complete", "In Progress"]) is False


def test_eligible_when_all_blockers_complete():
    assert is_work_task_eligible(_wt(), ["Complete", "Complete"]) is True


_PROFILES = [
    {"identifier": "AGP-001", "scope": "system", "area": "storage", "tier": "architect"},
    {"identifier": "AGP-002", "scope": "system", "area": "storage", "tier": "developer"},
    {"identifier": "AGP-003", "scope": "system", "area": "api", "tier": "developer"},
    {"identifier": "AGP-009", "scope": "ENG-001", "area": "api", "tier": "developer"},
]


def test_select_exact_area_tier():
    assert select_profile_id(_PROFILES, "api", "developer") == "AGP-003"


def test_select_falls_back_to_any_system_profile_of_tier():
    # No (access, developer) profile → fall back to a system developer profile.
    assert select_profile_id(_PROFILES, "access", "developer") == "AGP-002"


def test_select_ignores_engagement_scoped_and_wrong_tier():
    # architect tier request with no architect for 'mcp' → the storage architect.
    assert select_profile_id(_PROFILES, "mcp", "architect") == "AGP-001"
    # a tier with no system profile at all → None.
    assert select_profile_id(_PROFILES, "api", "tester") is None
