# PI-203 — File-Level Check-out/Check-in Lock: Architecture

**Wave 0 (independent) of the multi-agent release pipeline build** (build plan §19;
`blocked_by` nothing). Architecture-phase deliverable for **PI-203** — "Build the
file-level check-out/check-in lock for intra-area sub-agents." Project **PRJ-030**.
Branched off `main` (Waves 0–3 merged). The last unbuilt release-pipeline PI.

Governing design: `multi-agent-release-pipeline-architecture.md` §7.3
(DEC-469…474, FL-1…FL-6, REQ-203…207 refining REQ-194). It is the backstop under
the one judgment-based grain — an area owner's intra-area parallel sub-agent
fan-out.

## 1. Scope (the substrate, not the runtime)

PI-203 builds the **lock substrate**: the DB-backed named-resource locks +
acquire / verify / release / reclaim, and the detection-rule mapping from a diff to
logical resources. The **worktree-per-sub-agent + serialized merge-back** mechanic
(FL-3) is the *runtime* that drives this substrate (git worktree management,
spawning) — the same substrate-vs-runtime split used everywhere in this build; it
is a deferred follow-on. The substrate is what makes merge-back conflict-free
(disjoint locks) and provides the owner-independent verify.

## 2. The lock table (FL-4)

`resource_locks` — engagement-scoped satellite, surrogate PK:

| Column | Notes |
|---|---|
| `resource_name` | the named resource (a file path **or** a logical resource, e.g. `migration-chain`) — FL-1 |
| `holder` | the sub-agent holding it |
| `acquired_at`, `released_at` | `released_at IS NULL` = held |

- **Partial unique index** `(engagement_id, resource_name) WHERE released_at IS
  NULL` — at most one active lock per resource: the atomic, owner-independent,
  cross-process acquire backstop under `BEGIN IMMEDIATE` (FL-4). Overlapping
  acquires are refused → forced serial.

## 3. Detection rules (FL-2)

`detect_resources(paths)` maps a diff's file paths to the full set of named
resources to lock — each path itself, plus any **logical** resource its rule
matches. Default rule set: a path under `migrations/…*.py` also locks
`migration-chain` (two migrations are different files but collide on the chain).
Rules are module defaults with a clear seam for per-engagement extension.

## 4. Access layer (`access/locks.py`)

- `acquire(session, resource_name, holder)` — idempotent for the same holder;
  refused (forced serial) if held by another (FL-1).
- `acquire_many(session, resources, holder)` — all-or-nothing over a set (a
  planned overlap on any resource serializes the whole fan-out; FL-2 acquire).
- `release(session, resource_name, holder)` / `release_all(session, holder)` —
  holder-only; `release_all` at merge-back/end.
- `verify(session, holder, touched_paths)` — the FL-2/FL-5 verify moment:
  `detect_resources(touched_paths)`, confirm the holder held each; a miss is
  **retroactively acquired** (free → acquire; held by another → recorded conflict)
  and reported, so the miss feeds learning. Returns `{held, retroactively_acquired,
  conflicts}`.
- `reclaim(session, holder)` — FL-6 owner-supervised reclaim: release a dead
  child's locks. `reclaim_stale(session, ttl_seconds)` — the TTL backstop for a
  dead owner.
- `held_locks(session, resource_name=None)` — the read.

## 5. Schema / migration

`resource_locks` table; SQLite `0072` + PG `0029` (`create_table`, no CHECK
rebuilds — outside the refs/change_log discipline). Added to the 0038
scoped-tables allowlist.

## 6. API (`/locks`)

- `POST /locks/acquire` `{resources:[…], holder}` → acquire_many.
- `POST /locks/release` `{holder, resource?}` → release one or all.
- `POST /locks/verify` `{holder, touched_paths:[…]}` → the verify report.
- `POST /locks/reclaim` `{holder}` → reclaim a dead holder.
- `GET /locks?resource=` → held locks.

## 7. Tests

- acquire: idempotent same-holder; refused for another (forced serial); released →
  re-acquirable.
- acquire_many: all-or-nothing; a single conflict acquires none.
- detect_resources: a migration path also yields `migration-chain`.
- verify: an undeclared touch is retroactively acquired when free and reported as a
  conflict when held by another (FL-5).
- reclaim / reclaim_stale (TTL). SQLite + PG.

## 8. Requirement traceability

| REQ | Where |
|---|---|
| REQ-203 / FLR-1 check-out unit is a named resource | §2 (`resource_name` = path or logical) |
| REQ-204 / FLR-2 logical resources via detection rules; acquire + verify | §3, §4 (`detect_resources`, `acquire`/`verify`) |
| REQ-205 / FLR-3 worktree-isolated, serialized merge-back | substrate (disjoint locks); the worktree runtime is the deferred follow-on |
| REQ-206 / FLR-4 owner-independent DB locks, verified on diff | §2 (partial-unique), §4 (`verify`) |
| REQ-207 / FLR-5 dead sub-agent reclaimed | §4 (`reclaim` / `reclaim_stale`) |
