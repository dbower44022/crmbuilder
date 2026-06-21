"""Release reconciled change-set store — the durable, reviewable front-half artifact (PI-237).

PRJ-041 / REQ-285 (front-half completion). The reconciliation stage's merged
result (``release_orchestration.reconciled_delta_sets``) was re-derived on demand
and never stored, so there was nothing stable for a human to review. This
repository persists that reconciled change-set alongside the demand-set
(:mod:`release_demands`) and the conflicts (:mod:`reconciliation`): one row per
``(release, artifact)`` holding the ``merged`` artifact and its ``provenance``.

The set is refreshed wholesale on each reconciliation run (``persist_change_set``
replaces the release's rows), so it always reflects the latest reconciliation;
``list_change_set`` is the reviewable read the Reconciliation Review consumes.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.models import Release, ReleaseChangeSet

# Intra-model dependency order, so the persisted set lists in the same order the
# reconciliation produced it (entity before field before persona, …).
from crmbuilder_v2.access.repositories.reconciliation import _ARTIFACT_RANK


def _require_release(session: Session, release_identifier: str) -> None:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_identifier)
    ).first()
    if row is None:
        raise NotFoundError("release", release_identifier)


def list_change_set(session: Session, release_identifier: str) -> list[dict]:
    """The persisted reconciled change-set for a release — the reviewable artifact.

    Ordered by the reconciliation dependency rank, then artifact type/identifier,
    so the read mirrors the order the change-set was produced in.
    """
    _require_release(session, release_identifier)
    rows = session.scalars(
        select(ReleaseChangeSet).where(
            ReleaseChangeSet.release_identifier == release_identifier
        )
    ).all()
    dicts = [to_dict(r) for r in rows]
    dicts.sort(
        key=lambda d: (
            _ARTIFACT_RANK.get(d["artifact_type"], 99),
            d["artifact_type"],
            d["artifact_identifier"],
        )
    )
    return dicts


def persist_change_set(
    session: Session, release_identifier: str, delta_sets: list[dict]
) -> list[dict]:
    """Replace the release's persisted reconciled change-set with ``delta_sets``.

    ``delta_sets`` is the reconciled-delta-set shape produced by
    ``release_orchestration.reconciled_delta_sets``::

        [{"artifact_type", "artifact_identifier", "merged", "provenance"}, ...]

    The release's existing rows are dropped first so the persisted artifact is a
    faithful snapshot of the latest reconciliation (artifacts that fell out of
    scope do not linger). Returns the persisted rows.
    """
    _require_release(session, release_identifier)
    session.execute(
        delete(ReleaseChangeSet).where(
            ReleaseChangeSet.release_identifier == release_identifier
        )
    )
    rows: list[ReleaseChangeSet] = []
    for ds in delta_sets:
        row = ReleaseChangeSet(
            release_identifier=release_identifier,
            artifact_type=ds["artifact_type"],
            artifact_identifier=ds["artifact_identifier"],
            merged=ds.get("merged") or {},
            provenance=ds.get("provenance") or [],
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return [to_dict(r) for r in rows]


def clear_change_set(session: Session, release_identifier: str) -> int:
    """Drop a release's persisted change-set. Returns the number deleted."""
    _require_release(session, release_identifier)
    result = session.execute(
        delete(ReleaseChangeSet).where(
            ReleaseChangeSet.release_identifier == release_identifier
        )
    )
    session.flush()
    return result.rowcount or 0
