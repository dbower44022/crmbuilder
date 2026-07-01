"""Artifact-version repository — the versioned, release-tied change spine.

PI-208 (PRJ-031, DEC-503). One generic version store: each row is a complete
JSON ``snapshot`` of one versioned artifact (entity / field / persona / process /
association) at one ``version_number``, tied to the release that introduced it.
Numbering is per-artifact monotonic; the live/current definition is the highest
version whose release has shipped (§16.4 / REQ-214/215/216).

This module is the *store*; architecture planning (PI-209) authors snapshots from
the reconciled definition. Requirements are excluded by design (REQ-216).
"""

from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import serialize_identifier_assignment, to_dict
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.models import ArtifactVersion, Release
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.vocab import VERSIONED_ARTIFACT_TYPES

_MAX_ATTEMPTS = 50


def _require_type(artifact_type: object) -> str:
    return gov.require_in(
        artifact_type, VERSIONED_ARTIFACT_TYPES, field="artifact_type"
    )


def _next_number(session: Session, artifact_type: str, artifact_identifier: str) -> int:
    current = session.scalar(
        select(func.max(ArtifactVersion.version_number)).where(
            ArtifactVersion.artifact_type == artifact_type,
            ArtifactVersion.artifact_identifier == artifact_identifier,
        )
    )
    return (current or 0) + 1


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


def list_versions(
    session: Session, *, artifact_type: str, artifact_identifier: str
) -> list[dict]:
    _require_type(artifact_type)
    stmt = (
        select(ArtifactVersion)
        .where(
            ArtifactVersion.artifact_type == artifact_type,
            ArtifactVersion.artifact_identifier == artifact_identifier,
        )
        .order_by(ArtifactVersion.version_number)
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


def get_version(
    session: Session,
    *,
    artifact_type: str,
    artifact_identifier: str,
    version_number: int,
) -> dict:
    row = session.scalars(
        select(ArtifactVersion).where(
            ArtifactVersion.artifact_type == artifact_type,
            ArtifactVersion.artifact_identifier == artifact_identifier,
            ArtifactVersion.version_number == version_number,
        )
    ).first()
    if row is None:
        raise NotFoundError(
            "artifact_version",
            f"{artifact_type}/{artifact_identifier}/v{version_number}",
        )
    return to_dict(row)


def live(
    session: Session, *, artifact_type: str, artifact_identifier: str
) -> dict | None:
    """The live definition: the highest version whose release has shipped.

    Versions introduced by an in-flight release are frozen drafts and are not
    returned until that release ships (REQ-215). ``None`` if no shipped version.
    """
    _require_type(artifact_type)
    row = session.scalars(
        select(ArtifactVersion)
        .join(
            Release,
            and_(
                Release.engagement_id == ArtifactVersion.engagement_id,
                Release.release_identifier == ArtifactVersion.release_identifier,
            ),
        )
        .where(
            ArtifactVersion.artifact_type == artifact_type,
            ArtifactVersion.artifact_identifier == artifact_identifier,
            Release.release_status == "shipped",
        )
        .order_by(ArtifactVersion.version_number.desc())
    ).first()
    return to_dict(row) if row is not None else None


def versions_for_release(session: Session, release_identifier: str) -> list[dict]:
    """Every snapshot a release introduced — the provenance read."""
    stmt = (
        select(ArtifactVersion)
        .where(ArtifactVersion.release_identifier == release_identifier)
        .order_by(
            ArtifactVersion.artifact_type,
            ArtifactVersion.artifact_identifier,
            ArtifactVersion.version_number,
        )
    )
    return [to_dict(r) for r in session.scalars(stmt).all()]


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------


def snapshot(
    session: Session,
    *,
    artifact_type: str,
    artifact_identifier: str,
    release_identifier: str,
    snapshot: dict,
) -> dict:
    """Append the next version (vN+1) of an artifact, tied to a release.

    ``version_number`` is server-assigned as ``max(existing) + 1`` for that
    artifact; concurrency-safe via the unique constraint + SAVEPOINT retry.
    """
    _require_type(artifact_type)
    artifact_identifier = gov.require_nonempty(
        artifact_identifier, field="artifact_identifier"
    )
    release_identifier = gov.require_nonempty(
        release_identifier, field="release_identifier"
    )
    if not isinstance(snapshot, dict):
        raise ConflictError("snapshot must be a JSON object")

    # REQ-446 / PI-384: version_number is assigned max(existing)+1 per artifact —
    # the same read-then-insert race as identifier assignment. Serialize per
    # artifact so concurrent Postgres appenders don't exhaust the retry loop (a
    # no-op on SQLite, where BEGIN IMMEDIATE already serialises writers).
    serialize_identifier_assignment(
        session, f"artifact_version:{artifact_type}:{artifact_identifier}"
    )
    last_error: IntegrityError | None = None
    for _ in range(_MAX_ATTEMPTS):
        number = _next_number(session, artifact_type, artifact_identifier)
        sp = session.begin_nested()
        row = ArtifactVersion(
            artifact_type=artifact_type,
            artifact_identifier=artifact_identifier,
            version_number=number,
            release_identifier=release_identifier,
            snapshot=snapshot,
        )
        session.add(row)
        try:
            session.flush()
        except IntegrityError as exc:
            last_error = exc
            sp.rollback()
            continue
        sp.commit()
        return to_dict(row)
    raise ConflictError(
        f"could not assign a version number for {artifact_type}/"
        f"{artifact_identifier} after {_MAX_ATTEMPTS} attempts"
    ) from last_error
