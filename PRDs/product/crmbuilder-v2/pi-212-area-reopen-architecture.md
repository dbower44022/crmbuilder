# PI-212 — In-Lane Frozen-Area Reopen: Architecture

**Wave 2 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-206 + PI-216, both merged). Architecture-phase deliverable for **PI-212** —
"In-lane frozen-area reopen with downstream pause and resume." Project **PRJ-034**
(Rework & Reopen). Stacked on the `pi-215-reconciliation` branch.

Governing design: `multi-agent-release-pipeline-architecture.md` §14.1, §14.2,
§14.3 (DEC-466, REQ-199 / RW2, REQ-200 / RW3). The §14 D2 reopen is the **only**
in-flight reopen (a frozen *plan* is never reopened — that is PI-211 / RW1).

## 1. The area grain & "downstream"

The reopen acts on the **system-area dependency spine** (`vocab.SYSTEM_AREA_RANKS`:
storage 1 → access 2 → api 3 → mcp/ui 4 — the §14 "Data-Structure → Business-Logic"
axis), not the per-PI ADO phase axis. **Downstream of area X = areas with a
strictly higher rank.** Unranked areas (methodology, infra, …) are parallel: they
neither pause others nor are paused. The rank order gives the dependency cascade
without a separate per-area freeze table; the blast radius (PI-214) is exactly the
downstream set.

## 2. Mechanism (DEC-508)

A release-level **`area_reopens`** record (engagement-scoped satellite, surrogate
PK, composite FK to `releases`):

| Column | Notes |
|---|---|
| `release_identifier`, `area` | the reopened area |
| `reason` | the downstream area's discovered need (RW2 trigger) |
| `status` | `open` (thawing) / `resolved` (re-frozen) |
| `created_at`, `resolved_at` | |

`access/reopen.py`:
- `reopen_area(session, release, area, reason)` — RW2: requires the release to be
  **in the development lane** (`development`…`deployment` — an in-lane reopen) and
  the area to be a real, ranked dependency-spine area; rejects a second `open`
  reopen of the same `(release, area)`. Creates the `open` record. From now its
  downstream areas are **paused** (RW3).
- `refreeze_area(session, release, area)` — resolves the `open` reopen
  (`open → resolved`); the downstream resumes.
- `paused_areas(session, release)` — the union of the downstream sets of all
  `open` reopens (the areas that may not be worked).
- `assert_area_not_paused(session, work_task_id, ...)` — the enforcement: claiming
  a Work Task whose `(release, area)` is paused is refused while the upstream
  reopen is open (RW3 "never build on thawing ground"). A no-op outside a dev-lane
  release.

`work_tasks.claim_work_task` calls it (deferred import), beside PI-204's
`assert_area_owner`.

## 3. Boundary with PI-213 / PI-214 (Wave 3)

PI-212 is the **pause/resume mechanic**. The conservative full **cascade
re-validation** of every downstream area on re-freeze is **PI-213** (RW4); the
**blast-radius-sized approval** of the reopen request is **PI-214** (RW5). PI-212
deliberately stops at the reopen record + the pause; `reason` is a free-text
trigger now, upgraded to a finding-bound, approval-gated request by PI-214.

## 4. Schema / migration

`area_reopens` table + `AREA_REOPEN_STATUSES` vocab; SQLite `0069` + PG `0026`
(`create_table`, no CHECK rebuilds). Added to the 0038 scoped-tables allowlist.

## 5. API

- `POST /releases/{id}/area-reopens` `{area, reason}` → reopen.
- `POST /releases/{id}/area-reopens/{area}/refreeze` → re-freeze.
- `GET /releases/{id}/area-reopens` → `{reopens, paused_areas}`.

## 6. Tests

- `reopen_area` requires a dev-lane release; rejects a non-spine area and a double
  open; creates the open record.
- downstream pause: a claim in a downstream area is refused while a reopen is open;
  an upstream/parallel area is unaffected; `paused_areas` is the downstream set.
- `refreeze_area` resolves the reopen and the downstream resumes (claim allowed).
- a reopen of the top-rank area pauses nothing; an unranked area pauses nothing.
- SQLite + PG.

## 7. Requirement traceability

| REQ | Where |
|---|---|
| REQ-199 / RW2 only a frozen area reopens, in-lane, on downstream need | §2 `reopen_area` (dev-lane gate + reason) |
| REQ-200 / RW3 reopen pauses downstream until re-freeze | §2 `assert_area_not_paused` + `refreeze_area` |
