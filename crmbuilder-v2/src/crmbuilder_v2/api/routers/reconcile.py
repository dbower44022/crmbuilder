"""Three-way reconciliation comparison endpoints — PI-316 (REL-024).

Read-only endpoints over :mod:`crmbuilder_v2.access.reconcile_compare`. The
comparison is served from already-stored audit data (the canonical design plus
each instance's ``instance_membership`` snapshot), so it returns without a live
re-audit. All responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from crmbuilder_v2.access import reconcile_apply, reconcile_compare
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import instances
from crmbuilder_v2.access.repositories import reconcile_transactions as txn_repo
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok

router = APIRouter(prefix="/reconcile", tags=["reconcile"])


class CaptureIn(BaseModel):
    """Capture an instance's field-attribute value into the canonical design."""

    instance: str
    field_identifier: str
    attribute: str
    actor: str
    batch_id: str | None = None
    note: str | None = None


class RollbackIn(BaseModel):
    """Reverse a prior design change, restoring the previous value."""

    actor: str


@router.get("/compare")
def compare(
    instance_a: str = Query(..., description="First instance identifier"),
    instance_b: str = Query(..., description="Second instance identifier"),
    entity: str | None = Query(
        None, description="Scope to one entity (the per-entity drill); omit for the full scan"
    ),
):
    """Three-way diff across the canonical design and two instances (REQ-352/353).

    Returns differing rows grouped by entity. Supply ``entity`` to scope to one
    entity (the drill); omit it for the full scan across every member type.
    """
    with readonly_session() as s:
        for inst in (instance_a, instance_b):
            if instances.get_instance(s, inst, include_deleted=True) is None:
                raise NotFoundError("instance", inst)
        return ok(
            reconcile_compare.three_way_compare(
                s,
                instance_a=instance_a,
                instance_b=instance_b,
                entity_identifier=entity,
            )
        )


@router.post("/capture", status_code=201)
def capture(body: CaptureIn):
    """Capture an instance's field-attribute value into the design (REQ-356).

    Writes the instance's value onto the canonical field, logs the transaction,
    and clears that attribute's drift on the source instance.
    """
    with writable_session() as s:
        return ok(
            reconcile_apply.capture_field_attribute(
                s,
                instance=body.instance,
                field_identifier=body.field_identifier,
                attribute=body.attribute,
                actor=body.actor,
                batch_id=body.batch_id,
                note=body.note,
            )
        )


@router.post("/transactions/{transaction_id}/rollback")
def rollback(transaction_id: int, body: RollbackIn):
    """Reverse a prior design change, restoring its previous value (REQ-360)."""
    with writable_session() as s:
        return ok(reconcile_apply.rollback(s, transaction_id, actor=body.actor))


@router.get("/transactions")
def list_transactions(
    batch_id: str | None = Query(None),
    member_identifier: str | None = Query(None),
    status: str | None = Query(None),
    limit: int | None = Query(None),
):
    """The reconcile transaction log, newest first (REQ-359)."""
    with readonly_session() as s:
        return ok(
            txn_repo.list_transactions(
                s,
                batch_id=batch_id,
                member_identifier=member_identifier,
                status=status,
                limit=limit,
            )
        )
