# PI-384 — Per-prefix identifier-assignment lock: full repo coverage (REQ-446)

**Release:** REL-063 (manual) · **Project:** PRJ-097 · **Date:** 2026-07-01

## Background

REQ-446 / PI-384: server-assigned prefixed identifiers are allocated by a
**read-max-then-insert-and-retry** loop. On SQLite `BEGIN IMMEDIATE` serialises
writers so it never races; on **Postgres** (now the live cloud store) concurrent
writers read the same max, collide on the unique index, linear-probe, and at high
concurrency exhaust the retry budget (the PI-100 finding: ~2.3% failures at 16
writers). The fix is `access/_helpers.serialize_identifier_assignment(session,
prefix)` — a Postgres transaction-level `pg_advisory_xact_lock` keyed on the
prefix, a no-op on SQLite — called before the max-read so same-prefix writers
queue cleanly.

The first pass locked the **9 highest-traffic governance repos**. This pass
completes coverage across the **remaining ~44 auto-assign repos** — now urgent
because the production store is live multi-user Postgres.

## What landed

**53 repositories now call the lock** (9 prior + 44 this pass). Coverage:

- **41 uniform repos** — those with `candidate = next_<entity>_identifier(session)`
  and a `_IDENTIFIER_PREFIX` / `_PREFIX` constant — got
  `serialize_identifier_assignment(session, <PREFIX>)` inserted before the
  max-read (applied by a one-off script, then removed).
- **4 special cases, by hand:**
  - `task_transitions` — inline `next_prefixed_identifier(...)` (prefix `TXN`).
  - `artifact_versions` — assigns `version_number = max+1` **per artifact**; the
    same read-then-insert race on a non-identifier key. Locked per artifact
    (`artifact_version:<type>:<id>`).
  - `references` — **the most important**: REF-NNNN is read-max-then-inserted with
    **no retry loop at all**, so a concurrent collision was a hard 500, not a slow
    retry. References are the highest-traffic write (every edge). Locked on `REF`.
  - `identifier_reservations` — the reserve path reads `max(table, active
    reservations)` then inserts a block; locked per entity type
    (`reserve:<entity_type>`) so two reservers never overlap.

**Deliberately not locked (documented, not a silent cap):**
- `planning_claims` — inserts a `(release, area, claimed_by)` row guarded by a
  unique constraint with **no auto-assign and no retry loop** (a single-attempt
  claim). There is no read-then-insert identifier race to serialise.
- `identifier_reservations` locks reserve-vs-reserve only; reserve-vs-direct-create
  is out of scope (the reservation system is the sole assigner during parallel
  runs by design).

## Verification

- **Full access suite: 1931 passed** — every insertion is correctness-preserving.
- The PI-100 concurrency validation (`test_concurrency_substrate.py`) still holds
  (SQLite by default; Postgres when `CRMBUILDER_V2_TEST_PG_URL` is set — the real
  proof, per the PI-100 runbook: use a throwaway `crmbuilder_concval_test` DB,
  never the live store).
- ruff clean.

The lock helper is unchanged; this pass is purely its application across the
remaining call sites.
