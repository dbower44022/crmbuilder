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

_BELONGS_PROJECT = "planning_item_belongs_to_project"
_BLOCKED_BY = "blocked_by"
_RESOLVED = "Resolved"
# PI statuses a PM may dispatch (not yet started), actively-worked, and terminal.
_STARTABLE = frozenset({"Draft", "Decomposed", "Ready"})
_IN_FLIGHT = frozenset({"In Progress", "In Review"})
_TERMINAL = frozenset({"Resolved", "Cancelled"})


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
    if projects.get_project(session, project_id) is None:
        raise NotFoundError("project", project_id)

    pis = _project_planning_items(session, project_id)
    status_cache = {p["identifier"]: p["status"] for p in pis}

    items: list[dict] = []
    for pi in pis:
        pid = pi["identifier"]
        unresolved = _unresolved_blockers(session, pid, status_cache)
        status = pi["status"]
        eligible = status in _STARTABLE and not unresolved
        items.append({
            "identifier": pid,
            "title": pi.get("title"),
            "status": status,
            "blocked_by": _blocked_by(session, pid),
            "unresolved_blockers": unresolved,
            "eligible": eligible,
            "in_flight": status in _IN_FLIGHT,
            "terminal": status in _TERMINAL,
        })

    return {
        "project": project_id,
        "planning_items": items,
        "eligible": [i["identifier"] for i in items if i["eligible"]],
        "in_flight": [i["identifier"] for i in items if i["in_flight"]],
        "blocked": [
            i["identifier"] for i in items
            if i["unresolved_blockers"] and not i["terminal"] and not i["in_flight"]
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
    :raises ConflictError: the PI is already started/terminal, or a
        ``blocked_by`` predecessor is not yet ``Resolved``.
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
    return planning_items.update(session, pi_identifier, status="In Progress")
