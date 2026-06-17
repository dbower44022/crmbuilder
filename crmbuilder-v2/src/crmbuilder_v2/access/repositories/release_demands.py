"""Release demand-set store — the agent-layer's reconciliation input (PI-217).

PRJ-033, AL-1 / DEC-512/513. The model-area Reconciliation Agent authors the
structured requirement→design deltas that ``reconcile_release`` consumes; this
repository persists them as a stable, reviewable, replayable demand-set (the
substrate deliberately left demands as *input*). ``as_reconcile_input`` returns
the exact delta shape :func:`reconcile_release` expects. See
release-pipeline-agent-layer-architecture.md §3.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Release, ReleaseDemand
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import VERSIONED_ARTIFACT_TYPES

VALID_OPS = frozenset({"set", "add", "remove"})


def _require_release(session: Session, release_identifier: str) -> None:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_identifier)
    ).first()
    if row is None:
        raise NotFoundError("release", release_identifier)


def _validate(demand: dict) -> dict:
    errors: list[FieldError] = []
    req = demand.get("requirement_identifier")
    if not isinstance(req, str) or not req:
        errors.append(FieldError("requirement_identifier", "required",
                                 "a demanding requirement is required"))
    atype = demand.get("artifact_type")
    if atype not in VERSIONED_ARTIFACT_TYPES:
        errors.append(FieldError("artifact_type", "invalid",
                                 f"{atype!r} is not a versioned artifact type"))
    aid = demand.get("artifact_identifier")
    if not isinstance(aid, str) or not aid:
        errors.append(FieldError("artifact_identifier", "required",
                                 "an artifact identifier is required"))
    op = demand.get("op")
    if op not in VALID_OPS:
        errors.append(FieldError("op", "invalid",
                                 f"{op!r} is not one of {sorted(VALID_OPS)}"))
    if errors:
        raise UnprocessableError(errors)
    return demand


def list_demands(session: Session, release_identifier: str) -> list[dict]:
    _require_release(session, release_identifier)
    stmt = (
        select(ReleaseDemand)
        .where(ReleaseDemand.release_identifier == release_identifier)
        .order_by(
            ReleaseDemand.artifact_type,
            ReleaseDemand.artifact_identifier,
            ReleaseDemand.field,
            ReleaseDemand.facet,
            ReleaseDemand.requirement_identifier,
        )
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def add_demands(
    session: Session,
    release_identifier: str,
    demands: list[dict],
    authored_by: str,
) -> list[dict]:
    """Persist a set of authored demands for a release (the agent's output)."""
    _require_release(session, release_identifier)
    authored_by = gov.require_nonempty(authored_by, field="authored_by")
    rows: list[ReleaseDemand] = []
    for d in demands:
        _validate(d)
        row = ReleaseDemand(
            release_identifier=release_identifier,
            requirement_identifier=d["requirement_identifier"],
            artifact_type=d["artifact_type"],
            artifact_identifier=d["artifact_identifier"],
            field=d.get("field", "") or "",
            facet=d.get("facet"),
            op=d["op"],
            value=d.get("value"),
            authored_by=authored_by,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return [to_dict(r) for r in rows]


def clear_demands(
    session: Session,
    release_identifier: str,
    *,
    requirement_identifier: str | None = None,
) -> int:
    """Drop a release's demands (all, or just one requirement's) so re-authoring
    replaces rather than duplicates. Returns the number deleted."""
    _require_release(session, release_identifier)
    stmt = delete(ReleaseDemand).where(
        ReleaseDemand.release_identifier == release_identifier
    )
    if requirement_identifier is not None:
        stmt = stmt.where(
            ReleaseDemand.requirement_identifier == requirement_identifier
        )
    result = session.execute(stmt)
    session.flush()
    return result.rowcount or 0


def as_reconcile_input(session: Session, release_identifier: str) -> list[dict]:
    """The persisted demands in the exact shape ``reconcile_release`` consumes."""
    return [
        {
            "requirement_identifier": d["requirement_identifier"],
            "artifact_type": d["artifact_type"],
            "artifact_identifier": d["artifact_identifier"],
            "field": d["field"],
            "facet": d["facet"],
            "op": d["op"],
            "value": d["value"],
        }
        for d in list_demands(session, release_identifier)
    ]
