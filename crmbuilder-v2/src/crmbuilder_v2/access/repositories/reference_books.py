"""Reference book repository — the third governance entity type (UI v0.7).

Per ``governance-schema-specs/reference_book.md``. Documentary-shaped
three-status lifecycle (active → archived / superseded) with base
timestamps only. The ``superseded`` terminal requires an outbound
``supersedes`` edge. A sibling ``reference_book_versions`` child table
records one row per known version; the parent's denormalized
``current_version_label`` / ``current_version_date`` pointers are
recomputed (newest ``version_date`` wins) on any child-table write.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import ReferenceBook, ReferenceBookVersion
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import (
    REFERENCE_BOOK_KINDS,
    REFERENCE_BOOK_STATUS_TRANSITIONS,
    REFERENCE_BOOK_STATUSES,
)

_ENTITY_TYPE = "reference_book"
_IDENTIFIER_PREFIX = "RB"
_IDENTIFIER_RE = re.compile(r"^RB-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE_FIELDS = frozenset(
    {"title", "description", "notes", "kind", "status", "file_path"}
)


def _coerce_dt(value: object, *, field: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    raise UnprocessableError(
        [FieldError(field, "invalid_datetime", "must be an ISO 8601 datetime")]
    )


def _require_status(status: object) -> str:
    return gov.require_in(
        status, REFERENCE_BOOK_STATUSES, field="reference_book_status"
    )


def _require_kind(kind: object) -> str:
    return gov.require_in(kind, REFERENCE_BOOK_KINDS, field="reference_book_kind")


def _reject_duplicate_title(
    session: Session, title: str, *, exclude_identifier: str | None = None
) -> None:
    stmt = select(ReferenceBook).where(
        func.lower(ReferenceBook.reference_book_title) == title.lower(),
        ReferenceBook.reference_book_deleted_at.is_(None),
    )
    if exclude_identifier is not None:
        stmt = stmt.where(
            ReferenceBook.reference_book_identifier != exclude_identifier
        )
    if session.scalar(stmt) is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "reference_book_title",
                    "duplicate",
                    f"a reference_book titled {title!r} already exists",
                )
            ]
        )


def _get_row(session: Session, identifier: str) -> ReferenceBook:
    row = get_by_identifier(session, ReferenceBook, ReferenceBook.reference_book_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _recompute_current_version(session: Session, identifier: str) -> None:
    """Set the parent's denormalized current-version pointers (newest wins)."""
    row = get_by_identifier(session, ReferenceBook, ReferenceBook.reference_book_identifier, identifier)
    if row is None:
        return
    newest = session.scalars(
        select(ReferenceBookVersion)
        .where(ReferenceBookVersion.reference_book_identifier == identifier)
        .order_by(ReferenceBookVersion.reference_book_version_date.desc())
        .limit(1)
    ).first()
    if newest is None:
        row.reference_book_current_version_label = None
        row.reference_book_current_version_date = None
    else:
        row.reference_book_current_version_label = (
            newest.reference_book_version_label
        )
        row.reference_book_current_version_date = (
            newest.reference_book_version_date
        )


def _validate_terminal_edges(session: Session, identifier: str, status: str) -> None:
    if status == "superseded":
        gov.reject_missing_supersedes_edge(
            session,
            entity_type=_ENTITY_TYPE,
            identifier=identifier,
            error_code="supersession_requires_successor_edge",
        )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_reference_books(
    session: Session,
    *,
    include_deleted: bool = False,
    kind: str | None = None,
    status: str | None = None,
) -> list[dict]:
    stmt = select(ReferenceBook).order_by(ReferenceBook.reference_book_identifier)
    if not include_deleted:
        stmt = stmt.where(ReferenceBook.reference_book_deleted_at.is_(None))
    if kind is not None:
        stmt = stmt.where(ReferenceBook.reference_book_kind == kind)
    if status is not None:
        stmt = stmt.where(ReferenceBook.reference_book_status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_reference_book(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, ReferenceBook, ReferenceBook.reference_book_identifier, identifier)
    if row is None:
        return None
    if row.reference_book_deleted_at is not None and not include_deleted:
        return None
    return to_dict(row)


def next_reference_book_identifier(session: Session) -> str:
    identifiers = session.scalars(
        select(ReferenceBook.reference_book_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Version sub-resource
# ---------------------------------------------------------------------------


def list_reference_book_versions(session: Session, identifier: str) -> list[dict]:
    _get_row(session, identifier)  # 404 if missing
    rows = session.scalars(
        select(ReferenceBookVersion)
        .where(ReferenceBookVersion.reference_book_identifier == identifier)
        .order_by(ReferenceBookVersion.reference_book_version_date.desc())
    ).all()
    return [to_dict(r) for r in rows]


def create_reference_book_version(
    session: Session,
    identifier: str,
    *,
    version_label: str,
    version_date: object,
    version_summary: str | None = None,
) -> dict:
    _get_row(session, identifier)
    version_label = gov.require_nonempty(
        version_label, field="reference_book_version_label"
    )
    version_dt = _coerce_dt(version_date, field="reference_book_version_date")
    existing = session.scalar(
        select(ReferenceBookVersion).where(
            ReferenceBookVersion.reference_book_identifier == identifier,
            ReferenceBookVersion.reference_book_version_label == version_label,
        )
    )
    if existing is not None:
        raise UnprocessableError(
            [
                FieldError(
                    "reference_book_version_label",
                    "duplicate",
                    f"version {version_label!r} already exists for {identifier}",
                )
            ]
        )
    row = ReferenceBookVersion(
        reference_book_identifier=identifier,
        reference_book_version_label=version_label,
        reference_book_version_date=version_dt,
        reference_book_version_summary=version_summary,
    )
    session.add(row)
    session.flush()
    _recompute_current_version(session, identifier)
    session.flush()
    return to_dict(row)


def get_reference_book_version_at(
    session: Session, identifier: str, as_of: object
) -> dict | None:
    _get_row(session, identifier)
    as_of_dt = _coerce_dt(as_of, field="as_of")
    row = session.scalars(
        select(ReferenceBookVersion)
        .where(
            ReferenceBookVersion.reference_book_identifier == identifier,
            ReferenceBookVersion.reference_book_version_date <= as_of_dt,
        )
        .order_by(ReferenceBookVersion.reference_book_version_date.desc())
        .limit(1)
    ).first()
    return to_dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# Writes (parent)
# ---------------------------------------------------------------------------


def _new_row(identifier, title, description, notes, kind, status, file_path):
    return ReferenceBook(
        reference_book_identifier=identifier,
        reference_book_title=title,
        reference_book_description=description,
        reference_book_notes=notes,
        reference_book_kind=kind,
        reference_book_status=status,
        reference_book_file_path=file_path,
    )


def _insert_with_autoassign(
    session, title, description, notes, kind, status, file_path
):
    candidate = next_reference_book_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(
            candidate, title, description, notes, kind, status, file_path
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique reference_book identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create_reference_book(
    session: Session,
    *,
    title: str,
    description: str,
    kind: str,
    file_path: str,
    notes: str | None = None,
    status: str = "active",
    identifier: str | None = None,
    references: list[dict] | None = None,
    versions: list[dict] | None = None,
) -> dict:
    title = gov.require_nonempty(title, field="reference_book_title")
    description = gov.require_nonempty(
        description, field="reference_book_description"
    )
    kind = _require_kind(kind)
    file_path = gov.require_repo_relative_path(
        file_path, field="reference_book_file_path"
    )
    if status is None:
        status = "active"
    _require_status(status)
    _reject_duplicate_title(session, title)

    if identifier is None:
        row = _insert_with_autoassign(
            session, title, description, notes, kind, status, file_path
        )
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE,
            field="reference_book_identifier", example="RB-001",
        )
        if get_by_identifier(session, ReferenceBook, ReferenceBook.reference_book_identifier, identifier) is not None:
            raise ConflictError(f"reference_book {identifier!r} already exists")
        row = _new_row(
            identifier, title, description, notes, kind, status, file_path
        )
        session.add(row)
        session.flush()

    rb_identifier = row.reference_book_identifier
    for version in versions or []:
        create_reference_book_version(
            session,
            rb_identifier,
            version_label=version["version_label"],
            version_date=version["version_date"],
            version_summary=version.get("version_summary"),
        )

    gov.apply_reference_list(session, references)
    _validate_terminal_edges(session, rb_identifier, status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=rb_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update_reference_book(
    session: Session,
    identifier: str,
    *,
    reference_book_identifier: str | None = None,
    title: str | None = None,
    description: str | None = None,
    notes: str | None = None,
    kind: str | None = None,
    status: str | None = None,
    file_path: str | None = None,
    references: list[dict] | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if (
        reference_book_identifier is not None
        and reference_book_identifier != identifier
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "reference_book_identifier",
                    "path_mismatch",
                    "identifier in body must match the path",
                )
            ]
        )
    before = to_dict(row)

    title = gov.require_nonempty(title, field="reference_book_title")
    description = gov.require_nonempty(
        description, field="reference_book_description"
    )
    kind = _require_kind(kind)
    file_path = gov.require_repo_relative_path(
        file_path, field="reference_book_file_path"
    )
    if title.lower() != row.reference_book_title.lower():
        _reject_duplicate_title(session, title, exclude_identifier=identifier)

    gov.apply_reference_list(session, references)

    if status is not None and status != row.reference_book_status:
        _require_status(status)
        gov.check_transition(
            row.reference_book_status, status, REFERENCE_BOOK_STATUS_TRANSITIONS
        )
        row.reference_book_status = status

    row.reference_book_title = title
    row.reference_book_description = description
    row.reference_book_notes = notes
    row.reference_book_kind = kind
    row.reference_book_file_path = file_path
    session.flush()
    _validate_terminal_edges(session, identifier, row.reference_book_status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def patch_reference_book(
    session: Session, identifier: str, *, references: list[dict] | None = None, **fields
) -> dict:
    unknown = set(fields) - _PATCHABLE_FIELDS
    if unknown:
        raise UnprocessableError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown patchable fields: {sorted(unknown)}",
                )
            ]
        )
    row = _get_row(session, identifier)
    before = to_dict(row)

    gov.apply_reference_list(session, references)

    if "title" in fields:
        title = gov.require_nonempty(fields["title"], field="reference_book_title")
        if title.lower() != row.reference_book_title.lower():
            _reject_duplicate_title(session, title, exclude_identifier=identifier)
        row.reference_book_title = title
    if "description" in fields:
        row.reference_book_description = gov.require_nonempty(
            fields["description"], field="reference_book_description"
        )
    if "notes" in fields:
        row.reference_book_notes = fields["notes"]
    if "kind" in fields:
        row.reference_book_kind = _require_kind(fields["kind"])
    if "file_path" in fields:
        row.reference_book_file_path = gov.require_repo_relative_path(
            fields["file_path"], field="reference_book_file_path"
        )
    if "status" in fields:
        status = _require_status(fields["status"])
        if status != row.reference_book_status:
            gov.check_transition(
                row.reference_book_status,
                status,
                REFERENCE_BOOK_STATUS_TRANSITIONS,
            )
            row.reference_book_status = status

    session.flush()
    _validate_terminal_edges(session, identifier, row.reference_book_status)

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def delete_reference_book(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.reference_book_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.reference_book_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def restore_reference_book(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.reference_book_deleted_at is None:
        raise UnprocessableError(
            [
                FieldError(
                    "reference_book_deleted_at",
                    "not_deleted",
                    "reference_book is not soft-deleted",
                )
            ]
        )
    before = to_dict(row)
    row.reference_book_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after
