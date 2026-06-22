"""Deterministic release-stage drivers — the agent layer's substrate-facing spine.

PRJ-033 (PI-217 + PI-218). These functions wrap the deterministic substrate (the
PI-209 Option-A spine) and supply the *plumbing* of the reconciliation and
architecture-planning stages — never the judgment (demands authoring and the
work-task decomposition *spec* are the LLM agents' job, in
:mod:`crmbuilder_v2.scheduler.release_scheduler`). They reimplement no reconcile /
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
    area_specs,
    artifact_versions,
    findings,
    planning_items,
    release_change_sets,
    release_demands,
    release_signoffs,
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
from crmbuilder_v2.access.vocab import SYSTEM_AREA_RANKS

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
    # Persist the reconciled change-set as a durable, reviewable artifact (PI-237 /
    # REQ-285). Refreshed wholesale each run, so it tracks conflict resolutions as
    # they land; once the reconciliation gate opens it is the final set the
    # Reconciliation Review reads. Behaviour-preserving — additive to the existing
    # return shape.
    result["change_set"] = persist_reconciled_change_set(session, release_identifier)
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


def persist_reconciled_change_set(
    session: Session, release_identifier: str
) -> list[dict]:
    """Persist the reconciled change-set as a durable, reviewable artifact (PI-237).

    Computes the post-resolution reconciled delta-sets (the same merge the
    architecture-planning stage consumes) and stores them in the
    ``release_change_sets`` table, replacing any prior snapshot for the release.
    Called at the end of ``run_reconciliation`` so the durable artifact refreshes
    on every reconciliation run; also exposed as a standalone driver so the
    change-set can be (re)materialised on demand. Returns the persisted rows.
    """
    delta_sets = reconciled_delta_sets(session, release_identifier)
    return release_change_sets.persist_change_set(
        session, release_identifier, delta_sets
    )


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

    The decomposition must be a **well-formed phase structure** (REQ-258): at
    most one workstream per delivery phase. A spec that repeats a phase is
    rejected — duplicate, serially cross-chained phases of the same type tangle
    the dev-lane's phase walk and strand the planning item after its first phase
    (the failure a real fleet build surfaced: an architect spec with two
    Design/Develop/Test triples). The substrate enforces this regardless of what
    the planning agent proposes.
    """
    phase_types = [spec["phase_type"] for spec in workstreams]
    duplicates = sorted({p for p in phase_types if phase_types.count(p) > 1})
    if duplicates:
        raise ConflictError(
            f"decomposition of {pi_identifier!r} repeats phase(s) "
            f"{duplicates}: a planning item has at most one workstream per "
            "delivery phase (a well-formed, serially-ordered phase structure)"
        )
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
# Per-area Design fan-out (PI-245 / §4.5, the matrix back half)
# ---------------------------------------------------------------------------


def _area_rank_key(area: str):
    """Sort key: layer rank (storage 1 -> access 2 -> api 3 -> mcp/ui 4), then
    unranked areas (rank None -> last), then alphabetical for a stable order."""
    rank = SYSTEM_AREA_RANKS.get(area)
    return (rank if rank is not None else 10_000, area)


def touched_areas(session: Session, release_identifier: str) -> list[str]:
    """The distinct areas a release touches, in layer-rank order (PI-245, Decision 2).

    Re-aggregates the existing area-tagged Work Tasks of the release's in-scope
    Planning Items by ``area`` — the front half's decomposition is consumed, not
    redone. This is the axis the per-area back half fans Design / Develop / Test out
    on; the order encodes the feed-forward spine (lower rank designed first).
    """
    areas: set[str] = set()
    for prj in releases._in_scope_projects(session, release_identifier):
        for pi in releases._in_scope_planning_items(session, prj):
            for ws in releases._pi_workstreams(session, pi):
                for wt in releases._ws_work_tasks(session, ws):
                    row = work_tasks.get_work_task(session, wt)
                    area = row.get("work_task_area") or row.get("area")
                    if area:
                        areas.add(area)
    return sorted(areas, key=_area_rank_key)


def area_work_tasks(
    session: Session, release_identifier: str, area: str
) -> list[dict]:
    """The release's in-scope Work Tasks in one ``area`` (the Design task's work
    inputs) — across every in-scope Planning Item, regardless of phase."""
    out: list[dict] = []
    for prj in releases._in_scope_projects(session, release_identifier):
        for pi in releases._in_scope_planning_items(session, prj):
            for ws in releases._pi_workstreams(session, pi):
                for wt in releases._ws_work_tasks(session, ws):
                    row = work_tasks.get_work_task(session, wt)
                    if (row.get("work_task_area") or row.get("area")) == area:
                        out.append(row)
    return out


def run_area_design(
    session: Session, release_identifier: str, design_provider
) -> dict:
    """Fan out one Design task per touched area, in layer-rank order (PI-245 / §4.5).

    For each touched area the area's Architect (the injected ``design_provider``
    seam — the ``(area, architect)`` agent) authors the area's implementation +
    testable spec, which is persisted as the area's next ``area_spec`` version. The
    provider is called with the feed-forward context — the area, its Work Tasks, and
    the **lower-rank** areas' just-authored specs (upstream design outputs):

        design_provider({release_identifier, area, work_tasks, prior_area_specs})
          -> {implementation, testable, change_reason?, trigger_kind?}

    Areas are sequenced here by rank; the runtime (Phase 4f) runs rank-independent
    areas in parallel. A deterministic substrate driver — the judgment is the
    provider's; this arranges the calls and persists the specs (mirrors
    ``run_architecture_planning``). Returns the per-area specs persisted, in order.
    """
    areas = touched_areas(session, release_identifier)
    persisted: list[dict] = []
    for area in areas:
        my_rank = SYSTEM_AREA_RANKS.get(area)
        prior = [
            p for p in persisted
            if my_rank is not None
            and (pr := SYSTEM_AREA_RANKS.get(p["area"])) is not None
            and pr < my_rank
        ]
        design = design_provider({
            "release_identifier": release_identifier,
            "area": area,
            "work_tasks": area_work_tasks(session, release_identifier, area),
            "prior_area_specs": prior,
        })
        spec = area_specs.author_spec(
            session, release_identifier, area,
            implementation=design["implementation"],
            testable=design["testable"],
            change_reason=design.get("change_reason", ""),
            trigger_kind=design.get("trigger_kind", "initial"),
        )
        spec["area"] = area  # ensure the key is present for downstream feed-forward
        persisted.append(spec)
    return {"release_identifier": release_identifier, "areas": persisted}


# ---------------------------------------------------------------------------
# Design Review gate (PI-246 / §4.6, the matrix back half)
# ---------------------------------------------------------------------------


def design_review_status(session: Session, release_identifier: str) -> dict:
    """Whether the release has a *fresh* consolidated Design Review sign-off — the
    'reviewed / needs (re-)review' read for the per-area back half (PI-246). A
    revision to any area's spec voids the prior sign-off (the fingerprint is over
    the whole current spec set), so this re-opens review when any area changes."""
    return release_signoffs.signoff_status(session, release_identifier, "design")


def require_design_review_signoff(session: Session, release_identifier: str) -> None:
    """Gate the per-area Develop stage (PI-246 / §4.6): the back half does not proceed
    to Develop until a **fresh** human Design Review sign-off exists over the current
    set of area specs. Raises :class:`ConflictError` otherwise. Enforced by the Develop
    fan-out (PI-245's run_area_design produces the specs; this gates what follows)."""
    if release_signoffs.fresh_signoff(session, release_identifier, "design") is None:
        raise ConflictError(
            f"release {release_identifier!r} cannot enter per-area Develop: no "
            f"current Design Review sign-off over its area specs (record one against "
            f"the design output; a stale sign-off from before a spec revision does "
            f"not count) (PI-246)."
        )


# ---------------------------------------------------------------------------
# Per-area Develop fan-out (PI-247 / §4.7, the matrix back half)
# ---------------------------------------------------------------------------

# The one run-status vocabulary the develop seam reports back (mirrors the
# scheduler's TaskStatus by value; kept as plain strings so the access layer does
# not depend on the scheduler layer). "succeeded" is the only ok status.
_DEVELOP_OK = "succeeded"


def run_area_develop(session: Session, release_identifier: str, develop_provider) -> dict:
    """Fan out one Develop task per touched area, in layer-rank order (PI-247 / §4.7).

    Gated by the Design Review (``require_design_review_signoff``): the back half does
    not build until the area specs are human-approved. For each area in rank order the
    area's Developer (the injected ``(area, developer)`` seam — the runtime that claims
    its Work Tasks in a worktree, builds to the approved spec, self-verifies, and
    merges) is called with the approved spec + the area's Work Tasks + the prior
    (lower-rank) areas' merged outputs (feed-forward):

        develop_provider({release_identifier, area, implementation_spec, testable_spec,
                          work_tasks, prior_area_results}) -> {status, detail?}

    ``status`` is the run-status (``succeeded`` / ``needs_human`` / ``failed``). Areas
    are sequenced here by rank because higher-rank areas build on lower-rank merged
    code; the run **halts** at the first non-``succeeded`` area (downstream depends on
    it — the runtime in Phase 4f parallelises rank-independent areas). A deterministic
    driver: the build is the seam's; this gates, sequences, feeds forward, and
    collects. Returns ``{release_identifier, areas: [...], halted_on, all_succeeded}``.
    """
    require_design_review_signoff(session, release_identifier)
    areas = touched_areas(session, release_identifier)
    results: list[dict] = []
    halted_on: str | None = None
    for area in areas:
        spec = area_specs.current_spec(session, release_identifier, area)
        if spec is None:
            results.append({"area": area, "status": "needs_human",
                            "detail": "no approved area spec to build to"})
            halted_on = area
            break
        my_rank = SYSTEM_AREA_RANKS.get(area)
        prior = [
            r for r in results
            if my_rank is not None
            and (pr := SYSTEM_AREA_RANKS.get(r["area"])) is not None
            and pr < my_rank
        ]
        outcome = develop_provider({
            "release_identifier": release_identifier,
            "area": area,
            "implementation_spec": spec["spec_implementation"],
            "testable_spec": spec["spec_testable"],
            "work_tasks": area_work_tasks(session, release_identifier, area),
            "prior_area_results": prior,
        })
        status = outcome.get("status", "failed")
        results.append({"area": area, "status": status,
                        "detail": outcome.get("detail", "")})
        if status != _DEVELOP_OK:
            halted_on = area
            break
    return {
        "release_identifier": release_identifier,
        "areas": results,
        "halted_on": halted_on,
        "all_succeeded": halted_on is None and bool(areas),
    }


# ---------------------------------------------------------------------------
# Per-area blind Test + bounce (PI-248 / §4.8, the matrix back half)
# ---------------------------------------------------------------------------

_TEST_OK = "succeeded"


def run_area_test(session: Session, release_identifier: str, test_provider) -> dict:
    """Fan out one blind Test task per touched area (PI-248 / §4.8, Decision 4/5).

    For each area the area's Tester (the injected ``(area, tester)`` seam) implements
    the area's **testable spec** and verifies the build's *behaviour* against it —
    **blind**: the seam is given the testable spec + the area's Work Tasks, **not** the
    implementation spec or the Developer's code (blindness enforced at the work-inputs
    level, Decision 4). Areas are independent (each verifies its own spec), so every
    area is tested — the run does not halt; failures are collected.

        test_provider({release_identifier, area, testable_spec, work_tasks})
          -> {status, detail?, bounce_to?}   # bounce_to: "develop" | "design"

    On a non-``succeeded`` area the bounce is **recorded as a coherence finding**
    (Decision 5 — provenance) and routed to ``develop`` (code bug, default) or
    ``design`` (spec gap → an area_spec revision); the scheduler (Phase 4f) acts on
    the bounce. The heavyweight area-reopen is reserved for the outer
    cross-area/post-freeze case, not this inner loop. Returns
    ``{release_identifier, areas: [...], bounced: [...], all_passed}``.
    """
    areas = touched_areas(session, release_identifier)
    results: list[dict] = []
    for area in areas:
        spec = area_specs.current_spec(session, release_identifier, area)
        if spec is None:
            results.append({"area": area, "status": "needs_human",
                            "detail": "no approved area spec to test against",
                            "bounce_to": None, "finding": None})
            continue
        outcome = test_provider({
            "release_identifier": release_identifier,
            "area": area,
            "testable_spec": spec["spec_testable"],  # blind: spec only, not the code
            "work_tasks": area_work_tasks(session, release_identifier, area),
        })
        status = outcome.get("status", "failed")
        entry = {"area": area, "status": status,
                 "detail": outcome.get("detail", ""), "bounce_to": None,
                 "finding": None}
        if status != _TEST_OK:
            bounce_to = outcome.get("bounce_to") or "develop"
            finding = findings.create_finding(
                session,
                type="gap",
                severity="blocking",
                summary=(f"{area} failed blind verification against its testable "
                         f"spec (release {release_identifier})"),
                description=outcome.get("detail") or None,
                notes=f"per-area Test bounce -> {bounce_to} (PI-248, REQ-295)",
            )
            entry["bounce_to"] = bounce_to
            entry["finding"] = finding.get("identifier") or finding.get(
                "finding_identifier")
        results.append(entry)
    bounced = [r for r in results if r["status"] != _TEST_OK]
    return {
        "release_identifier": release_identifier,
        "areas": results,
        "bounced": bounced,
        "all_passed": not bounced and bool(areas),
    }


# ---------------------------------------------------------------------------
# The per-area back half, end-to-end (PI-249 / §4.5-4.8, the matrix back half)
# ---------------------------------------------------------------------------


def run_per_area_development(
    session: Session,
    release_identifier: str,
    *,
    develop_provider,
    test_provider,
    max_rounds: int = 3,
) -> dict:
    """The post-Design-Review per-area Develop → blind Test → bounce loop (PI-249),
    integrating 4d + 4e — the back half's development stage after the design specs are
    authored (``run_area_design``, 4b) and human-approved (the Design Review, 4c).

    Each round runs ``run_area_develop`` then ``run_area_test``:
    - **passed** — Test is clean across all areas → done.
    - **code-bug bounce** (``bounce_to='develop'``) — the next round's Develop fixes
      the bounced area; re-Test. Repeats up to ``max_rounds``.
    - **spec-gap bounce** (``bounce_to='design'``) — returns ``needs_redesign``: a new
      spec + a fresh Design Review are needed (the caller re-runs Design → review →
      this loop). The inner loop never silently re-designs.
    - **develop_blocked** — a Develop halt (a lower-rank area failed / needs_human).
    - **needs_human** — still bouncing after ``max_rounds``.

    Gated by the Design Review via ``run_area_develop`` (which calls
    ``require_design_review_signoff``); unsigned ⇒ ``ConflictError``. A deterministic
    orchestrator over the injected ``(area, developer|tester)`` seams; the worktree
    build + blind verification live in the seams (the scheduler's runtime). Returns
    ``{release_identifier, status, rounds, ...}``.
    """
    rounds: list[dict] = []
    for round_no in range(1, max_rounds + 1):
        dev = run_area_develop(session, release_identifier, develop_provider)
        if not dev["all_succeeded"]:
            rounds.append({"round": round_no, "develop": dev, "test": None})
            return {
                "release_identifier": release_identifier,
                "status": "develop_blocked",
                "halted_on": dev["halted_on"],
                "rounds": rounds,
            }
        test = run_area_test(session, release_identifier, test_provider)
        rounds.append({"round": round_no, "develop": dev, "test": test})
        if test["all_passed"]:
            return {
                "release_identifier": release_identifier,
                "status": "passed",
                "rounds": rounds,
            }
        if any(b.get("bounce_to") == "design" for b in test["bounced"]):
            return {
                "release_identifier": release_identifier,
                "status": "needs_redesign",
                "bounced": test["bounced"],
                "rounds": rounds,
            }
        # all bounces are code bugs → the next round's Develop fixes them, then re-Test.
    return {
        "release_identifier": release_identifier,
        "status": "needs_human",
        "detail": f"still bouncing after {max_rounds} round(s)",
        "rounds": rounds,
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
