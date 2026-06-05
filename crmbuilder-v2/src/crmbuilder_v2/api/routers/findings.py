"""Finding endpoints — PI-134 reconciliation-gate governance entity (DEC-400).

Standard eight-endpoint set delegating to
:mod:`crmbuilder_v2.access.repositories.findings`. Request bodies may carry an
inline ``references`` array (the ``finding_relates_to`` edge to the Planning
Item the finding involves, and later a ``finding_resolved_by`` edge) and, on a
backfill create, a ``timestamps`` dict. All responses use the
``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import findings
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    FindingCreateIn,
    FindingPatchIn,
    FindingReplaceIn,
)

router = APIRouter(prefix="/findings", tags=["findings"])
_FIELD_PREFIX = "finding_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(
    include_deleted: bool = False,
    status: str | None = None,
    severity: str | None = None,
):
    with readonly_session() as s:
        return ok(
            findings.list_findings(
                s, include_deleted=include_deleted, status=status, severity=severity
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": findings.next_finding_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = findings.get_finding(s, identifier, include_deleted=include_deleted)
        if record is None:
            raise NotFoundError("finding", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: FindingCreateIn):
    with writable_session() as s:
        return ok(
            findings.create_finding(
                s,
                type=body.finding_type,
                severity=body.finding_severity,
                summary=body.finding_summary,
                description=body.finding_description,
                status=body.finding_status or "open",
                resolution=body.finding_resolution,
                resolution_method=body.finding_resolution_method,
                notes=body.finding_notes,
                identifier=body.finding_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: FindingReplaceIn):
    with writable_session() as s:
        return ok(
            findings.update_finding(
                s,
                identifier,
                finding_identifier=body.finding_identifier,
                type=body.finding_type,
                severity=body.finding_severity,
                summary=body.finding_summary,
                description=body.finding_description,
                status=body.finding_status,
                resolution=body.finding_resolution,
                resolution_method=body.finding_resolution_method,
                notes=body.finding_notes,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: FindingPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {key[len(_FIELD_PREFIX):]: value for key, value in provided.items()}
    with writable_session() as s:
        return ok(findings.patch_finding(s, identifier, references=references, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(findings.delete_finding(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(findings.restore_finding(s, identifier))
