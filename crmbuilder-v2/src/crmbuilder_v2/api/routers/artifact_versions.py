"""Artifact-version endpoints — the versioned change spine (PI-208 / PRJ-031).

Delegates to :mod:`crmbuilder_v2.access.repositories.artifact_versions`. ``POST``
appends the next version (called by architecture planning); the GETs serve the
version history, the live (latest-shipped) definition, and a specific version.
All responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access.repositories import artifact_versions
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import ArtifactVersionSnapshotIn

router = APIRouter(prefix="/artifact-versions", tags=["artifact-versions"])


@router.get("")
def list_all(artifact_type: str, artifact_identifier: str):
    with readonly_session() as s:
        return ok(
            artifact_versions.list_versions(
                s,
                artifact_type=artifact_type,
                artifact_identifier=artifact_identifier,
            )
        )


@router.get("/live")
def live(artifact_type: str, artifact_identifier: str):
    with readonly_session() as s:
        return ok(
            artifact_versions.live(
                s,
                artifact_type=artifact_type,
                artifact_identifier=artifact_identifier,
            )
        )


@router.get("/version")
def get_version(artifact_type: str, artifact_identifier: str, version_number: int):
    with readonly_session() as s:
        return ok(
            artifact_versions.get_version(
                s,
                artifact_type=artifact_type,
                artifact_identifier=artifact_identifier,
                version_number=version_number,
            )
        )


@router.post("", status_code=201)
def create(body: ArtifactVersionSnapshotIn):
    with writable_session() as s:
        return ok(
            artifact_versions.snapshot(
                s,
                artifact_type=body.artifact_type,
                artifact_identifier=body.artifact_identifier,
                release_identifier=body.release_identifier,
                snapshot=body.snapshot,
            )
        )
