"""Releases endpoints — the multi-agent release pipeline keystone (PI-205).

PRJ-031. Delegates to :mod:`crmbuilder_v2.access.repositories.releases`. The
Release's ``release_status`` is mutated only through ``POST /releases/{id}/
transition`` (the guarded lifecycle move running the freeze / planned-completely
/ single-occupancy gates); ``PATCH`` handles non-status fields only. All
responses use the ``{data, meta, errors}`` envelope.
"""

from __future__ import annotations

from fastapi import APIRouter

from crmbuilder_v2.access import (
    coordination,
    freeze,
    planning,
    release_orchestration,
    reopen,
)
from crmbuilder_v2.access.exceptions import NotFoundError
from crmbuilder_v2.access.repositories import (
    artifact_versions,
    planning_claims,
    reconciliation,
    release_change_sets,
    release_demands,
    releases,
)
from crmbuilder_v2.api.deps import readonly_session, writable_session
from crmbuilder_v2.api.envelope import ok
from crmbuilder_v2.api.schemas import (
    ArchitecturePlanningIn,
    AreaReopenIn,
    DecomposeIn,
    DemandsIn,
    PlanningClaimIn,
    PlanReleaseIn,
    ReconcileIn,
    ReleaseCorrectionIn,
    ReleaseCreateIn,
    ReleaseLaneOrderIn,
    ReleasePatchIn,
    ReleaseTransitionIn,
    RevalidateIn,
)

router = APIRouter(prefix="/releases", tags=["releases"])
_FIELD_PREFIX = "release_"


def _edges(body) -> list[dict] | None:
    return [e.model_dump() for e in body.references] if body.references else None


@router.get("")
def list_all(include_deleted: bool = False, status: str | None = None):
    with readonly_session() as s:
        return ok(
            releases.list_releases(
                s, include_deleted=include_deleted, status=status
            )
        )


@router.get("/next-identifier")
def next_identifier():
    with readonly_session() as s:
        return ok({"next": releases.next_release_identifier(s)})


@router.get("/lane-holder")
def lane_holder():
    """The release currently holding the development lane, or null (PI-204)."""
    with readonly_session() as s:
        return ok(coordination.lane_holder(s))


@router.get("/{identifier}")
def get(identifier: str, include_deleted: bool = False):
    with readonly_session() as s:
        record = releases.get_release(
            s, identifier, include_deleted=include_deleted
        )
        if record is None:
            raise NotFoundError("release", identifier)
        return ok(record)


@router.get("/{identifier}/composition")
def composition(identifier: str):
    """The release's release-scoped Projects and their Planning Items (derived)."""
    with readonly_session() as s:
        return ok(releases.composition(s, identifier))


@router.get("/{identifier}/planning-item-status-counts")
def planning_item_status_counts(identifier: str):
    """The count of the release's in-scope planning items per lifecycle status,
    covering every status present (REQ-242). 404 when the release is unknown."""
    with readonly_session() as s:
        return ok(releases.planning_item_status_counts(s, identifier))


@router.get("/{identifier}/versions")
def versions(identifier: str):
    """Every artifact-version snapshot this release introduced (PI-208 provenance)."""
    with readonly_session() as s:
        return ok(artifact_versions.versions_for_release(s, identifier))


@router.get("/{identifier}/freeze")
def freeze_state(identifier: str):
    """The release's freeze enforcement band (PI-216): open / amend_window /
    locked, or null when terminal (shipped/cancelled/superseded)."""
    with readonly_session() as s:
        record = releases.get_release(s, identifier)
        if record is None:
            raise NotFoundError("release", identifier)
        return ok(
            {
                "release_identifier": identifier,
                "status": record["release_status"],
                "freeze_band": freeze.band_for_status(record["release_status"]),
            }
        )


@router.post("", status_code=201)
def create(body: ReleaseCreateIn):
    with writable_session() as s:
        return ok(
            releases.create_release(
                s,
                title=body.release_title,
                description=body.release_description,
                notes=body.release_notes,
                status=body.release_status or "preliminary_planning",
                lane_order=body.release_lane_order,
                identifier=body.release_identifier,
                references=_edges(body),
            )
        )


@router.post("/{identifier}/transition")
def transition(identifier: str, body: ReleaseTransitionIn):
    """The guarded lifecycle move — runs the freeze / planned-completely /
    single-occupancy gates. 409 on an illegal or ungated transition."""
    with writable_session() as s:
        return ok(
            releases.transition(s, identifier, body.to_status, actor=body.actor)
        )


@router.post("/{identifier}/lane-order")
def lane_order(identifier: str, body: ReleaseLaneOrderIn):
    with writable_session() as s:
        return ok(releases.set_lane_order(s, identifier, body.order))


@router.post("/{identifier}/open-correction", status_code=201)
def open_correction(identifier: str, body: ReleaseCorrectionIn):
    """Open a new release that corrects this frozen prior (PI-211 / RW1)."""
    with writable_session() as s:
        return ok(
            releases.open_correction_release(
                s, identifier, title=body.title, description=body.description,
                notes=body.notes,
            )
        )


@router.post("/{identifier}/qa-pass")
def qa_pass(identifier: str):
    """Record the release-level QA pass (PI-206); gates qa → testing."""
    with writable_session() as s:
        return ok(releases.qa_pass(s, identifier))


@router.post("/{identifier}/test-pass")
def test_pass(identifier: str):
    """Record the release-level test pass (PI-206); gates testing → deployment."""
    with writable_session() as s:
        return ok(releases.test_pass(s, identifier))


@router.get("/{identifier}/area-ownership")
def area_ownership(identifier: str):
    """The {area: owner} map for a release's claimed Work Tasks (PI-204)."""
    with readonly_session() as s:
        record = releases.get_release(s, identifier)
        if record is None:
            raise NotFoundError("release", identifier)
        return ok(coordination.area_ownership(s, identifier))


@router.post("/{identifier}/reconcile")
def reconcile(identifier: str, body: ReconcileIn):
    """Run reconciliation over the release's demands (PI-215); returns the
    conflict-free delta-sets + any open conflicts."""
    with writable_session() as s:
        return ok(reconciliation.reconcile_release(s, identifier, body.demands))


@router.get("/{identifier}/reconciliation-conflicts")
def reconciliation_conflicts(identifier: str, status: str | None = None):
    """The release's reconciliation conflicts (PI-215)."""
    with readonly_session() as s:
        return ok(reconciliation.list_conflicts(s, identifier, status=status))


@router.post("/{identifier}/plan")
def plan(identifier: str, body: PlanReleaseIn):
    """Architecture-planning pass (PI-209): author vN+1 designs from the
    reconciled delta-sets, then report planned-completely readiness."""
    with writable_session() as s:
        return ok(planning.plan_release(s, identifier, body.delta_sets))


@router.get("/{identifier}/planning-readiness")
def planning_readiness(identifier: str):
    """The planned-completely readiness report (PI-209)."""
    with readonly_session() as s:
        return ok(planning.planning_readiness(s, identifier))


# --- Agent layer: demand-set + stage drivers (PI-217/218 / PRJ-033) ----------
@router.get("/{identifier}/demands")
def list_demands(identifier: str):
    """The persisted demand-set feeding reconciliation (PI-217)."""
    with readonly_session() as s:
        return ok(release_demands.list_demands(s, identifier))


@router.post("/{identifier}/demands")
def add_demands(identifier: str, body: DemandsIn):
    """Persist agent-authored demands for the release (PI-217 / AL-1)."""
    with writable_session() as s:
        return ok(
            release_demands.add_demands(s, identifier, body.demands, body.authored_by)
        )


@router.delete("/{identifier}/demands")
def clear_demands(identifier: str, requirement: str | None = None):
    """Drop the release's demands (all, or one requirement's) so re-authoring
    replaces (PI-217)."""
    with writable_session() as s:
        return ok({
            "deleted": release_demands.clear_demands(
                s, identifier, requirement_identifier=requirement
            )
        })


@router.post("/{identifier}/run-reconciliation")
def run_reconciliation(identifier: str):
    """Reconcile the persisted demand-set (PI-217); returns the delta-sets +
    open conflicts to route to governed decisions. Persists the reconciled
    change-set as a durable, reviewable artifact (PI-237)."""
    with writable_session() as s:
        return ok(release_orchestration.run_reconciliation(s, identifier))


@router.get("/{identifier}/change-set")
def change_set(identifier: str):
    """The persisted reconciled change-set — the durable, reviewable front-half
    artifact (PI-237 / REQ-285): one entry per (artifact) with its merged
    definition and provenance."""
    with readonly_session() as s:
        return ok(release_change_sets.list_change_set(s, identifier))


@router.post("/{identifier}/persist-change-set")
def persist_change_set(identifier: str):
    """(Re)materialise the reconciled change-set for the release from the current
    demands + resolved conflicts, and persist it (PI-237). Returns the persisted
    set. Normally done as part of run-reconciliation; this drives it on demand."""
    with writable_session() as s:
        return ok(
            release_orchestration.persist_reconciled_change_set(s, identifier)
        )


@router.post("/{identifier}/run-architecture-planning")
def run_architecture_planning(identifier: str, body: ArchitecturePlanningIn):
    """Author vN+1 designs from the reconciled delta-sets + report readiness
    (PI-218). Re-derives the delta-sets when none are supplied."""
    with writable_session() as s:
        return ok(
            release_orchestration.run_architecture_planning(
                s, identifier, body.delta_sets
            )
        )


@router.post("/{identifier}/decompose-planning-item/{pi_identifier}")
def decompose_planning_item(identifier: str, pi_identifier: str, body: DecomposeIn):
    """Create a PI's workstreams + work-tasks directly (PI-218 / AL-3)."""
    with writable_session() as s:
        return ok(
            release_orchestration.decompose_planning_item_direct(
                s, pi_identifier, body.workstreams
            )
        )


@router.post("/{identifier}/finalize-planning")
def finalize_planning(identifier: str):
    """Assert readiness, flip in-scope PIs interactive→ado, enter ``ready``
    (PI-218 / AL-4)."""
    with writable_session() as s:
        return ok(release_orchestration.finalize_planning(s, identifier))


@router.get("/{identifier}/area-reopens")
def area_reopens(identifier: str, status: str | None = None):
    """The release's area reopens + the currently paused areas (PI-212)."""
    with readonly_session() as s:
        return ok({
            "reopens": reopen.list_reopens(s, identifier, status=status),
            "paused_areas": sorted(reopen.paused_areas(s, identifier)),
        })


@router.get("/{identifier}/reopen-impact")
def reopen_impact(identifier: str, area: str):
    """The blast-radius impact report for reopening an area (PI-214 / RW5)."""
    with readonly_session() as s:
        return ok(reopen.reopen_impact(s, identifier, area))


@router.post("/{identifier}/area-reopens", status_code=201)
def open_area_reopen(identifier: str, body: AreaReopenIn):
    """Reopen a frozen area in-lane (PI-212 / RW2); pauses its downstream. The
    reopen is gated by a blast-radius-sized approval (PI-214 / RW5)."""
    with writable_session() as s:
        return ok(
            reopen.reopen_area(
                s, identifier, body.area, body.reason,
                approval_decision_identifier=body.approval_decision_identifier,
                triggering_finding_identifier=body.triggering_finding_identifier,
            )
        )


@router.post("/{identifier}/area-reopens/{area}/refreeze")
def refreeze_area(identifier: str, area: str):
    """Re-freeze a reopened area (PI-212 / RW3); its downstream resumes."""
    with writable_session() as s:
        return ok(reopen.refreeze_area(s, identifier, area))


@router.post("/{identifier}/area-reopens/{reopen_id}/revalidate")
def revalidate_area(identifier: str, reopen_id: int, body: RevalidateIn):
    """Record a downstream area's cascade re-validation (PI-213 / RW4)."""
    with writable_session() as s:
        return ok(reopen.revalidate_area(s, reopen_id, body.area))


@router.get("/{identifier}/outstanding-revalidations")
def outstanding_revalidations(identifier: str):
    """Downstream areas still owed a cascade re-validation (PI-213 / RW4)."""
    with readonly_session() as s:
        return ok(sorted(reopen.outstanding_revalidations(s, identifier)))


@router.get("/{identifier}/temperature")
def temperature(identifier: str):
    """The planning temperature (PI-207): conceptual / committed / null."""
    with readonly_session() as s:
        record = releases.get_release(s, identifier)
        if record is None:
            raise NotFoundError("release", identifier)
        return ok(
            {
                "release_identifier": identifier,
                "status": record["release_status"],
                "temperature": planning_claims.temperature(record["release_status"]),
            }
        )


@router.get("/{identifier}/planning-claims")
def list_planning_claims(identifier: str):
    """The release's active planning-area claims (PI-207)."""
    with readonly_session() as s:
        return ok(planning_claims.area_claims(s, identifier))


@router.post("/{identifier}/planning-claims")
def claim_planning_area(identifier: str, body: PlanningClaimIn):
    """Claim an area's planning work (PI-207); single-threaded-by-area."""
    with writable_session() as s:
        return ok(
            planning_claims.claim_area(s, identifier, body.area, body.claimed_by)
        )


@router.delete("/{identifier}/planning-claims/{area}")
def release_planning_area(identifier: str, area: str, claimed_by: str):
    """Release an area claim (PI-207). Only the holder may release it."""
    with writable_session() as s:
        return ok(planning_claims.release_area(s, identifier, area, claimed_by))


@router.patch("/{identifier}")
def patch(identifier: str, body: ReleasePatchIn):
    provided = body.model_dump(exclude_unset=True)
    references = provided.pop("references", None)
    fields = {
        key[len(_FIELD_PREFIX):]: value for key, value in provided.items()
    }
    with writable_session() as s:
        return ok(
            releases.patch_release(s, identifier, references=references, **fields)
        )


@router.delete("/{identifier}")
def delete(identifier: str):
    with writable_session() as s:
        return ok(releases.delete_release(s, identifier))
