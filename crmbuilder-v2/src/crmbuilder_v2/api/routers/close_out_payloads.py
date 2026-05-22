"""Close-out payloads endpoints — the fifth governance entity type (UI v0.7).

Standard eight-endpoint set per ``close_out_payload.md`` §3.5, with the list
endpoint's ``?status=`` filter.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import close_out_payloads
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    CloseOutPayloadCreateIn,
    CloseOutPayloadPatchIn,
    CloseOutPayloadReplaceIn,
)

router = APIRouter(prefix="/close-out-payloads", tags=["close-out-payloads"])
_FIELD_PREFIX = "close_out_payload_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(include_deleted: bool = False, status: str | None = None):
    with readonly_session() as s:
        return ok(
            close_out_payloads.list_close_out_payloads(
                s, include_deleted=include_deleted, status=status
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok(
            {"next": close_out_payloads.next_close_out_payload_identifier(s)}
        )


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = close_out_payloads.get_close_out_payload(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("close_out_payload", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: CloseOutPayloadCreateIn):
    with writable_session() as s:
        return ok(
            close_out_payloads.create_close_out_payload(
                s,
                title=body.close_out_payload_title,
                description=body.close_out_payload_description,
                file_path=body.close_out_payload_file_path,
                notes=body.close_out_payload_notes,
                status=body.close_out_payload_status or "drafted",
                identifier=body.close_out_payload_identifier,
                references=_edges(body),
                timestamps=body.timestamps,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: CloseOutPayloadReplaceIn):
    with writable_session() as s:
        return ok(
            close_out_payloads.update_close_out_payload(
                s,
                identifier,
                close_out_payload_identifier=body.close_out_payload_identifier,
                title=body.close_out_payload_title,
                description=body.close_out_payload_description,
                file_path=body.close_out_payload_file_path,
                notes=body.close_out_payload_notes,
                status=body.close_out_payload_status,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: CloseOutPayloadPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            close_out_payloads.patch_close_out_payload(
                s, identifier, references=references, **fields
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(close_out_payloads.delete_close_out_payload(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(close_out_payloads.restore_close_out_payload(s, identifier))
