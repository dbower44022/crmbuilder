# PI-103 — Edit-locking for promoted governance records (REQ-396)

**Release:** REL-012 (Multi-User & Concurrency Safety) · **Project:** PRJ-020 ·
**Requirement:** REQ-396 (confirmed, *should* priority) · **Date:** 2026-06-30

## The problem

Once a draft governance record is promoted to a real record, the per-session
draft token that protected it during creation retires — leaving already-real
records with **no protection against two agents editing the same record and
silently overwriting one another** (the modify-modify / lost-update problem).
REQ-396's acceptance: *"Two concurrent edits to the same promoted record cannot
silently overwrite one another; a write based on stale state is rejected."*

## Decision — optimistic concurrency on `updated_at` (chosen 2026-06-30)

The mechanism choice REQ-396 deferred to this PI. Three options were on the
table — optimistic precondition on `updated_at`, a monotonic `row_version`
integer, and an advisory lease. **Chosen: optimistic precondition on the existing
`updated_at`.**

- **Why:** every governance row already carries an `updated_at` that bumps via
  `onupdate=_utcnow` on any successful update, so a committed edit always advances
  it — a reliable compare-and-swap token with **zero schema change**. `row_version`
  is marginally more robust (no same-tick hazard) but costs a dual-head migration
  across ~35 tables for a *should*-priority requirement; an advisory lease is
  coordination-heavy and doesn't itself prevent a lost update. The requirement's
  own scope note lists "reuse `updated_at`" as an acceptable mechanism.
- **How it works:** a caller that read a record passes the `updated_at` it saw as
  `expected_updated_at` on its update. If the record has since changed, the stored
  `updated_at` no longer matches → the write is **refused with 409 `stale_write`**
  rather than clobbering the concurrent change. When `expected_updated_at` is
  omitted the guard is skipped — **opt-in per request, fully backward compatible**.
- **Residual hazard (accepted):** two commits within the same microsecond would
  share an `updated_at`. Serialized writers (SQLite `BEGIN IMMEDIATE`; the
  Postgres per-prefix assignment lock) plus microsecond resolution make this
  vanishingly unlikely in the dogfood. If it ever proves real, the same call sites
  swap to a monotonic `row_version` with no API change — a documented follow-on.

## Implementation

- **`access/_helpers.check_lost_update(current_updated_at, expected_updated_at, *,
  entity_type, identifier)`** — the generic guard. `None` precondition → no-op;
  matching → pass; stale → `ConflictError` (409, message contains `stale_write`);
  unparseable precondition → `ValidationError` (422). Both sides parse to aware
  datetimes and compare for equality, tolerating a trailing `Z` vs `+00:00`.
- **Wired into the update paths of the entities the ADO fleet concurrently edits**
  — where lost updates actually occur:
  - `decisions.update`
  - `planning_items.update`
  - `work_tasks.patch_work_task` **and** `update_work_task`
  - `workstreams.patch_workstream` **and** `update_workstream`
  Each accepts an optional `expected_updated_at` and calls the guard immediately
  after loading the row, before any mutation.
- **API:** an optional `expected_updated_at` (prefixed `work_task_…` /
  `workstream_…` where the router strips a field prefix) on the update/patch
  schemas: `DecisionUpdateIn`, `PlanningItemUpdateIn`, `WorkTaskPatchIn`,
  `WorkstreamPatchIn`. The router threads it to the repository.

## Scope boundary (explicit — not a silent cap)

Coverage is the **concurrently-edited governance surface** (decisions, planning
items, work tasks, workstreams). The remaining governance entities (sessions,
conversations, requirements, projects, releases, findings, learnings) and the
single-author design/catalog entities (entity, field, layout, persona, process,
service, …) are **not yet wired**. They inherit the identical three-line pattern
(schema field → router pass-through → `check_lost_update` after the row load) as a
mechanical follow-on; they were deprioritised because the ADO fleet does not edit
them concurrently the way it does work tasks and workstreams during a build.

## Tests

- `tests/crmbuilder_v2/access/test__helpers.py` — the guard's unit contract
  (none/match/Z-suffix/stale/malformed/naive-current).
- `tests/crmbuilder_v2/access/test_decisions.py` — repo-level match/stale/omitted/
  malformed, proving the concurrent edit survives a refused stale write.
- `tests/crmbuilder_v2/api/test_decisions.py` — the full HTTP round-trip: PATCH
  with a stale precondition → 409 `stale_write`, the prior edit survives; fresh
  precondition → 200; no precondition → 200 (backward compatible).
