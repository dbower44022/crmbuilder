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


def test_select_refuses_when_no_matching_area_profile():
    # REQ-273: a task with no matching-area profile is REFUSED (None), never run
    # under a sibling area's profile (the WTK-176 wrong-area-contract failure).
    assert select_profile_id(_PROFILES, "access", "developer") is None
    assert select_profile_id(_PROFILES, "mcp", "architect") is None
    # a tier with no system profile at all → None.
    assert select_profile_id(_PROFILES, "api", "tester") is None


def test_select_ignores_engagement_scoped_profiles():
    # AGP-009 is engagement-scoped, not a system profile → never selected here.
    assert select_profile_id(_PROFILES, "api", "developer") == "AGP-003"


# --- REQ-281: technology-variant routing within one area ------------------

_TECH_PROFILES = [
    {"identifier": "AGP-ui-qt", "scope": "system", "area": "ui",
     "tier": "developer", "technology": "qt-desktop"},
    {"identifier": "AGP-ui-web", "scope": "system", "area": "ui",
     "tier": "developer", "technology": "web"},
    {"identifier": "AGP-storage", "scope": "system", "area": "storage",
     "tier": "developer", "technology": None},
]


def test_select_routes_by_technology_within_an_area():
    assert select_profile_id(_TECH_PROFILES, "ui", "developer",
                             technology="qt-desktop") == "AGP-ui-qt"
    assert select_profile_id(_TECH_PROFILES, "ui", "developer",
                             technology="web") == "AGP-ui-web"


def test_select_refuses_a_technology_with_no_matching_or_agnostic_profile():
    # Only qt-desktop + web exist for ui; a flutter task is not forced through either.
    assert select_profile_id(_TECH_PROFILES, "ui", "developer",
                             technology="flutter") is None


def test_select_technology_agnostic_profile_serves_any_technology():
    # The storage profile has no technology → it serves a storage task regardless.
    assert select_profile_id(_TECH_PROFILES, "storage", "developer",
                             technology="anything") == "AGP-storage"
