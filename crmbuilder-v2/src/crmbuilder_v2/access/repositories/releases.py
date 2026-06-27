"""Release repository — the multi-agent release pipeline keystone (PI-205).

PRJ-031. Backs the ``/releases`` REST endpoints. The Release is a born-early
forming container (REQ-209) whose ``release_status`` is its pipeline stage; the
single guarded mutator :func:`transition` is the only path that changes it,
validating the lifecycle table and running the three gate predicates:

* **freeze** (``development_planning → reconciliation``) — the scope is settled
  (≥1 release-scoped Project) and every in-scope requirement is ``confirmed``;
  stamps ``release_frozen_at`` (§9A/§16.7, REQ-197).
* **planned-completely** (``architecture_planning → ready``) — frozen + every
  in-scope Planning Item decomposed + the in-scope work-task ``blocked_by`` graph
  acyclic (REQ-190).
* **single-occupancy** (``ready → development``) — no other release in a lane
  state, lane-order respected, every ``blocked_by`` release shipped (REQ-189/210).

The frozen-ness *enforcement on other records* is PI-216; this module owns only
the transition + stamp. Composition lives in ``refs``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import (
    PlanningItem,
    Release,
    Requirement,
)
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    RELEASE_BACK_HALF_MODES,
    RELEASE_EXECUTION_MODES,
    RELEASE_LANE_STATUSES,
    RELEASE_STATUS_TRANSITIONS,
    RELEASE_STATUSES,
)

_ENTITY_TYPE = "release"
_IDENTIFIER_PREFIX = "REL"
_IDENTIFIER_RE = re.compile(r"^REL-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {"title", "description", "notes", "lane_order", "execution_mode"}
)
# PI-227: planning-item statuses that mean a project still has pending work. A
# project with any active PI is left ``in_flight`` on ship (its unfinished work
# belongs in a new project, never a silent completion); a project whose PIs are
# all Resolved/Deferred/Cancelled has no pending work and is auto-completed.
_ACTIVE_PI_STATUSES = frozenset(
    {"Draft", "Decomposed", "Ready", "In Progress", "In Review"}
)

# PI-327 / REQ-260 — the retire-not-delete gate. A terminal cancelled/superseded
# reached from a *lane* state (the release actually ran) is reachable only via
# ``abandon()``; a plain ``transition`` to one of these from a lane state is
# refused so a cleanup can never silently destroy a real run's evidence.
_LANE_TERMINAL_GUARD = frozenset({"cancelled", "superseded"})
_TERMINAL_STATUSES = frozenset({"shipped", "cancelled", "superseded"})
# The abandon ``outcome`` → the terminal RELEASE status it maps to. ``shipped`` is
# the ship path, never abandon, so it is deliberately absent.
_ABANDON_OUTCOME_TO_STATUS = {"abandoned": "cancelled", "superseded": "superseded"}

# status value -> per-status lifecycle timestamp column. Only the gated /
# terminal transitions materialise a stamp; the un-gated forward moves do not.
_STATUS_TIMESTAMP = {
    "reconciliation": "release_frozen_at",
    "ready": "release_planned_completely_at",
    "shipped": "release_shipped_at",
    "cancelled": "release_cancelled_at",
    "superseded": "release_superseded_at",
}


def _require_status(status: object) -> str:
    return gov.require_in(status, RELEASE_STATUSES, field="release_status")


def _require_execution_mode(mode: object) -> str:
    return gov.require_in(
        mode, RELEASE_EXECUTION_MODES, field="release_execution_mode"
    )


def _get_row(session: Session, identifier: str) -> Release:
    row = get_by_identifier(session, Release, Release.release_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_releases(
    session: Session, *, include_deleted: bool = False, status: str | None = None
) -> list[dict]:
    stmt = select(Release).order_by(Release.release_identifier)
    if not include_deleted:
        stmt = stmt.where(Release.release_deleted_at.is_(None))
    if status is not None:
        stmt = stmt.where(Release.release_status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_release(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, Release, Release.release_identifier, identifier)
    if row is None:
        return None
    if row.release_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_release_identifier(session: Session) -> str:
    identifiers = session.scalars(select(Release.release_identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def composition(session: Session, identifier: str) -> dict:
    """The release's release-scoped Projects and their Planning Items (derived)."""
    _get_row(session, identifier)
    projects = _in_scope_projects(session, identifier)
    out = []
    for prj in projects:
        pis = _in_scope_planning_items(session, prj)
        out.append({"project_identifier": prj, "planning_items": pis})
    return {"release_identifier": identifier, "projects": out}


# Canonical lifecycle order for the status-counts report (REQ-242). Only statuses
# actually present among the in-scope planning items appear in the output; this
# ordering only makes that output stable and readable (lifecycle, not alphabetic).
_PI_STATUS_ORDER = (
    "Draft",
    "Decomposed",
    "Ready",
    "In Progress",
    "In Review",
    "Resolved",
    "Deferred",
    "Cancelled",
)


def planning_item_status_counts(session: Session, identifier: str) -> dict:
    """Count the release's in-scope planning items per lifecycle status (REQ-242).

    Walks the release scope (``project_belongs_to_release`` →
    ``planning_item_belongs_to_project``) and tallies each in-scope planning
    item by its ``status``. ``status_counts`` covers every status present — a
    status with no in-scope item is omitted, never reported as a zero — ordered
    by the lifecycle sequence for a stable, at-a-glance read of how much release
    work remains and in what state. ``total`` is the in-scope planning-item
    count. 404 when the release does not exist.
    """
    from crmbuilder_v2.access.repositories import planning_items

    _get_row(session, identifier)
    counts: dict[str, int] = {}
    for prj in _in_scope_projects(session, identifier):
        for pi in _in_scope_planning_items(session, prj):
            status = planning_items.get(session, pi)["status"]
            counts[status] = counts.get(status, 0) + 1
    ordered = {
        status: counts[status] for status in _PI_STATUS_ORDER if status in counts
    }
    # Any status outside the known lifecycle order (defensive) is appended sorted.
    for status in sorted(set(counts) - set(_PI_STATUS_ORDER)):
        ordered[status] = counts[status]
    return {
        "release_identifier": identifier,
        "status_counts": ordered,
        "total": sum(ordered.values()),
    }


# ---------------------------------------------------------------------------
# Composition / scope traversal helpers
# ---------------------------------------------------------------------------


def _in_scope_projects(session: Session, release_id: str) -> list[str]:
    edges = gov.inbound_edges(
        session,
        target_type="release",
        target_id=release_id,
        relationship="project_belongs_to_release",
        source_type="project",
    )
    return sorted({e.source_id for e in edges})


def _in_scope_planning_items(session: Session, project_id: str) -> list[str]:
    edges = gov.inbound_edges(
        session,
        target_type="project",
        target_id=project_id,
        relationship="planning_item_belongs_to_project",
        source_type="planning_item",
    )
    return sorted({e.source_id for e in edges})


def _in_scope_requirements(session: Session, pi_id: str) -> list[str]:
    edges = gov.outbound_edges(
        session,
        source_type="planning_item",
        source_id=pi_id,
        relationship="planning_item_implements_requirement",
        target_type="requirement",
    )
    return sorted({e.target_id for e in edges})


# Already-delivered filter (REQ-265): a requirement whose implementing planning
# item has already reached a delivered state must never be planned, designed, or
# built a second time. "Delivered" mirrors the release loop's delivered_statuses.
_DELIVERED_PI_STATUSES: frozenset[str] = frozenset({"In Review", "Resolved"})


def _implementing_planning_items(session: Session, req_id: str) -> list[str]:
    """The planning items that implement ``req_id`` (the reverse of
    ``_in_scope_requirements``)."""
    edges = gov.inbound_edges(
        session,
        target_type="requirement",
        target_id=req_id,
        relationship="planning_item_implements_requirement",
        source_type="planning_item",
    )
    return sorted({e.source_id for e in edges})


def requirement_is_delivered(
    session: Session,
    req_id: str,
    delivered_statuses: frozenset[str] = _DELIVERED_PI_STATUSES,
) -> bool:
    """True if any planning item implementing ``req_id`` has reached a delivered
    state, so the requirement is already built and must be excluded from planning
    (REQ-265). A requirement with no implementing planning item is not delivered."""
    from crmbuilder_v2.access.repositories import planning_items

    for pi in _implementing_planning_items(session, req_id):
        row = planning_items.get(session, pi)
        if row and row.get("status") in delivered_statuses:
            return True
    return False


def pi_has_undelivered_requirements(session: Session, pi_id: str) -> bool:
    """True unless the planning item implements requirements and every one is
    already delivered — i.e. there is genuinely nothing left to build for it
    (REQ-265). A planning item with no traced requirements is left buildable: we
    cannot prove it is done, so we do not suppress it."""
    reqs = _in_scope_requirements(session, pi_id)
    if not reqs:
        return True
    return any(not requirement_is_delivered(session, r) for r in reqs)


def _pi_blocked_by(session: Session, pi_id: str) -> list[str]:
    edges = gov.outbound_edges(
        session,
        source_type="planning_item",
        source_id=pi_id,
        relationship="blocked_by",
        target_type="planning_item",
    )
    return sorted({e.target_id for e in edges})


def freeze_readiness(session: Session, release_identifier: str) -> dict:
    """Per-PI freeze readiness (PI-239 / REQ-285, target-model D14).

    The freeze gate's rule is: every in-scope planning item must be **ready** — its
    requirements confirmed AND no blocker outside this release — **or** have been
    **explicitly deferred** by a human (status ``Deferred``). There is no silent
    auto-defer: a not-ready, not-deferred PI keeps the release from freezing until a
    human readies it or defers it. This is the single source of truth for that rule
    (the gate raises on it; the UI reads it to show what to ready/defer).
    """
    in_scope: set[str] = set()
    for prj in _in_scope_projects(session, release_identifier):
        in_scope.update(_in_scope_planning_items(session, prj))

    items: list[dict] = []
    for pi in sorted(in_scope):
        row = get_by_identifier(session, PlanningItem, PlanningItem.identifier, pi)
        status = row.status if row is not None else None
        deferred = status == "Deferred"
        unconfirmed: list[str] = []
        external_blockers: list[str] = []
        if not deferred:
            for req in _in_scope_requirements(session, pi):
                r = get_by_identifier(
                    session, Requirement, Requirement.requirement_identifier, req
                )
                if r is None or r.requirement_status != "confirmed":
                    unconfirmed.append(req)
            for b in _pi_blocked_by(session, pi):
                if b in in_scope:
                    continue  # an in-release dependency is fine
                br = get_by_identifier(
                    session, PlanningItem, PlanningItem.identifier, b
                )
                if br is None or br.status != "Resolved":
                    external_blockers.append(b)
        ready = (not deferred) and not unconfirmed and not external_blockers
        items.append({
            "planning_item": pi,
            "status": status,
            "deferred": deferred,
            "ready": ready,
            "unconfirmed_requirements": sorted(unconfirmed),
            "external_blockers": sorted(external_blockers),
        })
    not_ready = [i for i in items if not i["deferred"] and not i["ready"]]
    return {
        "release_identifier": release_identifier,
        "items": items,
        "not_ready": not_ready,
        "ready_to_freeze": not not_ready,
    }


def defer_planning_item(
    session: Session, release_identifier: str, pi_identifier: str
) -> dict:
    """Explicitly defer an in-scope planning item out of the release (REQ-285 /
    PI-239) — the deliberate human action that removes a not-ready PI from the
    freeze readiness requirement, in place of a silent auto-defer. Sets the PI's
    status to ``Deferred`` (the existing lifecycle transition). Returns the PI."""
    from crmbuilder_v2.access.repositories import planning_items

    _get_row(session, release_identifier)  # 404 if the release is unknown
    in_scope: set[str] = set()
    for prj in _in_scope_projects(session, release_identifier):
        in_scope.update(_in_scope_planning_items(session, prj))
    if pi_identifier not in in_scope:
        raise ConflictError(
            f"planning item {pi_identifier!r} is not in scope of release "
            f"{release_identifier!r} (no planning_item_belongs_to_project edge to "
            f"a release-scoped Project)."
        )
    return planning_items.update(session, pi_identifier, status="Deferred")


def _pi_workstreams(session: Session, pi_id: str) -> list[str]:
    edges = gov.inbound_edges(
        session,
        target_type="planning_item",
        target_id=pi_id,
        relationship="workstream_belongs_to_planning_item",
        source_type="workstream",
    )
    return sorted({e.source_id for e in edges})


def _ws_work_tasks(session: Session, ws_id: str) -> list[str]:
    edges = gov.inbound_edges(
        session,
        target_type="workstream",
        target_id=ws_id,
        relationship="work_task_belongs_to_workstream",
        source_type="work_task",
    )
    return sorted({e.source_id for e in edges})


# ---------------------------------------------------------------------------
# Gate predicates
# ---------------------------------------------------------------------------


def _check_freeze(session: Session, identifier: str) -> None:
    """Freeze gate (REQ-197 + REQ-285 / PI-239, target-model D14).

    Requires a release-scoped Project, and every in-scope planning item to be
    **ready** (its requirements confirmed AND no blocker outside this release) or
    **explicitly deferred** by a human (status ``Deferred``). No silent auto-defer:
    a not-ready, not-deferred PI blocks the freeze until a human readies or defers
    it.
    """
    projects = _in_scope_projects(session, identifier)
    if not projects:
        raise ConflictError(
            f"release {identifier!r} cannot be frozen: no release-scoped "
            f"Project is attached (project_belongs_to_release)."
        )
    report = freeze_readiness(session, identifier)
    if report["not_ready"]:
        details: list[str] = []
        for item in report["not_ready"]:
            reasons: list[str] = []
            if item["unconfirmed_requirements"]:
                reasons.append(
                    f"requirement(s) not confirmed: {item['unconfirmed_requirements']}"
                )
            if item["external_blockers"]:
                reasons.append(
                    f"blocked by planning item(s) outside this release: "
                    f"{item['external_blockers']}"
                )
            details.append(f"{item['planning_item']} ({'; '.join(reasons)})")
        raise ConflictError(
            f"release {identifier!r} cannot be frozen: in-scope planning item(s) "
            f"not ready — {'; '.join(details)}. Ready each (confirm its "
            f"requirements / clear external blockers) or explicitly defer it "
            f"(set its status to Deferred) (REQ-285)."
        )


def _has_cycle(adjacency: dict[str, set[str]]) -> bool:
    """Return True if the directed graph (node -> its blockers) has a cycle."""
    WHITE, GREY, BLACK = 0, 1, 2
    color = dict.fromkeys(adjacency, WHITE)

    def visit(node: str) -> bool:
        color[node] = GREY
        for nxt in adjacency.get(node, ()):  # noqa: SIM118
            if nxt not in color:
                continue
            if color[nxt] == GREY:
                return True
            if color[nxt] == WHITE and visit(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color[n] == WHITE and visit(n) for n in adjacency)


def _check_planned_completely(session: Session, identifier: str) -> None:
    """Planned-completely gate — frozen + decomposed + sequenced (REQ-190).

    REQ-336 / DEC-661: an **interactive** in-scope planning item is delivered by
    hand, never by the automated pipeline — the ADO is forbidden from decomposing
    it (DEC-425), so it can never have phase workstreams. It is "planned" by being
    hand-executed, so this gate treats it as already planned rather than demanding
    a decomposition it cannot have. A manually-driven release (all in-scope items
    interactive) therefore reaches ``ready`` from its recorded review evidence,
    without automated decomposition; an ADO item still requires its phase plan.

    REQ-331 / PI-294: a ``manual`` execution-mode release is driven entirely by a
    human and is never decomposed into phase workstreams, so this gate requires
    only the freeze scope (frozen + at least one in-scope Planning Item) and skips
    the per-item decomposition and work-task sequencing checks. An ``automated``
    release is unchanged.
    """
    from crmbuilder_v2.access.repositories import pm

    row = _get_row(session, identifier)
    if row.release_frozen_at is None:
        raise ConflictError(
            f"release {identifier!r} cannot be planned-completely: not frozen."
        )
    pis: list[str] = []
    for prj in _in_scope_projects(session, identifier):
        pis.extend(_in_scope_planning_items(session, prj))
    if not pis:
        raise ConflictError(
            f"release {identifier!r} cannot be planned-completely: no in-scope "
            f"Planning Items."
        )
    # A manually-driven release is hand-delivered and never decomposed — the
    # freeze scope above is the whole gate (REQ-331).
    if row.release_execution_mode == "manual":
        return
    work_tasks: set[str] = set()
    for pi in pis:
        # Interactive items are hand-delivered — treat as already planned.
        if pm.is_ado_interactive(session, pi):
            continue
        wss = _pi_workstreams(session, pi)
        if not wss:
            raise ConflictError(
                f"release {identifier!r} cannot be planned-completely: planning "
                f"item {pi!r} is not decomposed (no phase workstreams)."
            )
        for ws in wss:
            work_tasks.update(_ws_work_tasks(session, ws))
    # Sequenced: the in-scope work-task blocked_by graph is acyclic.
    adjacency: dict[str, set[str]] = {wt: set() for wt in work_tasks}
    for wt in work_tasks:
        for e in gov.outbound_edges(
            session,
            source_type="work_task",
            source_id=wt,
            relationship="blocked_by",
            target_type="work_task",
        ):
            if e.target_id in adjacency:
                adjacency[wt].add(e.target_id)
    if _has_cycle(adjacency):
        raise ConflictError(
            f"release {identifier!r} cannot be planned-completely: the in-scope "
            f"work-task blocked_by graph has a cycle."
        )


def _check_single_occupancy(session: Session, identifier: str) -> None:
    """Single-occupancy gate — lane free, ordered, blockers shipped (REQ-189/210)."""
    row = _get_row(session, identifier)
    # 1. no other live release in a lane state.
    others = session.scalars(
        select(Release).where(
            Release.release_identifier != identifier,
            Release.release_deleted_at.is_(None),
            Release.release_status.in_(sorted(RELEASE_LANE_STATUSES)),
        )
    ).all()
    if others:
        raise ConflictError(
            f"release {identifier!r} cannot enter the lane: "
            f"{others[0].release_identifier!r} already holds it "
            f"(status {others[0].release_status!r})."
        )
    # 2. every release this one is blocked_by must be shipped (REQ-210).
    for e in gov.outbound_edges(
        session,
        source_type="release",
        source_id=identifier,
        relationship="blocked_by",
        target_type="release",
    ):
        blocker = get_by_identifier(
            session, Release, Release.release_identifier, e.target_id
        )
        if blocker is not None and blocker.release_status != "shipped":
            raise ConflictError(
                f"release {identifier!r} cannot enter the lane: blocked by "
                f"{e.target_id!r} which has not shipped "
                f"(status {blocker.release_status!r})."
            )
    # 3. lane order — no other ready release with a strictly lower lane_order.
    if row.release_lane_order is not None:
        ahead = session.scalars(
            select(Release).where(
                Release.release_identifier != identifier,
                Release.release_deleted_at.is_(None),
                Release.release_status == "ready",
                Release.release_lane_order.is_not(None),
                Release.release_lane_order < row.release_lane_order,
            )
        ).all()
        if ahead:
            raise ConflictError(
                f"release {identifier!r} cannot enter the lane: "
                f"{ahead[0].release_identifier!r} is earlier in lane order "
                f"({ahead[0].release_lane_order} < {row.release_lane_order})."
            )


def _check_qa_passed(session: Session, identifier: str) -> None:
    """Release-level QA gate (PI-206, §8) — QA must have passed to leave qa."""
    row = _get_row(session, identifier)
    if row.release_qa_passed_at is None:
        raise ConflictError(
            f"release {identifier!r} cannot leave qa: release-level QA has not "
            f"passed (POST /releases/{identifier}/qa-pass first)."
        )


def _check_test_passed(session: Session, identifier: str) -> None:
    """Release-level test gate (PI-206, §8) — tests must pass to leave testing."""
    row = _get_row(session, identifier)
    if row.release_test_passed_at is None:
        raise ConflictError(
            f"release {identifier!r} cannot leave testing: release-level testing "
            f"has not passed (POST /releases/{identifier}/test-pass first)."
        )


def _check_no_open_conflicts(session: Session, identifier: str) -> None:
    """Reconciliation gate (PI-215, RC-1) — no open model conflict may remain."""
    from crmbuilder_v2.access.repositories import reconciliation

    if reconciliation.has_open_conflicts(session, identifier):
        raise ConflictError(
            f"release {identifier!r} cannot leave reconciliation: it has open "
            f"model conflict(s); resolve them (governed decision) first (RC-1)."
        )


def _check_revalidations_complete(session: Session, identifier: str) -> None:
    """Cascade gate (PI-213, RW4) — every reopened-area downstream re-validated."""
    from crmbuilder_v2.access import reopen

    outstanding = reopen.outstanding_revalidations(session, identifier)
    if outstanding:
        raise ConflictError(
            f"release {identifier!r} cannot ship: area(s) {sorted(outstanding)} "
            f"downstream of a reopen have not re-validated (RW4 — no exemption)."
        )


def _require_fresh_review_signoff(
    session: Session, identifier: str, stage: str
) -> None:
    """Human-review gate (PI-238 / REQ-285) — a *fresh* sign-off must exist for the
    stage. Fresh = the sign-off's captured fingerprint matches the stage's current
    output, so a re-run that changed the output forces a re-review."""
    from crmbuilder_v2.access.repositories import release_signoffs

    if release_signoffs.fresh_signoff(session, identifier, stage) is None:
        raise ConflictError(
            f"release {identifier!r} cannot leave {stage}: no current human review "
            f"sign-off (record one against the {stage} output; a stale sign-off "
            f"from before the output changed does not count) (PI-238)."
        )


def _check_reconciliation_review(session: Session, identifier: str) -> None:
    """Reconciliation gate — no open conflicts (RC-1) AND a fresh human review
    sign-off of the reconciled change-set (PI-238)."""
    _check_no_open_conflicts(session, identifier)
    _require_fresh_review_signoff(session, identifier, "reconciliation")


def _check_architecture_planning_review(session: Session, identifier: str) -> None:
    """Architecture-planning gate — planned-completely (REQ-190) AND a fresh human
    review sign-off of the authored designs (PI-238)."""
    _check_planned_completely(session, identifier)
    _require_fresh_review_signoff(session, identifier, "architecture_planning")


def _all_in_scope_pis_resolved(session: Session, identifier: str) -> bool:
    """True when the release has at least one in-scope Planning Item and every one
    of them is ``Resolved`` (REQ-333 — the manual-release auto-ship condition)."""
    from crmbuilder_v2.access.models import PlanningItem

    pis: list[str] = []
    for prj in _in_scope_projects(session, identifier):
        pis.extend(_in_scope_planning_items(session, prj))
    if not pis:
        return False
    statuses = session.scalars(
        select(PlanningItem.status).where(PlanningItem.identifier.in_(sorted(set(pis))))
    ).all()
    return all(s == "Resolved" for s in statuses)


def _check_ship_approval(session: Session, identifier: str) -> None:
    """Ship gate (PI-260 / REQ-299) — the reopen-cascade revalidations complete (RW4)
    AND a fresh human **Ship Approval** sign-off, symmetric to freeze. Fresh = the
    sign-off's captured fingerprint matches the current shippable state (the QA + test
    pass stamps + the introduced artifact versions), so any change after approval
    voids it and forces a re-approval.

    REQ-333 / PI-295: for a ``manual`` execution-mode release, the ship approval
    auto-records once every in-scope Planning Item is ``Resolved`` — the human
    driver is not forced to hand-author the final approval. The earlier
    reconciliation and architecture human reviews are unaffected and still
    required. An ``automated`` release is unchanged: it always needs an explicit
    human ship sign-off."""
    from crmbuilder_v2.access.repositories import release_signoffs

    _check_revalidations_complete(session, identifier)
    if release_signoffs.fresh_signoff(session, identifier, "ship") is None:
        row = _get_row(session, identifier)
        if row.release_execution_mode == "manual" and _all_in_scope_pis_resolved(
            session, identifier
        ):
            release_signoffs.create_signoff(
                session,
                identifier,
                stage="ship",
                reviewer="manual-release",
                attestation=(
                    "Auto-recorded ship approval for a manual release: every "
                    "in-scope Planning Item is resolved (REQ-333)."
                ),
            )
            return
        raise ConflictError(
            f"release {identifier!r} cannot ship: no current human ship approval "
            f"(record a fresh ship sign-off against the shippable state; a stale "
            f"approval from before that state changed does not count) (PI-260)."
        )


_GATE_PREDICATES = {
    ("development_planning", "reconciliation"): _check_freeze,
    ("reconciliation", "architecture_planning"): _check_reconciliation_review,
    ("architecture_planning", "ready"): _check_architecture_planning_review,
    ("ready", "development"): _check_single_occupancy,
    ("qa", "testing"): _check_qa_passed,
    ("testing", "deployment"): _check_test_passed,
    ("deployment", "shipped"): _check_ship_approval,
}


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(
    identifier, title, description, notes, status, lane_order, execution_mode
) -> Release:
    return Release(
        release_identifier=identifier,
        release_title=title,
        release_description=description,
        release_notes=notes,
        release_status=status,
        release_lane_order=lane_order,
        release_execution_mode=execution_mode,
    )


def _insert_with_autoassign(
    session, title, description, notes, status, lane_order, execution_mode
):
    candidate = next_release_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(
            candidate, title, description, notes, status, lane_order, execution_mode
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique release identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_release(
    session: Session,
    *,
    title: str,
    description: str,
    notes: str | None = None,
    status: str = "preliminary_planning",
    lane_order: int | None = None,
    execution_mode: str = "automated",
    identifier: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    """Create a Release. Born early in ``preliminary_planning`` (REQ-209)."""
    title = gov.require_nonempty(title, field="release_title")
    description = gov.require_nonempty(description, field="release_description")
    if status is None:
        status = "preliminary_planning"
    _require_status(status)
    execution_mode = _require_execution_mode(execution_mode)

    if identifier is None:
        row = _insert_with_autoassign(
            session, title, description, notes, status, lane_order, execution_mode
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="release_identifier",
            example="REL-001",
        )
        if (
            get_by_identifier(
                session, Release, Release.release_identifier, identifier
            )
            is not None
        ):
            raise ConflictError(f"release {identifier!r} already exists")
        row = _new_row(
            identifier, title, description, notes, status, lane_order, execution_mode
        )
        session.add(row)
        session.flush()

    gov.apply_reference_list(session, references)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.release_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def _reject_missing_correction_edge(session: Session, identifier: str) -> None:
    """Raise 422 when a release reaches ``superseded`` without a correcting successor.

    A release expresses supersession through *correction*, not a generic
    ``supersedes`` edge: :func:`open_correction_release` creates
    ``new -release_corrects_release-> prior`` and never an outbound ``supersedes``
    edge. So a superseded release must carry an inbound ``release_corrects_release``
    edge — some correction release corrects it. This is the release-specific analogue
    of :func:`gov.reject_missing_supersedes_edge` (which stays correct for the other
    entity types and is deliberately not used here). The check is shared by the plain
    ``→ superseded`` transition and the ``abandon(outcome="superseded")`` path — a
    superseded run must always have a correction, so the ``_via_abandon`` bypass does
    not skip it.
    """
    edges = gov.inbound_edges(
        session,
        target_type=_ENTITY_TYPE,
        target_id=identifier,
        relationship="release_corrects_release",
        source_type=_ENTITY_TYPE,
    )
    if not edges:
        raise UnprocessableError(
            [
                FieldError(
                    "release_status",
                    "supersession_requires_correction_edge",
                    f"release {identifier!r} can only be superseded when a correction "
                    f"release corrects it (release_corrects_release); open one via "
                    f"open_correction_release first.",
                )
            ]
        )


def transition(
    session: Session, identifier: str, to_status: str, *, actor: str | None = None,
    _via_abandon: bool = False,
) -> dict:
    """The single guarded mutator for ``release_status`` (PI-205).

    Validates ``(from, to)`` against :data:`RELEASE_STATUS_TRANSITIONS`, runs the
    matching gate predicate (freeze / planned-completely / single-occupancy),
    stamps the lifecycle timestamp, and writes. ``actor`` is accepted for the
    deliberate-act record (role enforcement is RBAC's job — off by default).

    **The retire-not-delete gate (PI-327 / REQ-260).** A release that has *entered
    a lane* (its current status is in :data:`RELEASE_LANE_STATUSES` — it actually
    ran) may reach a terminal ``cancelled`` / ``superseded`` only through
    :func:`abandon`, which preserves the run's scope edges and phase workstreams as
    evidence. A *direct* transition to one of those terminals from a lane state is
    refused here; :func:`abandon` performs the same move through the internal
    ``_via_abandon`` bypass (which additionally skips the cancel-time
    decomposition clear, so the phase records survive). A *pre-lane* release (never
    ran) is unaffected — it has nothing to preserve and may plainly cancel/supersede.
    ``_via_abandon`` is private to :func:`abandon`; callers never pass it.
    """
    to_status = _require_status(to_status)
    row = _get_row(session, identifier)
    from_status = row.release_status
    before = to_dict(row)
    if to_status == from_status:
        return before
    gov.check_transition(from_status, to_status, RELEASE_STATUS_TRANSITIONS)

    # PI-327 / REQ-260: a lane-entered release can only reach a terminal through
    # the evidence-preserving abandon path.
    if (
        to_status in _LANE_TERMINAL_GUARD
        and from_status in RELEASE_LANE_STATUSES
        and not _via_abandon
    ):
        raise ConflictError(
            f"release {identifier!r} is {from_status!r} — it has entered a lane and "
            f"actually ran, so it can reach {to_status!r} only through abandon "
            f"(POST /releases/{identifier}/abandon), which preserves the run's scope "
            f"and phase records (REQ-260). A direct transition would risk destroying "
            f"that evidence."
        )

    gate = _GATE_PREDICATES.get((from_status, to_status))
    if gate is not None:
        gate(session, identifier)

    if to_status == "superseded":
        _reject_missing_correction_edge(session, identifier)

    row.release_status = to_status
    gov.set_status_timestamp(row, to_status, _STATUS_TIMESTAMP)
    # PI-206: a rework bounce-back to development invalidates the release-level
    # QA/test passes — re-QA and re-test are required on the way back up.
    if to_status == "development" and from_status in RELEASE_LANE_STATUSES:
        row.release_qa_passed_at = None
        row.release_test_passed_at = None
    # PI-227: shipping is the in-scope projects' full delivery — complete each
    # one whose work is done. Runs inside the ship transaction so the project
    # status and the ``release_shipped_at`` stamp commit atomically.
    if to_status == "shipped":
        _complete_delivered_projects(session, identifier)
    # REQ-275: cancelling a release clears its planning items' phase plans, so a
    # later run never inherits a stale decomposition. Runs inside the cancel
    # transaction. PI-327 / REQ-264: an abandon NEVER clears — preserving the phase
    # workstreams is the whole point of retire-not-delete, so the abandon bypass
    # skips the clear and leaves the failed decomposition attached as evidence.
    if to_status == "cancelled" and not _via_abandon:
        _clear_decompositions(session, identifier)
    session.flush()

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def _complete_delivered_projects(
    session: Session, release_identifier: str
) -> list[str]:
    """Complete each in-scope project whose work is fully delivered (PI-227).

    Called from the ``deployment → shipped`` transition. A project is completed
    (``in_flight → complete``) when it is currently ``in_flight`` and none of
    its planning items is still active (active = Draft/Decomposed/Ready/
    In Progress/In Review). Deferred/Cancelled/Resolved are decided
    dispositions, so a project carrying only those has no pending work — and
    ``project_belongs_to_release`` is single-membership, so the ship is the
    project's full delivery. A project with an active PI is deliberately left
    ``in_flight``: its unfinished work belongs in a new project, never a silent
    completion. Returns the identifiers completed.
    """
    from crmbuilder_v2.access.repositories import planning_items, projects

    completed: list[str] = []
    for project_id in _in_scope_projects(session, release_identifier):
        proj = projects.get_project(session, project_id)
        if proj.get("project_status") != "in_flight":
            continue
        pi_ids = _in_scope_planning_items(session, project_id)
        if any(
            planning_items.get(session, pi)["status"] in _ACTIVE_PI_STATUSES
            for pi in pi_ids
        ):
            continue
        projects.patch_project(session, project_id, status="complete")
        completed.append(project_id)
    return completed


def _clear_decompositions(
    session: Session, release_identifier: str
) -> list[str]:
    """Clear the phase plans of a cancelled release's planning items (REQ-275).

    For every in-scope planning item, delete each workstream's work tasks and the
    workstream itself, removing the ``work_task_belongs_to_workstream``,
    ``blocked_by`` and ``workstream_belongs_to_planning_item`` edges so the
    edge-based :func:`_pi_workstreams` no longer returns them — a later run sees
    no leftover decomposition and re-plans from scratch. Returns the cleared
    workstream identifiers.
    """
    from crmbuilder_v2.access.repositories import (
        references,
        work_tasks,
        workstreams,
    )

    cleared: list[str] = []
    for prj in _in_scope_projects(session, release_identifier):
        for pi in _in_scope_planning_items(session, prj):
            for ws in _pi_workstreams(session, pi):
                for wt in _ws_work_tasks(session, ws):
                    references.delete(
                        session, source_type="work_task", source_id=wt,
                        target_type="workstream", target_id=ws,
                        relationship="work_task_belongs_to_workstream",
                        _skip_cardinality_check=True,
                    )
                    work_tasks.delete_work_task(session, wt)
                for blocker in gov.outbound_edges(
                    session, source_type="workstream", source_id=ws,
                    relationship="blocked_by", target_type="workstream",
                ):
                    references.delete(
                        session, source_type="workstream", source_id=ws,
                        target_type="workstream", target_id=blocker.target_id,
                        relationship="blocked_by", _skip_cardinality_check=True,
                    )
                references.delete(
                    session, source_type="workstream", source_id=ws,
                    target_type="planning_item", target_id=pi,
                    relationship="workstream_belongs_to_planning_item",
                    _skip_cardinality_check=True,
                )
                workstreams.delete_workstream(session, ws)
                cleared.append(ws)
    return cleared


def _release_workstreams(session: Session, release_identifier: str) -> list:
    """Every phase-workstream row attached to the release's in-scope planning items.

    Down-traverses release → projects → planning items → workstreams (mirroring
    :func:`coordination._work_tasks_of_release` one level up), resolving each
    ``WSK-`` identifier to its row so :func:`abandon` can snapshot the per-phase
    terminal status at close.
    """
    from crmbuilder_v2.access.models import Workstream

    rows: list = []
    for prj in _in_scope_projects(session, release_identifier):
        for pi in _in_scope_planning_items(session, prj):
            for ws in _pi_workstreams(session, pi):
                row = get_by_identifier(
                    session, Workstream, Workstream.workstream_identifier, ws
                )
                if row is not None:
                    rows.append(row)
    return rows


def abandon(
    session: Session,
    identifier: str,
    *,
    reason: str,
    halt_point: str | None = None,
    cause_code: str | None = None,
    outcome: str = "abandoned",
) -> dict:
    """Retire a run that actually ran, preserving its evidence (PI-327 / REQ-260).

    The *only* sanctioned cleanup path for a release that has entered a lane. In one
    atomic transaction it:

    1. writes a born-terminal ``release_run`` outcome record (the PI-326 primitive)
       capturing a snapshot of the run at close — its ``scope`` (the in-scope
       projects + planning items, from :func:`composition`), its ``phases_run``
       (each phase workstream and its current/terminal status), the ``halt_point``,
       the ``cause`` (= ``reason``), the ``cause_code``, and the identifiers of any
       ``finding`` rows linked to the run's phase workstreams;
    2. transitions the release to its terminal status (``abandoned`` → ``cancelled``,
       ``superseded`` → ``superseded``) through the internal ``_via_abandon`` bypass;
    3. **explicitly preserves the evidence** — it does *not* delete the
       ``project_belongs_to_release`` scope edges or the phase workstreams (the
       bypass skips :func:`_clear_decompositions`). They remain attached as the run's
       record (REQ-264). A re-attempt is a *new* run that builds a fresh
       decomposition, leaving the failed set as evidence.

    :param identifier: the release to abandon (must exist).
    :param reason: free-text cause for the abandon (stored as the run's ``cause``).
    :param halt_point: the stage/phase the run stopped at (e.g. ``development``).
    :param cause_code: an optional structured cause code (e.g.
        ``malformed_decomposition``).
    :param outcome: ``abandoned`` (default → ``cancelled``) or ``superseded``;
        ``shipped`` is the ship path, not abandon, and is rejected.
    :returns: ``{"release": <release dict>, "run": <release_run dict>}``.
    :raises NotFoundError: the release does not exist.
    :raises UnprocessableError: ``outcome`` is not ``abandoned`` / ``superseded``,
        or ``reason`` is empty.
    :raises ConflictError: the release never entered a lane (a pre-lane release
        never ran — cancel/supersede it with a plain transition instead) or is
        already terminal (a closed run cannot be abandoned again).
    """
    from crmbuilder_v2.access.repositories import release_runs

    row = _get_row(session, identifier)  # 404 if unknown
    reason = gov.require_nonempty(reason, field="reason")
    if outcome not in _ABANDON_OUTCOME_TO_STATUS:
        raise UnprocessableError(
            [
                FieldError(
                    "outcome",
                    "invalid_value",
                    f"abandon outcome must be one of "
                    f"{sorted(_ABANDON_OUTCOME_TO_STATUS)}; 'shipped' is the ship "
                    f"path, not abandon",
                )
            ]
        )
    from_status = row.release_status
    if from_status in _TERMINAL_STATUSES:
        raise ConflictError(
            f"release {identifier!r} is already terminal ({from_status!r}); a closed "
            f"run cannot be abandoned again."
        )
    if from_status not in RELEASE_LANE_STATUSES:
        raise ConflictError(
            f"release {identifier!r} is {from_status!r} and never entered a lane — it "
            f"did not run, so there is no run evidence to preserve. Cancel or "
            f"supersede it with a plain transition instead (abandon is gated on "
            f"'did it run', REQ-260)."
        )

    # Snapshot the run at close (design §3.2/§3.3). The records are preserved, never
    # deleted, so this snapshot is a robustness backstop captured BEFORE the move.
    snapshot_scope = {"projects": composition(session, identifier)["projects"]}
    workstream_rows = _release_workstreams(session, identifier)
    phases_run = [
        {
            "workstream": w.workstream_identifier,
            "phase_type": w.workstream_phase_type,
            "status": w.workstream_status,
        }
        for w in workstream_rows
    ]
    # Best-effort: the findings linked to the run's phase workstreams
    # (finding -finding_relates_to-> workstream), de-duplicated, order-preserved.
    finding_ids: list[str] = []
    for w in workstream_rows:
        for e in gov.inbound_edges(
            session,
            target_type="workstream",
            target_id=w.workstream_identifier,
            relationship="finding_relates_to",
            source_type="finding",
        ):
            finding_ids.append(e.source_id)
    finding_ids = list(dict.fromkeys(finding_ids))

    # 1. write the born-terminal run-outcome record.
    run = release_runs.record(
        session,
        release_identifier=identifier,
        outcome=outcome,
        scope=snapshot_scope,
        phases_run=phases_run,
        halt_point=halt_point,
        cause=reason,
        cause_code=cause_code,
        finding_identifiers=finding_ids,
    )
    # 2. transition to the terminal status through the evidence-preserving bypass —
    #    same transaction → record + transition land atomically (or neither does).
    release = transition(
        session, identifier, _ABANDON_OUTCOME_TO_STATUS[outcome], _via_abandon=True
    )
    return {"release": release, "run": run}


def _record_pass(
    session: Session, identifier: str, *, require_status: str, column: str
) -> dict:
    row = _get_row(session, identifier)
    if row.release_status != require_status:
        raise ConflictError(
            f"release {identifier!r} is {row.release_status!r}, not "
            f"{require_status!r}; the pass can only be recorded during that stage."
        )
    before = to_dict(row)
    setattr(row, column, datetime.now(UTC))
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def qa_pass(session: Session, identifier: str) -> dict:
    """Record the release-level QA pass (PI-206, §8). Requires status ``qa``."""
    return _record_pass(
        session, identifier, require_status="qa", column="release_qa_passed_at"
    )


def test_pass(session: Session, identifier: str) -> dict:
    """Record the release-level test pass (PI-206, §8). Requires ``testing``."""
    return _record_pass(
        session, identifier, require_status="testing",
        column="release_test_passed_at",
    )


def set_back_half(session: Session, identifier: str, mode: str) -> dict:
    """Set the release's back-half mode (PI-249 / Decision 3): ``per_pi`` or
    ``per_area``. The durable switch the scheduler reads to route the development
    stage; default ``per_pi`` until a release is deliberately opted into per_area."""
    mode = gov.require_in(mode, RELEASE_BACK_HALF_MODES, field="release_back_half")
    row = _get_row(session, identifier)
    before = to_dict(row)
    row.release_back_half = mode
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def set_lane_order(session: Session, identifier: str, order: int | None) -> dict:
    row = _get_row(session, identifier)
    before = to_dict(row)
    row.release_lane_order = order
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def patch_release(
    session: Session, identifier: str, *, references: list[dict] | None = None, **fields
) -> dict:
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown patchable fields: {sorted(unknown)} "
                    f"(status changes go through /transition)",
                )
            ]
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    gov.apply_reference_list(session, references)

    if "title" in fields:
        row.release_title = gov.require_nonempty(fields["title"], field="release_title")
    if "description" in fields:
        row.release_description = gov.require_nonempty(
            fields["description"], field="release_description"
        )
    if "notes" in fields:
        row.release_notes = fields["notes"]
    if "lane_order" in fields:
        row.release_lane_order = fields["lane_order"]
    if "execution_mode" in fields:
        # The automated/manual choice is locked once the release enters the
        # exclusive lane (development..deployment) or reaches a terminal state —
        # flipping it mid-flight would leave the lane gates inconsistent with the
        # work already done. It is freely settable in the pre-lane planning stages.
        if row.release_status in RELEASE_LANE_STATUSES or row.release_status in (
            "shipped",
            "cancelled",
            "superseded",
        ):
            raise ConflictError(
                f"release {identifier!r} execution_mode is locked at status "
                f"{row.release_status!r}; set it before the release enters the "
                f"development lane."
            )
        row.release_execution_mode = _require_execution_mode(fields["execution_mode"])

    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


_FROZEN_OPEN_STATUSES = frozenset({"preliminary_planning", "development_planning"})


def open_correction_release(
    session: Session,
    prior_identifier: str,
    *,
    title: str,
    description: str,
    notes: str | None = None,
) -> dict:
    """Open a new release that corrects a frozen prior (PI-211, RW1).

    A frozen plan is never reopened; corrections go to a new release. Creates a
    successor in ``preliminary_planning`` linked ``new -release_corrects_release->
    prior``. ``prior`` must be frozen (past ``development_planning``) — correcting
    a still-open release is rejected (just edit it).
    """
    prior = _get_row(session, prior_identifier)
    if prior.release_status in _FROZEN_OPEN_STATUSES:
        raise ConflictError(
            f"release {prior_identifier!r} is {prior.release_status!r} (not yet "
            f"frozen); edit it directly rather than opening a correction release "
            f"(RW1 applies only to frozen plans)."
        )
    new = create_release(session, title=title, description=description, notes=notes)
    from crmbuilder_v2.access.repositories import references

    references.create(
        session,
        source_type=_ENTITY_TYPE,
        source_id=new["release_identifier"],
        target_type=_ENTITY_TYPE,
        target_id=prior_identifier,
        relationship="release_corrects_release",
    )
    return new


def delete_release(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.release_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.release_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after
