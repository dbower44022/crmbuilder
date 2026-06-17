# PI-211 — Plan-Freeze Inviolability (RW1): Architecture

**Wave 2 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-216, merged). Architecture-phase deliverable for **PI-211** — "Enforce
plan-freeze inviolability; route plan corrections to a new Release." Project
**PRJ-034** (Rework & Reopen). Stacked on the `pi-215-reconciliation` branch.

Governing design: `multi-agent-release-pipeline-architecture.md` §14.1, §14.3
(DEC-465, REQ-198 / RW1).

## 1. What is already enforced

RW1 — "a frozen plan is never reopened" — is **structurally enforced** by what is
already merged:

- **No backward path to a planning stage.** The Release lifecycle
  (`RELEASE_STATUS_TRANSITIONS`, PI-205) admits only forward moves plus the
  rework bounce-backs to `development` (D-07). There is no `ready →
  architecture_planning`, no `architecture_planning → reconciliation`, and
  `shipped` is terminal — so a planned-completely or shipped plan **cannot** be
  transitioned back into planning.
- **No demand edits past the gate.** PI-216's `locked` band rejects every demand
  edit once a release is past planned-completely; the change must be a new release
  (FE-4).

PI-211 **affirms** this (tests) — it adds no second backward-block.

## 2. The genuine delta — the correction route (DEC-507)

RW1's other half — "plan corrections go to a new Release" — needs a first-class,
**traceable** route so a correction is not an untracked fresh release. PI-211 adds:

- A new reference kind **`release_corrects_release`** (release → release): the new
  release *corrects* the frozen/shipped one whose plan was found wanting. Distinct
  from `supersedes` (a shipped release is not superseded by a follow-up
  correction; it stays shipped — the correction is a successor that revises
  specific requirements).
- `releases.open_correction_release(session, prior, *, title, description, notes)`
  — creates a new release in `preliminary_planning` and links it
  `new -release_corrects_release-> prior`. **Requires `prior` to be frozen**
  (status past `development_planning`); correcting a still-open release is
  rejected ("just edit it"). The revised requirements are then scheduled into the
  new release through the normal flow (pre-freeze, free).

## 3. Schema / migration

No new table. Migration `0068` rebuilds the `refs.relationship_kind` CHECK to admit
`release_corrects_release` (+ pg `0025`); vocab adds the kind to
`REFERENCE_RELATIONSHIPS` and `_kinds_for_pair` for the `(release, release)` pair.

## 4. API

- `POST /releases/{id}/open-correction` `{title, description, notes?}` → the
  successor release (the `{id}` is the prior being corrected).

## 5. Tests

- inviolability: `ready → architecture_planning` (and other backward planning
  moves) raise `StatusTransitionError`; `shipped` is terminal; a demand edit on a
  locked release is rejected (RW1 framing of PI-216).
- correction route: `open_correction_release` on a frozen prior creates a
  `preliminary_planning` successor with a `release_corrects_release` edge; on a
  still-open prior it is rejected.
- SQLite + PG.

## 6. Requirement traceability

| REQ | Where |
|---|---|
| REQ-198 / RW1 frozen plan never reopened; corrections → new release | §1 (structural inviolability, affirmed) + §2 (the traceable correction route) |
