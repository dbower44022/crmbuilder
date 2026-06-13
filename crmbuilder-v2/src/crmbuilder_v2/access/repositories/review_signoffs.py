"""Review sign-off repository (requirements-provenance Phase 6).

The recorded "reviewed, not reviewable" attestation. Append-only: a sign-off is
created and read, never edited. On create it snapshots the topic's current
requirement (identifier, status) pairs from :mod:`crmbuilder_v2.access.review`,
so later drift away from what was attested is detectable.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access import review
from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.change_log import emit
from crmbuilder_v2.access.exceptions import FieldError, UnprocessableError
from crmbuilder_v2.access.models import ReviewSignoff

_ENTITY_TYPE = "review_signoff"


def _require(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnprocessableError(
            [FieldError(field, "missing_or_empty", "must be a non-empty string")]
        )
    return value.strip()


def _flatten(roots: list[dict]) -> list[dict]:
    out: list[dict] = []

    def _walk(node: dict) -> None:
        out.append({"identifier": node["identifier"], "status": node["status"]})
        for child in node["children"]:
            _walk(child)

    for root in roots:
        _walk(root)
    return out


def create(
    session: Session,
    *,
    topic_identifier: str,
    reviewer: str,
    attestation: str,
) -> dict:
    """Record a sign-off, snapshotting the topic's current requirement set."""
    topic_identifier = _require(topic_identifier, field="signoff_topic_identifier")
    reviewer = _require(reviewer, field="signoff_reviewer")
    attestation = _require(attestation, field="signoff_attestation")

    snapshot = _flatten(
        review.topic_review(session, topic_identifier)["requirements"]
    )
    row = ReviewSignoff(
        signoff_topic_identifier=topic_identifier,
        signoff_reviewer=reviewer,
        signoff_attestation=attestation,
        signoff_reviewed_requirements=snapshot,
    )
    session.add(row)
    session.flush()
    after = to_dict(row)
    emit(
        session,
        entity_type=_ENTITY_TYPE,
        entity_identifier=str(row.id),
        operation="insert",
        before=None,
        after=after,
    )
    return after


def list_signoffs(
    session: Session, *, topic_identifier: str | None = None
) -> list[dict]:
    """List sign-offs, newest first, optionally filtered to one topic."""
    stmt = select(ReviewSignoff).order_by(ReviewSignoff.signoff_created_at.desc())
    if topic_identifier:
        stmt = stmt.where(
            ReviewSignoff.signoff_topic_identifier == topic_identifier
        )
    return [to_dict(r) for r in session.scalars(stmt).all()]
