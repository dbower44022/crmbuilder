"""Three-way reconciliation comparison endpoints — PI-316 (REL-024).

Read-only endpoints over :mod:`crmbuilder_v2.access.reconcile_compare`. The
comparison is served from already-stored audit data (the canonical design plus
each instance's ``instance_membership`` snapshot), so it returns without a live
re-audit. All responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from crmbuilder_v2.access import (
    reconcile_apply,
    reconcile_compare,
    reconcile_dataloss,
)
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


class CaptureSettingIn(BaseModel):
    """Capture an instance's entity-collection-setting value into the design."""

    instance: str
    entity_identifier: str
    attribute: str
    actor: str
    batch_id: str | None = None
    note: str | None = None


class PublishObjectIn(BaseModel):
    """Publish an object's parent entity from the design to a live instance.

    ``attribute`` narrows the membership reconcile to one setting; omit it to
    promote the whole member/entity. ``allow_no_backup`` overrides the
    pre-publish backup gate (REQ-292)."""

    instance: str
    member_type: str
    member_identifier: str
    actor: str
    attribute: str | None = None
    allow_no_backup: bool = False
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
    include_unchanged: bool = Query(
        False,
        description="Show all members (one present-everywhere row per in-sync member) "
        "instead of only the differing ones, so all fields can be verified (REQ-432)",
    ),
):
    """Three-way diff across the canonical design and two instances (REQ-352/353).

    Returns differing rows grouped by entity. Supply ``entity`` to scope to one
    entity (the drill); omit it for the full scan across every member type. Set
    ``include_unchanged`` to also surface in-sync members as present-everywhere
    rows so an operator can verify every field exists (REQ-432); the default
    stays differences-only.
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
                include_unchanged=include_unchanged,
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


@router.post("/capture-setting", status_code=201)
def capture_setting(body: CaptureSettingIn):
    """Capture an instance's entity-collection-setting value into the design (REQ-375).

    The entity-level twin of ``/capture``: writes the instance's value (sort
    field/direction, full-text search, text-filter fields) onto the canonical
    entity, logs the transaction, and clears that setting's drift on the source.
    """
    with writable_session() as s:
        return ok(
            reconcile_apply.capture_entity_setting(
                s,
                instance=body.instance,
                entity_identifier=body.entity_identifier,
                attribute=body.attribute,
                actor=body.actor,
                batch_id=body.batch_id,
                note=body.note,
            )
        )


@router.post("/publish", status_code=201)
def publish_object(body: PublishObjectIn):
    """Publish an object's parent entity from the design to a live instance (REQ-376).

    Resolves the object's parent entity, runs the existing safe scoped publish
    (backup + deploy + verify) against the target for just that entity, and — on
    a successful deploy — logs a publish transaction and reconciles the instance's
    stored membership back to the design. Drives a per-object push or a whole-entity
    promote (REQ-369) from within the reconcile surface, transaction-logged.
    """
    from datetime import UTC, datetime

    from crmbuilder_v2.access.engagement_scope import get_active_engagement
    from crmbuilder_v2.adapters.espocrm.client import RestDesignClient
    from crmbuilder_v2.api.routers.instances import (
        _resolve_publish_target,
        _serialize_publish_result,
    )
    from crmbuilder_v2.config import get_settings
    from crmbuilder_v2.publish import service as publish_service

    # Resolve which entity (and generated program) this object publishes with.
    with readonly_session() as s:
        scope = reconcile_apply.publish_scope_for_member(
            s, body.member_type, body.member_identifier
        )

    rec, api_key, secret_key = _resolve_publish_target(body.instance)
    engagement = get_active_engagement()
    design_client = RestDesignClient(
        base_url=get_settings().api_base_url, engagement=engagement
    )
    result = publish_service.publish(
        rec,
        design_client,
        api_key=api_key,
        secret_key=secret_key,
        rendered_at=datetime.now(UTC).isoformat(),
        engagement=engagement,
        scope={scope["filename"]},
        allow_no_backup=body.allow_no_backup,
    )
    payload = _serialize_publish_result(result)
    payload["scope"] = scope

    # Record + reconcile only when the entity actually deployed.
    deployed = not result.aborted and not result.validation_failed and any(
        p.deployed for p in result.programs
    )
    if deployed:
        with writable_session() as s:
            rc = reconcile_apply.record_publish(
                s,
                instance=body.instance,
                member_type=body.member_type,
                member_identifier=body.member_identifier,
                attribute=body.attribute,
                actor=body.actor,
                batch_id=body.batch_id,
                note=body.note,
            )
        payload["transaction"] = rc["transaction"]
    else:
        payload["transaction"] = None
    return ok(payload)


@router.get("/transactions/{transaction_id}/assess-revert")
def assess_revert(transaction_id: int):
    """Analyze a revert's impact and flag possible data loss (REQ-361).

    The UI calls this before confirming a live-instance revert; when
    ``requires_confirmation`` is true the operator is warned with the reasons.
    """
    with readonly_session() as s:
        return ok(reconcile_dataloss.assess_revert(txn_repo.get(s, transaction_id)))


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
