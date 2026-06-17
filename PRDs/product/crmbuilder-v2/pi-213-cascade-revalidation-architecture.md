# PI-213 — Conservative Full-Cascade Re-validation: Architecture

**Wave 3 of the multi-agent release pipeline build** (build plan §19; `blocked_by`
PI-212, merged). Architecture-phase deliverable for **PI-213** — "Conservative
full-cascade re-validation on reopen." Project **PRJ-034**. Branched off `main`
(Waves 0–2 merged).

Governing design: `multi-agent-release-pipeline-architecture.md` §14.2 step 4,
§14.3 (DEC-467, REQ-201 / RW4). Builds directly on PI-212's `area_reopens`.

## 1. The rule (RW4)

When an area is reopened, **every** area downstream of it must re-pass its QA/test
gate before the release can ship — **no suspected-no-impact exemption** (DEC-467).
The blast radius is the full downstream set; deep reopens are deliberately the most
expensive.

## 2. Mechanism (DEC-509)

Extend PI-212's `area_reopens` record with the cascade (migration `0070`, two
nullable JSON columns):

| Column | Notes |
|---|---|
| `cascade_areas` (JSON) | the downstream areas required to re-validate — set at reopen = `downstream_areas(area)` (the full set, no exemption) |
| `revalidated_areas` (JSON) | the subset that has re-passed |

- `reopen_area` (PI-212) now populates `cascade_areas` at creation.
- `revalidate_area(session, reopen_id, area)` — records that one downstream area
  re-passed; the area must be in `cascade_areas` and not already revalidated.
- `outstanding_revalidations(session, release)` — the union of
  `cascade_areas − revalidated_areas` across the release's reopens.
- **The ship gate:** `releases.transition` `deployment → shipped` is rejected
  while any outstanding re-validation remains (RW4 — a release cannot ship with an
  un-revalidated downstream area).

## 3. Boundary

PI-213 is the cascade *requirement + ship gate*. The reopen mechanic + downstream
pause is PI-212; the blast-radius-sized *approval* of the reopen is PI-214 (RW5).
"Re-validate" here is the recorded assertion that a downstream area re-passed; the
per-area QA/test execution is the area's own work (PI-206 area level).

## 4. Schema / migration

`area_reopens` gains `cascade_areas`, `revalidated_areas` (nullable JSON, default
empty). SQLite `0070` + PG `0027` (guarded add-column, no CHECK rebuilds).

## 5. API

- `POST /releases/{id}/area-reopens/{reopen_id}/revalidate` `{area}` → record a
  downstream re-validation.
- the area-reopens list (PI-212) surfaces `cascade_areas` / `revalidated_areas`;
  add `GET /releases/{id}/outstanding-revalidations`.

## 6. Tests

- `reopen_area` populates `cascade_areas` = the downstream set.
- `revalidate_area` reduces outstanding; rejects an area not in the cascade and a
  double re-validation.
- the ship gate: `deployment → shipped` rejected while outstanding; allowed once
  every cascade area is re-validated (no exemption — all required).
- SQLite + PG.

## 7. Requirement traceability

| REQ | Where |
|---|---|
| REQ-201 / RW4 reopen re-validates every downstream area, no exemption | §2 (full `cascade_areas`, `revalidate_area`, the `deployment → shipped` gate) |
