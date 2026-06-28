"""Pre-run cost estimate (REQ-317, PI-282).

Projects the token and dollar cost of an autonomous run *before* it starts, from
the recorded historical per-run spend in ``cost_events`` (the REQ-307 store). The
unit of projection is a past run of the same shape — by default a release run, so
the projection is the central tendency of completed release runs, with the
observed high-water mark surfaced alongside so an operator sees both the expected
and the worst-seen spend before committing.

Read-only: it computes from history and writes nothing.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access.repositories import cost_events

# The sample unit → the cost_events attribution filter key it aggregates over.
_SAMPLE_FILTER = {"release": "release_identifier", "area": "area", "tier": "tier"}


def _run_tokens(agg: dict) -> int:
    return (
        agg["input_tokens"]
        + agg["output_tokens"]
        + agg["cache_write_tokens"]
        + agg["cache_read_tokens"]
    )


def estimate_run(session: Session, *, sample: str = "release") -> dict:
    """Project a run's cost from historical runs of ``sample`` shape (REQ-317).

    :param sample: the run unit to sample — ``release`` (default), ``area`` or
        ``tier``. Each distinct, spend-bearing value of that dimension is one
        historical run.
    :returns: ``projected_cost_usd`` / ``projected_tokens`` (the mean over the
        sample), ``high_water_cost_usd`` (the max observed), ``basis_runs`` (how
        many historical runs informed it), and a human ``method`` string. When
        there is no history, the projection is zero and ``basis_runs`` is 0 —
        the caller surfaces that "no basis" state rather than a false figure.
    """
    if sample not in _SAMPLE_FILTER:
        sample = "release"
    filter_key = _SAMPLE_FILTER[sample]

    runs: list[dict] = []
    for row in cost_events.aggregate_by(session, sample):
        key = row.get("key")
        if not key:
            continue  # untagged spend is not a run
        agg = cost_events.aggregate(session, **{filter_key: key})
        if agg["cost_usd"] > 0 or _run_tokens(agg) > 0:
            runs.append(agg)

    if not runs:
        return {
            "projected_cost_usd": 0.0,
            "projected_tokens": 0,
            "high_water_cost_usd": 0.0,
            "basis_runs": 0,
            "sample": sample,
            "method": "no historical runs to project from",
        }

    n = len(runs)
    mean_cost = sum(r["cost_usd"] for r in runs) / n
    mean_tokens = sum(_run_tokens(r) for r in runs) / n
    high_water = max(r["cost_usd"] for r in runs)
    return {
        "projected_cost_usd": round(mean_cost, 4),
        "projected_tokens": int(round(mean_tokens)),
        "high_water_cost_usd": round(high_water, 4),
        "basis_runs": n,
        "sample": sample,
        "method": (
            f"mean of {n} historical {sample} run(s); "
            f"high_water is the most expensive one observed"
        ),
    }
