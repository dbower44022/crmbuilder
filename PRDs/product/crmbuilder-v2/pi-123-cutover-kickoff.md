# PI-123 Cutover — Session Kickoff (Stages 2–4 + build-closure)

**Use this to open a fresh Claude Code session that continues PI-123.** The safe,
additive, dormant foundation is built, tested, and pushed; what remains is the
**cutover** — flipping the dormant machinery to active and consolidating the live
data into one multi-tenant DB. This is the riskiest part of the PI (schema
surgery + a destructive live-data migration), so it is handed off deliberately.

---

## 0. First moves (orientation)

1. `git checkout pi-123 && git pull` — all PI-123 code lives on this branch (off
   `main`). Branch head at handoff: **`29a2ad4`** (cutover Stage 1).
2. Read, in order:
   - `PRDs/product/crmbuilder-v2/pi-123-unified-db-architecture.md` — the Architecture-phase design (D1–D11). The spec.
   - `PRDs/product/crmbuilder-v2/pi-123-slice3-enforce-plan.md` — the constraint-class landscape + why the enforce is consolidation-coupled. **Read this carefully — it drives Stages 2–4.**
   - This kickoff.
3. Skim the branch commits `502a9b6..29a2ad4` (Slices 1, 2a, 2b, 2c, 3, cutover Stage 1) — each commit message is a precise record of what landed and why.
4. **Tier-2 governance orientation** (CLAUDE.md protocol): `curl http://127.0.0.1:8765/planning-items/PI-123` etc. (run `crmbuilder-v2-api &` first).

## 1. What PI-123 is

Replace the per-engagement-DB-files architecture (one `data/engagements/X.db`
each, routed by `CRMBUILDER_V2_DB_PATH`, a separate meta DB, an Alembic chain
each) with **a single multi-tenant DB keyed by a row-level `engagement_id`**.
It is the production-architecture baseline and the practical enabler of the
Agent Profile Registry's cross-engagement learning (DEC-373). **PI-122 is
`blocked_by` PI-123.** Project: **PRJ-019** (Production Database Architecture).

The headline crux — preserve per-engagement identifier sequences (CBM `SES-001`
*and* CRMBUILDER `SES-150` coexist, no history renumbered) — is solved by
composite `(engagement_id, identifier)` keying (DEC-375 / D3), proven in
`tests/crmbuilder_v2/migration/test_engagement_id_collision_coexistence.py`.

## 2. What is DONE (branch, pushed, all tested)

| Commit | Slice / Stage | Nature |
|---|---|---|
| `502a9b6` | 1 — fold engagements into the unified `Base` (migration `0037`) | additive, dormant |
| `01d4a53` | 2a — nullable `engagement_id` on all 30 scoped tables (`0038`) | additive, dormant |
| `222f482` | 2b — central scope mechanism: `ContextVar` + `do_orm_execute` read-filter + `before_flush` stamp + unset-guard (`access/engagement_scope.py`) | dormant |
| `3165a7a` | 2c — request wiring: `X-Engagement` middleware + marker fallback + `engagement_scoping_enabled` flag (default off) | dormant, default-off |
| `0f1838a` | 3 — enforce plan (constraint-class analysis) + collision-coexistence proof | analysis + proof |
| `29a2ad4` | **Cutover Stage 1** — `get_by_identifier` helper; converted 64 identifier-as-PK `session.get` sites | behaviour-preserving |

**Everything is dormant.** With `engagement_scoping_enabled=False` (the default)
and no active engagement, the filter/stamp no-op, so the running app is
unchanged. The whole apparatus activates only at the cutover.

### Build-discovered refinements (fold into the design doc + a DEC at build-closure)
- **Discriminator = the stable identifier** `engagements.engagement_identifier` (`ENG-NNN`), not a new integer surrogate (DEC-375 said "integer surrogate"; the identifier is never renamed, so it *is* the durable key — less churn, consistent with v2's identifier model).
- **The enforce is consolidation-coupled**, not an independently-mergeable Alembic chain head (a NOT-NULL/composite head would break live `upgrade head` pre-backfill). The target schema is reached by **building the unified DB fresh at the strict schema and copying rows in** (D9), which sidesteps in-place PK rebuilds.
- **Slice 1's "retire the meta engine / serve `/engagements` from one engine"** is staged to the cutover (registry must stay shared in the per-engagement world).

## 3. The remaining work — the cutover (Stages 2–4)

### Stage 2 — strict-schema flip + central fixture stamp (the invasive one)

Goal: make the ORM express the **target** schema so a fresh `create_all` builds
it, and make the existing test suite pass under active scoping.

1. **Mixin → strict** (`access/models.py::EngagementScopedMixin`): `engagement_id`
   becomes `nullable=False` + `ForeignKey("engagements.engagement_identifier")`.
2. **Composite identifiers** per the three classes in `pi-123-slice3-enforce-plan.md` §1:
   - **Class A (19 identifier-as-PK tables):** PK → `(engagement_id, <entity>_identifier)`.
   - **Class B (surrogate-PK + UNIQUE):** swap `UNIQUE(<identifier>)` → `(engagement_id, <identifier>)`; for `refs` also prefix `uq_ref_full` with `engagement_id` and swap `UNIQUE(reference_identifier)`; `commits` also `(engagement_id, commit_sha)`; `reference_book_versions`, `charter`, `status` version uniques → prefixed; `engagement_areas` PK → `(engagement_id, engagement_area_name)`.
   - **Class C (change_log, identifier_reservations):** NOT NULL + FK + index only.
3. **Central fixture flip** (`tests/crmbuilder_v2/conftest.py::v2_env`): set
   `CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED=true`, seed one engagement in the
   engagements table (so the FK resolves), `install_engagement_scope` on the
   factory, and set an active engagement so the **write-stamp fills
   `engagement_id` on every insert**. Most tests then pass unchanged. Turn on
   `engagement_scope.set_enforcement(True)` here too.
4. **Expected fallout** (budget for it): shape tests that count columns/PK;
   tests that create *multiple* engagements or assert cross-engagement behaviour;
   the meta-DB two-database tests; identifier-sequence tests. Work through them —
   most are mechanical (the row now carries `engagement_id`; the PK is composite).
5. **Gotchas:** Stage 1 already removed the `session.get(Model, identifier)`
   blast radius via `get_by_identifier`. Audit the remaining D5 ORM-bypass list
   (raw SQL, the exporter, the change-log emitter, `apply_close_out.py`) — see
   `pi-123-unified-db-architecture.md` §7. The catalog YAMLs are decommissioned,
   so full-chain alembic tests are skipped; validate via `create_all` or a copy
   of the live DB (memory: `project_v2_catalog_data_gitignored`).

### Stage 3 — consolidation script + leak-test (against copies, non-destructive)

Build `migration/unify_engagement_dbs.py` (or similar) implementing D9: create a
fresh unified DB at the strict schema (`create_all`), then for each source
`data/engagements/{CODE}.db`, copy every scoped table's rows in with
`engagement_id` stamped (the engagement's `ENG-NNN`). Seed `engagements` from the
meta DB. Then validate: per-engagement per-table COUNT parity vs source;
identifier-set parity; ref-edge counts; **the cross-engagement leak-test** (seed
≥2 engagements with intentionally-colliding identifiers, assert every read/list
endpoint and identifier-assignment path returns only the active engagement's
rows). Test against **copies** of the live `CRMBUILDER.db` + `CBM.db` (read-only
on the originals) and synthetic fixtures. Numeric PKs reassign freely (refs join
by identifier string, not numeric FK — confirm in the audit).

### Stage 4 — live cutover (DESTRUCTIVE; Doug in the loop)

**Do not run this autonomously.** One-step-at-a-time at Doug's terminal (memory:
`feedback_one_step_at_a_time`), with backups:
1. Back up `data/engagements/CRMBUILDER.db` + `CBM.db` + the meta DB.
2. Run the consolidation → `data/v2-unified.db`; validate (Stage 3 checks) on the real output.
3. Repoint the default DB at the unified file; retire the meta engine / its chain (`access/meta_db.py`, `migrations/meta/`, `meta_exporter`, `run_meta_migrations`); enable scoping + enforcement by default.
4. Smoke-test the desktop app + API against the unified DB.
5. Cleanup commit removing the per-engagement files + meta DB after validation in use.

## 4. Close-out (on `main`, after merge)

Per the Branch-work protocol, governance lands on `main`. After the cutover
merges:
- **Build-closure** (DEC-232 / SES-074 pattern): a close-out payload that ingests
  the branch's slice commits (`commits` section), marks **WTK-026/027/028** (and
  the cutover work tasks) Complete, completes **WSK-009** (Development) and the
  Testing/Data-Migration/Deployment workstreams, and **resolves PI-123**
  (`resolves_planning_items`). Re-key identifiers to `main`'s current heads at
  authoring (verify with `list_recent_sessions` etc.).
- Author a **DEC** capturing the build-discovered refinements (§2): the
  string-identifier discriminator, the consolidation-coupled enforce.
- Fold those refinements into `pi-123-unified-db-architecture.md` (annotate D1/D3/D8).
- Read `specifications/governance-recording-rules.md` and
  `reference_v2_closeout_schema_gotchas` (memory) before authoring the payload.
- Once PI-123 is Resolved, **PI-122** (Agent Profile Registry) is unblocked — the
  registry build is the next workstream (registry PRD §14 build order).

## 5. Working rules (don't relearn the hard way)
- **Branch protocol:** `pi-123` carries only code/schema/migration/test/doc commits — never `db-export/`, `deposit-event-logs/`, or `apply_close_out.py` (it refuses off `main`; that's why ~18 `apply_close_out` tests "fail" in a branch run — they pass on `main`).
- **Test pollution:** `meta_export_dir()` is a hardcoded repo path — never seed engagements via `engagement_repo.create_engagement` in tests (it writes the real `db-export/meta/engagements.json`); insert `EngagementRow` directly (see `tests/crmbuilder_v2/api/test_engagement_scope_middleware.py`).
- **ContextVar + middleware:** the scope middleware is **pure ASGI** on purpose — `BaseHTTPMiddleware` drops ContextVar propagation to the handler.
- Commit messages on this branch are the source of truth for what each slice did.
