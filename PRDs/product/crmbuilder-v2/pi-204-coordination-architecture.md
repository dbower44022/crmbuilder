# PI-204 — Lane Single-Occupancy & Single-Owner-Per-Area: Architecture

**Wave 1 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-205). Architecture-phase deliverable for **PI-204** — "Enforce single-occupancy
of the development lane and single-owner-per-area." Project **PRJ-029** (Multi-Agent
Coordination). Stacked on the `pi-205-release-entity` branch.

Governing design: `multi-agent-release-pipeline-architecture.md` §6, §7.1, §7.2,
§11.1, §11.4 (REQ-188, REQ-191).

## 1. What is already enforced

- **REQ-188 — at most one release in the lane.** Delivered by PI-205:
  `_check_single_occupancy` gates `ready → development`, and the
  `uq_releases_one_in_lane` partial unique index is the concurrency-safe backstop.
  PI-204 **affirms** it and adds the coordination read `lane_holder`.
- **Per-task claims.** The ADO `claim_work_task` already refuses a second claim on
  one task (idempotent for the same agent, `ConflictError` otherwise).

## 2. The genuine delta — single-owner-per-area (REQ-191, DEC-506)

§7.2: an Area has **one owner** that decomposes its work and fans out
*sub-agents* (file-locked, PI-203) — not several independent task-claimants. But
per-task claims alone let agent A claim one task and agent B another task in the
**same area**, violating REQ-191. PI-204 closes that:

- **single-owner-per-area:** within a release that is **in the lane**
  (`development`…`deployment`), every claimed Work Task of a given `area` must
  share one claimant — the area owner. A claim on a task whose `(release, area)`
  is already owned by a different agent is refused.
- **Derived, not a new table.** Area ownership is computed from the existing Work
  Task claims (the area's current claimants), traversing
  `work_task → work_task_belongs_to_workstream → workstream_belongs_to_planning_item
  → planning_item_belongs_to_project → project_belongs_to_release`. No new claim
  store (contrast PI-207, where the planning window has no Work Tasks yet and so
  needed its own `(release, area)` claim).
- **No release context → no-op.** A Work Task not under a release (the existing
  non-pipeline ADO) is unaffected — existing claim behaviour is preserved exactly.

## 3. Mechanism

`access/coordination.py` (PRJ-029):
- `lane_holder(session) -> dict | None` — the release currently in a lane state.
- `release_of_work_task(session, wt_id) -> str | None` — the up-traversal.
- `area_owner(session, release_id, area) -> str | None` — the distinct claimant of
  that `(release, area)`'s claimed Work Tasks, or `None`.
- `assert_area_owner(session, wt_id, claimed_by)` — the gate; a no-op unless the
  task's release is in the lane.
- `area_ownership(session, release_id) -> {area: owner}` — the coordination read.

`work_tasks.claim_work_task` calls `assert_area_owner` (deferred import) after the
per-task check, before persisting.

## 4. API

- `GET /releases/lane-holder` — the release holding the dev lane (or null).
- `GET /releases/{id}/area-ownership` — `{area: owner}` for a release.

## 5. No schema change

PI-204 adds **no table and no migration** — single-occupancy is PI-205's index +
gate; single-owner-per-area is derived from existing Work Task claims.

## 6. Tests

- `lane_holder` reports the in-lane release; null when none.
- single-occupancy affirmation (a second release cannot enter — exercises PI-205's
  gate from the PRJ-029 angle).
- single-owner-per-area: agent B claiming a second task in an area owned by agent A
  (dev-lane release) is refused; agent A claiming another task in its own area
  succeeds; the same scenario with **no release** is unaffected; `area_ownership`
  read.
- SQLite + PG.

## 7. Requirement traceability

| REQ | Where |
|---|---|
| REQ-188 one release in the lane | §1 — PI-205 gate + index; `lane_holder` read |
| REQ-191 one owner per area | §2 — `assert_area_owner` on the claim path |
