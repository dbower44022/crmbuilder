"""Planning items endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import (
    decomposition,
    lead,
    planning_items,
    pm,
)
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    PlanningItemClaimIn,
    PlanningItemCreateIn,
    PlanningItemReleaseIn,
    PlanningItemUpdateIn,
)

router = APIRouter(prefix="/planning-items", tags=["planning_items"])


@router.get("")
def list_all():
    with readonly_session() as s:
        return ok(planning_items.list_all(s))


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``PI-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": planning_items.compute_next_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str):
    with readonly_session() as s:
        return ok(planning_items.get(s, identifier))


@router.post("", status_code=201)
def create(body: PlanningItemCreateIn):
    with writable_session() as s:
        return ok(planning_items.create(s, **body.model_dump()))


@router.patch("/{identifier}")
def update(identifier: str, body: PlanningItemUpdateIn):
    with writable_session() as s:
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        return ok(planning_items.update(s, identifier, **fields))


@router.post("/{identifier}/claim")
def claim(identifier: str, body: PlanningItemClaimIn):
    """Atomically claim an item for an orchestrator agent (PI-077)."""
    with writable_session() as s:
        return ok(planning_items.claim_planning_item(s, identifier, body.claimant))


@router.post("/{identifier}/release")
def release(identifier: str, body: PlanningItemReleaseIn):
    """Release an item's claim (PI-077)."""
    with writable_session() as s:
        return ok(
            planning_items.release_planning_item(s, identifier, body.claimant)
        )


@router.post("/{identifier}/dispatch", status_code=201)
def dispatch(identifier: str):
    """Project Manager: hand an eligible Planning Item to a Lead (ADO §3.1).
    Transitions the PI to In Progress, gated on eligibility (all blocked_by
    predecessors Resolved). 409 if already started/terminal or still blocked;
    404 if absent."""
    with writable_session() as s:
        return ok(pm.dispatch_planning_item(s, identifier))


@router.post("/{identifier}/approve-dispatch", status_code=201)
def approve_dispatch(identifier: str):
    """Record a human approval for an ``ado_with_approval`` Planning Item
    (PI-183 / DEC-424). Flips ``dispatch_approved`` to True — the only write
    path for that flag — so the PM dispatcher treats the item as eligible.
    Idempotent; 404 if the item does not exist."""
    with writable_session() as s:
        return ok(planning_items.approve_dispatch(s, identifier))


@router.get("/{identifier}/phase-overview")
def phase_overview(identifier: str):
    """The PI Lead's execution-state view (ADO §3.2-3.4): every phase
    Workstream with status, Work Task progress, serial-gate readiness, and the
    gate flags (all_scoped, all_terminal, needs_attention, next_executable)."""
    with readonly_session() as s:
        return ok(lead.phase_overview(s, identifier))


@router.post("/{identifier}/decompose", status_code=201)
def decompose(identifier: str):
    """Structurally decompose a Planning Item into its six phase Workstreams.

    The ADO structural step (design §3.2.1 / §4.1): creates every phase
    Workstream in ``Planned`` status, wires each one's
    ``workstream_belongs_to_planning_item`` edge to this PI, and chains
    consecutive phases with serial ``blocked_by`` gates. Returns the created
    Workstreams in canonical phase order. 409 if the PI is already decomposed;
    404 if it does not exist.
    """
    with writable_session() as s:
        return ok(decomposition.decompose_planning_item(s, identifier))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(planning_items.delete(s, identifier))
