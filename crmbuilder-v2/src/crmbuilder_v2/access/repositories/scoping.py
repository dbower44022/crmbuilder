"""Phase-specialist substrate — scope a Workstream and read prior-phase output.

The ADO **phase specialist** (tier 3, agent-delivery-organization-design.md §2.1
and §3.2) evaluates a Planning Item *through one phase's lens* and **documents its
scope by creating that phase's Work Tasks** — possibly zero, which is the
first-class ``Not Applicable`` assertion (§4.3). The judgment is the agent's; the
two deterministic operations it relies on live here:

- :func:`scope_workstream` — record the scoping decision atomically: create the
  Work Tasks (each ``work_task_belongs_to_workstream`` the phase) and drive the
  Workstream ``Planned → Scoping → Ready`` (work scoped) or
  ``Planned → Scoping → Not Applicable`` (evaluated empty).
- :func:`prior_phase_outputs` — the feed-forward read (§3.2): the Work Tasks of
  this PI's *earlier* phases (by :data:`PHASE_SEQUENCE` order), the accumulated
  context a specialist scopes against.

The specialist makes no scope judgment here — it supplies the Work Task specs (or
none) it decided on; this module just records that decision against the lifecycle.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import (
    pm,
    references,
    workstreams,
)
from crmbuilder_v2.access.repositories import work_tasks as work_tasks_repo
from crmbuilder_v2.access.repositories.decomposition import PHASE_SEQUENCE

_BELONGS_PI = "workstream_belongs_to_planning_item"
_BELONGS_WS = "work_task_belongs_to_workstream"


def _phase_index(phase_type: str) -> int | None:
    """Return the canonical order index of a phase, or None if unrecognized."""
    try:
        return PHASE_SEQUENCE.index(phase_type)
    except ValueError:
        return None


def _require_workstream(session: Session, workstream_id: str) -> dict:
    ws = workstreams.get_workstream(session, workstream_id)
    if ws is None:
        raise NotFoundError("workstream", workstream_id)
    return ws


def prior_phase_outputs(session: Session, workstream_id: str) -> dict:
    """Return the Work Tasks of this PI's earlier phases (feed-forward, §3.2).

    :returns: ``{planning_item, phase_type, prior_phases: [{workstream,
        phase_type, work_tasks}]}`` ordered by canonical phase. ``prior_phases``
        is empty for the first phase (Architecture) or an un-decomposed PI.
    :raises NotFoundError: the Workstream does not exist.
    """
    ws = _require_workstream(session, workstream_id)
    phase = ws["workstream_phase_type"]
    idx = _phase_index(phase)

    belongs = references.list_references(
        session, source_type="workstream", source_id=workstream_id,
        relationship_kind=_BELONGS_PI,
    )
    if not belongs:
        return {"planning_item": None, "phase_type": phase, "prior_phases": []}
    pi_id = belongs[0]["target_id"]

    siblings = references.list_references(
        session, target_type="planning_item", target_id=pi_id,
        relationship_kind=_BELONGS_PI,
    )
    prior: list[dict] = []
    for edge in siblings:
        sib_id = edge["source_id"]
        if sib_id == workstream_id:
            continue
        sib = workstreams.get_workstream(session, sib_id)
        if sib is None:
            continue
        sib_idx = _phase_index(sib["workstream_phase_type"])
        if sib_idx is None or idx is None or sib_idx >= idx:
            continue
        wt_edges = references.list_references(
            session, target_type="workstream", target_id=sib_id,
            relationship_kind=_BELONGS_WS,
        )
        work_tasks = []
        for wte in wt_edges:
            wt = work_tasks_repo.get_work_task(session, wte["source_id"])
            if wt is not None:
                work_tasks.append(wt)
        prior.append({
            "workstream": sib,
            "phase_type": sib["workstream_phase_type"],
            "phase_index": sib_idx,
            "work_tasks": work_tasks,
        })
    prior.sort(key=lambda p: p["phase_index"])
    return {"planning_item": pi_id, "phase_type": phase, "prior_phases": prior}


def scope_workstream(
    session: Session,
    workstream_id: str,
    work_tasks: list[dict] | None = None,
) -> dict:
    """Record a phase specialist's scoping decision for a Workstream.

    :param work_tasks: the Work Task specs the specialist decided on — each a
        dict with ``title`` and ``area`` (plus optional ``description`` /
        ``notes`` / ``resolved_agent_profile``). An empty / omitted list is the
        ``Not Applicable`` assertion (§4.3): the phase was evaluated and has no
        work.
    :returns: ``{workstream, work_tasks}`` — the Workstream at its new status and
        the created Work Tasks (in spec order).
    :raises NotFoundError: the Workstream does not exist.
    :raises ConflictError: the Workstream is not ``Planned`` (it has already been
        scoped or is mid-lifecycle — re-scoping a phase adds Work Tasks through
        the Lead's additive replanning, §6, not by re-running this).

    The two lifecycle transitions (``Planned → Scoping`` then
    ``Scoping → Ready | Not Applicable``) and all Work Task creates happen in the
    caller's transaction, so the scoping decision lands atomically.
    """
    ws = _require_workstream(session, workstream_id)
    # PI-190 / REQ-165: an interactive PI is ADO-invisible at every tier — the
    # ADO must not scope a phase of it (DEC-425).
    if pm.workstream_is_ado_interactive(session, workstream_id):
        raise ConflictError(
            f"workstream {workstream_id!r} belongs to an execution_mode "
            f"'interactive' planning item; the ADO must not scope it — "
            f"interactive work is executed by a human."
        )
    if ws["workstream_status"] != "Planned":
        raise ConflictError(
            f"workstream {workstream_id!r} is {ws['workstream_status']!r}, not "
            f"'Planned'; it has already been scoped. Re-scoping a phase adds "
            f"Work Tasks via the Lead's additive replanning (§6), not by "
            f"re-running scope."
        )
    specs = work_tasks or []

    # Planned -> Scoping: the specialist has started evaluating.
    workstreams.patch_workstream(session, workstream_id, status="Scoping")

    created: list[dict] = []
    for spec in specs:
        wt = work_tasks_repo.create_work_task(
            session,
            title=spec["title"],
            area=spec["area"],
            description=spec.get("description"),
            notes=spec.get("notes"),
            status="Planned",
            resolved_agent_profile=spec.get("resolved_agent_profile"),
        )
        references.create(
            session,
            source_type="work_task",
            source_id=wt["work_task_identifier"],
            target_type="workstream",
            target_id=workstream_id,
            relationship=_BELONGS_WS,
        )
        created.append(wt)

    # Scoping -> Ready (work scoped) or Not Applicable (evaluated empty, §4.3).
    final_status = "Ready" if created else "Not Applicable"
    ws_final = workstreams.patch_workstream(
        session, workstream_id, status=final_status
    )
    return {"workstream": ws_final, "work_tasks": created}
