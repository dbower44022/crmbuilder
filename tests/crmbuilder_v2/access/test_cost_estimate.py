"""Pre-run cost estimate tests — REQ-317 (PI-282).

The estimator projects a run's token + dollar cost from the historical per-run
spend in ``cost_events``: the mean over completed runs (default sample =
release), plus the observed high-water cost and the run count that informed it.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import cost_estimate
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import cost_events


def _event(s, release, ti, to):
    cost_events.record(
        s, source="sdk", model="claude-sonnet-4-6",
        input_tokens=ti, output_tokens=to, release_identifier=release,
    )


def test_no_history_is_zero_with_no_basis(v2_env):
    with session_scope() as s:
        est = cost_estimate.estimate_run(s)
    assert est["basis_runs"] == 0
    assert est["projected_cost_usd"] == 0.0
    assert est["projected_tokens"] == 0
    assert "no historical runs" in est["method"]


def test_projects_mean_and_high_water_over_release_runs(v2_env):
    with session_scope() as s:
        _event(s, "REL-1", 1000, 500)   # $0.0105, 1500 tokens
        _event(s, "REL-2", 2000, 1000)  # $0.0210, 3000 tokens
        est = cost_estimate.estimate_run(s)
    assert est["basis_runs"] == 2
    # mean of the two runs, rounded to 4dp (0.01575 -> 0.0158)
    assert est["projected_cost_usd"] == round((0.0105 + 0.0210) / 2, 4)
    assert est["projected_tokens"] == 2250
    # worst observed
    assert est["high_water_cost_usd"] == pytest.approx(0.0210, abs=1e-6)


def test_multiple_events_in_one_release_are_one_run(v2_env):
    """Two spend events tagged to the same release are one run, summed."""
    with session_scope() as s:
        _event(s, "REL-1", 1000, 500)
        _event(s, "REL-1", 1000, 500)  # same release -> summed into one run
        est = cost_estimate.estimate_run(s)
    assert est["basis_runs"] == 1
    assert est["projected_cost_usd"] == pytest.approx(0.0210, abs=1e-6)  # summed
    assert est["projected_tokens"] == 3000


def test_untagged_spend_is_not_a_run(v2_env):
    with session_scope() as s:
        _event(s, "REL-1", 1000, 500)
        cost_events.record(s, source="sdk", model="claude-sonnet-4-6",
                           input_tokens=9999, output_tokens=9999)  # no release tag
        est = cost_estimate.estimate_run(s)
    assert est["basis_runs"] == 1  # the untagged event is excluded
    assert est["projected_cost_usd"] == pytest.approx(0.0105, abs=1e-6)


def test_bad_sample_falls_back_to_release(v2_env):
    with session_scope() as s:
        _event(s, "REL-1", 1000, 500)
        est = cost_estimate.estimate_run(s, sample="bogus")
    assert est["sample"] == "release"
    assert est["basis_runs"] == 1
