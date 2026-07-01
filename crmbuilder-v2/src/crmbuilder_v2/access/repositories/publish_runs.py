"""Publish-run repository — PI-262 (PRJ-042).

A ``publish_run`` (``PUB-NNN``) is a lean engagement-scoped record of one
publish to a target instance: its pre-publish ``backup`` snapshot (REQ-292)
plus ``scope`` / ``status`` / timing / outcome ``summary`` (REQ-293). It is an
operational log, not a governance entity — no ``change_log`` / ``refs``
participation. ``create_publish_run`` allocates the next ``PUB-NNN`` with a
SAVEPOINT retry so it is safe under concurrent writers; ``list_publish_runs``
and ``get_publish_run`` back the history surfaces (Slice E).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import (
    next_prefixed_identifier,
    serialize_identifier_assignment,
    to_dict,
)
from crmbuilder_v2.access.exceptions import ConflictError
from crmbuilder_v2.access.models import PublishRun
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import PUBLISH_RUN_STATUSES

_IDENTIFIER_PREFIX = "PUB"
_MAX_AUTOASSIGN_ATTEMPTS = 50


def next_publish_run_identifier(session: Session) -> str:
    """Compute the next free ``PUB-NNN`` identifier for the active engagement."""
    identifiers = session.scalars(
        select(PublishRun.publish_run_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


def list_publish_runs(
    session: Session,
    *,
    instance_identifier: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Return publish runs (newest first), optionally filtered by instance."""
    stmt = select(PublishRun).order_by(PublishRun.id.desc())
    if instance_identifier is not None:
        stmt = stmt.where(
            PublishRun.instance_identifier == instance_identifier
        )
    if limit is not None:
        stmt = stmt.limit(limit)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_publish_run(session: Session, identifier: str) -> dict | None:
    """Return one publish run by its ``PUB-NNN`` identifier, or ``None``."""
    row = session.scalars(
        select(PublishRun).where(
            PublishRun.publish_run_identifier == identifier
        )
    ).first()
    return to_dict(row) if row is not None else None


def create_publish_run(
    session: Session,
    *,
    instance_identifier: str,
    status: str,
    scope: list[str] | None = None,
    backup: dict | None = None,
    summary: dict | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> dict:
    """Record one publish run, auto-assigning the next ``PUB-NNN`` identifier.

    :param instance_identifier: the target instance (``INST-NNN``).
    :param status: a terminal :data:`PUBLISH_RUN_STATUSES` value.
    :param scope: the published program filenames, or ``None`` for the whole
        design.
    :param backup: the pre-publish target snapshot (REQ-292), or ``None``.
    :param summary: the outcome summary — deploy counts + verification.
    :param started_at: when the publish began.
    :param ended_at: when the publish finished.
    :returns: the persisted row as a dict.
    """
    instance_identifier = gov.require_nonempty(
        instance_identifier, field="instance_identifier"
    )
    status = gov.require_in(
        status, PUBLISH_RUN_STATUSES, field="publish_run_status"
    )

    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
    candidate = next_publish_run_identifier(session)
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = PublishRun(
            publish_run_identifier=candidate,
            instance_identifier=instance_identifier,
            publish_run_status=status,
            publish_run_scope=scope,
            publish_run_backup=backup,
            publish_run_summary=summary,
            publish_run_started_at=started_at,
            publish_run_ended_at=ended_at,
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            candidate = next_prefixed_identifier(
                [candidate], _IDENTIFIER_PREFIX
            )
            continue
        savepoint.commit()
        return to_dict(row)
    raise ConflictError(
        "could not assign a unique publish_run identifier after "
        f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts"
    ) from last_error
