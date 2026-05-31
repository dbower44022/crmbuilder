"""PI Lead substrate — the per-PI execution gate and phase advance.

The ADO **PI Lead** (tier 2, agent-delivery-organization-design.md §3.2-3.4) runs
one Planning Item's lifecycle: planning loop → gate → execution loop with
verification gates. The verification judgment is the Lead *agent's*; the
deterministic state-machine it drives lives here, reconstructed entirely from the
records (DB-backed statelessness, §4.4):

- :func:`phase_overview` — "where are we": every phase Workstream in canonical
  order with status, Work Task progress, serial-gate readiness, plus the gate
  flags (all-scoped, all-terminal, needs-attention, next-executable).
- :func:`start_phase` — open a phase for execution: ``Ready → In Progress`` and
  ready its Work Tasks (``Planned → Ready``, making them pullable by area
  specialists), gated on the phase being scoped and all its ``blocked_by``
  predecessors being terminal (§5 serial phases).
- :func:`complete_phase` — verify-and-advance: require every Work Task
  ``Complete`` (the substrate's half of §3.4 step 2), then
  ``In Progress → Complete``, which opens the next serial gate.

When :func:`phase_overview` reports ``all_terminal``, the Lead drives the PI to
``Resolved`` via the normal close-out ``resolves`` edge (§3.4) — that resolution
is governance, not done here.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import (
    planning_items,
    references,
    workstreams,
)
from crmbuilder_v2.access.repositories import work_tasks as work_tasks_repo
from crmbuilder_v2.access.repositories.decomposition import PHASE_SEQUENCE

_BELONGS_PI = "workstream_belongs_to_planning_item"
_BELONGS_WS = "work_task_belongs_to_workstream"
_BLOCKED_BY = "blocked_by"

# Workstream statuses that count as "scoped" (the planning gate) and as
# "terminal" (a serial gate is satisfied / the PI can resolve).
_SCOPED = frozenset({"Ready", "Not Applicable"})
_TERMINAL = frozenset({"Complete", "Not Applicable"})


def _phase_index(phase_type: str) -> int:
    try:
        return PHASE_SEQUENCE.index(phase_type)
    except ValueError:
        return len(PHASE_SEQUENCE)


def _require_workstream(session: Session, workstream_id: str) -> dict:
    ws = workstreams.get_workstream(session, workstream_id)
    if ws is None:
        raise NotFoundError("workstream", workstream_id)
    return ws


def _phase_workstreams(session: Session, pi_identifier: str) -> list[dict]:
    """The PI's phase Workstreams, sorted in canonical phase order."""
    edges = references.list_references(
        session, target_type="planning_item", target_id=pi_identifier,
        relationship_kind=_BELONGS_PI,
    )
    out: list[dict] = []
    for e in edges:
        ws = workstreams.get_workstream(session, e["source_id"])
        if ws is not None:
            out.append(ws)
    out.sort(key=lambda w: _phase_index(w["workstream_phase_type"]))
    return out


def _work_tasks_of(session: Session, workstream_id: str) -> list[dict]:
    edges = references.list_references(
        session, target_type="workstream", target_id=workstream_id,
        relationship_kind=_BELONGS_WS,
    )
    out: list[dict] = []
    for e in edges:
        wt = work_tasks_repo.get_work_task(session, e["source_id"])
        if wt is not None:
            out.append(wt)
    return out


def _predecessors(session: Session, workstream_id: str) -> list[dict]:
    """The Workstreams this one is ``blocked_by`` (its serial predecessors)."""
    edges = references.list_references(
        session, source_type="workstream", source_id=workstream_id,
        target_type="workstream", relationship_kind=_BLOCKED_BY,
    )
    out: list[dict] = []
    for e in edges:
        ws = workstreams.get_workstream(session, e["target_id"])
        if ws is not None:
            out.append(ws)
    return out


def _predecessors_terminal(session: Session, workstream_id: str) -> tuple[bool, list[str]]:
    """Whether every ``blocked_by`` predecessor is terminal; plus the blockers."""
    blockers = [
        p["workstream_identifier"]
        for p in _predecessors(session, workstream_id)
        if p["workstream_status"] not in _TERMINAL
    ]
    return (not blockers, blockers)


def phase_overview(session: Session, pi_identifier: str) -> dict:
    """Reconstruct the PI's execution state from the records (§4.4).

    :raises NotFoundError: the Planning Item does not exist.
    """
    planning_items.get(session, pi_identifier)  # raises if absent
    phases_raw = _phase_workstreams(session, pi_identifier)

    phases: list[dict] = []
    next_executable: str | None = None
    for ws in phases_raw:
        wsid = ws["workstream_identifier"]
        tasks = _work_tasks_of(session, wsid)
        complete = sum(1 for t in tasks if t["work_task_status"] == "Complete")
        preds_ok, blockers = _predecessors_terminal(session, wsid)
        executable_now = ws["workstream_status"] == "Ready" and preds_ok
        if executable_now and next_executable is None:
            next_executable = wsid
        phases.append({
            "workstream": ws,
            "phase_type": ws["workstream_phase_type"],
            "phase_index": _phase_index(ws["workstream_phase_type"]),
            "status": ws["workstream_status"],
            "work_tasks": {"total": len(tasks), "complete": complete},
            "predecessors_terminal": preds_ok,
            "blocked_by": blockers,
            "executable_now": executable_now,
        })

    decomposed = len(phases) > 0
    return {
        "planning_item": pi_identifier,
        "decomposed": decomposed,
        "phases": phases,
        "all_scoped": decomposed and all(p["status"] in _SCOPED for p in phases),
        "all_terminal": decomposed and all(p["status"] in _TERMINAL for p in phases),
        "needs_attention": [
            p["workstream"]["workstream_identifier"]
            for p in phases
            if p["workstream"]["workstream_needs_attention"]
        ],
        "next_executable": next_executable,
    }


def start_phase(session: Session, workstream_id: str) -> dict:
    """Open a scoped phase for execution: Ready → In Progress + ready its tasks.

    Drives the Workstream ``Ready → In Progress`` and each of its ``Planned``
    Work Tasks ``Planned → Ready`` so area specialists can pull them. Nothing is
    pullable before this — the Lead opens the gate only when the phase's serial
    predecessors are done.

    :raises NotFoundError: the Workstream does not exist.
    :raises ConflictError: the Workstream is not ``Ready`` (not scoped, already
        started, or terminal), or a ``blocked_by`` predecessor is not yet
        terminal.
    """
    ws = _require_workstream(session, workstream_id)
    if ws["workstream_status"] != "Ready":
        raise ConflictError(
            f"workstream {workstream_id!r} is {ws['workstream_status']!r}, not "
            f"'Ready'; only a scoped, not-yet-started phase can be opened for "
            f"execution."
        )
    preds_ok, blockers = _predecessors_terminal(session, workstream_id)
    if not preds_ok:
        raise ConflictError(
            f"workstream {workstream_id!r} is blocked_by non-terminal phase(s) "
            f"{sorted(blockers)}; finish them before starting this phase "
            f"(serial phases, §5)."
        )

    workstreams.patch_workstream(session, workstream_id, status="In Progress")
    readied: list[dict] = []
    for wt in _work_tasks_of(session, workstream_id):
        if wt["work_task_status"] == "Planned":
            readied.append(
                work_tasks_repo.patch_work_task(
                    session, wt["work_task_identifier"], status="Ready"
                )
            )
    ws_after = workstreams.get_workstream(session, workstream_id)
    return {"workstream": ws_after, "readied_work_tasks": readied}


def complete_phase(session: Session, workstream_id: str) -> dict:
    """Verify-and-advance: require all Work Tasks Complete, then phase → Complete.

    :raises NotFoundError: the Workstream does not exist.
    :raises ConflictError: the Workstream is not ``In Progress``, or one or more
        of its Work Tasks is not ``Complete`` (the verification gate of §3.4).
    """
    ws = _require_workstream(session, workstream_id)
    if ws["workstream_status"] != "In Progress":
        raise ConflictError(
            f"workstream {workstream_id!r} is {ws['workstream_status']!r}, not "
            f"'In Progress'; only an executing phase can be completed."
        )
    incomplete = [
        t["work_task_identifier"]
        for t in _work_tasks_of(session, workstream_id)
        if t["work_task_status"] != "Complete"
    ]
    if incomplete:
        raise ConflictError(
            f"workstream {workstream_id!r} has non-Complete Work Task(s) "
            f"{sorted(incomplete)}; the phase cannot advance until every Work "
            f"Task is Complete (§3.4 verification gate)."
        )
    workstreams.patch_workstream(session, workstream_id, status="Complete")
    return {"workstream": workstreams.get_workstream(session, workstream_id)}
