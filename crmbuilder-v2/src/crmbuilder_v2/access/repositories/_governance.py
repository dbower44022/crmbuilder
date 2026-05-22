"""Shared helpers for the v0.7 governance entity repositories.

The six governance entity types (workstream, conversation, reference_book,
work_ticket, close_out_payload, deposit_event) share a substantial amount of
machinery the methodology entities did not: status-transition maps with
truly-terminal terminals, per-status lifecycle timestamps, repo-relative
file-path validation, and — most distinctively — edge-required-at-terminal
rules enforced against the universal ``refs`` table (supersession-requires
-edge, consumed-requires-edge, applied-requires-edge, production-edge).

This module centralises those shared concerns. Each repository module keeps
its own field inventory and its own create/update/patch/delete/restore
orchestration, but defers to the helpers here for the cross-cutting rules so
the behaviour is identical across the family.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import (
    FieldError,
    StatusTransitionError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Reference
from crmbuilder_v2.access.repositories import references as references_repo

# A repo-relative path: no leading slash, no ``..`` segment, no scheme prefix.
_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


# ---------------------------------------------------------------------------
# Scalar-field validators
# ---------------------------------------------------------------------------


def require_identifier_format(
    identifier: str, *, regex: re.Pattern[str], field: str, example: str
) -> str:
    if not isinstance(identifier, str) or not regex.match(identifier):
        raise UnprocessableError(
            [
                FieldError(
                    field,
                    "invalid_format",
                    f"must match {regex.pattern} (e.g. {example})",
                )
            ]
        )
    return identifier


def require_nonempty(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnprocessableError(
            [FieldError(field, "missing_or_empty", "must be a non-empty string")]
        )
    return value.strip()


def require_in(value: object, allowed: frozenset[str], *, field: str) -> str:
    if value not in allowed:
        raise UnprocessableError(
            [
                FieldError(
                    field,
                    "invalid_value",
                    f"must be one of {sorted(allowed)}",
                )
            ]
        )
    return value  # type: ignore[return-value]


def require_repo_relative_path(value: object, *, field: str) -> str:
    """Validate a repo-relative file path: no leading slash, no ``..``, no scheme."""
    path = require_nonempty(value, field=field)
    if path.startswith("/"):
        raise UnprocessableError(
            [FieldError(field, "invalid_path", "must not start with '/'")]
        )
    if _SCHEME_RE.match(path):
        raise UnprocessableError(
            [FieldError(field, "invalid_path", "must not carry a scheme prefix")]
        )
    if ".." in path.split("/"):
        raise UnprocessableError(
            [FieldError(field, "invalid_path", "must not contain '..' segments")]
        )
    return path


def check_transition(
    current: str,
    requested: str,
    transitions: dict[str, frozenset[str]],
) -> None:
    """Raise :class:`StatusTransitionError` for a disallowed status move.

    A no-op (``requested == current``) is always permitted; otherwise
    ``requested`` must appear in the current value's successor set. Terminal
    states (empty successor set) reject every non-no-op transition.
    """
    if requested == current:
        return
    if requested not in transitions.get(current, frozenset()):
        raise StatusTransitionError(current, requested)


# ---------------------------------------------------------------------------
# Lifecycle timestamps
# ---------------------------------------------------------------------------


def coerce_datetime(value: object, *, field: str = "timestamp") -> datetime:
    """Coerce an ISO 8601 string (or datetime) to a datetime, or raise 422."""
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


def apply_timestamps(row: object, timestamps: dict | None) -> None:
    """Set backfill lifecycle timestamps verbatim, coercing ISO strings."""
    if not timestamps:
        return
    for column, value in timestamps.items():
        setattr(row, column, coerce_datetime(value, field=column))


def set_status_timestamp(
    row: object,
    status: str,
    timestamp_map: dict[str, str],
    *,
    now: datetime | None = None,
) -> None:
    """Server-set the per-status lifecycle timestamp for ``status``.

    ``timestamp_map`` maps a status value to the column attribute that
    records when the record entered that status. Idempotent: the timestamp
    is set only if currently null, so re-setting the same status does not
    overwrite the original moment.
    """
    attr = timestamp_map.get(status)
    if attr is None:
        return
    if getattr(row, attr) is None:
        setattr(row, attr, now or datetime.now(UTC))


# ---------------------------------------------------------------------------
# Edge helpers (operating on the universal ``refs`` table)
# ---------------------------------------------------------------------------


def outbound_edges(
    session: Session,
    *,
    source_type: str,
    source_id: str,
    relationship: str | None = None,
    target_type: str | None = None,
) -> list[Reference]:
    """Return refs rows where this record is the source."""
    stmt = select(Reference).where(
        and_(
            Reference.source_type == source_type,
            Reference.source_id == source_id,
        )
    )
    if relationship is not None:
        stmt = stmt.where(Reference.relationship_kind == relationship)
    if target_type is not None:
        stmt = stmt.where(Reference.target_type == target_type)
    return list(session.scalars(stmt).all())


def inbound_edges(
    session: Session,
    *,
    target_type: str,
    target_id: str,
    relationship: str | None = None,
    source_type: str | None = None,
) -> list[Reference]:
    """Return refs rows where this record is the target."""
    stmt = select(Reference).where(
        and_(
            Reference.target_type == target_type,
            Reference.target_id == target_id,
        )
    )
    if relationship is not None:
        stmt = stmt.where(Reference.relationship_kind == relationship)
    if source_type is not None:
        stmt = stmt.where(Reference.source_type == source_type)
    return list(session.scalars(stmt).all())


def apply_reference_list(
    session: Session, refs: Iterable[dict] | None
) -> None:
    """Idempotently create the edges named in a request's ``references`` array.

    Each entry is a full edge spec — ``source_type``, ``source_id``,
    ``target_type``, ``target_id`` and ``relationship`` (the access-layer
    keyword for ``relationship_kind``). Edges are created within the caller's
    transaction so edge-required validation downstream sees them; already
    -present edges are no-ops (upsert). Vocabulary and pair validity are
    enforced by the references repository.
    """
    if not refs:
        return
    for spec in refs:
        references_repo.upsert(
            session,
            source_type=spec["source_type"],
            source_id=spec["source_id"],
            target_type=spec["target_type"],
            target_id=spec["target_id"],
            relationship=spec["relationship"],
        )


def reject_missing_supersedes_edge(
    session: Session,
    *,
    entity_type: str,
    identifier: str,
    error_code: str = "supersession_requires_successor_edge",
) -> None:
    """Raise 422 when a record at status ``superseded`` has no outbound supersedes edge."""
    edges = outbound_edges(
        session,
        source_type=entity_type,
        source_id=identifier,
        relationship="supersedes",
    )
    if not edges:
        raise UnprocessableError(
            [FieldError("status", error_code, "an outbound 'supersedes' edge is required")]
        )
