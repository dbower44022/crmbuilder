# Production Multi-Tenant API — Architecture & Decomposition

**Status:** v0.1 — Architecture/design pass (06-02-26). Successor program to PI-123
(the unified multi-engagement DB). Produces the design + decomposition the build
phases consume; it is **not** implementation.
**Project:** PRJ-019 — Production Database Architecture.
**Builds on:** `pi-123-unified-db-architecture.md` (the unified row-level
`engagement_id` schema, the central ContextVar scope filter/stamp, the
Session-class listener registration) — all of which carry forward unchanged.
**Governing direction (06-02-26, Doug):** make the API a true multi-tenant,
**multi-user** application; **migrate to Postgres**; **eliminate the
per-engagement-file cutover apparatus**; **eliminate the db-export snapshot
process**; **all clients use API or MCP** (no static-file fallback). DB is the
source of truth; the git-tracked governance trail becomes the close-out payloads
+ deposit-event logs.

---

## 1. Purpose

PI-123 made the *data* multi-tenant (one DB, every governance/methodology row
carries `engagement_id`, reads filtered + writes stamped centrally). But the
*runtime* is still half in the per-engagement-file world: a single-active
marker, a subprocess-swap-per-engagement activation worker, the meta DB,
file-routing, a per-transaction JSON snapshot export, and no concept of users.
This program finishes the transition to a genuine production service:

1. **Postgres** as the store (real concurrency; the SaaS-grade foundation).
2. **Identity, authentication, and RBAC** — multiple principals (human users
   *and* AI service agents), roles, per-engagement permissions.
3. **Remove the per-engagement-file apparatus** entirely — one service, one DB,
   engagement selected per request.
4. **Remove the snapshot/export process** — the DB is authoritative; no
   per-table JSON in git.
5. **API/MCP only** — retire the static-JSON file-fallback orientation tier.

The just-built `v2-unified.db` is the clean, validated **source** for the
Postgres migration — that is its payoff.

---

## 2. The change in one paragraph

Move CRMBuilder v2 from a single-operator SQLite desktop tool that binds one
engagement's file per process to a **deployed, Postgres-backed, multi-tenant
service** where each request carries an **authenticated principal** (a human
user or an AI service agent) whose **roles** grant access to specific
**engagements**; the access layer composes RBAC with the existing per-request
engagement scope (filter + stamp), so the same query path enforces both "which
tenant" and "who, with what rights." The per-engagement files, meta DB,
activation-worker subprocess swap, single-active marker, and the JSON snapshot
export all disappear; the DB is the source of truth and clients reach it only
through the API or MCP.

---

## 3. Current state (post PI-123 cutover, precise)

| Concern | Current mechanism | Fate |
|---|---|---|
| Store | SQLite `data/v2-unified.db` (one file, row-level `engagement_id`, strict composite keys) | → **Postgres** (D1); v2-unified.db becomes the migration source (D9) |
| Concurrency | `isolation_level=None` + `BEGIN IMMEDIATE` + `busy_timeout=5000` (single-writer serialization), `PRAGMA foreign_keys=ON` | → PG MVCC + connection pool (D10) |
| JSON columns | SQLite `JSON` (text) — `session_medium_metadata`, `payload`, `commit_parent_shas`, … | → `JSONB` (D1) |
| Engagement selection | per-request `X-Engagement` header / `current_engagement.json` marker → `ContextVar`; `do_orm_execute` filter + `before_flush` stamp on the **Session class** | filter/stamp **kept**; marker **retired** → per-request from the authenticated principal (D5) |
| Engagement routing | `route_settings_to_engagement` (now points at the unified file), `engagement_db_path`, the meta DB (`meta_db`, `meta_models`, `migrations/meta/`, `meta_exporter`), the two-database server, `dogfood_v0_5`, `lazy_migration`, the activation-worker subprocess swap (`ui/activation_worker.py`) | → **removed** (D6) |
| Identity / auth | none (localhost, single operator; `SharedSecretMiddleware` already removed; the OAuth 2.1/PKCE infra shelved upstream-blocked, DEC-244) | → **principals + tokens + RBAC** (D2/D3/D4) |
| Snapshot/export | `session_scope` flush→`build_snapshot`→`write_staging`→`promote`; git-tracked `db-export/*.json`; `meta_exporter` | → **removed** (D7); payloads + deposit-event logs are the git trail |
| Client orientation | CLAUDE.md Tier-2 has an MCP path **and** a static-JSON file-fallback (`db-export/`) | → **API/MCP only** (D8) |
| Clients | Claude Code, desktop app (`StorageClient` → API), MCP-stdio (Claude Desktop), the chat-UI-on-Anthropic-API (DEC-245); claude.ai-web blocked upstream | all → API/MCP principals |

Live engagements in the unified DB: `CRMBUILDER` (ENG-001, full data) and `CBM`
(ENG-002, freshly empty per the cutover decision).

---

## 4. Target state

```
                         Postgres (one cluster/database)
   ┌──────────────────────────────────────────────────────────────────────┐
   │  principals (humans + AI service agents) · api_tokens · roles ·        │
   │  role_assignments (principal × engagement × role)   ← RBAC             │
   │  engagements (tenant registry)                                         │
   │  ENGAGEMENT-SCOPED tables (engagement_id NOT NULL FK, composite keys)  │
   │  SYSTEM/SHARED tables (catalog_*, + future registry)                   │
   └──────────────────────────────────────────────────────────────────────┘
            ▲ one connection pool; MVCC; no single-writer lock
            │
   [ FastAPI service ] —— per request ——▶ resolve_principal(req) → Principal{
            ▲                                  identity, roles, allowed_engagements }
            │                              → set active engagement (ContextVar)
   API / MCP only  ── Claude Code · Desktop · MCP · chat-UI-on-API · (claude.ai later)
```

A request is authenticated to a **Principal**, the Principal's **roles**
determine which **engagements** it may touch and read-vs-write rights, the
chosen engagement is set on the scope `ContextVar`, and the PI-123 filter/stamp
do the row-level tenant isolation. No marker, no per-engagement file, no
snapshot.

---

## 5. Design decisions

### D1 — Postgres is the store
Replace SQLite with Postgres. The PI-123 schema **ports directly** — it was
designed without SQLite-only tricks beyond batch-mode DDL, and composite PKs /
composite uniques / FKs / partial-unique indexes are all native to PG. Changes:
`JSON` columns → **`JSONB`**; drop the SQLite transaction hacks
(`isolation_level=None`, `BEGIN IMMEDIATE`, `busy_timeout`, the `connect`/`begin`
pragma listeners) in favor of standard SQLAlchemy/PG transactions; keep the
engagement-scope event listeners (Session-class `do_orm_execute` + `before_flush`)
**unchanged** (they are dialect-agnostic). The schema is materialized on PG by a
**fresh PG Alembic baseline** at the current strict models (`create_all` /
`autogenerate` from `Base.metadata`) — the SQLite-oriented batch-mode chain is
**not** replayed on PG; PG starts at one baseline revision and grows its own
chain. (This mirrors PI-123's "build fresh + copy rows" posture.)

### D2 — Identity & authentication: bearer tokens behind a `Principal` resolver
Add a `principals` table (humans *and* AI service agents) and hashed
`api_tokens`. A **single chokepoint** dependency — `resolve_principal(request)
→ Principal{principal_id, kind, roles, allowed_engagements}` — turns every
request into an authenticated principal; middleware/`Depends` runs it before any
access-layer call. Bearer-token validation is its first (and, for now, only)
implementation. **OIDC/OAuth is deferred** to a later *additive issuer* feeding
the same `Principal` — not a rewrite: the shelved Cloudflare Managed-OAuth setup
(validated to consent, blocked only on Anthropic's connector bug, DEC-244) stays
parked and plugs in here when that upstream fix ships or external human users
with their own IdPs become a requirement. *Rationale:* the claude.ai OAuth payoff
is upstream-blocked, the current clients are first-party, and the real substance
of RBAC is the model (D3), not the front door — so build the swappable
abstraction and the model now, layer SSO later.

### D3 — RBAC model
`roles` (e.g. `owner`, `editor`, `viewer`, plus agent-tier roles) and
`role_assignments(principal_id, engagement_id, role)` — a principal's rights are
**per engagement**. The access layer composes RBAC with the engagement scope in
two places: (a) the resolver/middleware **rejects an `X-Engagement` the principal
has no assignment for** (and the principal may only select among
`allowed_engagements`); (b) write paths check the assigned role permits the
operation (read vs create/update/delete vs admin). Enforcement lives at the
access/repository layer (a thin `require(permission)` guard), composed with — not
duplicating — the existing row-level `engagement_id` filter. System/shared
tables (catalog, future registry) have their own coarse policy (read-all,
admin-write).

### D4 — AI agents are scoped service principals
Each ADO agent (Area Specialist, PI Lead, …) authenticates as its **own service
principal** with an engagement-scoped, role-limited token; its writes attribute
to that principal in the change log / deposit events. The orchestrator mints and
assigns agent tokens at spawn. *Rationale:* a true multi-user system with
autonomous writers needs real attribution and least-privilege lanes; this ties
directly into PI-122 (the Agent Profile Registry, whose `system | engagement`
scope and learning records key on a principal) and makes "an agent can't exceed
its lane" enforceable rather than conventional.

### D5 — Per-request engagement; retire the single-active marker
The active engagement is derived **per request** from the authenticated context
(the `X-Engagement` header or a `/engagements/{code}/…` path prefix), validated
against the principal's `allowed_engagements`, and set on the scope `ContextVar`.
The process-global `current_engagement.json` marker is **retired** — it encoded
"one active engagement per process," which directly contradicts multi-user. The
desktop app sends its currently-selected engagement as a header on every request;
**switching engagements becomes a client-side context change**, not a subprocess
teardown/rebuild (this also dissolves the broken activation-worker Step 3/8).

### D6 — Remove the per-engagement-file apparatus
Delete: the activation-worker subprocess swap (`ui/activation_worker.py` → a
lightweight "set active engagement" with at most an API health re-check),
`route_settings_to_engagement`'s file-routing + `engagement_db_path`, the entire
meta layer (`access/meta_db.py`, `access/meta_models.py`, `migrations/meta/`,
`access/meta_exporter.py`, the meta-engine pool, `run_meta_migrations`), the
two-database FastAPI wiring, and the `dogfood_v0_5` + per-engagement
`lazy_migration` migrators. `/engagements/*` serves the unified `engagements`
table on the one engine. One service, one Postgres.

### D7 — Eliminate the snapshot/export process
Remove `build_snapshot`, `write_staging`/`promote_staging`/`cleanup_staging`, the
`session_scope` export hook, the `assert_export_dir_ready` gate, `force_export`,
`meta_exporter`, and the `db-export/` tree. `session_scope` collapses to
flush→commit. **The DB is the source of truth**; the git-tracked governance audit
trail is the **close-out payloads** (`close-out-payloads/*.json`) plus the
**deposit-event logs** (`deposit-event-logs/dep_*.log`), both already committed
per apply. (`apply_close_out.py` keeps writing the deposit-event log; it stops
regenerating snapshots.)

### D8 — API/MCP-only clients; retire the file-fallback orientation
There is no static-JSON tier. The CLAUDE.md session-orientation protocol's
**Tier-2 file-fallback** (read `db-export/*.json`) is removed; orientation is
**MCP** (`get_current_status`, `get_current_charter`, `list_recent_sessions`, …)
or the **REST API** only. Claude.ai sessions connect via MCP/the chat-UI-on-API
(DEC-245), never by reading committed JSON. Update `CLAUDE.md`,
`specifications/governance-recording-rules.md`, and the orientation/conduct docs
accordingly.

### D9 — Data migration: SQLite-unified → Postgres
One-shot, idempotent, validated (the PI-123 D9 posture): stand up the PG schema
at the strict unified models (PG baseline migration / `create_all`); copy every
table from `v2-unified.db` into PG with `engagement_id` preserved (the data is
already stamped post-cutover — a straight copy, no offset gymnastics needed);
copy `catalog_*` once; **seed the initial RBAC** (Doug as an `owner` principal
on every engagement; agent service principals as the orchestrator needs them);
validate per-engagement per-table count + identifier parity, FK integrity, and a
cross-engagement isolation re-run of the PI-123 leak-test against PG.

### D10 — Concurrency & ops
A real connection pool (SQLAlchemy `QueuePool`, or async `asyncpg`/`psycopg` if
the API goes async); concurrent readers **and** writers via MVCC — the
single-writer `BEGIN IMMEDIATE` serialization is gone. Backups/HA/patching move
to the DB platform. The PI-123 scope mechanism (ContextVar + Session-class
listeners) is unchanged and thread/async-safe as before.

### D11 — Hosting / deployment
**Dev/test:** local Docker Postgres (ephemeral, per-developer; CI spins one up).
**Prod:** managed Postgres (DigitalOcean Managed Postgres, matching the existing
droplet workflow) with the API deployed as a service (droplet/container). The
design stays DB-agnostic ("a Postgres"); the exact prod topology
(droplet-vs-container, region, pooling sidecar) is pinned at PI-α's Deployment
phase. *Rationale:* managed PG offloads the ops that going-production is meant to
reduce; self-hosting on the droplet is the fallback if cost/control demands it.

---

## 6. Decomposition

Three planning items under PRJ-019. Each gets the standard ADO phase
Workstreams (Architecture is **this document** for the program; each PI refines
its own Architecture/scoping).

```
   PI-α Postgres foundation ──┬──► PI-γ Identity/auth/RBAC
                              │
   PI-β De-file + kill snapshots + API/MCP-only  (mostly parallel)
```

- **PI-α — Postgres foundation (D1, D9, D10).** PG baseline schema from the
  strict models; port JSON→JSONB + drop SQLite transaction hacks + add the pool;
  the one-shot `v2-unified.db` → Postgres migration, validated (incl. the
  leak-test on PG); the whole test suite green on PG. *Foundation — everything
  else lands on it.*
- **PI-β — De-file the runtime + kill snapshots + API/MCP-only (D5 partial, D6,
  D7, D8).** Remove the per-engagement apparatus + the meta layer + the
  activation-worker swap; remove the snapshot/export machinery; rewrite the
  orientation/governance docs for API/MCP-only. *Largely DB-agnostic — can run in
  parallel with PI-α; absorbs the broken-switch fix.*
- **PI-γ — Identity, authentication & RBAC (D2, D3, D4, D5 final).** `principals`
  / `api_tokens` / `roles` / `role_assignments`; the `resolve_principal`
  chokepoint + bearer-token middleware; per-engagement permission enforcement
  composed with the scope; agents as scoped service principals; finalize
  per-request engagement selection. *Best on Postgres; needs the multi-user
  request model.*

PI-122 (Agent Profile Registry) remains gated on PI-123 and now also consumes
PI-γ's principal/agent model.

**Order of operations:** merge PI-123 to `main` + do its build-closure **first**
(make the unified DB the committed baseline + the blessed migration source),
then start this program on a fresh branch. PI-α → PI-γ; PI-β in parallel.

---

## 7. Open questions & deferred

- **Exact prod topology** (D11) — pinned at PI-α Deployment.
- **OIDC/SSO timing** (D2) — deferred additive issuer; revived when claude.ai's
  connector bug is fixed or external human users arrive.
- **Token lifecycle** — rotation, revocation, secret storage for agent tokens
  (likely the OS keyring locally / a secrets manager in prod) — PI-γ scoping.
- **Async API?** — whether to move FastAPI to async + `asyncpg` for concurrency,
  or stay sync + threadpool + a sync pool — PI-α scoping decision.
- **Desktop app shape** — it is already an API client (`StorageClient`); confirm
  it has no remaining direct-DB paths once the meta layer is gone.
- **Multi-region / horizontal scale** — out of scope; the row-level-tenant model
  is the standard thing that scales to it later.

---

## 8. Cross-references
- `pi-123-unified-db-architecture.md` (the unified schema + scope mechanism this
  builds on); `pi-123-stage4-cutover-runbook.md` (the deferred de-file items D6
  absorbs).
- `agent-profile-registry/agent-profile-registry-PRD-v0.1.md` (PI-122; consumes
  D4's agent-principal model).
- DEC-244 (claude.ai OAuth upstream-blocked), DEC-245 (chat-UI-on-Anthropic-API),
  DEC-373 (system|engagement scope) — context for D2/D8.
- `specifications/governance-recording-rules.md`, `CLAUDE.md` — rewritten by D8.

*End of document — Architecture pass v0.1. Next: review/refine, then create
PI-α/β/γ (via close-out on `main`) once PI-123 is merged + resolved.*
