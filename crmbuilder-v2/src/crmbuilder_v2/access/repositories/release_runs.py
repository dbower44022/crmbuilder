"""Release-run repository — the run-outcome satellite (PI-326, DEC-742).

PRJ-065 / REQ-262. Born-terminal append-only, mirroring ``deposit_event``: the
only write verb is :func:`record`; there is no update, patch, delete, or restore
(the structural guarantee behind REQ-264 — cleaning up a failed run can never
destroy the record of what it scoped and where it stopped).

A :class:`~crmbuilder_v2.access.models.ReleaseRunRow` is written when a run of a
release through the lane *closes* (abandon / ship). A release may run the lane
more than once, so this is **not** 1:1 with the release — :func:`list_for_release`
returns every run, newest first.

The ``releases.abandon`` operation that *writes* a run on the cancel/transition
path is the sibling PI-327; this repository is the primitive it will call. See
preserve-failed-run-history-design.md §3.3.
"""

from __future__ import annotations

import re
from datetime import datetime

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
from crmbuilder_v2.access.models import Release, ReleaseRunRow
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories import references as references_repo
from crmbuilder_v2.access.vocab import RELEASE_RUN_OUTCOMES

_ENTITY_TYPE = "release_run"
_IDENTIFIER_PREFIX = "RUN"
_IDENTIFIER_RE = re.compile(r"^RUN-\d{3}$")
_RELATES_TO_FINDING_KIND = "release_run_relates_to_finding"
_MAX_AUTOASSIGN_ATTEMPTS = 50


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def get(session: Session, identifier: str) -> dict | None:
    """Return one run-outcome record by identifier, or ``None``."""
    row = get_by_identifier(
        session, ReleaseRunRow, ReleaseRunRow.release_run_identifier, identifier
    )
    return to_dict(row) if row is not None else None


def list_for_release(session: Session, release_identifier: str) -> list[dict]:
    """Return every run-outcome record for one release, newest first.

    Ordered by ``release_run_created_at`` descending (identifier descending as the
    tie-break) — the most recent run first. A release may have run the lane more
    than once, so this is a list, not a single record (the explicit not-1:1 rule).
    """
    _require_release(session, release_identifier)
    stmt = (
        select(ReleaseRunRow)
        .where(ReleaseRunRow.release_identifier == release_identifier)
        .order_by(
            ReleaseRunRow.release_run_created_at.desc(),
            ReleaseRunRow.release_run_identifier.desc(),
        )
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def next_release_run_identifier(session: Session) -> str:
    identifiers = session.scalars(
        select(ReleaseRunRow.release_run_identifier)
    ).all()
    return next_prefixed_identifier(identifiers, _IDENTIFIER_PREFIX)


# ---------------------------------------------------------------------------
# Write (record-only — born-terminal append-only)
# ---------------------------------------------------------------------------


def _require_release(session: Session, release_identifier: str) -> None:
    release_identifier = gov.require_nonempty(
        release_identifier, field="release_identifier"
    )
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_identifier)
    ).first()
    if row is None:
        raise NotFoundError("release", release_identifier)


def _increment_identifier(identifier: str) -> str:
    number = int(identifier.split("-", 1)[1])
    return f"{_IDENTIFIER_PREFIX}-{number + 1:03d}"


def record(
    session: Session,
    *,
    release_identifier: str,
    outcome: str,
    scope: dict,
    phases_run: list,
    halt_point: str | None = None,
    cause: str | None = None,
    cause_code: str | None = None,
    finding_identifiers: list[str] | None = None,
    identifier: str | None = None,
    created_at: datetime | None = None,
) -> dict:
    """Append one run-outcome record for a release (record-only, append-only).

    Validates ``outcome`` and that the release exists, assigns a server-assigned
    ``RUN-NNN`` identifier under SAVEPOINT-retry, inserts the born-terminal row,
    and creates a ``release_run_relates_to_finding`` edge to each named finding —
    all in the caller's transaction.

    :param release_identifier: the release this run belongs to (must exist).
    :param outcome: one of :data:`RELEASE_RUN_OUTCOMES`
        (``shipped`` | ``abandoned`` | ``superseded``).
    :param scope: a JSON snapshot of the projects + planning items in the run at
        close (design §3.2 backstop).
    :param phases_run: the list of each phase workstream and its terminal status.
    :param halt_point: the stage/phase the run stopped at; ``None`` for a shipped
        run.
    :param cause: free-text cause; ``None`` when there is nothing to explain.
    :param cause_code: an optional structured cause code (e.g.
        ``malformed_decomposition``).
    :param finding_identifiers: identifiers of any ``finding`` (FND-) records the
        run produced, linked via ``release_run_relates_to_finding`` edges.
    :param identifier: an explicit ``RUN-NNN`` (validated, collision → 409); when
        omitted the next free identifier is server-assigned.
    :param created_at: an optional explicit close timestamp (defaults to now).
    :raises NotFoundError: the release does not exist.
    :raises UnprocessableError: ``outcome`` is not a valid value, or ``scope`` /
        ``phases_run`` are the wrong JSON shape.
    :raises ConflictError: an explicit ``identifier`` collides with an existing row.
    """
    _require_release(session, release_identifier)
    outcome = gov.require_in(
        outcome, RELEASE_RUN_OUTCOMES, field="release_run_outcome"
    )
    if not isinstance(scope, dict):
        raise UnprocessableError(
            [
                FieldError(
                    "release_run_scope",
                    "invalid_value",
                    "must be a JSON object",
                )
            ]
        )
    if not isinstance(phases_run, list):
        raise UnprocessableError(
            [
                FieldError(
                    "release_run_phases_run",
                    "invalid_value",
                    "must be a JSON array",
                )
            ]
        )

    if identifier is None:
        # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
        # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
        serialize_identifier_assignment(session, _IDENTIFIER_PREFIX)
        candidate = next_release_run_identifier(session)
    else:
        gov.require_identifier_format(
            identifier,
            regex=_IDENTIFIER_RE,
            field="release_run_identifier",
            example="RUN-001",
        )
        if (
            get_by_identifier(
                session,
                ReleaseRunRow,
                ReleaseRunRow.release_run_identifier,
                identifier,
            )
            is not None
        ):
            raise ConflictError(f"release_run {identifier!r} already exists")
        candidate = identifier

    row: ReleaseRunRow | None = None
    last_error: IntegrityError | None = None
    for _ in range(_MAX_AUTOASSIGN_ATTEMPTS):
        savepoint = session.begin_nested()
        row = ReleaseRunRow(
            release_run_identifier=candidate,
            release_identifier=release_identifier,
            release_run_scope=scope,
            release_run_phases_run=phases_run,
            release_run_halt_point=halt_point,
            release_run_cause=cause,
            release_run_cause_code=cause_code,
            release_run_outcome=outcome,
        )
        if created_at is not None:
            row.release_run_created_at = created_at
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            savepoint.rollback()
            if identifier is not None:
                raise ConflictError(
                    f"release_run {identifier!r} already exists"
                ) from exc
            candidate = _increment_identifier(candidate)
            continue
        savepoint.commit()
        break
    else:
        raise UnprocessableError(
            [
                FieldError(
                    "release_run_identifier",
                    "autoassign_exhausted",
                    "could not assign a unique release_run identifier after "
                    f"{_MAX_AUTOASSIGN_ATTEMPTS} attempts",
                )
            ]
        ) from last_error

    run_identifier = row.release_run_identifier

    # Outbound edges to any findings the run produced (the "findings" half of
    # the record). De-duplicated; each is a release_run_relates_to_finding edge.
    for fnd_identifier in dict.fromkeys(finding_identifiers or []):
        if not fnd_identifier:
            continue
        references_repo.upsert(
            session,
            source_type=_ENTITY_TYPE,
            source_id=run_identifier,
            target_type="finding",
            target_id=fnd_identifier,
            relationship=_RELATES_TO_FINDING_KIND,
        )

    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=run_identifier,
        operation="insert",
        before=None,
        after=after,
    )
    return after
