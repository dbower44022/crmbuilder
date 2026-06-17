"""Planning-orchestration substrate (PI-209 Option A, §5.1/§10).

PRJ-033. The deterministic spine of the architecture-planning stage: author each
touched artifact's versioned design (vN+1) from the reconciled delta-sets, and
report planned-completely readiness. The LLM Architect / area-planning-specialist
agents (Agent Profile Registry, PI-122) and the spawn runtime drive this later;
they are not part of Option A.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.models import Release
from crmbuilder_v2.access.repositories import _governance as gov
from crmbuilder_v2.access.repositories import artifact_versions
from crmbuilder_v2.access.repositories import releases as rel_repo


def _release(session: Session, release_id: str) -> Release:
    row = session.scalars(
        select(Release).where(Release.release_identifier == release_id)
    ).first()
    if row is None:
        raise NotFoundError("release", release_id)
    return row


def author_designs(
    session: Session, release_identifier: str, delta_sets: list[dict]
) -> list[dict]:
    """Snapshot each reconciled delta-set as the release-tied vN+1 (RC-5).

    Requires the release in ``architecture_planning``. Idempotent: an artifact
    already versioned for this release is skipped, so re-running is safe.
    """
    rel = _release(session, release_identifier)
    if rel.release_status != "architecture_planning":
        raise ConflictError(
            f"release {release_identifier!r} is {rel.release_status!r}, not "
            f"'architecture_planning'; designs are authored in that stage."
        )
    already = {
        (v["artifact_type"], v["artifact_identifier"])
        for v in artifact_versions.versions_for_release(session, release_identifier)
    }
    authored: list[dict] = []
    for ds in delta_sets:
        key = (ds["artifact_type"], ds["artifact_identifier"])
        if key in already:
            continue
        authored.append(
            artifact_versions.snapshot(
                session,
                artifact_type=ds["artifact_type"],
                artifact_identifier=ds["artifact_identifier"],
                release_identifier=release_identifier,
                snapshot=ds.get("merged", {}),
            )
        )
        already.add(key)
    return authored


def planning_readiness(session: Session, release_identifier: str) -> dict:
    """The deterministic planned-completely readiness report (drives the gate)."""
    rel = _release(session, release_identifier)
    frozen = rel.release_frozen_at is not None

    pis: list[str] = []
    for prj in rel_repo._in_scope_projects(session, release_identifier):
        pis.extend(rel_repo._in_scope_planning_items(session, prj))
    pis = sorted(set(pis))

    undecomposed = [pi for pi in pis if not rel_repo._pi_workstreams(session, pi)]

    work_tasks: set[str] = set()
    for pi in pis:
        for ws in rel_repo._pi_workstreams(session, pi):
            work_tasks.update(rel_repo._ws_work_tasks(session, ws))
    adjacency: dict[str, set[str]] = {wt: set() for wt in work_tasks}
    for wt in work_tasks:
        for e in gov.outbound_edges(
            session, source_type="work_task", source_id=wt,
            relationship="blocked_by", target_type="work_task",
        ):
            if e.target_id in adjacency:
                adjacency[wt].add(e.target_id)
    sequencing_ok = not rel_repo._has_cycle(adjacency)

    designs = artifact_versions.versions_for_release(session, release_identifier)

    missing: list[str] = []
    if not frozen:
        missing.append("release is not frozen")
    if not pis:
        missing.append("no in-scope planning items")
    if undecomposed:
        missing.append(f"undecomposed planning items: {undecomposed}")
    if not sequencing_ok:
        missing.append("work-task blocked_by graph has a cycle")
    ready = frozen and bool(pis) and not undecomposed and sequencing_ok

    return {
        "release_identifier": release_identifier,
        "frozen": frozen,
        "in_scope_planning_items": pis,
        "undecomposed_planning_items": undecomposed,
        "designs_authored": len(designs),
        "sequencing_ok": sequencing_ok,
        "ready": ready,
        "missing": missing,
    }


def plan_release(
    session: Session, release_identifier: str, delta_sets: list[dict]
) -> dict:
    """The architecture-planning pass: author designs, then report readiness."""
    authored = author_designs(session, release_identifier, delta_sets)
    return {
        "release_identifier": release_identifier,
        "authored_designs": authored,
        "readiness": planning_readiness(session, release_identifier),
    }
