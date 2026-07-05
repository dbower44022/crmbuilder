"""PI-122 runtime — dispatcher eligibility + profile-selection logic."""

from __future__ import annotations

import io
import json as _json
import urllib.error
import urllib.request

from crmbuilder_v2.scheduler import dispatcher as _d
from crmbuilder_v2.scheduler.dispatcher import (
    is_work_task_eligible,
    resolve_profile_for_task,
    select_profile_id,
    select_stamped_profile_id,
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


# --- PI-302: resolved-agent-profile stamp routing -------------------------

_STAMP_PROFILES = [
    {"identifier": "AGP-010", "scope": "system", "area": "storage",
     "tier": "developer", "status": "active"},
    {"identifier": "AGP-011", "scope": "system", "area": "storage",
     "tier": "developer", "status": "active"},
    {"identifier": "AGP-012", "scope": "system", "area": "api",
     "tier": "developer", "status": "active"},
    {"identifier": "AGP-013", "scope": "system", "area": "storage",
     "tier": "developer", "status": "retired"},
]


def test_select_stamped_profile_id_valid_stamp_holds():
    assert select_stamped_profile_id(
        _STAMP_PROFILES, "AGP-011", "storage", "developer") == "AGP-011"


def test_select_stamped_profile_id_rejects_wrong_area_tier_status_unknown():
    # Wrong area (AGP-012 is api), wrong tier, inactive, and an unknown id all None.
    assert select_stamped_profile_id(
        _STAMP_PROFILES, "AGP-012", "storage", "developer") is None
    assert select_stamped_profile_id(
        _STAMP_PROFILES, "AGP-010", "storage", "tester") is None
    assert select_stamped_profile_id(
        _STAMP_PROFILES, "AGP-013", "storage", "developer") is None
    assert select_stamped_profile_id(
        _STAMP_PROFILES, "AGP-999", "storage", "developer") is None


def test_resolve_prefers_a_valid_stamp():
    profile_id, warning = resolve_profile_for_task(
        _STAMP_PROFILES, area="storage", tier="developer", stamp="AGP-011")
    assert profile_id == "AGP-011"
    assert warning is None


def test_resolve_falls_back_to_generalist_when_unstamped():
    # No stamp → existing (area, tier) selection (first matching, AGP-010).
    profile_id, warning = resolve_profile_for_task(
        _STAMP_PROFILES, area="storage", tier="developer", stamp=None)
    assert profile_id == "AGP-010"
    assert warning is None


def test_resolve_falls_back_with_warning_when_stamp_fails_revalidation():
    # Inactive stamp → generalist fallback (AGP-010) AND a warning message.
    profile_id, warning = resolve_profile_for_task(
        _STAMP_PROFILES, area="storage", tier="developer", stamp="AGP-013")
    assert profile_id == "AGP-010"
    assert warning is not None
    assert "AGP-013" in warning


# ---------------------------------------------------------------------------
# REQ-465 / PI-395 — transient-retry policy on the store HTTP layer
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._body = _json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _no_sleep(monkeypatch):
    monkeypatch.setattr(_d.time, "sleep", lambda s: None)


def test_get_retries_transient_urlerror_then_succeeds(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError(TimeoutError("timed out"))
        return _FakeResponse({"data": {"ok": True}, "errors": None})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert _d._get("http://x", "/work-tasks/WTK-1", "ENG-004") == {"ok": True}
    assert calls["n"] == 3


def test_get_raises_after_persistent_transients(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    try:
        _d._get("http://x", "/work-tasks/WTK-1", "ENG-004")
        raise AssertionError("expected URLError")
    except urllib.error.URLError:
        pass
    assert calls["n"] == len(_d._RETRY_BACKOFF_SECONDS)


def test_get_never_retries_a_4xx_verdict(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.HTTPError(
            "http://x", 404, "not found", hdrs=None, fp=io.BytesIO(b"")
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    try:
        _d._get("http://x", "/work-tasks/WTK-404", "ENG-004")
        raise AssertionError("expected HTTPError")
    except urllib.error.HTTPError:
        pass
    assert calls["n"] == 1  # a real API verdict, never retried


def test_get_retries_5xx(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError(
                "http://x", 503, "unavailable", hdrs=None, fp=io.BytesIO(b"")
            )
        return _FakeResponse({"data": {"ok": True}, "errors": None})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert _d._get("http://x", "/topics/TOP-1", "ENG-004") == {"ok": True}
    assert calls["n"] == 2


def test_post_does_not_retry_ambiguous_delivery(monkeypatch):
    """A write whose request may have reached the server must not repeat:
    only connection-phase failures (refused/reset) retry for non-idempotent
    requests; a generic timeout after send surfaces immediately."""
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    try:
        _d._post("http://x", "/findings", "ENG-004", {"finding_summary": "s"})
        raise AssertionError("expected URLError")
    except urllib.error.URLError:
        pass
    assert calls["n"] == 1


def test_post_retries_connection_refused(monkeypatch):
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(req, timeout=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.URLError(ConnectionRefusedError("refused"))
        return _FakeResponse({"data": {"ok": True}, "errors": None})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    assert _d._post("http://x", "/findings", "ENG-004", {"a": 1}) == {"ok": True}
    assert calls["n"] == 2
