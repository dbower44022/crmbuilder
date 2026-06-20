# PI-207 — Two-Temperature Planning: Architecture

**Wave 1 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-205). Architecture-phase deliverable for **PI-207** — "Build two-temperature
planning (conceptual-parallel → reconciliation single-threaded-by-area)." Stacked
on the `pi-205-release-entity` branch.

Governing design: `multi-agent-release-pipeline-architecture.md` §5.1, §10, §11.8
(D-12 / DEC-462, REQ-195). REQ-195 is implemented by **both** PI-207 (PRJ-031, the
*substrate*) and PI-209 (PRJ-033, the *planning agents* that consume it).

## 1. The two temperatures (REQ-195)

| Temperature | Release statuses | Regime |
|---|---|---|
| **conceptual** (hot) | `preliminary_planning`, `development_planning` | unrestricted, parallel — drafts are independent; nothing is locked |
| **committed** (cold) | `reconciliation`, `architecture_planning` | single-threaded **by area** |

(Once a release passes `ready` into the lane, it is dev-side single-owner-per-area
— **PI-204** — not planning. PI-207's scope is the *planning* temperature, i.e.
the post-freeze planning window `{reconciliation, architecture_planning}`.)

- **Conceptual is free by construction.** Nothing constrains pre-freeze drafting,
  so the hot temperature needs *no* enforcement — PI-207 only exposes a
  `temperature()` classifier so callers can tell which regime applies.
- **Committed is single-threaded by area.** The temperature flip happens at the
  freeze gate (PI-205 transition; PI-216 closes ungoverned demand edits). PI-207
  adds the missing piece: a **planning-area claim** that serializes each area's
  planning work within a frozen release.

## 2. The planning-area claim (DEC-505)

A claim keyed on `(release, area)`, honored only in the committed planning window.

- **Options:** (a) leave single-threading to the planning agents' good behavior;
  (b) a `(release, area)` claim the access layer enforces. **Chosen:** (b) — the
  whole concept is "structure over good behavior"; the agents (PI-209) need a
  substrate to claim against, and overlap must be *refused*, not hoped away.
- **`planning_area_claims`** table (engagement-scoped satellite, surrogate PK):
  `(engagement_id, release_identifier, area, claimed_by, claimed_at)` with
  `UNIQUE(engagement_id, release_identifier, area)` (single owner per area) and a
  composite FK to `releases`. Area is validated against System ∪ this engagement's
  Engagement areas (`engagement_areas.valid_area_names`).
- **Repository** (`repositories/planning_claims.py`):
  - `temperature(release_status) -> "conceptual" | "committed" | None` (None for
    terminal/lane states — out of the planning regime).
  - `claim_area(session, release, area, claimed_by)` — requires the release in the
    committed planning window (`reconciliation` / `architecture_planning`); a
    second claim on the same `(release, area)` is refused (`ConflictError`) — this
    *is* single-threaded-by-area.
  - `release_area(session, release, area, claimed_by)` — only the holder releases.
  - `area_claims(session, release)` — the read.

## 3. Division of labour (no redundancy)

- **PI-207** — the planning-area single-threading substrate + the temperature
  classifier (this doc).
- **PI-216** — closes ungoverned demand edits once frozen (the *what* you may
  change); PI-207 serializes *who* works an area's planning.
- **PI-215** — the reconciliation engine is single-*writer* over the model area;
  it runs inside the committed temperature PI-207 defines.
- **PI-209** — the Architect + area planning specialists *consume* `claim_area`.
- **PI-204** — dev-lane single-owner-per-area (post-`ready`), a different window.

## 4. Schema / migration

`planning_area_claims` table; SQLite `0066` + PG `0023` (`create_table`, no CHECK
rebuilds — outside the refs/change_log discipline). Added to the 0038
scoped-tables allowlist.

## 5. API

- `POST /releases/{id}/planning-claims` `{area, claimed_by}` — claim.
- `DELETE /releases/{id}/planning-claims/{area}?claimed_by=` — release.
- `GET /releases/{id}/planning-claims` — list.
- `GET /releases/{id}/temperature` — the classifier.

## 6. Tests

- `temperature()` classification per status;
- claim refused when the release is conceptual (not yet frozen) or terminal;
- claim succeeds in the committed window; a second claim on the same `(release,
  area)` is refused (single-threaded-by-area); a *different* area is claimable in
  parallel; release-then-reclaim; only the holder may release; invalid area
  rejected; SQLite + PG.

## 7. Requirement traceability

| REQ | Where |
|---|---|
| REQ-195 conceptual parallel → committed single-threaded-by-area | §1 (classifier), §2 (the claim refuses area overlap in the committed window) |
| REQ-197 freeze is the flip point | the temperature boundary is the freeze gate (PI-205/PI-216); PI-207 reads it |
