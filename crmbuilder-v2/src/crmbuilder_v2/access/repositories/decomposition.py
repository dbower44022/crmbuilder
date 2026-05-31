"""Structural decomposition of a Planning Item into phase Workstreams.

The ADO **structural step** (agent-delivery-organization-design.md §3.2 step 1
and §4.1): given a Planning Item, create **every** phase Workstream — one per
value in :data:`PHASE_SEQUENCE`, in canonical order — and chain them with serial
``blocked_by`` gates (each phase ``blocked_by`` the prior). This is the
generalist's *only* job; scope judgment (which phases have work) belongs to the
phase specialists later, expressed as ``Not Applicable`` on an evaluated-empty
Workstream (§4.1/§4.3), never as an omitted phase here.

The decomposer is deliberately dumb and total: it always creates all six
Workstreams in ``Planned`` status, wires each one's
``workstream_belongs_to_planning_item`` edge to the PI, and links consecutive
phases with ``blocked_by`` so the Lead gets serial gate signals (§5, decision 5).
It is **not** idempotent-on-re-run: a second decomposition of the same PI is a
bug (double-planning), so it raises :class:`ConflictError` if the PI already has
any phase Workstream.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.repositories import (
    planning_items,
    references,
    workstreams,
)

# Canonical phase order (design §4.1, resolved decision 8). The Lead's
# feed-forward planning loop (§3.2) walks this exact sequence, each phase
# scoping against the accumulated output of the prior ones — so the
# ``blocked_by`` chain mirrors it.
PHASE_SEQUENCE: tuple[str, ...] = (
    "Architecture",
    "Development",
    "Testing",
    "Documentation",
    "Data Migration",
    "Deployment",
)

_BELONGS_KIND = "workstream_belongs_to_planning_item"


def existing_phase_workstreams(session: Session, pi_identifier: str) -> list[str]:
    """Return the identifiers of Workstreams already belonging to ``pi``."""
    edges = references.list_references(
        session,
        target_type="planning_item",
        target_id=pi_identifier,
        relationship_kind=_BELONGS_KIND,
    )
    return [e["source_id"] for e in edges]


def decompose_planning_item(
    session: Session, pi_identifier: str
) -> list[dict]:
    """Create all six phase Workstreams for ``pi_identifier`` and gate them.

    :param session: open SQLAlchemy session.
    :param pi_identifier: the ``PI-NNN`` to decompose; must exist.
    :returns: the created Workstream dicts in :data:`PHASE_SEQUENCE` order.
    :raises NotFoundError: the Planning Item does not exist.
    :raises ConflictError: the PI already has at least one phase Workstream
        (decomposition is a once-only structural step; re-running it would
        double-plan the PI).
    """
    # PI must exist — get() raises NotFoundError otherwise.
    pi = planning_items.get(session, pi_identifier)

    already = existing_phase_workstreams(session, pi_identifier)
    if already:
        raise ConflictError(
            f"planning item {pi_identifier!r} is already decomposed "
            f"({len(already)} phase workstream(s) exist: {sorted(already)}). "
            f"Decomposition is a once-only structural step; re-scoping adds "
            f"Work Tasks within the existing phases, it does not re-decompose."
        )

    pi_title = pi.get("title") or pi_identifier
    created: list[dict] = []
    prev_id: str | None = None
    for phase in PHASE_SEQUENCE:
        title = f"{phase} — {pi_title}"[:255]
        ws = workstreams.create_workstream(
            session,
            phase_type=phase,
            title=title,
            status="Planned",
        )
        wsid = ws["workstream_identifier"]
        references.create(
            session,
            source_type="workstream",
            source_id=wsid,
            target_type="planning_item",
            target_id=pi_identifier,
            relationship=_BELONGS_KIND,
        )
        if prev_id is not None:
            # Serial gate: this phase is blocked by the immediately prior one.
            references.create(
                session,
                source_type="workstream",
                source_id=wsid,
                target_type="workstream",
                target_id=prev_id,
                relationship="blocked_by",
            )
        prev_id = wsid
        created.append(ws)
    return created
