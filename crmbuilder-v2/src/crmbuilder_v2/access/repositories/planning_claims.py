"""Two-temperature planning substrate — single-threaded-by-area (PI-207).

PRJ-031, §5.1/§11.8 (DEC-462/DEC-505, REQ-195). Conceptual planning (pre-freeze)
is unrestricted and parallel — no enforcement. Once a release is frozen, planning
becomes single-threaded **by area**: within the committed planning window
(``reconciliation`` / ``architecture_planning``) each area's planning work is
owned by one agent, enforced by a ``(release, area)`` claim. The planning agents
(PI-209) consume ``claim_area``; the dev-lane single-owner-per-area is PI-204.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import PlanningAreaClaim, Release
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories.engagement_areas import valid_area_names

CONCEPTUAL_STATUSES = frozenset({"preliminary_planning", "development_planning"})
# The committed *planning* window — where single-threaded-by-area applies.
COMMITTED_PLANNING_STATUSES = frozenset({"reconciliation", "architecture_planning"})


def temperature(release_status: str) -> str | None:
    """conceptual (pre-freeze) / committed (frozen planning) / None (out of the
    planning regime — terminal or in/after the dev lane)."""
    if release_status in CONCEPTUAL_STATUSES:
        return "conceptual"
    if release_status in COMMITTED_PLANNING_STATUSES:
        return "committed"
    return None


def _release_status(session: Session, release_id: str) -> str:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_id)
    ).first()
    if row is None:
        raise NotFoundError("release", release_id)
    return row.release_status


def _require_area(session: Session, area: object) -> str:
    if not isinstance(area, str) or not area:
        raise UnprocessableError(
            [FieldError("area", "required", "a single area is required")]
        )
    valid = valid_area_names(session)
    if area not in valid:
        raise UnprocessableError(
            [FieldError("area", "invalid", f"{area!r} is not a valid area")]
        )
    return area


def area_claims(session: Session, release_identifier: str) -> list[dict]:
    _release_status(session, release_identifier)  # 404 if absent
    stmt = (
        select(PlanningAreaClaim)
        .where(PlanningAreaClaim.release_identifier == release_identifier)
        .order_by(PlanningAreaClaim.area)
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def claim_area(
    session: Session, release_identifier: str, area: str, claimed_by: str
) -> dict:
    """Claim an area's planning work for a frozen release (single-threaded).

    :raises ConflictError: the release is not in the committed planning window, or
        the area is already claimed (the single-threaded-by-area refusal).
    """
    status = _release_status(session, release_identifier)
    if temperature(status) != "committed":
        raise ConflictError(
            f"release {release_identifier!r} is {status!r}; planning-area claims "
            f"apply only in the committed planning window (reconciliation / "
            f"architecture_planning). Conceptual planning is free and parallel."
        )
    area = _require_area(session, area)
    claimed_by = gov.require_nonempty(claimed_by, field="claimed_by")
    row = PlanningAreaClaim(
        release_identifier=release_identifier, area=area, claimed_by=claimed_by
    )
    # SAVEPOINT so an expected unique violation rolls back cleanly without
    # poisoning the outer BEGIN IMMEDIATE transaction (the SQLite recipe).
    savepoint = session.begin_nested()
    session.add(row)
    try:
        session.flush()
    except IntegrityError as exc:
        savepoint.rollback()
        raise ConflictError(
            f"area {area!r} of release {release_identifier!r} is already claimed "
            f"(single-threaded-by-area); release it before reclaiming."
        ) from exc
    savepoint.commit()
    return to_dict(row)


def release_area(
    session: Session, release_identifier: str, area: str, claimed_by: str
) -> dict:
    """Release an area claim. Only the holder may release it."""
    row = session.scalars(
        select(PlanningAreaClaim).where(
            PlanningAreaClaim.release_identifier == release_identifier,
            PlanningAreaClaim.area == area,
        )
    ).first()
    if row is None:
        raise NotFoundError(
            "planning_area_claim", f"{release_identifier}/{area}"
        )
    if row.claimed_by != claimed_by:
        raise ConflictError(
            f"area {area!r} of release {release_identifier!r} is held by "
            f"{row.claimed_by!r}, not {claimed_by!r}; only the holder may release "
            f"it."
        )
    out = to_dict(row)
    session.delete(row)
    session.flush()
    return out
