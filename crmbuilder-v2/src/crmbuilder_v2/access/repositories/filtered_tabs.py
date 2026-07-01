"""Filtered-tab repository — PI-195 (PRJ-027).

A filtered tab (``FTB-NNN``) is one engine-neutral entity-bound report-filter
view. Standard CRUD backing the ``/filtered-tabs`` REST endpoints plus the
allocator; ``filtered_tab_status`` is a controlled vocabulary. Reconcile matches
by (entity, label) via :func:`list_filtered_tabs`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    get_by_identifier,
    next_prefixed_identifier,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import FilteredTab
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import FILTERED_TAB_STATUSES

_ENTITY_TYPE = "filtered_tab"
_PREFIX = "FTB"
_IDENTIFIER_RE = re.compile(r"^FTB-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE = frozenset({"entity_identifier", "label", "filter", "status", "notes"})


def _require_status(v: object) -> str:
    return gov.require_in(v, FILTERED_TAB_STATUSES, field="filtered_tab_status")


def _get_row(session: Session, identifier: str) -> FilteredTab:
    row = get_by_identifier(
        session, FilteredTab, FilteredTab.filtered_tab_identifier, identifier
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment(identifier: str) -> str:
    return f"{_PREFIX}-{int(identifier.split('-', 1)[1]) + 1:03d}"


def list_filtered_tabs(
    session: Session,
    *,
    include_deleted: bool = False,
    entity_identifier: str | None = None,
    label: str | None = None,
) -> list[dict]:
    stmt = select(FilteredTab).order_by(FilteredTab.filtered_tab_identifier)
    if not include_deleted:
        stmt = stmt.where(FilteredTab.filtered_tab_deleted_at.is_(None))
    if entity_identifier is not None:
        stmt = stmt.where(
            FilteredTab.filtered_tab_entity_identifier == entity_identifier
        )
    if label is not None:
        stmt = stmt.where(FilteredTab.filtered_tab_label == label)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_filtered_tab(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(
        session, FilteredTab, FilteredTab.filtered_tab_identifier, identifier
    )
    if row is None or (
        row.filtered_tab_deleted_at is not None and not include_deleted
    ):
        return None
    return to_dict(row)


def next_filtered_tab_identifier(session: Session) -> str:
    return next_prefixed_identifier(
        session.scalars(select(FilteredTab.filtered_tab_identifier)).all(), _PREFIX
    )


def _new_row(identifier, entity_identifier, label, filter_, status, notes):
    return FilteredTab(
        filtered_tab_identifier=identifier,
        filtered_tab_entity_identifier=entity_identifier,
        filtered_tab_label=label,
        filtered_tab_filter=filter_,
        filtered_tab_status=status,
        filtered_tab_notes=notes,
    )


def _insert_with_autoassign(session, **kw) -> FilteredTab:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _PREFIX)
    candidate = next_filtered_tab_identifier(session)
    last: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        sp = session.begin_nested()
        row = _new_row(candidate, **kw)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last = exc
            sp.rollback()
            candidate = _increment(candidate)
            continue
        sp.commit()
        return row
    raise ConflictError(
        "could not assign a unique filtered_tab identifier"
    ) from last


def create_filtered_tab(
    session: Session,
    *,
    entity_identifier: str,
    label: str,
    filter: dict | None = None,
    status: str = "candidate",
    notes: str | None = None,
    identifier: str | None = None,
) -> dict:
    entity_identifier = gov.require_nonempty(
        entity_identifier, field="filtered_tab_entity_identifier"
    )
    label = gov.require_nonempty(label, field="filtered_tab_label")
    status = _require_status(status or "candidate")
    kw = {
        "entity_identifier": entity_identifier,
        "label": label,
        "filter_": filter,
        "status": status,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="filtered_tab_identifier",
            example="FTB-001",
        )
        if get_by_identifier(
            session, FilteredTab, FilteredTab.filtered_tab_identifier, identifier
        ) is not None:
            raise ConflictError(f"filtered_tab {identifier!r} already exists")
        row = _new_row(identifier, **kw)
        session.add(row)
        session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE,
         entity_identifier=row.filtered_tab_identifier, operation="insert",
         before=None, after=after)
    return after


def update_filtered_tab(
    session: Session, identifier: str, *,
    filtered_tab_identifier: str | None = None,
    entity_identifier: str, label: str,
    filter: dict | None = None, status: str = "candidate",
    notes: str | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if filtered_tab_identifier is not None and filtered_tab_identifier != identifier:
        raise UnprocessableError([FieldError(
            "filtered_tab_identifier", "path_mismatch",
            "identifier in body must match the path")])
    before = to_dict(row)
    row.filtered_tab_entity_identifier = gov.require_nonempty(
        entity_identifier, field="filtered_tab_entity_identifier")
    row.filtered_tab_label = gov.require_nonempty(
        label, field="filtered_tab_label")
    row.filtered_tab_status = _require_status(status or "candidate")
    row.filtered_tab_filter = filter
    row.filtered_tab_notes = notes
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def patch_filtered_tab(session: Session, identifier: str, **fields) -> dict:
    unknown = set(fields) - _PATCHABLE
    if unknown:
        raise UnprocessableError([FieldError(
            "fields", "unknown_field",
            f"unknown patchable fields: {sorted(unknown)}")])
    row = _get_row(session, identifier)
    before = to_dict(row)
    if "entity_identifier" in fields:
        row.filtered_tab_entity_identifier = gov.require_nonempty(
            fields["entity_identifier"], field="filtered_tab_entity_identifier")
    if "label" in fields:
        row.filtered_tab_label = gov.require_nonempty(
            fields["label"], field="filtered_tab_label")
    if "status" in fields:
        row.filtered_tab_status = _require_status(fields["status"])
    if "filter" in fields:
        row.filtered_tab_filter = fields["filter"]
    if "notes" in fields:
        row.filtered_tab_notes = fields["notes"]
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def delete_filtered_tab(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.filtered_tab_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.filtered_tab_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def restore_filtered_tab(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.filtered_tab_deleted_at is None:
        raise UnprocessableError([FieldError(
            "filtered_tab_deleted_at", "not_deleted",
            "filtered_tab is not soft-deleted")])
    before = to_dict(row)
    row.filtered_tab_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after
