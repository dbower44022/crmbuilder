"""Best-effort cost-capture helper tests — PI-264 (PRJ-041 / REQ-307), v1.

The capture entry points used at the spend surfaces: ``record_sdk_usage`` (SDK response
usage) and ``record_cli_result`` (a ``claude -p --output-format json`` result). Both must
record a cost_events row and must NEVER raise — a capture failure can't break the work.
"""

from __future__ import annotations

from types import SimpleNamespace

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import cost_events
from crmbuilder_v2.scheduler import cost_capture


def _usage(i=0, o=0, cw=0, cr=0):
    return SimpleNamespace(
        input_tokens=i, output_tokens=o,
        cache_creation_input_tokens=cw, cache_read_input_tokens=cr,
    )


def test_record_sdk_usage_writes_row(v2_env):
    cost_capture.record_sdk_usage(
        _usage(i=1_000_000, o=0), "claude-sonnet-4-6",
        stage="demands", release_identifier="REL-1")
    with session_scope() as s:
        rows = cost_events.recent(s, source="sdk")
    assert len(rows) == 1
    assert rows[0]["cost_usd"] > 0  # sonnet input priced
    assert rows[0]["stage"] == "demands" and rows[0]["release_identifier"] == "REL-1"


def test_record_prefers_ambient_engagement_over_explicit(v2_env):
    # DEC-637: an ambient active engagement (set by the scheduler around a release run)
    # wins over an explicit arg — so a config that carries a code, or a stale/unknown
    # value, can't misroute the row. The event records under the ambient ENG-001.
    from crmbuilder_v2.access.engagement_scope import get_active_engagement

    assert get_active_engagement()  # v2_env sets ENG-001 active
    cost_capture.record_sdk_usage(
        _usage(i=10), "claude-sonnet-4-6", engagement="ENG-NOPE", stage="qa")
    with session_scope() as s:
        assert cost_events.aggregate(s)["event_count"] == 1


def test_record_never_raises_on_unresolvable_engagement(v2_env):
    # No ambient + an unresolvable engagement → swallowed, no row, no raise.
    from crmbuilder_v2.access.engagement_scope import active_engagement

    with active_engagement(None):  # clear the ambient
        cost_capture.record_sdk_usage(
            _usage(i=10), "claude-sonnet-4-6", engagement="ENG-NOPE", stage="qa")
    with session_scope() as s:
        assert cost_events.aggregate(s)["event_count"] == 0


def test_resolve_engagement_accepts_code_and_identifier(v2_env):
    # v2_env seeds ENG-001 with code TESTENG; both resolve to the identifier.
    assert cost_capture._resolve_engagement("ENG-001") == "ENG-001"
    assert cost_capture._resolve_engagement("TESTENG") == "ENG-001"
    assert cost_capture._resolve_engagement("testeng") == "ENG-001"
    assert cost_capture._resolve_engagement("nope") is None


def test_record_cli_result_from_json_string(v2_env):
    blob = (
        '{"type":"result","total_cost_usd":0.4242,'
        '"usage":{"input_tokens":1000,"output_tokens":500,'
        '"cache_creation_input_tokens":0,"cache_read_input_tokens":0},'
        '"model":"claude-opus-4-8"}'
    )
    cost_capture.record_cli_result(blob, work_task="WTK-7", area="storage", stage="develop")
    with session_scope() as s:
        rows = cost_events.recent(s, source="claude_cli")
    assert len(rows) == 1
    row = rows[0]
    assert row["cost_reported_usd"] == 0.4242
    assert row["work_task"] == "WTK-7" and row["area"] == "storage"
    assert row["cost_usd"] > 0  # opus priced from tokens


def test_record_cli_result_unpriced_model_falls_back_to_reported(v2_env):
    blob = (
        '{"total_cost_usd":1.25,'
        '"usage":{"input_tokens":1000,"output_tokens":0},'
        '"model":"some-internal-model"}'
    )
    cost_capture.record_cli_result(blob, area="api")
    with session_scope() as s:
        row = cost_events.recent(s, source="claude_cli")[0]
    # unpriced model → cost_usd falls back to the tool's reported total.
    assert row["cost_usd"] == 1.25
    assert row["cost_reported_usd"] == 1.25


def test_record_cli_result_accepts_dict(v2_env):
    cost_capture.record_cli_result(
        {"usage": {"input_tokens": 1_000_000}, "total_cost_usd": 0.0,
         "model": "claude-haiku-4-5"})
    with session_scope() as s:
        assert cost_events.aggregate(s, source="claude_cli")["event_count"] == 1


def test_record_cli_result_ignores_empty_or_nonjson(v2_env):
    cost_capture.record_cli_result("")          # crashed/empty agent stdout
    cost_capture.record_cli_result("not json {")
    cost_capture.record_cli_result(None)
    with session_scope() as s:
        assert cost_events.aggregate(s)["event_count"] == 0
