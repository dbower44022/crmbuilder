"""Reconciliation gate — PI-134 (DEC-400), built on the runtime's dispatch path.

REQ-027/031..036 / TOP-010: at the end of Design the area specifications for a
Planning Item are checked against each other, and every problem is recorded as a
``finding``. **Develop does not begin until that check is clean** — every
*blocking* finding resolved (REQ-033). This module enforces that as a gate on
the runtime's dispatch: before a Planning Item's **Develop** Work Tasks are
dispatched, the runtime requires the PI's **Design** phase Complete *and* zero
**open blocking** findings related to the PI; a Develop Work Task is withheld
while an open blocking finding exists and dispatched once it is resolved.

The decision — *given the Design state and the findings, may Develop dispatch?* —
is a pure predicate (:func:`evaluate_develop_gate`), split from the API reads
(:func:`develop_gate`) so the gate is unit-testable without a server.
"""

from __future__ import annotations

import urllib.parse
from dataclasses import dataclass, field

from crmbuilder_v2.access.vocab import FINDING_OPEN_STATUSES
from crmbuilder_v2.scheduler import dispatcher

_DEVELOP_PHASE = "Develop"
_DESIGN_PHASE = "Design"
_COMPLETE_STATUS = "Complete"
_NOT_APPLICABLE_STATUS = "Not Applicable"
# A Design phase is "settled" — the Develop gate may proceed — when it is
# Complete (reconciliation ran over real design work) OR Not Applicable (the
# Architect found no design work to do, so there is nothing to reconcile).
_DESIGN_SETTLED_STATUSES = frozenset({_COMPLETE_STATUS, _NOT_APPLICABLE_STATUS})
_BLOCKING_SEVERITY = "blocking"


@dataclass
class GateDecision:
    """Whether a Develop Work Task may be dispatched, and why.

    ``allow`` is the answer; ``reason`` is a short human-readable explanation;
    ``open_blocking`` lists the finding identifiers holding the gate (empty when
    allowed). ``design_complete`` records the Design-phase check.
    """

    allow: bool
    reason: str
    design_complete: bool = True
    open_blocking: list[str] = field(default_factory=list)


def is_open_blocking(finding: dict) -> bool:
    """True if a finding is *blocking* and still *unresolved* (open or referred)."""
    return (
        finding.get("finding_severity") == _BLOCKING_SEVERITY
        and finding.get("finding_status") in FINDING_OPEN_STATUSES
    )


def evaluate_develop_gate(
    phase_type: str | None,
    design_complete: bool,
    findings: list[dict],
) -> GateDecision:
    """The pure gate decision (REQ-027/033).

    A non-Develop phase is never gated by reconciliation — it passes straight
    through. For a Develop phase, dispatch is allowed only when the PI's Design
    phase is *settled* — Complete (reconciliation ran) **or** Not Applicable
    (there was no design work to reconcile) — **and** no related finding is open
    + blocking. ``design_complete`` carries that settled predicate.
    """
    if phase_type != _DEVELOP_PHASE:
        return GateDecision(True, f"not a Develop phase ({phase_type})")
    open_blocking = [
        f["finding_identifier"] for f in findings if is_open_blocking(f)
    ]
    if not design_complete:
        return GateDecision(
            False,
            "Design phase is not settled (neither Complete nor Not Applicable) "
            "— reconciliation has not run",
            design_complete=False,
            open_blocking=open_blocking,
        )
    if open_blocking:
        return GateDecision(
            False,
            f"{len(open_blocking)} open blocking finding(s): {', '.join(open_blocking)}",
            design_complete=True,
            open_blocking=open_blocking,
        )
    return GateDecision(True, "Design complete, no open blocking findings")


# --------------------------------------------------------------------------
# I/O: resolve a Work Task's Develop-gate state from the API
# --------------------------------------------------------------------------


def _owning_workstream(api_base: str, engagement: str, work_task_id: str) -> dict | None:
    edges = dispatcher._get(
        api_base,
        "/references?"
        + urllib.parse.urlencode(
            {"source_id": work_task_id, "relationship": "work_task_belongs_to_workstream"}
        ),
        engagement,
    )
    for e in edges:
        if e.get("target_type") == "workstream":
            return dispatcher._get(
                api_base, f"/workstreams/{e['target_id']}", engagement
            )
    return None


def _planning_item_of(api_base: str, engagement: str, workstream_id: str) -> str | None:
    edges = dispatcher._get(
        api_base,
        "/references?"
        + urllib.parse.urlencode(
            {"source_id": workstream_id, "relationship": "workstream_belongs_to_planning_item"}
        ),
        engagement,
    )
    for e in edges:
        if e.get("target_type") == "planning_item":
            return e["target_id"]
    return None


def _sibling_workstreams(api_base: str, engagement: str, planning_item_id: str) -> list[dict]:
    edges = dispatcher._get(
        api_base,
        "/references?"
        + urllib.parse.urlencode(
            {"target_id": planning_item_id, "relationship": "workstream_belongs_to_planning_item"}
        ),
        engagement,
    )
    out = []
    for e in edges:
        if e.get("source_type") == "workstream":
            out.append(dispatcher._get(api_base, f"/workstreams/{e['source_id']}", engagement))
    return out


def _findings_for_targets(api_base: str, engagement: str, target_ids: list[str]) -> list[dict]:
    """All findings with a ``finding_relates_to`` edge to any of ``target_ids``."""
    seen: dict[str, dict] = {}
    for target_id in target_ids:
        edges = dispatcher._get(
            api_base,
            "/references?"
            + urllib.parse.urlencode(
                {"target_id": target_id, "relationship": "finding_relates_to"}
            ),
            engagement,
        )
        for e in edges:
            if e.get("source_type") != "finding":
                continue
            fid = e["source_id"]
            if fid not in seen:
                seen[fid] = dispatcher._get(api_base, f"/findings/{fid}", engagement)
    return list(seen.values())


def develop_gate(api_base: str, engagement: str, work_task: dict) -> GateDecision:
    """Resolve the Develop-gate decision for one Work Task from the live API.

    A Work Task whose owning Workstream is not a Develop phase passes straight
    through. For a Develop Work Task, this reads the owning Workstream → its
    Planning Item → the PI's Design Workstream status and the findings related to
    the PI (and its Design Workstream), then applies :func:`evaluate_develop_gate`.
    Conservative on missing structure: a Develop Work Task with no resolvable
    Planning Item / Design phase is treated as *not design-complete* and held.
    """
    work_task_id = work_task["work_task_identifier"]
    workstream = _owning_workstream(api_base, engagement, work_task_id)
    phase = workstream.get("workstream_phase_type") if workstream else None
    if phase != _DEVELOP_PHASE:
        return GateDecision(True, f"not a Develop phase ({phase})")

    planning_item_id = _planning_item_of(
        api_base, engagement, workstream["workstream_identifier"]
    )
    if planning_item_id is None:
        return GateDecision(
            False, "Develop phase has no resolvable Planning Item", design_complete=False
        )
    siblings = _sibling_workstreams(api_base, engagement, planning_item_id)
    design = next(
        (w for w in siblings if w.get("workstream_phase_type") == _DESIGN_PHASE), None
    )
    design_complete = (
        design is not None
        and design.get("workstream_status") in _DESIGN_SETTLED_STATUSES
    )

    targets = [planning_item_id]
    if design is not None:
        targets.append(design["workstream_identifier"])
    findings = _findings_for_targets(api_base, engagement, targets)
    return evaluate_develop_gate(_DEVELOP_PHASE, design_complete, findings)
