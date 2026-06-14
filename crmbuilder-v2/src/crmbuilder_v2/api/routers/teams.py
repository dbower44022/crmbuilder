"""Team endpoints — PI-194 (PRJ-027).

The eight standard methodology routes for the engine-neutral security team.
Each delegates to :mod:`crmbuilder_v2.access.repositories.teams`; bodies use the
parent-prefixed ``team_*`` field names. Responses use the v2
``{data, meta, errors}`` envelope.

Static routes (``next-identifier``) are declared before ``/{identifier}`` —
route order is load-bearing, the ``field.py`` precedent.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import teams
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import TeamCreateIn, TeamPatchIn, TeamReplaceIn

router = APIRouter(prefix="/teams", tags=["teams"])

_PREFIX = "team_"


@router.get("")
def list_all(include_deleted: bool = False, name: str | None = None):
    with readonly_session() as s:
        return ok(
            teams.list_teams(s, include_deleted=include_deleted, name=name)
        )


@router.get("/next-identifier")
def next_identifier():
    """Return the next available ``TM-NNN`` identifier (DEC-043)."""
    with readonly_session() as s:
        return ok({"next": teams.next_team_identifier(s)})


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = teams.get_team(s, identifier, include_deleted=include_deleted)
        if record is None:
            raise NotFoundError("team", identifier)
        return ok(record)


@router.post("", status_code=201)
def create(body: TeamCreateIn):
    with writable_session() as s:
        return ok(
            teams.create_team(
                s,
                name=body.team_name,
                description=body.team_description,
                status=body.team_status or "candidate",
                notes=body.team_notes,
                identifier=body.team_identifier,
            )
        )


@router.put("/{identifier}")
def replace(identifier: str, body: TeamReplaceIn):
    with writable_session() as s:
        return ok(
            teams.update_team(
                s,
                identifier,
                team_identifier=body.team_identifier,
                name=body.team_name,
                description=body.team_description,
                status=body.team_status or "candidate",
                notes=body.team_notes,
            )
        )


@router.patch("/{identifier}")
def patch(identifier: str, body: TeamPatchIn):
    # ``exclude_unset`` keeps an explicit null (clear) distinct from an
    # omitted key (leave unchanged).
    provided = body.model_dump(exclude_unset=True)
    fields = {
        (key[len(_PREFIX):] if key.startswith(_PREFIX) else key): value
        for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(teams.patch_team(s, identifier, **fields))


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(teams.delete_team(s, identifier))


@router.post("/{identifier}/restore")
def restore(identifier: str):
    with writable_session() as s:
        return ok(teams.restore_team(s, identifier))
