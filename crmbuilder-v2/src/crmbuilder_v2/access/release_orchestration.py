"""Deterministic release-stage drivers — the agent layer's substrate-facing spine.

PRJ-033 (PI-217 + PI-218). These functions wrap the deterministic substrate (the
PI-209 Option-A spine) and supply the *plumbing* of the reconciliation and
architecture-planning stages — never the judgment (demands authoring and the
work-task decomposition *spec* are the LLM agents' job, in
:mod:`crmbuilder_v2.runtime.release_runtime`). They reimplement no reconcile /
version / gate logic (AL-5): they call the substrate and arrange the calls.

Stage steps
-----------
- ``run_reconciliation`` (PI-217): merge the persisted demand-set against each
  artifact's live base; returns the conflict-free delta-sets + any open conflicts.
- ``reconciled_delta_sets`` (PI-217): the same merge as a pure, non-gated,
  re-runnable read (D-37) — used by the planning stage, which runs *after* the
  reconciliation gate, so conflicts are already resolved.
- ``run_architecture_planning`` (PI-218): author each artifact's vN+1 from the
  reconciled delta-sets + report planned-completely readiness.
- ``decompose_planning_item_direct`` (PI-218): create a PI's workstreams +
  work-tasks directly (honouring DEC-425 — the ADO structural decomposer refuses
  interactive PIs; the planning agent decomposes interactive release PIs itself).
- ``finalize_planning`` (PI-218 / AL-4): assert readiness, flip in-scope PIs
  ``interactive → ado``, transition ``architecture_planning → ready``.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access import planning
from crmbuilder_v2.access import reconciliation as engine
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import (
    artifact_versions,
    planning_items,
    release_demands,
    releases,
    work_tasks,
)
from crmbuilder_v2.access.repositories import reconciliation as recon
from crmbuilder_v2.access.repositories import workstreams as ws_repo

# Reuse the substrate's intra-model dependency order + resolved-value fold so the
# re-derivation in ``reconciled_delta_sets`` cannot diverge from ``reconcile_release``.
from crmbuilder_v2.access.repositories.reconciliation import (
    _ARTIFACT_RANK,
    _apply_resolution,
)

# ---------------------------------------------------------------------------
# Reconciliation stage (PI-217)
# ---------------------------------------------------------------------------


def run_reconciliation(session: Session, release_identifier: str) -> dict:
    """Run reconciliation over the release's *persisted* demand-set (AL-1).

    Reads the demands authored into the ``release_demands`` store and feeds them to
    the substrate ``reconcile_release`` (status-gated to ``reconciliation``), which
    upserts the typed conflicts. Returns the reconciled delta-sets, the open-conflict
    count, and the open conflicts themselves so the caller (agent or human) can open
    governed decisions and re-run.
    """
    demands = release_demands.as_reconcile_input(session, release_identifier)
    result = recon.reconcile_release(session, release_identifier, demands)
    result["open_conflicts"] = recon.list_conflicts(
        session, release_identifier, status="open"
    )
    return result


def reconciled_delta_sets(session: Session, release_identifier: str) -> list[dict]:
    """The reconciled delta-sets as a pure, non-gated, re-runnable read (D-37).

    Mirrors ``reconcile_release``'s merge — same engine, same live bases, same
    dependency order, same resolved-value fold — but neither gates on status nor
    upserts conflicts. Used by the architecture-planning stage, reached only after
    the reconciliation gate (so conflicts are resolved).
    """
    demands = release_demands.as_reconcile_input(session, release_identifier)
    by_artifact: dict[tuple[str, str], list[dict]] = {}
    for d in demands:
        by_artifact.setdefault((d["artifact_type"], d["artifact_identifier"]), []).append(d)

    resolved = recon.list_conflicts(session, release_identifier, status="resolved")
    resolved_by_artifact: dict[tuple[str, str], list[dict]] = {}
    for c in resolved:
        resolved_by_artifact.setdefault(
            (c["artifact_type"], c["artifact_identifier"]), []
        ).append(c)

    def _order(item):
        (atype, aid), _ = item
        return (_ARTIFACT_RANK.get(atype, 99), atype, aid)

    delta_sets: list[dict] = []
    for (atype, aid), ds in sorted(by_artifact.items(), key=_order):
        live = artifact_versions.live(
            session, artifact_type=atype, artifact_identifier=aid
        )
        base = live["snapshot"] if live else {}
        result = engine.reconcile_artifact(base, ds)
        merged = result["merged"]
        for c in resolved_by_artifact.get((atype, aid), []):
            _apply_resolution(merged, c["facet"], c["resolved_value"])
        delta_sets.append({
            "artifact_type": atype,
            "artifact_identifier": aid,
            "merged": merged,
            "provenance": result["provenance"],
        })
    return delta_sets


# ---------------------------------------------------------------------------
# Architecture-planning stage (PI-218)
# ---------------------------------------------------------------------------


def run_architecture_planning(
    session: Session,
    release_identifier: str,
    delta_sets: list[dict] | None = None,
) -> dict:
    """Author vN+1 designs from the reconciled delta-sets + report readiness.

    ``delta_sets`` may be passed forward from ``run_reconciliation`` in a single
    scheduler pass; when omitted it is re-derived (``reconciled_delta_sets``) so the
    stage is self-sufficient on stateless re-entry.
    """
    if delta_sets is None:
        delta_sets = reconciled_delta_sets(session, release_identifier)
    return planning.plan_release(session, release_identifier, delta_sets)


def decompose_planning_item_direct(
    session: Session, pi_identifier: str, workstreams: list[dict]
) -> dict:
    """Create a PI's workstreams + work-tasks directly (AL-3, DEC-425 honoured).

    ``workstreams`` is the agent-authored decomposition spec::

        [{"phase_type": "Design"|"Develop"|"Test",
          "title": str, "description": str | None,
          "work_tasks": [{"title": str, "area": str, "description": str | None}]}]

    Workstreams are chained serially (each ``blocked_by`` the previous — the
    Design→Develop→Test phase order); work-tasks are left independent within a
    phase (acyclic by construction, satisfying the planned-completely sequencing
    check). The structural ADO decomposer is bypassed because it refuses interactive
    release-pipeline PIs.

    Each phase is driven to its **scoped** status — ``Ready`` (it has work) or
    ``Not Applicable`` (empty) — so the development stage (the ADO runtime) walks
    the finished prerequisite graph and *executes* it (§5.2) rather than re-scoping
    it. The architect's decomposition IS the scoping; ``scope_workstream`` is not
    reused because it refuses the still-interactive release PI (DEC-425) — the
    transition is driven directly here, which is the same carve-out.
    """
    created_ws: list[dict] = []
    created_wt: list[dict] = []
    prev_ws_id: str | None = None
    for spec in workstreams:
        # Create first (auto-assigns the identifier), then wire edges with the real
        # id — apply_reference_list takes source_id verbatim, it does not back-fill.
        ws = ws_repo.create_workstream(
            session,
            phase_type=spec["phase_type"],
            title=spec["title"],
            description=spec.get("description"),
        )
        ws_id = ws["workstream_identifier"]
        _edge(session, "workstream", ws_id, "workstream_belongs_to_planning_item",
              "planning_item", pi_identifier)
        created_ws.append(ws)
        if prev_ws_id is not None:
            _edge(session, "workstream", ws_id, "blocked_by", "workstream", prev_ws_id)
        prev_ws_id = ws_id
        tasks = spec.get("work_tasks", [])
        for t in tasks:
            wt = work_tasks.create_work_task(
                session,
                title=t["title"],
                area=t["area"],
                description=t.get("description"),
            )
            _edge(session, "work_task", wt["work_task_identifier"],
                  "work_task_belongs_to_workstream", "workstream", ws_id)
            created_wt.append(wt)
        # Scope the phase: Planned → Scoping → Ready (has work) | Not Applicable.
        ws_repo.patch_workstream(session, ws_id, status="Scoping")
        ws_repo.patch_workstream(
            session, ws_id, status="Ready" if tasks else "Not Applicable")
    return {
        "planning_item": pi_identifier,
        "workstreams": created_ws,
        "work_tasks": created_wt,
    }


def finalize_planning(session: Session, release_identifier: str) -> dict:
    """Assert readiness, flip in-scope PIs interactive→ado (AL-4), enter ``ready``.

    The ``architecture_planning → ready`` transition re-enforces the
    planned-completely gate; we surface a clear pre-check first and perform the
    execution-mode flip so the development stage is an autonomous ADO walk of the
    finished prerequisite graph (RB-014 §5.2).
    """
    readiness = planning.planning_readiness(session, release_identifier)
    if not readiness["ready"]:
        raise ConflictError(
            f"release {release_identifier!r} is not planned completely: "
            f"{readiness['missing']}"
        )
    flipped: list[str] = []
    for prj in releases._in_scope_projects(session, release_identifier):
        for pi in releases._in_scope_planning_items(session, prj):
            row = planning_items.get(session, pi)
            if row.get("execution_mode") != "ado":
                planning_items.update(session, pi, execution_mode="ado")
                flipped.append(pi)
    after = releases.transition(session, release_identifier, "ready")
    return {
        "release": after,
        "readiness": readiness,
        "flipped_to_ado": sorted(flipped),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _edge(session, src_t, src_id, relationship, tgt_t, tgt_id) -> None:
    from crmbuilder_v2.access.repositories import references as refs

    refs.create(
        session,
        source_type=src_t,
        source_id=src_id,
        target_type=tgt_t,
        target_id=tgt_id,
        relationship=relationship,
    )
