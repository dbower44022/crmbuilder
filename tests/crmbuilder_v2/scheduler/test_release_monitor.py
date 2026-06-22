"""Release Scheduler monitor tests — PI-259 (PRJ-041 / REQ-298), Phase 2.

The scan + single-occupancy arbitration over multiple frozen releases (target §3):
``arbitrate_lane`` (pure) plus ``monitor_once`` driving front-half releases without the
dev lane and admitting exactly one release into the lane (by lane order, else
``needs_human``). The driving itself reuses the tested ReleaseScheduler; here a stub
``drive`` records which release was driven with which dev-lane flag.
"""

from __future__ import annotations

from types import SimpleNamespace

from crmbuilder_v2.access._helpers import get_by_identifier
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import releases
from crmbuilder_v2.scheduler import release_monitor as rm


def _release(s, title, status, lane_order=None):
    rel = releases.create_release(s, title=title, description="d")[
        "release_identifier"
    ]
    row = get_by_identifier(s, Release, Release.release_identifier, rel)
    row.release_status = status
    row.release_lane_order = lane_order
    s.flush()
    return rel


def _recording_drive(calls, *, raise_on=None):
    def drive(rid, dev_lane):
        calls.append((rid, dev_lane))
        if raise_on is not None and rid == raise_on:
            raise RuntimeError("simulated gate conflict")
        return SimpleNamespace(final_status="deployment", stopped_reason="ship owed")
    return drive


# --- pure arbitration -------------------------------------------------------


def test_arbitrate_empty():
    assert rm.arbitrate_lane([]) == (None, None)


def test_arbitrate_single_uncontested_even_without_order():
    assert rm.arbitrate_lane([{"identifier": "REL-1", "lane_order": None}]) == (
        "REL-1", None)


def test_arbitrate_lowest_order_wins():
    ready = [{"identifier": "REL-2", "lane_order": 5},
             {"identifier": "REL-1", "lane_order": 2}]
    assert rm.arbitrate_lane(ready) == ("REL-1", None)


def test_arbitrate_tie_needs_human():
    ready = [{"identifier": "REL-1", "lane_order": 3},
             {"identifier": "REL-2", "lane_order": 3}]
    driver, reason = rm.arbitrate_lane(ready)
    assert driver is None and "tie" in reason


def test_arbitrate_unordered_competitor_needs_human():
    ready = [{"identifier": "REL-1", "lane_order": 1},
             {"identifier": "REL-2", "lane_order": None}]
    driver, reason = rm.arbitrate_lane(ready)
    assert driver is None and "no lane_order" in reason


# --- monitor pass -----------------------------------------------------------


def test_monitor_admits_lowest_lane_order_others_wait(v2_env):
    with session_scope() as s:
        a = _release(s, "A", "ready", lane_order=1)
        b = _release(s, "B", "ready", lane_order=2)
    calls: list = []
    report = rm.monitor_once(_recording_drive(calls), log=lambda m: None)
    assert report.lane_driver == a
    assert report.waiting == [b]
    # exactly one release driven, with the dev lane, and it is the lowest-ordered.
    assert calls == [(a, True)]


def test_monitor_existing_lane_holder_keeps_lane(v2_env):
    with session_scope() as s:
        held = _release(s, "Held", "development")
        _release(s, "Ready", "ready", lane_order=1)
    calls: list = []
    report = rm.monitor_once(_recording_drive(calls), log=lambda m: None)
    assert report.lane_driver == held
    # the ready release waits; only the lane holder is driven (dev lane).
    assert calls == [(held, True)]
    assert report.needs_human is None


def test_monitor_needs_human_on_ambiguous_order(v2_env):
    with session_scope() as s:
        _release(s, "A", "ready")  # no order
        _release(s, "B", "ready")  # no order
    calls: list = []
    report = rm.monitor_once(_recording_drive(calls), log=lambda m: None)
    assert report.lane_driver is None
    assert report.needs_human is not None
    # no release enters the lane when the choice is ambiguous.
    assert all(dev_lane is False for _, dev_lane in calls)
    assert calls == []  # no front-half releases either


def test_monitor_drives_front_half_without_dev_lane(v2_env):
    with session_scope() as s:
        recon = _release(s, "Recon", "reconciliation")
        arch = _release(s, "Arch", "architecture_planning")
        ready = _release(s, "Ready", "ready", lane_order=1)
    calls: list = []
    report = rm.monitor_once(_recording_drive(calls), log=lambda m: None)
    assert report.lane_driver == ready
    driven = dict(calls)
    assert driven[recon] is False
    assert driven[arch] is False
    assert driven[ready] is True


def test_monitor_records_driver_error_without_crashing(v2_env):
    with session_scope() as s:
        a = _release(s, "A", "ready", lane_order=1)
    calls: list = []
    report = rm.monitor_once(
        _recording_drive(calls, raise_on=a), log=lambda m: None)
    assert report.errors and report.errors[0]["release"] == a
    assert report.driven == []


def test_monitor_ignores_unfrozen_and_terminal(v2_env):
    with session_scope() as s:
        _release(s, "Pre", "development_planning")  # not frozen
        _release(s, "Done", "shipped")              # terminal
        ready = _release(s, "Ready", "ready", lane_order=1)
    calls: list = []
    report = rm.monitor_once(_recording_drive(calls), log=lambda m: None)
    assert report.lane_driver == ready
    assert calls == [(ready, True)]
