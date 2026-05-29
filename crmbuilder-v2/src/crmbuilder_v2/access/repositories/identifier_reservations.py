"""Identifier reservation repository (PI-078).

Backs ``POST /identifiers/reserve``. The parallel-agent orchestrator
reserves a block of prefixed identifiers (e.g. the next five ``SES-NNN``)
at the start of a run so concurrent child agents never race on
next-available numbers when they post their close-out records.

Head computation reuses each entity type's own canonical next-identifier
function (so prefix/width quirks — e.g. ``CM-0001`` width-4 commits — are
respected) and treats an *unexpired* reservation block as already "taken":

    next free number = max(table_max, active_reservation_max) + 1

Once a reserved identifier becomes a real row, the table itself advances
``table_max`` past it, so the reservation is implicitly consumed — no
create-path hook is needed. An expired reservation is ignored (and
garbage-collected on the next reserve), which is the TTL auto-release.
The engine's ``BEGIN IMMEDIATE`` + ``busy_timeout`` serialise concurrent
reservers so two never overlap.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import (
    FieldError,
    UnprocessableError,
    ValidationError,
)
from crmbuilder_v2.access.models import IdentifierReservation
from crmbuilder_v2.access.repositories import (
    conversations,
    decisions,
    planning_items,
    risks,
    sessions,
    topics,
)

DEFAULT_TTL_SECONDS = 3600  # 1 hour
_MAX_COUNT = 1000
_IDENT_RE = re.compile(r"^([A-Z]+)-(\d+)$")

# entity_type -> callable(session) returning that type's next-available
# identifier string. Charter/status are version-based singletons (not
# PREFIX-NNN) and references are numeric REF-NNNN, so none are reservable
# here; new prefixed governance types are added by extending this map.
_NEXT_IDENTIFIER = {
    "session": sessions.compute_next_identifier,
    "decision": decisions.compute_next_identifier,
    "planning_item": planning_items.compute_next_identifier,
    "risk": risks.compute_next_identifier,
    "topic": topics.compute_next_identifier,
    "conversation": conversations.next_conversation_identifier,
}

RESERVABLE_ENTITY_TYPES = frozenset(_NEXT_IDENTIFIER)


def _parse(identifier: str) -> tuple[str, int, int]:
    """Return ``(prefix, number, width)`` parsed from a ``PREFIX-NNN`` id."""
    m = _IDENT_RE.match(identifier)
    if m is None:  # pragma: no cover - canonical generators always match
        raise ValidationError(
            [FieldError("identifier", "invalid_format", f"unparseable: {identifier!r}")]
        )
    digits = m.group(2)
    return m.group(1), int(digits), len(digits)


def _purge_expired(session: Session, now: datetime) -> None:
    session.execute(
        delete(IdentifierReservation).where(IdentifierReservation.expires_at <= now)
    )


def reserve(
    session: Session,
    *,
    entity_type: str,
    count: int,
    reserved_by: str | None = None,
    ttl_seconds: int | None = None,
) -> dict:
    """Atomically reserve a block of ``count`` identifiers for ``entity_type``.

    Returns ``{entity_type, reserved, head_after, reserved_by,
    expires_at}`` where ``reserved`` is the ordered list of identifier
    strings and ``head_after`` is the next free identifier after the block.
    """
    if entity_type not in _NEXT_IDENTIFIER:
        raise UnprocessableError(
            [
                FieldError(
                    "entity_type",
                    "invalid_value",
                    f"must be one of {sorted(_NEXT_IDENTIFIER)}",
                )
            ]
        )
    if not isinstance(count, int) or isinstance(count, bool) or count < 1 or count > _MAX_COUNT:
        raise ValidationError(
            [FieldError("count", "invalid_value", f"must be an integer 1..{_MAX_COUNT}")]
        )
    if ttl_seconds is None:
        ttl_seconds = DEFAULT_TTL_SECONDS
    if not isinstance(ttl_seconds, int) or isinstance(ttl_seconds, bool) or ttl_seconds < 1:
        raise ValidationError(
            [FieldError("ttl_seconds", "invalid_value", "must be a positive integer")]
        )

    now = datetime.now(UTC)
    _purge_expired(session, now)

    prefix, table_next, width = _parse(_NEXT_IDENTIFIER[entity_type](session))
    table_max = table_next - 1
    active_reservation_max = (
        session.scalar(
            select(func.max(IdentifierReservation.max_number)).where(
                IdentifierReservation.entity_type == entity_type,
                IdentifierReservation.expires_at > now,
            )
        )
        or 0
    )

    start = max(table_max, active_reservation_max) + 1
    numbers = list(range(start, start + count))
    reserved = [f"{prefix}-{n:0{width}d}" for n in numbers]
    head_after = f"{prefix}-{start + count:0{width}d}"
    expires_at = now + timedelta(seconds=ttl_seconds)

    session.add(
        IdentifierReservation(
            entity_type=entity_type,
            reserved_identifiers=reserved,
            max_number=numbers[-1],
            reserved_by=reserved_by,
            reserved_at=now,
            expires_at=expires_at,
        )
    )
    session.flush()

    return {
        "entity_type": entity_type,
        "reserved": reserved,
        "head_after": head_after,
        "reserved_by": reserved_by,
        "expires_at": expires_at.isoformat(),
    }
