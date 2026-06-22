"""Cost-event telemetry + pricing tests — PI-263 (PRJ-041 / REQ-307), Phase v1.

The measurement foundation: a per-model price table that computes dollar cost from
tokens (uniform across SDK + claude_cli surfaces), and a cost_events satellite store that
records one row per spend event and sums cost/tokens over any attribution filter.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access import cost_pricing
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import cost_events

# --- pricing ----------------------------------------------------------------


def test_pricing_family_match():
    # sonnet: input $3 / output $15 per million tokens.
    cost = cost_pricing.compute_cost_usd(
        "claude-sonnet-4-6-20260101", input_tokens=1000, output_tokens=500)
    assert cost == pytest.approx((1000 * 3.0 + 500 * 15.0) / 1_000_000)


def test_pricing_includes_cache_tokens():
    cost = cost_pricing.compute_cost_usd(
        "claude-opus-4-8", input_tokens=0, output_tokens=0,
        cache_write_tokens=1_000_000, cache_read_tokens=1_000_000)
    assert cost == pytest.approx(18.75 + 1.50)


def test_pricing_unknown_model_is_zero_but_not_priced():
    assert cost_pricing.compute_cost_usd("gpt-4o", input_tokens=1000) == 0.0
    assert cost_pricing.is_priced("gpt-4o") is False
    assert cost_pricing.is_priced("claude-haiku-4-5") is True


def test_pricing_env_override(monkeypatch):
    monkeypatch.setenv(
        "CRMBUILDER_V2_COST_PRICES",
        '{"sonnet": {"input": 99.0, "output": 0, "cache_write": 0, "cache_read": 0}}',
    )
    cost = cost_pricing.compute_cost_usd("claude-sonnet-4-6", input_tokens=1_000_000)
    assert cost == pytest.approx(99.0)


def test_pricing_malformed_override_keeps_defaults(monkeypatch):
    monkeypatch.setenv("CRMBUILDER_V2_COST_PRICES", "not json {")
    cost = cost_pricing.compute_cost_usd("claude-sonnet-4-6", input_tokens=1_000_000)
    assert cost == pytest.approx(3.0)  # default sonnet input rate


# --- record -----------------------------------------------------------------


def test_record_computes_cost_and_keeps_attribution(v2_env):
    with session_scope() as s:
        row = cost_events.record(
            s, source="sdk", model="claude-sonnet-4-6",
            input_tokens=1000, output_tokens=500,
            release_identifier="REL-1", area="api", stage="qa")
    assert row["cost_usd"] == pytest.approx(0.0105)
    assert row["release_identifier"] == "REL-1"
    assert row["area"] == "api" and row["stage"] == "qa"
    assert row["cost_source"] == "sdk"


def test_record_keeps_reported_cost_crosscheck(v2_env):
    with session_scope() as s:
        row = cost_events.record(
            s, source="claude_cli", model="claude-opus-4-8",
            input_tokens=10, output_tokens=10, reported_usd=0.4242,
            work_task="WTK-9", area="storage")
    assert row["cost_reported_usd"] == pytest.approx(0.4242)
    assert row["cost_source"] == "claude_cli"


def test_record_unpriced_claude_cli_falls_back_to_reported(v2_env):
    # An unpriced model + a reported cost → cost_usd uses the tool's authoritative total.
    with session_scope() as s:
        row = cost_events.record(
            s, source="claude_cli", model="some-internal-model",
            input_tokens=1000, reported_usd=0.99)
    assert row["cost_usd"] == pytest.approx(0.99)
    assert row["cost_reported_usd"] == pytest.approx(0.99)


def test_record_priced_model_ignores_reported_for_cost(v2_env):
    # A priced model computes uniformly from tokens; reported is kept only as cross-check.
    with session_scope() as s:
        row = cost_events.record(
            s, source="claude_cli", model="claude-sonnet-4-6",
            input_tokens=1_000_000, reported_usd=999.0)
    assert row["cost_usd"] == pytest.approx(3.0)
    assert row["cost_reported_usd"] == pytest.approx(999.0)


def test_record_rejects_bad_source(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        cost_events.record(s, source="nope", model="claude-sonnet-4-6")


def test_record_rejects_unknown_attribution(v2_env):
    with session_scope() as s, pytest.raises(UnprocessableError):
        cost_events.record(s, source="sdk", model="m", bogus_tag="x")


# --- aggregate --------------------------------------------------------------


def _seed(s):
    cost_events.record(s, source="sdk", model="claude-sonnet-4-6",
                       input_tokens=1_000_000, release_identifier="REL-1", area="api",
                       stage="qa")              # $3
    cost_events.record(s, source="claude_cli", model="claude-opus-4-8",
                       input_tokens=1_000_000, release_identifier="REL-1", area="storage",
                       stage="develop")          # $15
    cost_events.record(s, source="sdk", model="claude-sonnet-4-6",
                       input_tokens=1_000_000, release_identifier="REL-2", area="api",
                       stage="qa")               # $3


def test_aggregate_totals_and_filter(v2_env):
    with session_scope() as s:
        _seed(s)
        assert cost_events.aggregate(s)["cost_usd"] == pytest.approx(21.0)
        assert cost_events.aggregate(s)["event_count"] == 3
        rel1 = cost_events.aggregate(s, release_identifier="REL-1")
        assert rel1["cost_usd"] == pytest.approx(18.0)
        assert rel1["event_count"] == 2
        assert cost_events.aggregate(s, area="api")["cost_usd"] == pytest.approx(6.0)


def test_aggregate_by_dimension(v2_env):
    with session_scope() as s:
        _seed(s)
        by_area = cost_events.aggregate_by(s, "area")
        top = by_area[0]
        assert top["key"] == "storage" and top["cost_usd"] == pytest.approx(15.0)
        by_source = {r["key"]: r["cost_usd"] for r in cost_events.aggregate_by(s, "source")}
        assert by_source["sdk"] == pytest.approx(6.0)
        assert by_source["claude_cli"] == pytest.approx(15.0)


def test_aggregate_rejects_bad_filter_and_dimension(v2_env):
    with session_scope() as s:
        with pytest.raises(UnprocessableError):
            cost_events.aggregate(s, nonsense="x")
        with pytest.raises(UnprocessableError):
            cost_events.aggregate_by(s, "nonsense")


def test_recent_newest_first_and_limit(v2_env):
    with session_scope() as s:
        _seed(s)
        rows = cost_events.recent(s, limit=2)
        assert len(rows) == 2
        rel2 = cost_events.recent(s, release_identifier="REL-2")
        assert len(rel2) == 1 and rel2[0]["release_identifier"] == "REL-2"
