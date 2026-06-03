# PI-122 — Agent Profile Registry: Architecture & Scoping

**Status:** v0.1 — PI-122's Architecture/scoping pass (06-03-26). Turns the
registry PRD v0.3 (`agent-profile-registry/agent-profile-registry-PRD-v0.1.md`,
header-authoritative v0.3) into a build-ready plan now that its prerequisites
have landed. Not implementation.
**Project:** the ADO Project (the registry is the ADO §10 follow-on). Tracked as
**PI-122** ("Build the Agent Profile Registry").
**Builds on (all now landed):** **PI-123** (unified multi-engagement DB —
row-level `engagement_id`), **PI-β** (one DB, header-per-request engagement),
**PI-γ** (principals + RBAC + the `agent_tier`/`agent_area` columns on service
principals), and the ADO substrate (PI-114 / WTK-001…006).
**Feeds:** the runtime scheduler (the separate §10 follow-on that injects
resolved contracts and spawns ephemeral agents).

---

## 0. What changed since the PRD, and why this pass is needed

The registry PRD v0.3 §13.5 / §14 names the **unified multi-engagement-DB
migration as a prerequisite PI (PI-123) that PI-122 `blocked_by`**, and treats
the current architecture as "per-engagement DB files routed by a meta layer."
**That prerequisite is done, and the foundation moved further than the PRD
assumed:**

- **PI-123** delivered the single unified DB with a row-level `engagement_id`
  discriminator (`EngagementScopedMixin`) and the central read-filter/write-stamp
  scope. The PRD's predicted simplification has happened: scope **is** row scope,
  and cross-engagement learning **is** a `GROUP BY content` across
  `engagement_id` — exactly as §13.3/§13.5 foresaw.
- **PI-β** removed the meta DB / marker / per-engagement-file apparatus; the
  active engagement is named per request by `X-Engagement`.
- **PI-γ** added `principals` + `api_tokens` + `role_assignments` and — load-
  bearing for this build — **`principals.agent_tier` and `principals.agent_area`
  columns plus `mint_agent_principal()` / `POST /admin/agents`**, which were
  added anticipating the ADO agent runtime. **An agent_profile is the template;
  a `service_agent` principal is its runtime instance.**

So PI-122 is **unblocked** and should be designed directly against this
foundation, not against the per-engagement-file world the PRD described. This
doc fixes the scope-discriminator design concretely (the PRD's "one design choice
that makes the migration rework-free", §13.7 item 2) and wires the registry into
the principal/RBAC layer.

---

## 1. Scope boundary (what PI-122 is and is NOT)

**In scope (PI-122) — the registry as a living, system-level learning memory:**
- **Four governance entities** (registry PRD §9 + §13.7): `agent_profile`
  (`AGP-`), `skill` (`SKL-`), `governance_rule` (`GVR-`), `learning` (`LRN-`).
- **Scope-awareness** on every registry row: `system` vs a specific engagement,
  realized via a **nullable `engagement_id`** (D-δ2).
- **Binding edges** (reference vocab): `agent_profile_has_skill`,
  `agent_profile_governed_by_rule`, `learning_derived_from`,
  `learning_contradicted_by`, `learning_promoted_to`.
- **The resolver** — compose a profile id → an *effective contract* (system
  prompt + tool set + enforced ruleset + active learnings + version + scope
  merge).
- **The write-back lifecycle** — capture (at Work-Task close / from findings /
  from test failures), accumulate, propose, promote — reusing the hybrid-
  governance split + float/pin versioning + the `needs_attention` human gate.
- **REST + MCP surfaces** + monitoring panels, per the governance conventions.

**Explicitly OUT of scope / deferred:**
- **The runtime scheduler** — the separate §10 follow-on that *injects* contracts
  and *spawns* ephemeral agents (registry PRD §12 / §13.6). PI-122 makes the
  resolver **runtime-ready** (returns a complete contract); it spawns nothing.
- **The `finding` (`FND-`) entity** — an ADO-substrate / reconciliation build
  concern (evolution §4.2), *consumed* by the learning loop via
  `learning_derived_from → finding`. See D-δ6 for how PI-122 handles the coupling
  without pulling the whole finding build forward.
- **Authoring the concrete prompt text** for each (area × tier) profile — the
  registry *holds* prompts; only the two proven prompts are seeded (D-δ3).
- **Point-in-time catalog versioning** — pinning stays a drift assertion
  (PRD §7.4).

---

## 2. Current state (the foundation the registry binds to)

- **Governance-entity machinery is mature:** six v0.7 entities + the PI-112/PI-114
  ADO entities all ride the same access-layer / Alembic / `{data,meta,errors}` /
  MCP / panel pattern. Adding four more is incremental, not novel.
- **The ADO substrate endpoints are the concrete tool-skills** profiles bind
  (PRD §12): `decompose`, `scope`, `prior-phase-outputs`, `start-execution`,
  `complete-phase`, `backlog`, `dispatch`, `phase-overview`, claim/release.
- **PI-γ principal model:** `principals(kind ∈ {human, service_agent},
  agent_tier, agent_area, …)`, `role_assignments(principal_id, engagement_id,
  role)`, `mint_agent_principal(engagement_id, role, agent_tier, agent_area)`.
  The agent-tier roles (`orchestrator`, `pi_lead`, `phase_specialist`,
  `area_specialist`) already exist in `RBAC_ROLES`.
- **System/shared-table precedent:** `principals` / `api_tokens` are plain `Base`
  tables (no `EngagementScopedMixin`); `role_assignments` is a plain `Base` table
  that carries a **non-discriminator `engagement_id` FK** (the engagement a grant
  applies to). **The registry tables follow this exact pattern** (D-δ2).
- **Identifier prefixes free:** `AGP` / `SKL` / `GVR` verified at PRD v0.2;
  `LRN` / `FND` do not collide with the now-in-use set (… `PRN`, `TOK` added by
  PI-γ).

---

## 3. Design decisions

### D-δ1 — Four governance entities, authored through the schema-spec guide
`agent_profile` (`AGP-`), `skill` (`SKL-`), `governance_rule` (`GVR-`),
`learning` (`LRN-`) — full governance entities (PRD §10.1 resolved), each with a
schema spec under `governance-schema-specs/`, a table, REST endpoints, MCP tools,
and a read-only monitoring panel under the Governance sidebar. Proposed shapes
(settle exact columns through the schema-spec process):

```
agent_profile (AGP-): area, tier {architect|developer|tester|orchestrator|pi_lead},
                      description (seeds the system prompt), status, scope (D-δ2)
skill (SKL-):         kind {instruction|tool}, description, io_contract (JSON schema,
                      tool kind), backing_callable (optional pointer), version, status, scope
governance_rule (GVR-): rule_type, enforcement {advisory|enforced|enforced_with_override},
                      severity, body, predicate (JSON, enforced kind), version, status, scope
learning (LRN-):      area, tier {architect|developer}, category {gotcha|pattern|constraint|preference},
                      content (situation → guidance), status {active|stale|retired|promoted},
                      confidence (derived), scope (D-δ2)
```

`area` is validated against `vocab.SYSTEM_AREA_RANKS` ∪ the engagement's
Engagement areas (the existing two-tier area model). `tier` is a new small vocab.

### D-δ2 — Scope-awareness = a nullable `engagement_id` (NOT `EngagementScopedMixin`)
**This is the load-bearing decision** (PRD §13.7 item 2 — "the one design choice
that makes the unified-DB migration rework-free", now realized against the
landed unified DB). The registry tables are **system/shared tables that carry a
nullable `engagement_id` FK to `engagements`**, mirroring PI-γ's `role_assignments`:

- `engagement_id IS NULL` ⇒ a **system** row (universal — the system-level
  workforce).
- `engagement_id = ENG-NNN` ⇒ an **engagement overlay** row (addition / override
  / disable specific to one engagement).

They are **plain `Base` tables, not `EngagementScopedMixin`** — because the mixin
makes `engagement_id` **NOT NULL** and applies the central read-filter, which
would (a) make system rows impossible and (b) hide system rows from an
engagement-scoped query. Instead the **resolver** does the scope merge explicitly
(D-δ4). This is the same reasoning that put `principals`/`role_assignments`
outside the mixin in PI-γ, so the registry stays consistent with the auth layer
and the `engagement_id` discriminator semantics are not overloaded.

Cross-engagement learning is then a plain query over `learning` rows grouped by
`content`/area/tier across `engagement_id` values — the unified-DB payoff the PRD
predicted, with no special machinery.

### D-δ3 — Roster is per-(area × tier); seed the two proven prompts (DEC-368)
Profiles multiply along **(area × tier)** but are **defined once at system level**
(`engagement_id IS NULL`) and instantiated only for the cells a release touches.
Build areas get **Architect / Developer / Tester**; design/methodology areas get
**Architect only**; **PM** and **PI Lead** remain single orchestration profiles.
Seed with the two proven prompts under `agent-profile-registry/profiles/`
(`development-phase-specialist.md` → a Development-area **Architect**;
`area-specialist.md` → a **Developer**), re-keyed onto the (area × tier) axis.

### D-δ4 — The resolver returns a runtime-ready *effective contract*
`resolve_contract(profile_id, engagement_id) → Contract` where
`Contract = { system_prompt, tools, enforced_ruleset, active_learnings,
version_stamp, scope }`, composed as the **scope merge**:

```
EFFECTIVE = System ∪ engagement-additions − engagement-disabled ⊕ engagement-overrides
```

i.e. `WHERE engagement_id IS NULL OR engagement_id = :active`, minus rows an
engagement-overlay marks disabled, with engagement overrides winning over their
system counterpart. The contract injects the profile description + instruction-
skill text + advisory-rule bodies (prompt), the tool-skill I/O contracts (tools),
the enforced rules (largely **bindings onto existing access-layer enforcement**,
PRD §3.5 — not a second engine), and the expert's **active (area, tier)
learnings** ("all active" first; relevance-retrieval is a scale follow-on, open
Q). The resolver is read-only and cache-on-version — the ADO's DB-backed
statelessness (ADO §4.4) applied to capability.

### D-δ5 — agent_profile ↔ PI-γ principal (template ↔ instance)
The registry **holds** the profile; PI-γ **instantiates** it as a runtime
principal. The seam: when the runtime scheduler spawns an agent for a claimed
Work Task, it (1) resolves the (area × tier) profile → contract via D-δ4, and
(2) calls PI-γ `mint_agent_principal(engagement_id, role, agent_tier=tier,
agent_area=area)` to get the engagement-scoped service principal + token that
the agent authenticates with. `principals.agent_tier`/`agent_area` (added by
PI-γ) are the join back to the profile cell; the tier→`RBAC_ROLES` mapping
(`architect`/`developer`/`tester` ↦ an agent-tier role) gives the agent its
lane. **PI-122 defines the resolver + the profile↔role mapping; the minting call
itself is the runtime follow-on.** No PI-γ change is required.

### D-δ6 — The `learning_derived_from → finding` coupling, without the finding build
The `finding` (`FND-`) entity is an ADO-substrate/reconciliation concern
(evolution §4.2), not the registry's to build. But the learning loop consumes
findings as evidence. Resolution: **PI-122 ships the `learning` entity and its
edges to the targets that exist today** (`work_task`, `decision`, and a generic
evidence target), and adds `learning_derived_from`/`_contradicted_by`/
`_promoted_to` to the vocab. The **`(learning, finding)` pair in `_kinds_for_pair`
is added only when the `finding` entity lands** (it cannot be a valid edge target
before `finding` is an `ENTITY_TYPE`). So the learning loop is fully functional
on Work-Task/Decision/test-failure evidence now, and gains finding-derived
evidence when the reconciliation build adds `finding`. Recorded as a scoping
decision so the two builds stay decoupled but compatible.

### D-δ7 — Promotion gate reuses hybrid governance (no new safety system)
The conservative-then-earned gate (PRD §13.4) is data, not a new engine:
`learning` is always free/advisory; promoting to a **skill** rides float/pin;
promoting to an **enforced `governance_rule`** **always requires human review**
(the `needs_attention` path); a **system enforced rule** is the top gate (human
review **+** cross-engagement evidence). Curation is a **per-(release, area)
"curate" Work Task** the Architect runs each release + triggered re-validation on
contradiction/source-refactor. (Release-batched curation depends on the Release
entity, an ADO-runtime concern — PI-122 ships the curate *mechanism*; the
per-release *cadence* is wired by the runtime.)

---

## 4. Build order (each slice green)

1. **Schema specs + entity 1–3 (catalog):** `agent_profile`/`skill`/
   `governance_rule` schema specs + one Alembic migration (tables + the two
   binding edge kinds in `REFERENCE_RELATIONSHIPS`/`_kinds_for_pair` + the
   `relationship_kind` CHECK) + access layer + REST + MCP. Scope column (D-δ2)
   from the start.
2. **Bindings + resolver (catalog-only):** the binding edges and
   `resolve_contract` over profiles/skills/rules with the scope merge (D-δ4),
   minus learnings. Effective-contract = prompt + tools + enforced ruleset +
   version + scope.
3. **`learning` entity + edges (D-δ1/D-δ6):** the fourth entity, its three edge
   kinds (to the targets that exist today), and the capture step at Work-Task
   close.
4. **Write-back lifecycle (D-δ7):** accumulate (evidence → existing learning,
   confidence), propose (refine skill / add rule), promote (gated; `needs_attention`
   for enforced), and the per-(release, area) curate Work Task mechanism.
   Resolver now injects active (area, tier) learnings.
5. **Cross-engagement learning + scope overlays (D-δ2):** the
   `GROUP BY content across engagement_id` cross-engagement promotion path
   (engagement → system), and engagement override/disable in the resolver merge.
6. **Seed + panels + docs:** seed the two proven prompts as system profiles
   (D-δ3); read-only Governance panels for the four entities; CLAUDE.md note +
   governance-recording-rules update; recording goes through API/MCP.

## 5. Phase decomposition (PI-122 Workstreams)
PI-122 is already decomposed into phase Workstreams **WSK-002…007** (the existing
`workstream_belongs_to_planning_item` edges). This Architecture pass is the
**Architecture** phase; map §4's slices onto the **Development** phase's Work
Tasks (scope per area — `storage`/`access`/`api`/`mcp`/`ui`). Testing covers the
resolver scope-merge matrix, the promotion-gate matrix (free/earned/human),
cross-engagement promotion, and the binding-edge vocab constraints.

## 6. Open questions & deferred
- **Learning retrieval at scale** (PRD §10.6) — inject all-active first; relevance
  retrieval is a scale follow-on, not a blocker.
- **Automatic stale-learning detection** (PRD §10.7) — left to expert review +
  contradiction/source-change triggers + human spot-checks.
- **Broker scope** (PRD §10.3) — bind existing access-layer enforcement; add a
  standalone predicate evaluator only for enforced rules the access layer cannot
  express (likely few).
- **`finding` coupling timing** (D-δ6) — the `(learning, finding)` edge pair lands
  with the reconciliation build; sequence so neither blocks the other.
- **Release-batched curate cadence** (D-δ7) — the mechanism is PI-122; the
  per-release trigger waits on the Release entity (ADO runtime).

## 7. Sequencing (important)
**PI-122 is unblocked** — its `blocked_by PI-123` is satisfied (PI-123 Resolved),
and PI-α/β/γ provide the unified DB + principal foundation. Clean order
(registry PRD §14): **PI-123 (done) → PI-122 (this) → runtime scheduler**. PI-122
is built scope-aware against the unified DB directly; the runtime follow-on then
injects PI-122-resolved contracts (D-δ5) and spawns the ephemeral agents the ADO
substrate (PI-114) already exposes endpoints for.

## 8. Cross-references
- `agent-profile-registry/agent-profile-registry-PRD-v0.1.md` (v0.3 — the source
  this refines; §13/§14 in particular).
- `agent-delivery-organization-evolution.md` (v0.3 — DEC-367…374; the `finding`
  entity §4.2; the learning loop §7; the standing-agent runtime §9B).
- `agent-delivery-organization-design.md` (the ADO lifecycle + substrate the
  registry serves).
- `pi-gamma-rbac-architecture.md` + the PI-γ principal model (D-δ5 — the
  template↔instance seam; `mint_agent_principal`, `agent_tier`/`agent_area`).
- `governance-entity-schema-spec-guide.md` (how the four entities are authored).

*End of document — PI-122 Architecture/scoping pass v0.1. Next: Development
slice 1 (the agent_profile/skill/governance_rule catalog, scope-aware).*
