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
    Release,
    Requirement,
)
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    RELEASE_LANE_STATUSES,
    RELEASE_STATUS_TRANSITIONS,
    RELEASE_STATUSES,
)

_ENTITY_TYPE = "release"
_IDENTIFIER_PREFIX = "REL"
_IDENTIFIER_RE = re.compile(r"^REL-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {"title", "description", "notes", "lane_order"}
)

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
    """Freeze gate — settled scope of confirmed requirements (REQ-197)."""
    projects = _in_scope_projects(session, identifier)
    if not projects:
        raise ConflictError(
            f"release {identifier!r} cannot be frozen: no release-scoped "
            f"Project is attached (project_belongs_to_release)."
        )
    unconfirmed: list[str] = []
    for prj in projects:
        for pi in _in_scope_planning_items(session, prj):
            for req in _in_scope_requirements(session, pi):
                row = get_by_identifier(
                    session, Requirement, Requirement.requirement_identifier, req
                )
                if row is None or row.requirement_status != "confirmed":
                    unconfirmed.append(req)
    if unconfirmed:
        raise ConflictError(
            f"release {identifier!r} cannot be frozen: in-scope requirement(s) "
            f"not confirmed: {sorted(set(unconfirmed))}."
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
    """Planned-completely gate — frozen + decomposed + sequenced (REQ-190)."""
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
    work_tasks: set[str] = set()
    for pi in pis:
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


_GATE_PREDICATES = {
    ("development_planning", "reconciliation"): _check_freeze,
    ("reconciliation", "architecture_planning"): _check_no_open_conflicts,
    ("architecture_planning", "ready"): _check_planned_completely,
    ("ready", "development"): _check_single_occupancy,
    ("qa", "testing"): _check_qa_passed,
    ("testing", "deployment"): _check_test_passed,
}


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def _new_row(identifier, title, description, notes, status, lane_order) -> Release:
    return Release(
        release_identifier=identifier,
        release_title=title,
        release_description=description,
        release_notes=notes,
        release_status=status,
        release_lane_order=lane_order,
    )


def _insert_with_autoassign(session, title, description, notes, status, lane_order):
    candidate = next_release_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, title, description, notes, status, lane_order)
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
    identifier: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    """Create a Release. Born early in ``preliminary_planning`` (REQ-209)."""
    title = gov.require_nonempty(title, field="release_title")
    description = gov.require_nonempty(description, field="release_description")
    if status is None:
        status = "preliminary_planning"
    _require_status(status)

    if identifier is None:
        row = _insert_with_autoassign(
            session, title, description, notes, status, lane_order
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
        row = _new_row(identifier, title, description, notes, status, lane_order)
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


def transition(
    session: Session, identifier: str, to_status: str, *, actor: str | None = None
) -> dict:
    """The single guarded mutator for ``release_status`` (PI-205).

    Validates ``(from, to)`` against :data:`RELEASE_STATUS_TRANSITIONS`, runs the
    matching gate predicate (freeze / planned-completely / single-occupancy),
    stamps the lifecycle timestamp, and writes. ``actor`` is accepted for the
    deliberate-act record (role enforcement is RBAC's job — off by default).
    """
    to_status = _require_status(to_status)
    row = _get_row(session, identifier)
    from_status = row.release_status
    before = to_dict(row)
    if to_status == from_status:
        return before
    gov.check_transition(from_status, to_status, RELEASE_STATUS_TRANSITIONS)

    gate = _GATE_PREDICATES.get((from_status, to_status))
    if gate is not None:
        gate(session, identifier)

    if to_status == "superseded":
        gov.reject_missing_supersedes_edge(
            session, entity_type=_ENTITY_TYPE, identifier=identifier
        )

    row.release_status = to_status
    gov.set_status_timestamp(row, to_status, _STATUS_TIMESTAMP)
    # PI-206: a rework bounce-back to development invalidates the release-level
    # QA/test passes — re-QA and re-test are required on the way back up.
    if to_status == "development" and from_status in RELEASE_LANE_STATUSES:
        row.release_qa_passed_at = None
        row.release_test_passed_at = None
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
