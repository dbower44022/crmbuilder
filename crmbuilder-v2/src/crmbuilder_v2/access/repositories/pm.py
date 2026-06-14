"""Project Manager substrate — the Project's dependency-aware PI backlog.

The ADO **Project Manager** (tier 1, agent-delivery-organization-design.md §2 and
§3.1) owns one Project's Planning Item backlog: it watches the PIs and their
``blocked_by`` edges, identifies which are eligible to start (upstream
dependencies satisfied), and **spawns a PI Lead per eligible PI** — independent
PIs (no ``blocked_by`` between them) run concurrently under separate Leads. The
PM does no per-PI planning itself; it sequences and dispatches.

The prioritization and the act of spawning a Lead are the PM *agent's*; the
deterministic dependency/eligibility computation it relies on lives here,
reconstructed from the records (statelessness, §4.4):

- :func:`project_backlog` — every PI in the Project with its status, its
  ``blocked_by`` predecessors and which are unresolved, and an ``eligible`` flag;
  plus the rolled-up ``eligible`` / ``in_flight`` / ``blocked`` / ``resolved``
  partitions and ``all_resolved``.
- :func:`eligible_planning_items` — the eligible subset (deps satisfied, not yet
  started); the PM agent orders these by priority and dispatches Leads.
- :func:`dispatch_planning_item` — hand an eligible PI to a Lead: transition it
  to ``In Progress``, gated on eligibility.

A PI is **eligible** when its status is startable (``Draft`` / ``Decomposed`` /
``Ready``) and every PI it is ``blocked_by`` is ``Resolved``. When a Lead drives a
PI to ``Resolved`` (its close-out ``resolves`` edge), downstream PIs that were
blocked on it become eligible — the next batch the PM dispatches.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import planning_items, projects, references
from crmbuilder_v2.access.vocab import DEFAULT_EXECUTION_MODE, EXECUTION_MODE_RANK

_BELONGS_PROJECT = "planning_item_belongs_to_project"
_BLOCKED_BY = "blocked_by"
_RESOLVED = "Resolved"
# PI statuses a PM may dispatch (not yet started), actively-worked, and terminal.
_STARTABLE = frozenset({"Draft", "Decomposed", "Ready"})
_IN_FLIGHT = frozenset({"In Progress", "In Review"})
_TERMINAL = frozenset({"Resolved", "Cancelled"})
_INTERACTIVE = "interactive"
_ADO_WITH_APPROVAL = "ado_with_approval"


def _effective_mode(pi: dict, project_mode: str) -> str:
    """The PI's effective execution_mode: the more restrictive of its own value
    and its parent Project's (PI-183 / DEC-423, REQ-152). ``ado`` is least
    restrictive, ``interactive`` most. A PI can tighten the gate, never loosen
    it below its Project's."""
    pi_mode = pi.get("execution_mode") or DEFAULT_EXECUTION_MODE
    project_mode = project_mode or DEFAULT_EXECUTION_MODE
    return max((pi_mode, project_mode), key=lambda m: EXECUTION_MODE_RANK[m])


def _is_dispatchable(mode: str, dispatch_approved: bool) -> bool:
    """True if the ADO dispatcher may dispatch an item with this effective mode.

    ``interactive`` is never dispatchable (REQ-153); ``ado_with_approval`` only
    once a human has recorded approval (REQ-155); ``ado`` always."""
    if mode == _INTERACTIVE:
        return False
    if mode == _ADO_WITH_APPROVAL:
        return bool(dispatch_approved)
    return True


def _project_of(session: Session, pi_identifier: str) -> str | None:
    edges = references.list_references(
        session, source_type="planning_item", source_id=pi_identifier,
        target_type="project", relationship_kind=_BELONGS_PROJECT,
    )
    return edges[0]["target_id"] if edges else None


def _project_mode(session: Session, project_id: str | None) -> str:
    if project_id is None:
        return DEFAULT_EXECUTION_MODE
    project = projects.get_project(session, project_id)
    if project is None:
        return DEFAULT_EXECUTION_MODE
    return project.get("project_execution_mode") or DEFAULT_EXECUTION_MODE


def _safe_pi(session: Session, identifier: str) -> dict | None:
    try:
        return planning_items.get(session, identifier)
    except NotFoundError:
        return None


def _project_planning_items(session: Session, project_id: str) -> list[dict]:
    edges = references.list_references(
        session, target_type="project", target_id=project_id,
        relationship_kind=_BELONGS_PROJECT,
    )
    out: list[dict] = []
    for e in edges:
        pi = _safe_pi(session, e["source_id"])
        if pi is not None:
            out.append(pi)
    out.sort(key=lambda p: p["identifier"])
    return out


def _blocked_by(session: Session, pi_identifier: str) -> list[str]:
    edges = references.list_references(
        session, source_type="planning_item", source_id=pi_identifier,
        target_type="planning_item", relationship_kind=_BLOCKED_BY,
    )
    return [e["target_id"] for e in edges]


def _unresolved_blockers(
    session: Session, pi_identifier: str, status_cache: dict[str, str]
) -> list[str]:
    """The PI's ``blocked_by`` predecessors that are not yet ``Resolved``.

    A missing/unknown blocker counts as unresolved (conservative)."""
    unresolved: list[str] = []
    for blocker in _blocked_by(session, pi_identifier):
        status = status_cache.get(blocker)
        if status is None:
            pi = _safe_pi(session, blocker)
            status = pi["status"] if pi is not None else None
            status_cache[blocker] = status or "<unknown>"
        if status != _RESOLVED:
            unresolved.append(blocker)
    return sorted(unresolved)


def project_backlog(session: Session, project_id: str) -> dict:
    """Reconstruct the Project's PI backlog with dependency eligibility (§3.1).

    :raises NotFoundError: the Project does not exist.
    """
    project = projects.get_project(session, project_id)
    if project is None:
        raise NotFoundError("project", project_id)
    project_mode = project.get("project_execution_mode") or DEFAULT_EXECUTION_MODE

    pis = _project_planning_items(session, project_id)
    status_cache = {p["identifier"]: p["status"] for p in pis}

    items: list[dict] = []
    for pi in pis:
        pid = pi["identifier"]
        unresolved = _unresolved_blockers(session, pid, status_cache)
        status = pi["status"]
        mode = _effective_mode(pi, project_mode)
        approved = bool(pi.get("dispatch_approved"))
        startable = status in _STARTABLE and not unresolved
        # PI-183: eligibility now also respects the execution_mode gate —
        # interactive is never eligible (REQ-153), ado_with_approval only when
        # approved (REQ-155).
        eligible = startable and _is_dispatchable(mode, approved)
        interactive = mode == _INTERACTIVE
        pending_approval = (
            startable and mode == _ADO_WITH_APPROVAL and not approved
        )
        items.append({
            "identifier": pid,
            "title": pi.get("title"),
            "status": status,
            "blocked_by": _blocked_by(session, pid),
            "unresolved_blockers": unresolved,
            "execution_mode": mode,
            "dispatch_approved": approved,
            "eligible": eligible,
            "in_flight": status in _IN_FLIGHT,
            "terminal": status in _TERMINAL,
            "interactive": interactive,
            "pending_approval": pending_approval,
        })

    return {
        "project": project_id,
        "project_execution_mode": project_mode,
        "planning_items": items,
        "eligible": [i["identifier"] for i in items if i["eligible"]],
        "in_flight": [i["identifier"] for i in items if i["in_flight"]],
        "blocked": [
            i["identifier"] for i in items
            if i["unresolved_blockers"] and not i["terminal"] and not i["in_flight"]
        ],
        # PI-183 / DEC-425: interactive items (any status) the operator must
        # run by hand — never dispatched by the ADO.
        "interactive": [i["identifier"] for i in items if i["interactive"]],
        # PI-183 / DEC-424: ado_with_approval items otherwise ready but held
        # pending a human approve-dispatch signal.
        "pending_approval": [
            i["identifier"] for i in items if i["pending_approval"]
        ],
        "resolved": [i["identifier"] for i in items if i["status"] == _RESOLVED],
        "all_resolved": bool(items) and all(i["terminal"] for i in items),
    }


def eligible_planning_items(session: Session, project_id: str) -> list[dict]:
    """The PIs eligible to start now (the PM agent prioritizes + dispatches)."""
    backlog = project_backlog(session, project_id)
    eligible = set(backlog["eligible"])
    return [i for i in backlog["planning_items"] if i["identifier"] in eligible]


def dispatch_planning_item(session: Session, pi_identifier: str) -> dict:
    """Hand an eligible PI to a Lead: transition it to ``In Progress``.

    :raises NotFoundError: the PI does not exist.
    :raises ConflictError: the PI is already started/terminal, a ``blocked_by``
        predecessor is not yet ``Resolved``, or its effective execution_mode
        forbids ADO dispatch (interactive, or unapproved ado_with_approval).
    """
    pi = planning_items.get(session, pi_identifier)  # raises if absent
    status = pi["status"]
    if status not in _STARTABLE:
        raise ConflictError(
            f"planning item {pi_identifier!r} is {status!r}; only a startable "
            f"PI (Draft/Decomposed/Ready) can be dispatched."
        )
    unresolved = _unresolved_blockers(session, pi_identifier, {})
    if unresolved:
        raise ConflictError(
            f"planning item {pi_identifier!r} is blocked_by unresolved PI(s) "
            f"{unresolved}; they must be Resolved before a Lead is dispatched."
        )
    # PI-183: the execution_mode gate — the structural backstop that keeps the
    # ADO out of human-only and unapproved work even if a caller bypasses the
    # eligibility query.
    mode = _effective_mode(pi, _project_mode(session, _project_of(session, pi_identifier)))
    if mode == _INTERACTIVE:
        raise ConflictError(
            f"planning item {pi_identifier!r} is execution_mode 'interactive'; "
            f"it must be executed by a human and is never dispatched by the ADO."
        )
    if mode == _ADO_WITH_APPROVAL and not bool(pi.get("dispatch_approved")):
        raise ConflictError(
            f"planning item {pi_identifier!r} is execution_mode "
            f"'ado_with_approval' and not yet approved; a human must approve "
            f"dispatch (POST /planning-items/{pi_identifier}/approve-dispatch) "
            f"before a Lead is dispatched."
        )
    return planning_items.update(session, pi_identifier, status="In Progress")
