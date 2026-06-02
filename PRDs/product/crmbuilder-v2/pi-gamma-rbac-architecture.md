# PI-γ — Identity, Authentication & RBAC: Architecture & Scoping

**Status:** v0.1 — PI-γ's Architecture/scoping pass (06-02-26). Refines the
program-level design (`production-multitenant-api-architecture.md` D2/D3/D4/
D5-final) into a build-ready plan. Not implementation.
**Project:** PRJ-019 — Production Database Architecture.
**Planning item:** PI-γ (identity / auth / RBAC) — created under PRJ-019 at PI-α's
close-out (`ses_154.json`, draft id **PI-127**), `blocked_by` PI-α (PI-125).
**Branch:** `pi-gamma-rbac` (off `main`).
**Builds on:** PI-123 (unified DB), **PI-α** (Postgres — the principal/RBAC tables
and cross-engagement learning want one real multi-tenant store), **PI-β**
(header-only engagement resolution — PI-γ validates that header against the
principal). **Feeds PI-122** (the Agent Profile Registry keys learning on a
principal + a `system | engagement` scope).

---

## 0. Scope boundary (what PI-γ is and is NOT)

PI-123 made the data multi-tenant; PI-α/PI-β made it a Postgres service with no
file apparatus. **PI-γ makes it multi-*user*:** every request carries an
authenticated **principal** (a human user *or* an AI service agent) whose **roles**
grant access to specific **engagements**, composed with the existing row-level
engagement scope so the same query path enforces both "which tenant" and "who,
with what rights."

**In scope (PI-γ):**
- **D2 — identity + authentication:** a `principals` table (humans + service
  agents), hashed `api_tokens`, and a single `resolve_principal(request)`
  chokepoint with bearer-token validation as its first (and, for now, only)
  implementation.
- **D3 — RBAC:** `roles` + `role_assignments(principal_id, engagement_id, role)`;
  a thin `require(permission)` guard at the access layer composed with the scope;
  coarse policy for system/shared tables.
- **D4 — agents as scoped service principals:** each ADO agent authenticates as
  its own engagement-scoped, role-limited service principal; writes attribute to
  it (the `claimed_by` columns + `change_log.actor` + deposit events become real
  principal references). The orchestrator mints + assigns agent tokens at spawn.
- **D5-final — per-request engagement from the authenticated context:** the
  `X-Engagement` header (PI-β) is **validated against the principal's
  `allowed_engagements`**; reject otherwise.

**Explicitly OUT of scope / deferred:**
- **OIDC / SSO** — a *later additive issuer* feeding the same `Principal`. The
  shelved Cloudflare Managed-OAuth + the MCP OAuth AS (`mcp_server/auth.py`,
  Google OIDC, validated to consent, blocked on Anthropic's connector bug
  DEC-244) stay parked and plug into `resolve_principal` when that upstream fix
  ships or external human users with their own IdPs arrive. PI-γ ships
  bearer-tokens-only.
- **The file/snapshot removal** — PI-β. **The Postgres port** — PI-α.

**Don't break the single-operator localhost flow.** Like PI-123's
`engagement_scoping_enabled`, PI-γ gates auth behind a flag
(`principal_auth_enabled`, default **off** locally): with it off, a default
**owner** principal is assumed (today's behavior, zero tokens); with it on
(deployed), a bearer token is required. Auth becomes load-bearing exactly when the
service is deployed (PI-α's managed PG + a public endpoint), not on the desktop.

---

## 1. Current state (from the auth/RBAC surface survey)

- **The REST API at `127.0.0.1:8765` has zero authentication** — every endpoint is
  open (by design: single-operator localhost tool). The middleware stack
  (`api/main.py`) is just `EngagementScopeMiddleware` (resolves the engagement
  ContextVar) then the marker-guard (PI-β removes the latter).
- **The chokepoint pattern already exists.** `api/scope_middleware.py` resolves the
  active engagement and sets a `_active_engagement` ContextVar (a pure-ASGI
  middleware, gated by a setting). `resolve_principal` mirrors it exactly with a
  `_active_principal` ContextVar.
- **Write attribution is half-built.** `access/change_log.py` has a
  `set_actor`/`current_actor`/`emit` ContextVar; `change_log.actor` is constrained
  to `CHANGE_LOG_ACTORS = {claude_session, migration, manual}`. `planning_items`
  and `work_tasks` carry **`claimed_by`** (a string agent id, e.g. `CNV-NNN`) +
  `claimed_at`. These are the seams PI-γ ties to a principal.
- **ADO claim/release endpoints trust the request body** — they accept the agent
  id with no proof the caller *is* that agent (the API is unauthenticated). PI-γ
  validates it against the authenticated principal.
- **MCP has no identity.** `mcp_server/tools.py` calls the REST API
  unauthenticated; change_log gets the default `claude_session`. The MCP **OAuth
  AS** (`mcp_server/auth.py`) authenticates the *claude.ai MCP client* over HTTP
  only — it is **not** the API's auth and PI-γ's tokens must not collide with it
  (separate namespace; its JWT-claims shape is a useful template).

---

## 2. Design decisions

### D-γ1 — `principals` + `api_tokens` (system/shared tables)
New tables in the unified `Base`, **not** engagement-scoped (a principal spans
engagements):
- **`principals`**: `principal_id` (PRN-NNN), `kind` ∈ {`human`, `service_agent`},
  `display_name`, `identity` (email for humans / agent label), `status` ∈
  {`active`, `disabled`}, timestamps. Service agents additionally note their
  ADO tier/area for the registry (PI-122).
- **`api_tokens`**: `token_id`, `principal_id` FK, **`token_hash`** (a strong KDF
  hash — never the plaintext), `label`, `created_at`, `expires_at`, `revoked_at`,
  `last_used_at`. The plaintext is shown **once** at mint time. Validation hashes
  the presented bearer token and looks it up.

These live in the one multi-tenant DB (Postgres in prod) and migrate via **both**
chains (SQLite chain next-after-0039 + the `migrations/pg/` tree — the PI-α
dual-head posture).

### D-γ2 — `resolve_principal` chokepoint + bearer middleware
A single dependency `resolve_principal(request) → Principal{principal_id, kind,
roles, allowed_engagements}`, implemented first as bearer-token validation:
`Authorization: Bearer <token>` → hash → `api_tokens` lookup (active, unexpired,
unrevoked) → `principals` row → its `role_assignments` → derived `roles` +
`allowed_engagements`. It sets a `_active_principal` ContextVar (mirroring
`engagement_scope`). **Middleware order:** principal resolution is **outermost**,
*before* engagement resolution, so the engagement selection can be validated
against the principal (D5-final). With `principal_auth_enabled` off, the resolver
yields the **default owner** principal (every engagement allowed) — preserving
today's localhost flow. *OIDC is a future second implementation feeding the same
`Principal`; the abstraction is the point.*

### D-γ3 — RBAC model + the `require` guard
- **`roles`**: a small set — `owner`, `editor`, `viewer`, plus agent-tier roles
  (`orchestrator`, `pi_lead`, `phase_specialist`, `area_specialist`) aligned to the
  ADO tiers. A role → permission mapping (`read`, `create`, `update`, `delete`,
  `admin`, plus action perms like `claim`).
- **`role_assignments(principal_id, engagement_id, role)`** — rights are **per
  engagement**.
- **Enforcement composes with the scope in two places** (not duplicating the
  row-filter):
  1. **Engagement selection:** the resolver/middleware **rejects an `X-Engagement`
     the principal has no assignment for**, and the principal may only select among
     `allowed_engagements` (403).
  2. **Operation:** a thin **`require(permission)`** guard at the access/repository
     entry checks the active principal's role on the active engagement permits the
     op (read vs create/update/delete vs admin). Lives next to where the
     engagement scope is already applied — one chokepoint, both checks.
- **System/shared tables** (catalog, `principals`/`api_tokens`/`roles`
  themselves): coarse policy — read for any authenticated principal, write for
  `admin`/`owner` only.

### D-γ4 — Agents are scoped service principals; attribution becomes real
- The ADO orchestrator **mints a service principal + an engagement-scoped,
  role-limited token per agent at spawn** (e.g. an Area-Specialist agent on ENG-001
  gets an `area_specialist` assignment on ENG-001 only). Its token is injected into
  the agent's contract (the runtime spawns the agent with it).
- **`claimed_by`** (planning_items, work_tasks) is set to the agent's
  `principal_id`; the claim/release endpoints **validate the bearer principal
  matches** (an agent can't claim as someone else).
- **Write attribution:** `change_log.actor`/the actor ContextVar is set from the
  active principal automatically (no caller work). Decision: add a
  **`principal_id` FK column to `change_log`** (and surface the minting principal on
  `deposit_event`), keeping the coarse `actor` *kind* (extend `CHANGE_LOG_ACTORS`
  with `service_agent`/`user`, or relax it) — so history shows *which* principal,
  not just "claude_session". This makes "an agent can't exceed its lane"
  enforceable, and ties directly into PI-122's per-principal learning records.

### D-γ5 — Per-request engagement from the authenticated context (finishes D5)
PI-β made engagement resolution header-only (no marker). PI-γ adds: the resolved
engagement is **validated against `allowed_engagements`** and rejected otherwise;
then set on the scope ContextVar as today. The desktop sends both its bearer token
and its selected `X-Engagement`; switching stays a client-side context change.

### D-γ6 — Token lifecycle, secret storage, provisioning
- **Mint/rotate/revoke** via an admin path (a CLI `crmbuilder-v2-token` and/or an
  `/admin/tokens` endpoint restricted to `owner`): create returns the plaintext
  once; rotate = mint-new + revoke-old; revoke = stamp `revoked_at`.
- **Secret storage:** locally the operator's token rides the existing OS-keyring
  (`automation/core/secrets.py` pattern); agent tokens are minted by the
  orchestrator and held in-process / keyring for the agent's lifetime; in prod a
  secrets manager holds the service + agent tokens. Tokens are bearer secrets —
  stored only hashed server-side.
- **Bootstrap (D9-analog):** a migration/seed creates the tables, seeds **Doug as
  an `owner` principal on every engagement** + an initial token, and the default
  owner used when `principal_auth_enabled` is off.

---

## 3. Build order (each slice green)

1. **Schema + seed:** `principals`/`api_tokens`/`roles`/`role_assignments` tables
   (both migration chains) + the owner/bootstrap seed + the keyring token store.
2. **`resolve_principal` + bearer middleware (auth off by default):** the
   ContextVar, the resolver, the default-owner path. No enforcement yet — every
   request resolves a principal; behavior unchanged with auth off.
3. **RBAC enforcement:** the `require(permission)` guard + the engagement-selection
   check (allowed_engagements). Gated by `principal_auth_enabled`.
4. **Attribution:** `change_log.principal_id` + actor-from-principal; claim/release
   validate the principal; deposit-event minting principal.
5. **Agents as service principals:** orchestrator mints/assigns agent tokens at
   spawn; the agent contract carries the token; `claimed_by` → principal.
6. **MCP + admin surface:** MCP tools forward a bearer token to the API; the
   `crmbuilder-v2-token` CLI / `/admin/tokens` endpoint; docs.

## 4. Phase decomposition (PI-γ Workstreams)
| Phase | Scope |
|---|---|
| **Architecture** | *This document.* |
| **Development** | Slices 1-6 of §3. |
| **Data Migration** | Seed the owner principal + token + role_assignments on every existing engagement (slice 1). |
| **Testing** | Auth-off (default-owner) keeps the whole suite green; auth-on tests for token validation, allowed-engagement rejection, per-role permission matrix, agent-lane enforcement, attribution. |
| **Documentation** | CLAUDE.md auth/RBAC note; the token runbook; update governance-recording-rules for principal attribution. |
| **Deployment** | Turn `principal_auth_enabled` on in the deployed (PI-α managed-PG) service; provision the owner + agent tokens; pin secret storage. |

## 5. Open questions & deferred
- **OIDC issuer timing** (D2) — revived when claude.ai's connector bug is fixed or
  external human users arrive; the MCP OAuth AS / Cloudflare setup is the parked
  implementation.
- **`change_log.actor` vs a new `principal_id`** — add the FK column (proposed) vs
  repurpose `actor`; settle at Development (additive FK is safer).
- **Permission granularity** — start coarse (read/write/admin + claim); finer
  per-entity perms only if a real need appears.
- **Agent token TTL / rotation cadence** — short-lived per-spawn tokens vs
  longer-lived per-agent; pin at Development with the orchestrator runtime (PI-122).
- **Two token namespaces (REST bearer vs MCP OAuth JWT)** — keep separate for now;
  a unified issuer is the OIDC-era decision.

## 6. Sequencing (important)
PI-γ **depends on PI-α** (the principal/RBAC tables + cross-engagement learning
want the real Postgres multi-tenant store; recorded as `blocked_by` PI-α) and
**composes with PI-β** (it validates PI-β's header-only engagement resolution and
edits the same `scope_middleware`/middleware stack). Clean order: **PI-α → PI-β →
PI-γ**, each branch rebased onto the prior's merged `main`. This branch
(`pi-gamma-rbac`) is off pre-PI-α `main`; the design is valid now, but the *code*
wants PI-α + PI-β landed first. PI-122 (Agent Profile Registry) consumes PI-γ's
principal model + the `system | engagement` scope (DEC-373) and follows it.

## 7. Cross-references
- `production-multitenant-api-architecture.md` (D2/D3/D4/D5-final this refines).
- `pi-alpha-postgres-foundation-architecture.md`, `pi-beta-defile-architecture.md`
  (the prerequisites + the shared middleware/scope edits).
- `agent-profile-registry/` (PI-122 — consumes D4's agent-principal model).
- DEC-244 (claude.ai OAuth upstream-blocked), DEC-245 (chat-UI-on-API), DEC-373
  (system|engagement scope) — context for the deferred OIDC + the agent model.
- The PI-γ auth/RBAC surface survey (this session) — the file:line seams the
  Development slices consume (`scope_middleware`, `change_log`, `claimed_by`,
  `mcp_server/auth.py`, the ADO claim endpoints).

*End of document — PI-γ Architecture/scoping pass v0.1. Next: after PI-α + PI-β
land, Development slice 1 (the principal/token/role schema + owner seed).*
