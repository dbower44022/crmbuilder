"""PI-134 — reconciliation gate: pure decision, I/O resolution, runtime filter.

* **pure decision** — ``evaluate_develop_gate`` / ``is_open_blocking``: a
  non-Develop phase passes; a Develop phase is held while Design is incomplete
  or any related finding is open + blocking, and clears once Design is Complete
  with no open blocking findings (advisory / resolved findings never hold it);
* **I/O resolution** — ``develop_gate`` against a stubbed edge graph;
* **runtime filter** — the Layer 2 pool excludes a gated Develop Work Task and
  includes it once the blocking finding resolves.

The genuine end-to-end gate (real findings API on a create_all DB) is the demo
in the build notes; the decision is pinned deterministically here.
"""

from __future__ import annotations

from crmbuilder_v2.runtime import parallel_runtime as pr
from crmbuilder_v2.runtime import reconciliation
from crmbuilder_v2.runtime.reconciliation import (
    GateDecision,
    evaluate_develop_gate,
    is_open_blocking,
)


def _finding(severity="blocking", status="open", ident="FND-001"):
    return {
        "finding_identifier": ident,
        "finding_severity": severity,
        "finding_status": status,
    }


# ==========================================================================
# Pure: is_open_blocking
# ==========================================================================


def test_is_open_blocking():
    assert is_open_blocking(_finding("blocking", "open")) is True
    assert is_open_blocking(_finding("blocking", "referred")) is True  # still unresolved
    assert is_open_blocking(_finding("blocking", "resolved")) is False
    assert is_open_blocking(_finding("advisory", "open")) is False


# ==========================================================================
# Pure: evaluate_develop_gate
# ==========================================================================


def test_non_develop_phase_passes():
    d = evaluate_develop_gate("Design", design_complete=False, findings=[_finding()])
    assert d.allow is True
    d2 = evaluate_develop_gate("Test", design_complete=True, findings=[])
    assert d2.allow is True


def test_develop_blocked_when_design_incomplete():
    d = evaluate_develop_gate("Develop", design_complete=False, findings=[])
    assert d.allow is False
    assert "not settled" in d.reason


def test_develop_blocked_by_open_blocking_finding():
    d = evaluate_develop_gate(
        "Develop", design_complete=True, findings=[_finding("blocking", "open")]
    )
    assert d.allow is False
    assert d.open_blocking == ["FND-001"]


def test_develop_blocked_by_referred_blocking_finding():
    # A referred finding is unresolved (handed to a person) → still holds.
    d = evaluate_develop_gate(
        "Develop", design_complete=True, findings=[_finding("blocking", "referred")]
    )
    assert d.allow is False


def test_develop_allowed_when_finding_resolved():
    d = evaluate_develop_gate(
        "Develop", design_complete=True, findings=[_finding("blocking", "resolved")]
    )
    assert d.allow is True


def test_develop_allowed_with_only_advisory_findings():
    d = evaluate_develop_gate(
        "Develop",
        design_complete=True,
        findings=[_finding("advisory", "open"), _finding("advisory", "open", "FND-002")],
    )
    assert d.allow is True


def test_develop_allowed_clean():
    d = evaluate_develop_gate("Develop", design_complete=True, findings=[])
    assert d.allow is True
    assert d.open_blocking == []


# ==========================================================================
# I/O: develop_gate over a stubbed edge graph
# ==========================================================================


def _stub_graph(monkeypatch, *, design_status="Complete", finding=None):
    """Route dispatcher._get for one Develop WTK-1 → WSK-DEV → PI-1, sibling
    Design WSK-DES, and an optional finding related to PI-1."""

    def fake_get(api_base, path, eng):
        if path.startswith("/references?"):
            if "source_id=WTK-1" in path and "work_task_belongs_to_workstream" in path:
                return [{"target_type": "workstream", "target_id": "WSK-DEV"}]
            if "source_id=WSK-DEV" in path and "workstream_belongs_to_planning_item" in path:
                return [{"target_type": "planning_item", "target_id": "PI-1"}]
            if "target_id=PI-1" in path and "workstream_belongs_to_planning_item" in path:
                return [
                    {"source_type": "workstream", "source_id": "WSK-DES"},
                    {"source_type": "workstream", "source_id": "WSK-DEV"},
                ]
            if "finding_relates_to" in path:
                if "target_id=PI-1" in path and finding is not None:
                    return [{"source_type": "finding", "source_id": finding["finding_identifier"]}]
                return []
            return []
        if path == "/workstreams/WSK-DEV":
            return {"workstream_identifier": "WSK-DEV", "workstream_phase_type": "Develop",
                    "workstream_status": "In Progress"}
        if path == "/workstreams/WSK-DES":
            return {"workstream_identifier": "WSK-DES", "workstream_phase_type": "Design",
                    "workstream_status": design_status}
        if path.startswith("/findings/"):
            return finding
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(reconciliation.dispatcher, "_get", fake_get)


_DEV_TASK = {"work_task_identifier": "WTK-1", "work_task_area": "api"}


def test_develop_gate_blocks_on_open_blocking_finding(monkeypatch):
    _stub_graph(monkeypatch, finding=_finding("blocking", "open"))
    d = reconciliation.develop_gate("http://x", "ENG", _DEV_TASK)
    assert d.allow is False
    assert d.open_blocking == ["FND-001"]


def test_develop_gate_allows_when_resolved(monkeypatch):
    _stub_graph(monkeypatch, finding=_finding("blocking", "resolved"))
    d = reconciliation.develop_gate("http://x", "ENG", _DEV_TASK)
    assert d.allow is True


def test_develop_gate_blocks_when_design_incomplete(monkeypatch):
    _stub_graph(monkeypatch, design_status="In Progress", finding=None)
    d = reconciliation.develop_gate("http://x", "ENG", _DEV_TASK)
    assert d.allow is False
    assert d.design_complete is False


def test_develop_gate_allows_when_design_not_applicable(monkeypatch):
    # A Not Applicable Design (the Architect found no design work) is a settled
    # terminal state with nothing to reconcile — the Develop gate must open, not
    # block forever waiting for a "Complete" that will never come. Regression
    # for the gate bug surfaced running PI-146 through the ADO.
    _stub_graph(monkeypatch, design_status="Not Applicable", finding=None)
    d = reconciliation.develop_gate("http://x", "ENG", _DEV_TASK)
    assert d.allow is True
    assert d.design_complete is True


def test_develop_gate_passes_non_develop(monkeypatch):
    # WSK-DEV reports a Design phase → not gated.
    monkeypatch.setattr(
        reconciliation.dispatcher,
        "_get",
        lambda api, path, eng: (
            [{"target_type": "workstream", "target_id": "WSK-X"}]
            if path.startswith("/references?")
            else {"workstream_identifier": "WSK-X", "workstream_phase_type": "Test",
                  "workstream_status": "Ready"}
        ),
    )
    d = reconciliation.develop_gate("http://x", "ENG", _DEV_TASK)
    assert d.allow is True


# ==========================================================================
# Runtime filter — the pool excludes a gated Develop Work Task
# ==========================================================================


def test_pool_excludes_gated_develop_task(monkeypatch):
    cfg = pr.ParallelRuntimeConfig(target_work_tasks=["WTK-1"], max_concurrent=2)
    rt = pr.ParallelCoordinatingRuntime(config=cfg, log=lambda m: None)

    monkeypatch.setattr(
        pr.dispatcher, "_get",
        lambda api, path, eng: {
            "work_task_identifier": "WTK-1", "work_task_status": "Ready",
            "work_task_claimed_by": None,
        },
    )
    monkeypatch.setattr(pr.dispatcher, "_blocker_statuses", lambda a, e, t: [])

    # Gate closed → the candidate is withheld.
    monkeypatch.setattr(
        rt._l1, "_reconciliation_gate_open", lambda wt: False
    )
    assert rt._eligible_candidates() == []

    # Gate open → the candidate is dispatchable.
    monkeypatch.setattr(rt._l1, "_reconciliation_gate_open", lambda wt: True)
    assert rt._eligible_candidates() == ["WTK-1"]


def test_gate_open_helper_logs_and_returns(monkeypatch):
    from crmbuilder_v2.runtime.coordinating_runtime import (
        CoordinatingRuntime,
        RuntimeConfig,
    )

    logs: list[str] = []
    rt = CoordinatingRuntime(config=RuntimeConfig(), log=logs.append)
    monkeypatch.setattr(
        reconciliation, "develop_gate",
        lambda api, eng, wt: GateDecision(False, "2 open blocking finding(s)"),
    )
    monkeypatch.setattr(
        "crmbuilder_v2.runtime.coordinating_runtime.reconciliation.develop_gate",
        lambda api, eng, wt: GateDecision(False, "2 open blocking finding(s)"),
    )
    assert rt._reconciliation_gate_open({"work_task_identifier": "WTK-9"}) is False
    assert any("reconciliation gate holds WTK-9" in m for m in logs)
