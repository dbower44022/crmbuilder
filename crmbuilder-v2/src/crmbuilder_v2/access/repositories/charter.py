"""Charter repository — singleton document, versioned."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import require_string, to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.access.models import Charter

_ENTITY_TYPE = "charter"
_SINGLETON_ID = "charter"  # used as the change-log entity_identifier


def get_current(session: Session) -> dict:
    row = session.scalar(select(Charter).where(Charter.is_current.is_(True)))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, "current")
    return to_dict(row)


def get_version(session: Session, version: int) -> dict:
    row = session.scalar(select(Charter).where(Charter.version == version))
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, f"version {version}")
    return to_dict(row)


def list_versions(session: Session) -> list[dict]:
    rows = session.scalars(select(Charter).order_by(Charter.version.desc())).all()
    return [to_dict(r) for r in rows]


def replace(session: Session, *, payload: dict) -> dict:
    """Create a new charter version. Marks any existing current row not-current."""
    if not isinstance(payload, dict):
        raise ValidationError(
            [FieldError("payload", "invalid_type", "must be an object")]
        )
    require_string(payload.get("scope", ""), field="payload.scope") if payload.get(
        "scope"
    ) else None  # scope is canonical but accept any structured payload

    current = session.scalar(select(Charter).where(Charter.is_current.is_(True)))
    before = to_dict(current) if current else None
    next_version = (current.version + 1) if current else 1

    if current is not None:
        session.execute(
            update(Charter).where(Charter.id == current.id).values(is_current=False)
        )

    new_row = Charter(version=next_version, is_current=True, payload=payload)
    session.add(new_row)
    session.flush()
    after = to_dict(new_row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=_SINGLETON_ID,
        operation="insert" if before is None else "update",
        before=before,
        after=after,
    )
    return after


def upsert_seed(
    session: Session,
    *,
    payload: dict,
    version: int,
    is_current: bool,
    created_at: Any | None = None,
) -> dict:
    """Bootstrap-only: insert a specific historical version with a fixed version
    number. Idempotent on (version) — re-running with the same version updates
    the row in place.
    """
    existing = session.scalar(select(Charter).where(Charter.version == version))
    if existing is None:
        row = Charter(version=version, is_current=is_current, payload=payload)
        if created_at is not None:
            row.created_at = created_at
        session.add(row)
        operation = "insert"
        before = None
    else:
        before = to_dict(existing)
        existing.payload = payload
        existing.is_current = is_current
        if created_at is not None:
            existing.created_at = created_at
        row = existing
        operation = "update"
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=_SINGLETON_ID,
        operation=operation,
        before=before,
        after=after,
    )
    return after
