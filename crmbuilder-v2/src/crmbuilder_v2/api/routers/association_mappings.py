"""Association mapping endpoints — PI-255 (PRJ-027 / DEC-654).

Relationship-level source-mapping decisions (``AMP-NNN``), parallel to
``field_mappings`` but keyed to the source instance. The standard methodology
routes plus a ``/{identifier}/mark-stale`` lifecycle action. Each delegates to
:mod:`crmbuilder_v2.access.repositories.association_mapping`; bodies use the
prefixed ``association_mapping_*`` field names. Responses use the v2
``{data, meta, errors}`` envelope.

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``layouts.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import association_mapping
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    AssociationMappingCreateIn,
    AssociationMappingPatchIn,
    AssociationMappingReplaceIn,
    MarkStaleIn,
)

router = APIRouter(prefix="/association-mappings", tags=["association-mappings"])

_PREFIX = "association_mapping_"


@router.get("")
def list_all(
    instance_identifier: str | None = None,
    status: str | None = None,
    include_deleted: bool = False,
):
    with readonly_session() as s:
        return ok(
            association_mapping.list_association_mappings(
                s,
                instance_identifier=instance_identifier,
                status=status,
                include_deleted=include_deleted,
            )
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``AMP-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok(
            {"next": association_mapping.next_association_mapping_identifier(s)}
        )


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = association_mapping.get_association_mapping(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("association_mapping", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: AssociationMappingCreateIn):
    with writable_session() as s:
        return ok(
            association_mapping.create_association_mapping(
                s,
                instance_identifier=body.association_mapping_instance_identifier,
                source_association_name=(
                    body.association_mapping_source_association_name
                ),
                decision_type=body.association_mapping_decision_type,
                target_association_identifier=(
                    body.association_mapping_target_association_identifier
                ),
                notes=body.association_mapping_notes,
                identifier=body.association_mapping_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: AssociationMappingReplaceIn):
    with writable_session() as s:
        return ok(
            association_mapping.update_association_mapping(
                s,
                identifier,
                source_association_name=(
                    body.association_mapping_source_association_name
                ),
                decision_type=body.association_mapping_decision_type,
                status=body.association_mapping_status,
                target_association_identifier=(
                    body.association_mapping_target_association_identifier
                ),
                notes=body.association_mapping_notes,
                stale_reason=body.association_mapping_stale_reason,
                stale_severity=body.association_mapping_stale_severity,
                superseded_by=body.association_mapping_superseded_by,
                resolved_at=body.association_mapping_resolved_at,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: AssociationMappingPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an omitted
    # key (leave unchanged). The prefix is stripped to the repo's patchable kwargs.
    provided = body.model_dump(exclude_unset=True)
    fields = {
        key[len(_PREFIX):] if key.startswith(_PREFIX) else key: value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            association_mapping.patch_association_mapping(s, identifier, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(association_mapping.delete_association_mapping(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(association_mapping.restore_association_mapping(s, identifier))


@router.post("/{identifier}/mark-stale")
def mark_stale(identifier: str, body: MarkStaleIn):
    """Transition the mapping to ``stale`` with a graded reason + severity."""
    with writable_session() as s:
        return ok(
            association_mapping.mark_stale(
                s, identifier, reason=body.reason, severity=body.severity
            )
        )
