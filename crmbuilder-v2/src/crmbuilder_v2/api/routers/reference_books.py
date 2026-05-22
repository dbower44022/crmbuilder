"""Reference books endpoints — the third governance entity type (UI v0.7).

Standard eight-endpoint set per ``reference_book.md`` §3.5.1 plus the three
version-management sub-endpoints (§3.5.2): list versions, add a version, and
the in-force-at-time-T query.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import reference_books
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ReferenceBookCreateIn,
    ReferenceBookPatchIn,
    ReferenceBookReplaceIn,
    ReferenceBookVersionIn,
)

router = APIRouter(prefix="/reference-books", tags=["reference-books"])
_FIELD_PREFIX = "reference_book_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(
    include_deleted: bool = False,
    kind: str | None = None,
    status: str | None = None,
):
    with readonly_session() as s:
        return ok(
            reference_books.list_reference_books(
                s, include_deleted=include_deleted, kind=kind, status=status
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": reference_books.next_reference_book_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = reference_books.get_reference_book(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("reference_book", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: ReferenceBookCreateIn):
    versions = (
        [v.model_dump() for v in body.versions] if body.versions else None
    )
    with writable_session() as s:
        return ok(
            reference_books.create_reference_book(
                s,
                title=body.reference_book_title,
                description=body.reference_book_description,
                kind=body.reference_book_kind,
                file_path=body.reference_book_file_path,
                notes=body.reference_book_notes,
                status=body.reference_book_status or "active",
                identifier=body.reference_book_identifier,
                references=_edges(body),
                versions=versions,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: ReferenceBookReplaceIn):
    with writable_session() as s:
        return ok(
            reference_books.update_reference_book(
                s,
                identifier,
                reference_book_identifier=body.reference_book_identifier,
                title=body.reference_book_title,
                description=body.reference_book_description,
                kind=body.reference_book_kind,
                file_path=body.reference_book_file_path,
                notes=body.reference_book_notes,
                status=body.reference_book_status,
                references=_edges(body),
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: ReferenceBookPatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            reference_books.patch_reference_book(
                s, identifier, references=references, **fields
            )
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(reference_books.delete_reference_book(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(reference_books.restore_reference_book(s, identifier))


# --- version sub-resource ---------------------------------------------------


@router.get("/{identifier}/versions")
def list_versions(identifier: str):
    with readonly_session() as s:
        return ok(reference_books.list_reference_book_versions(s, identifier))


@router.post("/{identifier}/versions", status_code=201)
def add_version(identifier: str, body: ReferenceBookVersionIn):
    with writable_session() as s:
        return ok(
            reference_books.create_reference_book_version(
                s,
                identifier,
                version_label=body.version_label,
                version_date=body.version_date,
                version_summary=body.version_summary,
            )
        )


@router.get("/{identifier}/version-at")
def version_at(identifier: str, as_of: str):
    with readonly_session() as s:
        return ok(
            reference_books.get_reference_book_version_at(s, identifier, as_of)
        )
