"""Release front-half review sign-offs — the human review gate store (PI-238).

PRJ-041 / REQ-285 (front-half completion). Reconciliation and architecture-planning
each conclude on a recorded human sign-off; the release transitions gate on it (in
addition to the deterministic check). A sign-off is append-only and **freshness-
checked**: it captures a stable content fingerprint of the stage output reviewed,
so if that output later changes the sign-off goes stale and the gate forces a
re-review (the ``review_signoffs`` drift-snapshot pattern, applied to release
stages).

``stage`` names the reviewed output and the from-status of the transition it
unblocks:

* ``reconciliation`` — the persisted reconciled change-set (``release_change_sets``);
  unblocks ``reconciliation → architecture_planning``.
* ``architecture_planning`` — the authored designs (``artifact_versions`` introduced
  by the release); unblocks ``architecture_planning → ready``.
"""

from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import (
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import Release, ReleaseSignoff
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories import (
    artifact_versions,
    release_change_sets,
)
from crmbuilder_v2.access.vocab import RELEASE_SIGNOFF_STAGES


def _require_release(session: Session, release_identifier: str) -> None:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_identifier)
    ).first()
    if row is None:
        raise NotFoundError("release", release_identifier)


def _fingerprint(payload: object) -> str:
    """A stable content hash of a JSON-able payload (sorted keys, compact)."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def stage_fingerprint(
    session: Session, release_identifier: str, stage: str
) -> str:
    """The current content fingerprint of a stage's reviewable output.

    ``reconciliation`` fingerprints the persisted reconciled change-set;
    ``architecture_planning`` fingerprints the designs the release introduced.
    Recomputed from live state each call, so it tracks any change to the output.
    """
    if stage == "reconciliation":
        rows = release_change_sets.list_change_set(session, release_identifier)
        payload = [
            {
                "artifact_type": r["artifact_type"],
                "artifact_identifier": r["artifact_identifier"],
                "merged": r["merged"],
            }
            for r in rows
        ]
    elif stage == "architecture_planning":
        versions = artifact_versions.versions_for_release(
            session, release_identifier
        )
        payload = sorted(
            (
                {
                    "artifact_type": v["artifact_type"],
                    "artifact_identifier": v["artifact_identifier"],
                    "version_number": v["version_number"],
                    "snapshot": v["snapshot"],
                }
                for v in versions
            ),
            key=lambda v: (
                v["artifact_type"],
                v["artifact_identifier"],
                v["version_number"],
            ),
        )
    else:
        raise UnprocessableError(
            [FieldError("signoff_stage", "invalid",
                        f"{stage!r} is not one of {sorted(RELEASE_SIGNOFF_STAGES)}")]
        )
    return _fingerprint(payload)


def create_signoff(
    session: Session,
    release_identifier: str,
    *,
    stage: str,
    reviewer: str,
    attestation: str,
    decision_identifier: str | None = None,
) -> dict:
    """Record a human review sign-off for a release stage (append-only).

    Captures the current stage fingerprint so the gate can later tell a fresh
    sign-off from a stale one. Returns the created row.
    """
    _require_release(session, release_identifier)
    if stage not in RELEASE_SIGNOFF_STAGES:
        raise UnprocessableError(
            [FieldError("signoff_stage", "invalid",
                        f"{stage!r} is not one of {sorted(RELEASE_SIGNOFF_STAGES)}")]
        )
    reviewer = gov.require_nonempty(reviewer, field="signoff_reviewer")
    attestation = gov.require_nonempty(attestation, field="signoff_attestation")
    row = ReleaseSignoff(
        release_identifier=release_identifier,
        signoff_stage=stage,
        signoff_reviewer=reviewer,
        signoff_attestation=attestation,
        signoff_fingerprint=stage_fingerprint(session, release_identifier, stage),
        signoff_decision_identifier=decision_identifier or None,
    )
    session.add(row)
    session.flush()
    return to_dict(row)


def list_signoffs(
    session: Session, release_identifier: str, *, stage: str | None = None
) -> list[dict]:
    """A release's sign-offs, newest first; optionally filtered to one stage."""
    _require_release(session, release_identifier)
    stmt = select(ReleaseSignoff).where(
        ReleaseSignoff.release_identifier == release_identifier
    )
    if stage is not None:
        stmt = stmt.where(ReleaseSignoff.signoff_stage == stage)
    rows = [to_dict(r) for r in session.scalars(stmt).all()]
    rows.sort(key=lambda r: r["signoff_created_at"], reverse=True)
    return rows


def fresh_signoff(
    session: Session, release_identifier: str, stage: str
) -> dict | None:
    """The latest sign-off for ``stage`` whose fingerprint matches the current
    output — i.e. a sign-off that still reflects what is there now, or ``None``."""
    current = stage_fingerprint(session, release_identifier, stage)
    for row in list_signoffs(session, release_identifier, stage=stage):
        if row["signoff_fingerprint"] == current:
            return row
    return None


def signoff_status(
    session: Session, release_identifier: str, stage: str
) -> dict:
    """Whether the stage has a fresh sign-off + the current fingerprint, so the
    review surface can show 'reviewed / needs (re-)review'."""
    fresh = fresh_signoff(session, release_identifier, stage)
    return {
        "release_identifier": release_identifier,
        "stage": stage,
        "current_fingerprint": stage_fingerprint(session, release_identifier, stage),
        "is_signed_fresh": fresh is not None,
        "fresh_signoff": fresh,
    }
