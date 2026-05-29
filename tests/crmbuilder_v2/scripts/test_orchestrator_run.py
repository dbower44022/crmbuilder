"""Driver glue tests for the orchestrator (PI-081) — plan + render only.

Exercises the pure planning/rendering glue in ``run.py`` (the parts that
don't touch the API, git, or subprocesses). Loaded by file path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MOD = (
    Path(__file__).resolve().parents[3]
    / "crmbuilder-v2"
    / "scripts"
    / "orchestrator"
    / "run.py"
)
_spec = importlib.util.spec_from_file_location("orch_run", _MOD)
run = importlib.util.module_from_spec(_spec)
sys.modules["orch_run"] = run
_spec.loader.exec_module(run)


def _item(ident, area, **extra):
    base = {
        "identifier": ident,
        "title": f"title {ident}",
        "executive_summary": "exec summary",
        "area": area,
        "claimed_by": None,
    }
    base.update(extra)
    return base


_READY = {
    "batches": [
        {"depth": 0, "items": [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-ui"])]},
        {"depth": 1, "items": [_item("PI-003", ["v2-storage"])]},
    ],
    "cyclic": [],
    "warnings": [],
}


def test_plan_waves_produces_disjoint_clusters():
    waves = run.plan_waves(_READY)
    assert [w.depth for w in waves] == [0, 1]
    # depth 0: two disjoint areas -> two parallel children
    assert len(waves[0].clusters) == 2
    # depth 1: one child
    assert len(waves[1].clusters) == 1


def test_summarize_plan_mentions_each_wave():
    waves = run.plan_waves(_READY)
    summary = run.summarize_plan(_READY, waves)
    assert "depth 0" in summary
    assert "depth 1" in summary
    assert "PI-001" in summary


def test_render_child_kickoff_matches_template_contract():
    waves = run.plan_waves(_READY)
    cluster = waves[0].clusters[0]
    body = run._load_template()
    text = run.render_child_kickoff(
        body,
        cluster=cluster,
        session_identifier="SES-200",
        conversation_identifier="CNV-200",
        orchestrator_conversation="CNV-199",
        branch_name="orch-wave0-child1",
        engagement_code="CRMBUILDER",
        workstream_identifier="WS-012",
        workstream_title="Parallel agent orchestrator",
        api_base="http://127.0.0.1:8765",
    )
    # The driver's substitution set must satisfy every template placeholder.
    assert "{{" not in text and "}}" not in text
    assert "SES-200" in text
    assert "ses_200.json" in text


def test_execute_is_guarded():
    import pytest

    class _NS:
        execute = True
        api_base = "http://127.0.0.1:8765"

    # _execute is the human-driven acceptance path; it must refuse to run
    # silently rather than spawn a swarm.
    with pytest.raises(NotImplementedError):
        run._execute(_NS())
