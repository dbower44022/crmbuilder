"""Team repository — PI-194 (PRJ-027).

A team (``TM-NNN``) is one engine-neutral security team: a name plus an optional
description. Standard CRUD backing the ``/teams`` REST endpoints plus the
allocator; ``team_status`` is a controlled vocabulary. Reconcile matches by name
via :func:`list_teams`.
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
from crmbuilder_v2.access.models import Team
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import TEAM_STATUSES

_ENTITY_TYPE = "team"
_PREFIX = "TM"
_IDENTIFIER_RE = re.compile(r"^TM-\d{3}$")
_MAX_AUTOASSIGN_ATTEMPTS = 50
_PATCHABLE = frozenset({"name", "description", "status", "notes"})


def _require_status(v: object) -> str:
    return gov.require_in(v, TEAM_STATUSES, field="team_status")


def _get_row(session: Session, identifier: str) -> Team:
    row = get_by_identifier(session, Team, Team.team_identifier, identifier)
    if row is None:
        raise NotFoundError(_ENTITY_TYPE, identifier)
    return row


def _increment(identifier: str) -> str:
    return f"{_PREFIX}-{int(identifier.split('-', 1)[1]) + 1:03d}"


def list_teams(
    session: Session,
    *,
    include_deleted: bool = False,
    name: str | None = None,
) -> list[dict]:
    stmt = select(Team).order_by(Team.team_identifier)
    if not include_deleted:
        stmt = stmt.where(Team.team_deleted_at.is_(None))
    if name is not None:
        stmt = stmt.where(Team.team_name == name)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_team(
    session: Session, identifier: str, *, include_deleted: bool = False
) -> dict | None:
    row = get_by_identifier(session, Team, Team.team_identifier, identifier)
    if row is None or (row.team_deleted_at is not None and not include_deleted):
        return None
    return to_dict(row)


def next_team_identifier(session: Session) -> str:
    return next_prefixed_identifier(
        session.scalars(select(Team.team_identifier)).all(), _PREFIX
    )


def _new_row(identifier, name, description, status, notes):
    return Team(
        team_identifier=identifier,
        team_name=name,
        team_description=description,
        team_status=status,
        team_notes=notes,
    )


def _insert_with_autoassign(session, **kw) -> Team:
    # REQ-446 / PI-384: serialize per-prefix assignment so concurrent
    # Postgres writers don't race the read-then-probe loop (no-op on SQLite).
    serialize_identifier_assignment(session, _PREFIX)
    candidate = next_team_identifier(session)
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
    raise ConflictError("could not assign a unique team identifier") from last


def create_team(
    session: Session,
    *,
    name: str,
    description: str | None = None,
    status: str = "candidate",
    notes: str | None = None,
    identifier: str | None = None,
) -> dict:
    name = gov.require_nonempty(name, field="team_name")
    status = _require_status(status or "candidate")
    kw = {
        "name": name,
        "description": description,
        "status": status,
        "notes": notes,
    }
    if identifier is None:
        row = _insert_with_autoassign(session, **kw)
    else:
        gov.require_identifier_format(
            identifier, regex=_IDENTIFIER_RE, field="team_identifier",
            example="TM-001",
        )
        if get_by_identifier(
            session, Team, Team.team_identifier, identifier
        ) is not None:
            raise ConflictError(f"team {identifier!r} already exists")
        row = _new_row(identifier, **kw)
        session.add(row)
        session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE,
         entity_identifier=row.team_identifier, operation="insert",
         before=None, after=after)
    return after


def update_team(
    session: Session, identifier: str, *,
    team_identifier: str | None = None,
    name: str,
    description: str | None = None,
    status: str = "candidate",
    notes: str | None = None,
) -> dict:
    row = _get_row(session, identifier)
    if team_identifier is not None and team_identifier != identifier:
        raise UnprocessableError([FieldError(
            "team_identifier", "path_mismatch",
            "identifier in body must match the path")])
    before = to_dict(row)
    row.team_name = gov.require_nonempty(name, field="team_name")
    row.team_status = _require_status(status or "candidate")
    row.team_description = description
    row.team_notes = notes
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def patch_team(session: Session, identifier: str, **fields) -> dict:
    unknown = set(fields) - _PATCHABLE
    if unknown:
        raise UnprocessableError([FieldError(
            "fields", "unknown_field",
            f"unknown patchable fields: {sorted(unknown)}")])
    row = _get_row(session, identifier)
    before = to_dict(row)
    if "name" in fields:
        row.team_name = gov.require_nonempty(fields["name"], field="team_name")
    if "status" in fields:
        row.team_status = _require_status(fields["status"])
    if "description" in fields:
        row.team_description = fields["description"]
    if "notes" in fields:
        row.team_notes = fields["notes"]
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def delete_team(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.team_deleted_at is not None:
        return to_dict(row)
    before = to_dict(row)
    row.team_deleted_at = datetime.now(UTC)
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after


def restore_team(session: Session, identifier: str) -> dict:
    row = _get_row(session, identifier)
    if row.team_deleted_at is None:
        raise UnprocessableError([FieldError(
            "team_deleted_at", "not_deleted", "team is not soft-deleted")])
    before = to_dict(row)
    row.team_deleted_at = None
    session.flush()
    after = to_dict(row)
    emit(session, entity_type=_ENTITY_TYPE, entity_identifier=identifier,
         operation="update", before=before, after=after)
    return after
