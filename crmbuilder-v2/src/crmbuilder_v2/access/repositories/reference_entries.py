"""Reference Entry repository (REL-016 / PI-063, REQ-398; DEC-886/887).

A ``reference_entry`` (``RFE-NNN``) is a cross-engagement reference-library
record of client-industry knowledge for the discovery phase, distinguished by
``kind`` (Domain Knowledge / Organization Structure / Inventory Items). A
system/shared row with a nullable ``engagement_id`` scope — it reuses the Agent
Profile Registry's cross-engagement store pattern (``_registry`` helper), NOT a
new store (DEC-886).

Validation: identifier-format, required ``name``, ``kind`` enum, ``status`` enum,
and a per-kind ``content`` shape (``domain_knowledge`` requires a non-empty
``body``; the ``organization_structure`` / ``inventory_items`` shapes are
tightened by PI-064 / PI-065 — here they only require a JSON object).
``trigger_keywords`` (the PI-066 loader index) must be a list of strings.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    require_string,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.models import ReferenceEntry
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import REFERENCE_ENTRY_KINDS, REGISTRY_STATUSES

_ENTITY_TYPE = "reference_entry"
_IDENTIFIER_PREFIX = "RFE"
_IDENTIFIER_RE = re.compile(r"^RFE-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_UPDATABLE_FIELDS = frozenset(
    {"name", "kind", "applies_to", "trigger_keywords", "content", "version", "status"}
)


def compute_next_identifier(session: Session) -> str:
    identifiers = session.scalars(select(ReferenceEntry.identifier)).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def _require_identifier_format(identifier: str) -> str:
    if not isinstance(identifier, str) or not _IDENTIFIER_RE.match(identifier):
        raise UnprocessableError(
            [FieldError("identifier", "invalid_format", r"must match ^RFE-\d{3}$")]
        )
    return identifier


def _increment(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def _require_vocab(field: str, value: str, allowed) -> str:
    if value not in allowed:
        raise UnprocessableError(
            [FieldError(field, "invalid", f"{field} must be one of {sorted(allowed)}")]
        )
    return value


def _require_trigger_keywords(value) -> list | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(
        isinstance(k, str) and k.strip() for k in value
    ):
        raise UnprocessableError(
            [
                FieldError(
                    "trigger_keywords",
                    "invalid",
                    "must be a list of non-empty strings",
                )
            ]
        )
    return value


def _require_str_list(content: dict, key: str, *, non_empty: bool = False) -> list:
    value = content.get(key)
    if not isinstance(value, list) or not all(
        isinstance(v, str) and v.strip() for v in value
    ):
        raise UnprocessableError(
            [
                FieldError(
                    f"content.{key}",
                    "invalid",
                    f"'{key}' must be a list of non-empty strings",
                )
            ]
        )
    if non_empty and not value:
        raise UnprocessableError(
            [FieldError(f"content.{key}", "empty", f"'{key}' must not be empty")]
        )
    return value


def _validate_content(kind: str, content) -> dict:
    """Validate the per-kind ``content`` payload shape.

    All kinds require a JSON object. ``domain_knowledge`` requires a non-empty
    ``body`` string (PI-063). ``organization_structure`` requires string-list
    ``typical_entities`` (non-empty) + ``typical_relationships`` (PI-064).
    ``inventory_items`` requires string-list ``entities`` / ``personas`` /
    ``processes``, at least one non-empty (PI-065).
    """
    if not isinstance(content, dict) or not content:
        raise UnprocessableError(
            [FieldError("content", "invalid", "must be a non-empty JSON object")]
        )
    if kind == "domain_knowledge":
        body = content.get("body")
        if not isinstance(body, str) or not body.strip():
            raise UnprocessableError(
                [
                    FieldError(
                        "content.body",
                        "missing_or_empty",
                        "domain_knowledge content requires a non-empty 'body'",
                    )
                ]
            )
    elif kind == "organization_structure":
        _require_str_list(content, "typical_entities", non_empty=True)
        _require_str_list(content, "typical_relationships")
    elif kind == "inventory_items":
        lists = [
            _require_str_list(content, "entities"),
            _require_str_list(content, "personas"),
            _require_str_list(content, "processes"),
        ]
        if not any(lists):
            raise UnprocessableError(
                [
                    FieldError(
                        "content",
                        "empty",
                        "inventory_items requires at least one of entities / "
                        "personas / processes to be non-empty",
                    )
                ]
            )
    return content


def _enrich(row: ReferenceEntry) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def get(session: Session, identifier: str) -> dict:
    row = session.scalar(
        select(ReferenceEntry).where(ReferenceEntry.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return _enrich(row)


def list_all(
    session: Session,
    *,
    kind: str | None = None,
    status: str | None = None,
    scope: str | None = None,
) -> list[dict]:
    stmt = select(ReferenceEntry).order_by(ReferenceEntry.identifier)
    if kind is not None:
        stmt = stmt.where(ReferenceEntry.kind == kind)
    if status is not None:
        stmt = stmt.where(ReferenceEntry.status == status)
    if scope is not None:
        stmt = stmt.where(
            ReferenceEntry.engagement_id == resolve_scope(session, scope)
        )
    return [_enrich(r) for r in session.scalars(stmt).all()]


def _new_row(
    identifier,
    *,
    name,
    kind,
    applies_to,
    trigger_keywords,
    content,
    version,
    status,
    engagement_id,
) -> ReferenceEntry:
    return ReferenceEntry(
        identifier=identifier,
        engagement_id=engagement_id,
        name=name,
        kind=kind,
        applies_to=applies_to,
        trigger_keywords=trigger_keywords,
        content=content,
        version=version,
        status=status,
    )


def _insert_with_autoassign(session: Session, **fields) -> ReferenceEntry:
    # REQ-446 / PI-384: serialize per-prefix assignment (PG advisory lock;
    # SQLite no-op) so concurrent writers don't race the read-then-probe loop.
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = compute_next_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = _new_row(candidate, **fields)
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = _increment(candidate)
            continue
        savepoint.commit()
        return row
    raise ConflictError(
        "could not assign a unique reference_entry identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error


def create(
    session: Session,
    *,
    identifier: str | None = None,
    name: str,
    kind: str,
    content: dict,
    applies_to: str | None = None,
    trigger_keywords: list | None = None,
    version: int = 1,
    status: str = "active",
    scope: str | None = None,
) -> dict:
    require_string(name, field="name")
    _require_vocab("kind", kind, REFERENCE_ENTRY_KINDS)
    _require_vocab("status", status, REGISTRY_STATUSES)
    trigger_keywords = _require_trigger_keywords(trigger_keywords)
    content = _validate_content(kind, content)
    engagement_id = resolve_scope(session, scope)
    fields = {
        "name": name,
        "kind": kind,
        "applies_to": applies_to,
        "trigger_keywords": trigger_keywords,
        "content": content,
        "version": version,
        "status": status,
        "engagement_id": engagement_id,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **fields)
    else:
        _require_identifier_format(identifier)
        if session.get(ReferenceEntry, identifier) is not None:
            raise ConflictError(f"reference_entry {identifier!r} already exists")
        row = _new_row(identifier, **fields)
        session.add(row)
        session.flush()
    after = _enrich(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=row.identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after


def update(
    session: Session, identifier: str, *, scope: str | None = None, **fields
) -> dict:
    row = session.scalar(
        select(ReferenceEntry).where(ReferenceEntry.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    unknown = set(fields) - _UPDATABLE_FIELDS
    if unknown:
        raise ValidationError(
            [
                FieldError(
                    "fields",
                    "unknown_field",
                    f"unknown updatable fields: {sorted(unknown)}",
                )
            ]
        )
    if "kind" in fields:
        _require_vocab("kind", fields["kind"], REFERENCE_ENTRY_KINDS)
    if "status" in fields:
        _require_vocab("status", fields["status"], REGISTRY_STATUSES)
    if "trigger_keywords" in fields:
        fields["trigger_keywords"] = _require_trigger_keywords(
            fields["trigger_keywords"]
        )
    # Validate content against the effective (new-or-existing) kind.
    if "content" in fields:
        effective_kind = fields.get("kind", row.kind)
        fields["content"] = _validate_content(effective_kind, fields["content"])
    before = _enrich(row)
    for k, v in fields.items():
        setattr(row, k, v)
    if scope is not None:
        row.engagement_id = resolve_scope(session, scope)
    session.flush()
    after = _enrich(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="update",
        before=before,
        after=after,
    )
    return after


def delete(session: Session, identifier: str) -> dict:
    row = session.scalar(
        select(ReferenceEntry).where(ReferenceEntry.identifier == identifier)
    )
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    before = _enrich(row)
    session.delete(row)
    session.flush()
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=identifier,
        operation="delete",
        before=before,
        after=None,
    )
    return before
