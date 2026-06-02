# PI-123 Slice 3 — Enforce plan: composite identifiers, FK, NOT NULL (analysis + revised sequencing)

**Status:** Slice 3 design output (branch `pi-123`, WTK-028). Companion to
`pi-123-unified-db-architecture.md` (D3/D4/D8/D9).

This documents a build-discovered finding from mapping the actual constraint
landscape of the 30 scoped tables. It revises how the "enforce" step (the
composite-identifier collision fix + NOT NULL + FK) is delivered: **not as an
independently-mergeable Alembic chain migration, but as part of the
consolidation/cutover that builds the unified DB fresh at the strict schema.**

## 1. The constraint landscape is heterogeneous

Mapping `engagement_id`-bearing tables by how identifier uniqueness is enforced
splits them into three classes:

| Class | Tables | Identifier uniqueness today | Enforce change |
|---|---|---|---|
| **A — identifier-as-PK** (19) | sessions, domains, entities, fields, personas, processes, projects, workstreams, work_tasks, work_tickets, conversations, reference_books, crm_candidates, manual_configs, test_specs, requirements, deposit_events, close_out_payloads, commits | the `<entity>_identifier` column **is** the PRIMARY KEY | **PK → composite** `(engagement_id, <identifier>)` (full table rebuild) |
| **B — surrogate-PK + UNIQUE(identifier)** (9) | decisions, planning_items, risks, topics, refs, charter, status, reference_book_versions | `id` PK + a separate `UNIQUE` on the identifier/version | **swap UNIQUE → composite** `(engagement_id, <identifier>)` |
| **C — no identifier-unique** (2) | change_log, identifier_reservations | none (id PK only) | **NOT NULL + FK + index only** |

Notable specials:
- **refs** is class B but has *two* uniques: `UNIQUE(reference_identifier)` → `(engagement_id, reference_identifier)`, **and** `uq_ref_full(source_type, source_id, target_type, target_id, relationship_kind)` → prefix with `engagement_id` (D4 — the same edge can exist in two engagements).
- **commits** is class A and also has `UNIQUE(commit_sha)` → `(engagement_id, commit_sha)` (a sha is recorded per-engagement).
- **reference_book_versions** has `uq_reference_book_version(reference_book_identifier, version_label)` → prefix `engagement_id`.
- **charter / status** are versioned singletons: `uq_*_version(version)` → `(engagement_id, version)` so each engagement has its own version series.
- **engagement_areas** PK is `engagement_area_name` → composite `(engagement_id, engagement_area_name)`.

## 2. Why the enforce is NOT an independently-mergeable chain migration

The add-nullable→backfill→enforce sequence (D8) has a hard ordering constraint
the chain cannot satisfy on the live per-engagement DBs:

- A lazy-applied chain migration that sets `engagement_id NOT NULL` (or installs
  composite uniqueness that depends on a non-NULL discriminator) **fails on the
  live DB**, whose rows are still NULL until backfill. The desktop UI lazy-runs
  `alembic upgrade head` at engagement activation, so a `0039` enforce head would
  break activation of `CRMBUILDER.db` / `CBM.db`.
- The backfill is **engagement-aware** (each row's `engagement_id` = the
  engagement that owns the file), which a blind chain migration cannot know — the
  ownership lives in the marker/filename at runtime, not in the DB.

**Conclusion:** the enforce is reached by the **consolidation building the unified
DB fresh at the strict (target) schema and copying rows in with `engagement_id`
stamped** (D9 steps 2–6), not by ALTER-ing the live tables in place. Building
fresh + insert sidesteps the 19 in-place PK rebuilds entirely — `create_all`
(or a clean chain on a fresh DB) materialises the composite PKs/uniques + NOT
NULL + FK, and the consolidation INSERTs the backfilled rows.

## 3. The model-strictness flip is coupled to the cutover

Expressing the strict schema in the ORM (composite PK/unique, `engagement_id`
NOT NULL + FK on the mixin) is what makes `create_all` build the target — but it
**breaks the current dormant test suite**, which inserts scoped rows without an
`engagement_id` (no active engagement, stamp dormant). So the model flip is
bundled with:

1. Enabling engagement scoping in the test fixtures (install + an active
   engagement) so the **write-stamp** supplies `engagement_id` on every insert.
2. The consolidation building fresh + copying (§2).
3. Turning on the unset-guard enforcement (the fail-loud from Slice 2b).

These are **one coherent cutover**, not separable pre-cutover slices. Slices 1–2
(additive `engagement_id` column + dormant filter/stamp/middleware) are the safe,
independently-mergeable foundation; the strict-schema flip + consolidation +
enforcement is the cutover transition.

## 4. Revised Slice 3 → Data Migration / Deployment sequencing

- **Slice 3 (this analysis + the crux proof):** the constraint classification
  above; an empirical proof that the target composite-identifier schema lets the
  same identifier coexist across engagements while still rejecting an
  intra-engagement duplicate (`test_engagement_id_collision_coexistence`); and
  the access-layer **refs same-engagement assertion** (D4) authored guarded.
- **Cutover unit (Data Migration + Deployment phases):** flip the model to the
  strict schema + update test fixtures to stamp; build the consolidation that
  creates the fresh unified DB at the strict schema and copies `CRMBUILDER.db` +
  `CBM.db` rows in with `engagement_id`; validate (the cross-engagement
  leak-test + per-table count/identifier parity); enable scoping + enforcement;
  retire the meta engine; repoint the default DB. This is best executed as one
  focused unit given the 19 PK changes and the dormant→active flip.

## 5. Cross-references
- `pi-123-unified-db-architecture.md` — D3 (composite identifiers), D4 (refs), D8 (add-nullable→backfill→enforce), D9 (consolidation builds fresh + copies).
- `tests/crmbuilder_v2/migration/test_engagement_id_collision_coexistence.py` — the empirical crux proof.
