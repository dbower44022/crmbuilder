# Production Cutover — Deployment-Planning Design Pass (Kickoff)

**Planning items spanned:** PI-100 (PRJ-019, scale validation), PI-135 (PRJ-020, Postgres cutover), PI-136 (PRJ-020, per-user identity/permissions activation)
**Projects:** PRJ-019 (Production Database Architecture) + PRJ-020 (Multi-User & Concurrency Safety)
**Session type:** Deployment-planning / Architecture design pass. **No provisioning, no cutover, no flipping defaults.** Output is a *cutover runbook + design doc + decisions + reviewable requirement(s)*, plus a decomposition that separates operator-only steps from ADO-buildable code.
**Why this session exists:** The production *capabilities* are all built — Postgres support (PI-α), de-filed unified DB (PI-β), identity/RBAC (PI-γ) — but they are **not activated for production**, by design: SQLite is still the default and auth is off. The activation is currently three bare-stub PIs in two projects with no requirement, no decomposition, and no plan. Much of it is operational (provision managed PG, choose topology, decide cutover timing) — *your* calls, not autonomous agent builds. This session turns the three stubs into one coherent, sequenced production-cutover plan so the operational decisions are made deliberately and the genuinely-buildable code is split out cleanly.

---

## 1. The three PIs are one effort split across two projects

| PI | Project | Facet |
|----|---------|-------|
| PI-100 | PRJ-019 | Validate the production substrate at target concurrent-writer scale — the **scale gate** for the flip |
| PI-135 | PRJ-020 | Flip the production store to Postgres for true concurrent writes |
| PI-136 | PRJ-020 | Turn on per-user identity + permissions (RBAC) and complete it for production |

**Resolve the project-boundary question as a first-class output.** PRJ-019's stated purpose is that production-deployment work *"accrues here,"* yet the activation PIs live in PRJ-020, and PI-100 (PRJ-019) feeds PI-135 (PRJ-020). Recommend one of: (a) consolidate the cutover PIs under one project, or (b) keep the split but declare PI-100 → PI-135 the cross-project dependency explicitly (`blocked_by`). Either is fine — just make it deliberate, not accidental.

---

## 2. Orientation — read these first

**Tier 1:** `CLAUDE.md` — the **PI-α Postgres**, **PI-β de-file**, **PI-γ RBAC**, and **PI-110 (API lifecycle / desktop-owns-API)** sections. Critical standing facts: the flip mechanism is `CRMBUILDER_V2_DATABASE_URL` set → Postgres, unset → SQLite default (`Settings` reads `crmbuilder-v2/data/crmbuilder.env` each process start); **dual-head Alembic** — Postgres has its own tree at `migrations/pg/` (`0001_pg_baseline` = `create_all`) and must **never** be run through the SQLite chain; **RBAC auth is OFF by default**; **the desktop UI owns + auto-restarts the API** today (a model that changes for a shared multi-user server).

**Tier 2 — the architecture + runbook docs (read from disk):**
- `production-multitenant-api-architecture.md` — the umbrella prod design (PI-α/β/γ decomposition, D5–D8).
- `pi-alpha-postgres-foundation-architecture.md` + `pi-alpha-postgres-migration-runbook.md` — the Postgres foundation and the **one-shot data migration** (`crmbuilder_v2/migration/sqlite_to_postgres.py`, `migrate(sqlite, pg_url)`, FK-ordered, validated). **The PI-α "Deployment phase" — prod topology, managed PG, flip-the-default timing — was explicitly deferred and is exactly this session's subject.**
- `pi-beta-defile-architecture.md` — the `X-Engagement`-header request scoping (`engagement_scoping_enabled` default True), and that prod enforcement is currently off for the single-engagement dogfood.
- `pi-gamma-rbac-architecture.md` — identity, `role_assignments`, `service_agent` principals, `mint_agent_principal`; what "complete it for production" (PI-136) actually entails.
- `pi-123-stage4-cutover-runbook.md` — the prior unified-DB cutover runbook; the prod cutover extends this pattern.

**Tier 2 — governance (read live, `X-Engagement: CRMBUILDER`):** `GET /planning-items/PI-100`, `/PI-135`, `/PI-136`; `GET /decisions/DEC-446` (PI-100 reframe). Skim PI-125/126/127 (the α/β/γ resolutions) for what shipped.

---

## 3. Questions this session must answer

1. **Topology.** Managed Postgres (provider? region?) vs self-hosted on the existing droplet. Connection pooling (`QueuePool` is wired; `pre_ping`/`recycle` set) — sized for what?
2. **The shared-server shift.** Production multi-user means a **standing, shared API server**, not the desktop-UI-owned-and-auto-restarted API of today (PI-110). Define the prod process model: who runs/monitors the API, how the desktop app connects to a remote prod API vs a local one, and what happens to the auto-restart ownership.
3. **Cutover sequence + rollback.** Rehearse → provision PG → run `sqlite_to_postgres.migrate()` → validate (incl. the leak-test) → set `CRMBUILDER_V2_DATABASE_URL` in `crmbuilder.env` → restart → verify. Define the **rollback** (unset the URL → back to SQLite) and the point of no return (when prod writes have landed only in PG).
4. **Scale gate (PI-100).** What load must Postgres demonstrably hold before the flip — order-of-magnitude peak concurrent writers per engagement and total, partitioned vs contending. How is it measured (the `CRMBUILDER_V2_TEST_PG_URL` CI path, a load harness)?
5. **Auth activation completion (PI-136).** Enumerate what "complete it for production" means beyond setting a flag: user provisioning, `role_assignments` for real human users, the `X-Engagement` enforcement transition (`engagement_scoping_enabled`), how the desktop app authenticates, what the default-deny posture is. What's already built vs genuinely remaining.
6. **Ops consolidation.** Backups (managed-PG automated vs the current mariadb-dump-style), the rotating API log (`api.log`) in a shared deployment, monitoring/health (PI-111 heartbeat is the deferred follow-on).

---

## 4. Deliverables (triple-artifact close-out)

1. **A production-cutover design doc + runbook** at `PRDs/product/crmbuilder-v2/production-cutover-plan.md`: topology decision, the prod process model (§3 q2), the step-by-step cutover + rollback runbook (extending `pi-123-stage4-cutover-runbook.md`), the scale-gate definition (q4), and the auth-activation completion checklist (q5).
2. **Governance decisions** for the load-bearing choices — managed-PG-vs-self-hosted, cutover timing trigger, the prod process/ownership model, the project-boundary resolution (§1). These are operational architecture decisions; capture them as `POST /decisions`.
3. **A traced, reviewable requirement** (or small set) for the production-multi-user activation, anchored to a topic + provenance conversation and surfaced in the **Requirements Review panel** — the gate before any implementing code is ADO-built.
4. **A decomposition recommendation that splits the work by who does it:** operator-only steps (provision PG, run the migration, flip the env var, prod ops) vs ADO-buildable code (auth-completion code, a load-test harness, a health heartbeat, any cutover tooling). Only the second set becomes dispatchable PIs/workstreams; the first stays operator runbook steps.

**Explicitly out of scope:** provisioning anything, running `sqlite_to_postgres.migrate()` against prod, setting `CRMBUILDER_V2_DATABASE_URL`, or enabling auth. This session plans the cutover; it does not perform it.

---

## 5. After this session

The buildable subset (auth completion, load harness, health heartbeat) becomes normal ADO-buildable PIs once their requirement is approved. The operational cutover stays an **operator-run runbook** executed deliberately at a time you choose, gated on the PI-100 scale result. PI-100/PI-135/PI-136 stay `Draft` until then; the plan is what makes them executable.

**Prioritization note:** this is real production work, but the repo's stated active direction is the Master CRMBuilder PRD / v2 dogfood, which runs fine on the SQLite default. Confirm the cutover is worth scheduling now vs. when a second concurrent user/engagement actually arrives.
