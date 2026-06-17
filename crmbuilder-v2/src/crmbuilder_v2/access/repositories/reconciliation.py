"""Reconciliation orchestration + conflict store (PI-215, §5.4/§16.5).

PRJ-031. Runs the pure engine (:mod:`crmbuilder_v2.access.reconciliation`) over a
frozen release's demanded deltas, against each artifact's live base
(:func:`artifact_versions.live`), single-writer and dependency-ordered
(entities/personas before associations); persists the typed conflicts (RC-4);
backs the reconciliation gate (RC-1) and the governed conflict resolution.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access import reconciliation as engine
from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.models import ReconciliationConflict, Release
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories import artifact_versions

# Intra-model dependency order (RC-6): the model definitions before the relations
# that bind them. Lower rank reconciles first.
_ARTIFACT_RANK = {"entity": 0, "persona": 0, "field": 1, "association": 2}


def _locus(field: str, facet) -> str:
    """The flat conflict-locus string for (field, facet)."""
    return f"{field}.{facet}"


def _release(session: Session, release_id: str) -> Release:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_id)
    ).first()
    if row is None:
        raise NotFoundError("release", release_id)
    return row


# ---------------------------------------------------------------------------
# Conflict store
# ---------------------------------------------------------------------------


def list_conflicts(
    session: Session, release_identifier: str, *, status: str | None = None
) -> list[dict]:
    stmt = (
        select(ReconciliationConflict)
        .where(ReconciliationConflict.release_identifier == release_identifier)
        .order_by(
            ReconciliationConflict.artifact_type,
            ReconciliationConflict.artifact_identifier,
            ReconciliationConflict.facet,
        )
    )
    if status is not None:
        stmt = stmt.where(ReconciliationConflict.status == status)
    return [to_dict(r) for r in session.scalars(stmt).all()]


def has_open_conflicts(session: Session, release_identifier: str) -> bool:
    return (
        session.scalars(
            select(ReconciliationConflict.id).where(
                ReconciliationConflict.release_identifier == release_identifier,
                ReconciliationConflict.status == "open",
            )
        ).first()
        is not None
    )


def _existing(
    session: Session, release_id: str, artifact_type: str, artifact_id: str
) -> dict[str, ReconciliationConflict]:
    rows = session.scalars(
        select(ReconciliationConflict).where(
            ReconciliationConflict.release_identifier == release_id,
            ReconciliationConflict.artifact_type == artifact_type,
            ReconciliationConflict.artifact_identifier == artifact_id,
        )
    ).all()
    return {r.facet: r for r in rows}


def _upsert_artifact_conflicts(
    session: Session,
    release_id: str,
    artifact_type: str,
    artifact_id: str,
    computed: list[dict],
) -> None:
    """Upsert one artifact's conflicts: refresh open, keep resolved, drop stale."""
    by_locus = {_locus(c["field"], c["facet"]): c for c in computed}
    existing = _existing(session, release_id, artifact_type, artifact_id)

    for locus, row in existing.items():
        if locus in by_locus:
            if row.status == "open":
                c = by_locus[locus]
                row.conflict_type = c["conflict_type"]
                row.competing = c["competing"]
            # resolved + still present → resolution sticks.
            del by_locus[locus]
        else:
            # locus no longer conflicts → drop (open or stale-resolved).
            session.delete(row)

    for locus, c in by_locus.items():
        session.add(
            ReconciliationConflict(
                release_identifier=release_id,
                artifact_type=artifact_type,
                artifact_identifier=artifact_id,
                facet=locus,
                conflict_type=c["conflict_type"],
                competing=c["competing"],
                status="open",
            )
        )
    session.flush()


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def reconcile_release(
    session: Session, release_identifier: str, demands: list[dict]
) -> dict:
    """Reconcile a frozen release's demands into per-artifact delta-sets (RC-5).

    Requires the release to be in ``reconciliation``. Processes artifacts in
    intra-model dependency order, merges each against its live base, upserts the
    conflicts, and returns the conflict-free reconciled delta-sets (auto-merged +
    any prior-resolved values), each change carrying its requirement provenance.
    """
    rel = _release(session, release_identifier)
    if rel.release_status != "reconciliation":
        raise ConflictError(
            f"release {release_identifier!r} is {rel.release_status!r}, not "
            f"'reconciliation'; reconciliation runs only in that stage."
        )

    by_artifact: dict[tuple[str, str], list[dict]] = {}
    for d in demands:
        key = (d["artifact_type"], d["artifact_identifier"])
        by_artifact.setdefault(key, []).append(d)

    def _order(item):
        (atype, aid), _ = item
        return (_ARTIFACT_RANK.get(atype, 99), atype, aid)

    delta_sets = []
    for (atype, aid), ds in sorted(by_artifact.items(), key=_order):
        live = artifact_versions.live(
            session, artifact_type=atype, artifact_identifier=aid
        )
        base = live["snapshot"] if live else {}
        result = engine.reconcile_artifact(base, ds)
        _upsert_artifact_conflicts(session, release_identifier, atype, aid,
                                   result["conflicts"])
        delta_sets.append({
            "artifact_type": atype,
            "artifact_identifier": aid,
            "merged": result["merged"],
            "provenance": result["provenance"],
            "open_conflicts": len(result["conflicts"]),
        })

    return {
        "release_identifier": release_identifier,
        "delta_sets": delta_sets,
        "has_open_conflicts": has_open_conflicts(session, release_identifier),
    }


def resolve_conflict(
    session: Session,
    conflict_id: int,
    *,
    decision_identifier: str,
    resolved_value=None,
) -> dict:
    """Settle a conflict by a governed decision (RC-4). Flips open → resolved."""
    row = session.get(ReconciliationConflict, conflict_id)
    if row is None:
        raise NotFoundError("reconciliation_conflict", str(conflict_id))
    if row.status != "open":
        raise ConflictError(
            f"reconciliation conflict {conflict_id} is {row.status!r}, not 'open'."
        )
    decision_identifier = gov.require_nonempty(
        decision_identifier, field="decision_identifier"
    )
    row.status = "resolved"
    row.resolving_decision_identifier = decision_identifier
    row.resolved_value = resolved_value
    row.resolved_at = datetime.now(UTC)
    session.flush()
    return to_dict(row)
