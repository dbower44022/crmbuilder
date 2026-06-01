# Agent Profile Registry — PRD

**Document type:** Application development design (the centralized registry of skill and governance-rule definitions that the Agent Delivery Organization's agents draw from)
**Proposed path:** `PRDs/product/crmbuilder-v2/agent-profile-registry/agent-profile-registry-PRD-v0.1.md`
**Status:** v0.3 — DRAFT proposal. Nothing built. Reconciled against the locked ADO design, the completed ADO substrate (PI-114 / WTK-001…006), the PI-112 governance model, and — as of v0.3 — the **agent-layer evolution** (`agent-delivery-organization-evolution.md` v0.2, design-complete; governed as **DEC-367…373** via SES-149). (Filename retains `-v0.1` as the stable path; the version inside this header is authoritative.)
**Last Updated:** 06-01-26

---

## Status & positioning

This PRD specifies an **Agent Profile Registry**: the centrally-managed store of *what each agent knows and is allowed to do* — its skills and its governance rules — so that capabilities can be managed in one place even when agents run dispersed.

It is **the explicitly-deferred follow-on to the Agent Delivery Organization (ADO) design.** ADO v0.3 §10 lists as out of scope: "the concrete agent prompts / skill definitions for each specialist (follow-on, once the model is locked)" and "an 'agent profile' registry (skill definitions per phase/area) — deferred." The data model is locked (PI-112) and, as of v0.2, the **ADO substrate is built**: PI-114 / WTK-001…006 delivered the four agent-tier substrates (Project Manager, PI Lead, Phase Specialist, Area Specialist) as deterministic REST endpoints, on Alembic head **`0036`**. This document proposes the behavior-supporting registry those follow-ons call for — the layer that *holds* the agent prompts/skills/rules that drive that now-existing substrate.

This PRD is the product of a Claude.ai design conversation that ran **before** the ADO and governance model were in view. The registry *pattern* it proposes is sound and carried over; the original agent roster from that conversation (generic EspoCRM-deployment agents) was aimed at the wrong layer and has been re-pointed at the ADO tiers here. See §3 for the reconciliation and §7 for the decision history, preserved intact.

---

## Revision Control

| Version | Date (MM-DD-YY HH:MM) | Author | Summary |
|---------|------------------------|--------|---------|
| 0.1 | 05-31-26 18:15 | Doug Bower / Claude | Initial proposal. Registry pattern (versioned skill + governance-rule catalog, float/pin propagation, hybrid advisory/enforced governance, resolver→contract) re-pointed from the original generic-agent framing onto the ADO tiers/phases/areas and reconciled with the PI-112 governance model. Illustrative artifacts attached under `illustrative/`. |
| 0.2 | 05-31-26 20:10 | Doug Bower / Claude | Reconciliation pass after the ADO substrate landed (PI-114 / WTK-001…006). Refreshed the Alembic head (`0033` → `0036`). Closed two open questions: skills/rules are full governance entities (§10.1), and the `AGP`/`SKL`/`GVR` prefixes are verified collision-free (§10.2). Added §12, the registry↔runtime seam (the registry *holds and resolves*; the runtime *injects and runs* — a distinct §10 deferral), and noted the WTK-002…006 substrate endpoints as the concrete tool-skills profiles bind. No change to the model or the four decisions. |
| 0.3 | 06-01-26 | Doug Bower / Claude | **Scope expansion** to absorb the agent-layer evolution (`agent-delivery-organization-evolution.md` v0.2; governed as DEC-367…373 via SES-149). The registry is no longer a static catalog — it becomes a **living, curated, system-level learning knowledge base**. Five expansions, all in new §13: (a) the roster is now **per (area × tier)** — build areas get Architect/Developer/Tester, design/methodology areas Architect-only (DEC-368), superseding §3.1's per-ADO-tier roster; (b) a **fourth registry entity — `learning` (`LRN-`)** — plus the capture→accumulate→propose→promote write-back lifecycle, the graded conservative-then-earned promotion gate, and per-release curation (DEC-369); (c) every registry row carries a **`system | engagement` scope discriminator** and the resolver merges System ∪ engagement-overlay, with **cross-engagement learning** as the multiplier (DEC-373); (d) the **unified multi-engagement-DB migration** is recorded as a **prerequisite PI** PI-122 depends on (DEC-373 / evolution item 8); (e) the **standing-agent runtime** is clarified — "standing" is a *contract scope*, not a process (all agents spawn-on-demand), sharpening the §12 seam (DEC-372). The v0.2 model (§4), hybrid split (§5), versioning (§6), and the four preserved decisions (§7) remain valid and are *extended*, not replaced, by §13. |

## Change Log

**Version 0.1 (05-31-26 18:15):** First draft. Reframes a prior design conversation's agent-registry work as the ADO §10 agent-profile registry. Records the four design decisions made in that conversation (hybrid governance, two-kind skill taxonomy, storage path, drift-assertion pinning) with rationale and alternatives, and maps them onto V2 conventions. Implementation approach (governance entity + Alembic + access layer + REST envelope + MCP + recording rules) specified at proposal level only.

**Version 0.2 (05-31-26 20:10):** Reconciliation pass once the ADO substrate was complete (PI-114 / WTK-001…006 on Alembic head `0036`). Mechanical refreshes (head reference) and two now-answerable open questions resolved — full governance entities for `skill`/`governance_rule` (§10.1), and the proposed identifier prefixes confirmed free against the live prefix registry (§10.2). Added §12 making the registry↔runtime boundary explicit so the registry is not mistaken for the whole §10 job, and tied the abstract "tool-skill" to the concrete substrate endpoints now shipped. The model (§4), the hybrid-governance split (§5), the versioning policy (§6), and the four preserved decisions (§7) are unchanged.

**Version 0.3 (06-01-26):** Scope expansion folding in the agent-layer evolution (`agent-delivery-organization-evolution.md` v0.2, governed as DEC-367…373). The driving reframe: the registry stops being a static catalog of prompts/skills/rules and becomes **the organization's living memory** — a system-level, scope-aware, learning knowledge base that the area experts grow each release. Concretely the build now must add a fourth entity (`learning`/`LRN-`) and its write-back lifecycle, carry a `system | engagement` scope discriminator on every row, model the roster as per-(area × tier) experts, and be designed scope-aware so the future unified multi-engagement DB needs no rework. All of this is captured in the new **§13** (which supersedes the v0.2 §3.1 roster and extends §4/§5/§6/§10); the rest of the v0.2 document remains valid as the catalog-layer foundation §13 builds on. No code written; this is a PRD-scope change ahead of the PI-122 build.

---

## 1. Purpose & scope

**Purpose.** Give every ADO agent a single authoritative source for its skills (what it can do) and its governance rules (what it must and must not do), versioned and centrally managed, so that improving a capability once propagates to every agent that uses it and dispersed agents never carry stale hardcoded rules.

**In scope:** the registry's conceptual model (profiles, skills, governance rules, bindings), the versioning/propagation policy, how an agent resolves its profile into an actionable contract, the advisory-vs-enforced governance split, and the mapping onto the ADO tiers/phases/areas.

**Out of scope:** the ADO lifecycle itself (owned by `agent-delivery-organization-design.md`); the concrete prompt text for each specialist (a follow-on this registry *holds* but does not author); changes to the locked PI-112 data model beyond the additive new entity proposed here.

---

## 2. The problem

The ADO is a standing organization of role-specialized agents — a Project Manager, a PI Lead per Planning Item, six Phase Specialists, and Area Specialists per area. For that to work, each agent must know its own skills and the governance rules that bind it. If those definitions live inside agent code or prompts, then (a) a dispersed agent can drift from the current rules, (b) a capability shared across agents has to be updated in many places, and (c) there is no single queryable answer to "what is this agent allowed to do, and at what version?"

The registry makes the agent **thin**: it holds only its identity, and resolves its skills + rules + a version stamp from the governance DB at startup and on change. The DB is the single source of truth; updating behavior is a data change, not a redeploy.

---

## 3. Reconciliation with existing work

This is the load-bearing section. The registry only earns its place if it fits what already exists.

### 3.1 The agents are the ADO tiers, not generic operators

> **Superseded by §13.1 (v0.3).** The agent-layer evolution (DEC-368) refines the roster from the per-ADO-tier list below to a **per-(area × tier)** matrix: build areas get **Architect / Developer / Tester** profiles, design/methodology areas **Architect-only**. The "one profile per phase / per area" framing here is the right *shape*; §13.1 gives the corrected axis. Read §13.1 for the authoritative roster.

An "agent profile" is the skill-and-rule definition for **one ADO role or specialization**:

- **Project Manager** — one profile.
- **PI Lead** — one profile.
- **Phase Specialist** — one profile per phase: Architecture, Development, Testing, Documentation, Data Migration, Deployment.
- **Area Specialist** — one profile per area, keyed to `vocab.SYSTEM_AREA_RANKS` (storage, access, api, mcp, ui, espo, automation, …) plus per-engagement Engagement areas.

The original conversation's roster (`deployment-agent`, `validation-agent`, etc., with skills about applying YAML to an EspoCRM instance) described the *v1 product's* deploy operations, not the *v2 agents that build the software*. That roster is **not** carried forward; the illustrative artifacts retain it only as a worked example of the pattern.

### 3.2 Refines, does not replace, DEC-343 / ADO
ADO §7 already maps the tiers onto the data model. This registry adds the *profile* layer ADO §10 defers. It introduces no new orchestration; it supplies the skills and rules the existing tiers consume.

### 3.3 Skills and rules become governance entities, not raw tables
In the conversation we modeled `agent`/`skill`/`governance_rule` as relational tables with join tables. In V2 these become **governance entities** following `governance-entity-schema-spec-guide.md`:

- `agent_profile` (proposed identifier prefix **`AGP-NNN`**) — one per ADO role/specialization.
- `skill` (**`SKL-NNN`**) — a shared, reusable capability definition.
- `governance_rule` (**`GVR-NNN`**) — a shared, reusable rule.

Bindings are **reference edges**, not join tables, consistent with the reference-vocab model: proposed kinds `agent_profile_has_skill` and `agent_profile_governed_by_rule`, added to `REFERENCE_RELATIONSHIPS` with `(source,target)` constraints in `_kinds_for_pair`. Identifiers and prefixes are proposals to be settled per the schema-spec process, not fixed here.

### 3.4 Versioning/propagation maps onto existing patterns
The float/pin propagation policy (§6) rides on the existing record-versioning and supersession machinery rather than a bespoke `pinned_revision` column; `reference_book_versions` (child version history) is the nearest precedent. Pinning as a *drift assertion* (§7.4) is the right semantics until/unless full point-in-time catalog versioning is wanted.

### 3.5 Enforcement reconciles with the access layer
The hybrid governance split (§5) lands naturally on the existing substrate:

- **Advisory rules** compose into the specialist agent's prompt — pure guidance the agent is trusted to follow.
- **Enforced rules** are, in large part, *already enforced* by the access layer: edge rules, CHECK constraints, lifecycle-transition validation, supersession-requires-edge, single-use Work Tickets, etc. The genuinely new contribution is **declarative, per-profile binding** of which constraints apply to which agent — making "what blocks this agent" queryable — rather than a second enforcement engine. A standalone broker (as in the illustrative runtime) is only warranted for rules the access layer does not already cover.

---

## 4. The registry model

Four conceptual layers plus resolution:

1. **Profile (identity + role).** `agent_profile` carries the ADO role/specialization, a description that seeds the agent's system prompt, and status.
2. **Skill catalog (shared).** `skill` defines a reusable capability: a description, an I/O contract (JSON schema) for tool-backed skills, and an optional pointer to a backing callable. Defined once, bound to many profiles.
3. **Governance-rule catalog (shared).** `governance_rule` defines a reusable rule: type, enforcement mode (§5), severity, body, and — for enforced rules — a structured predicate.
4. **Bindings.** Reference edges associate a profile with its skills and rules (§3.3).

**Resolution → contract.** An agent boots holding only its profile identifier. It resolves, via the access layer/MCP, a **contract**: a composed system prompt (description + instruction-skill text + advisory-rule bodies), a tool set (from tool-skill I/O contracts), the enforced ruleset, and a version stamp. The agent caches it and re-resolves on version change. This is the ADO's DB-backed statelessness (ADO §4.4) applied to capability.

---

## 5. Hybrid governance (advisory + enforced)

Every governance rule carries an `enforcement` mode: `advisory`, `enforced`, or `enforced_with_override`. Advisory rules are guidance composed into the prompt; the agent is trusted to follow them. Enforced rules are machine-checkable and block the action (largely via the existing access layer, §3.5); `enforced_with_override` blocks pending a logged human decision — a natural fit with the ADO's **Needs Attention** flag.

The principle: enforce the rules that protect the system (destructive operations, lifecycle and edge integrity, contradicting a recorded Architecture decision); leave style and judgment as advisory. Starting mostly-advisory and hardening high-stakes rules over time requires no re-architecture because both kinds live in one catalog distinguished by the mode field.

---

## 6. Versioning & propagation

Skills and rules are independently versioned, shared catalog items. A binding either **floats** (tracks the latest revision) or **pins** (locks to a revision, requiring an explicit bump to adopt a change). Default policy:

- **Float** pure guidance — instruction skills and advisory rules. Improvements propagate immediately; this is the centralization win.
- **Pin** anything that changes execution or imposes a hard constraint — tool skills and enforced/override rules. A catalog edit must not silently change what every bound agent does.

A binding may override its class default explicitly. This rides on the existing versioning/supersession patterns (§3.4).

---

## 7. Decisions made (conversation history, preserved)

These four decisions were taken in the originating design conversation. They are recorded here with rationale and the alternatives considered, because the *why* is the point of this handoff.

### 7.1 Hybrid governance (vs advisory-only or fully-enforced)
**Decided:** hybrid. **Why:** advisory-only makes safety only as reliable as agent compliance — unacceptable for agents that can run destructive operations; fully-enforced forces every rule into a checkable predicate and is costly. Hybrid lets high-stakes rules be hard and soft guidance stay flexible, in one catalog. **In V2 terms:** the enforced half largely reuses the access layer (§3.5), which strengthens, not weakens, this choice.

### 7.2 Two skill kinds: `instruction` and `tool` (vs a three-way split)
**Decided:** two kinds; a tool is "code-backed" when it carries a pointer to a callable, advisory otherwise. **Why:** the original three-kind split (instruction / tool / code_asset) created an ambiguous line — deterministic operations like "validate" or "diff" are code yet were typed as plain tools. Collapsing to "is there a backing callable?" removes the ambiguity with no loss of meaning.

### 7.3 Storage path (conversation: SQLite-now / Postgres-later — superseded here)
**Decided in conversation:** maintain portable SQLite + Postgres migrations. **Superseded by V2 reality:** V2 already runs SQLite under Alembic (head `0036` as of v0.2) behind the access layer; there is no separate Postgres target to plan for at this layer. The illustrative dual-engine DDL is therefore reference-only; real implementation is a single Alembic migration consistent with the current head.

### 7.4 Drift-assertion pinning (vs full point-in-time versioning)
**Decided:** with one catalog row per item, pinning is a *drift assertion* — a floating binding adopts the current row; a pinned binding is flagged stale if the catalog has moved past its pinned revision, prompting human review. **Why:** true point-in-time retrieval of a superseded revision needs versioned catalog tables; that is a larger enhancement to adopt only if controlled rollback to prior revisions becomes a requirement. The drift assertion captures the *intent* of pinning (controlled adoption) at low cost and maps onto existing version/supersession patterns.

---

## 8. Mapping onto ADO tiers, phases, and areas

A worked illustration of how profiles compose (not a fixed roster — the real skills/rules are authored as the follow-on this registry holds):

- A **Development phase-specialist** profile binds skills like "scope code change by area" and "sequence Work Tasks by layer rank," and advisory rules like "prefer additive replanning" plus enforced rules drawn from the access layer (e.g. cannot mark a Workstream `Ready` without Work Tasks).
- An **Area Specialist (storage)** profile binds skills for schema/migration work and is governed by enforced rules such as "a destructive migration contradicting a recorded Architecture decision sets Needs Attention" (an `enforced_with_override` rule routing to the ADO escalation path).
- The **PI Lead** profile binds the verification and gate skills the lifecycle (ADO §3.2–3.4) requires, with the replanning rules (ADO §6) bound as governance — additive automatic (advisory), contradictory escalates (`enforced_with_override`).

The registry is what lets these definitions be edited centrally and inherited by every PI's freshly-spawned specialists.

---

## 9. Implementation requirements within V2

Real implementation must, per the governance conventions:

1. Be a **new governance entity** set (`agent_profile`, `skill`, `governance_rule`) authored through `governance-entity-schema-spec-guide.md`, with schema specs under `PRDs/product/crmbuilder-v2/governance-schema-specs/`.
2. Ship as a **single Alembic migration** onto the current head, adding tables + the new reference-edge kinds (`agent_profile_has_skill`, `agent_profile_governed_by_rule`) to `REFERENCE_RELATIONSHIPS` and `_kinds_for_pair`, plus any `relationship_kind` CHECK update.
3. Expose **REST endpoints** under the `{data, meta, errors}` envelope and **MCP tools**; record creation goes through API/MCP per `governance-recording-rules.md`, never the UI.
4. Use **server-assigned identifiers** (`identifier: null` accepted) consistent with PI-002.
5. Treat enforced rules as **bindings onto existing access-layer enforcement** wherever possible (§3.5); add a broker only for rules the access layer cannot express.

This work itself should be governed: a Planning Item, decomposed by the ADO once the ADO exists, or hand-authored Workstreams/Work Tasks in the interim (the ADO bootstrap pattern, ADO §8).

---

## 10. Open questions

### Resolved in v0.2

1. **Entity vs vocab for skills/rules — RESOLVED: full governance entities.** `skill` and `governance_rule` are full governance entities (not vocab/config). Rationale: the ADO values queryability and auditability ("what is this agent allowed to do, at what version?"), bindings are reference edges (which vocab cannot carry), and the entities want monitoring panels alongside the Workstream/Work Task panels just shipped — all of which the entity route gives and vocab does not. The added weight is one more entity set behind the same access-layer/Alembic/REST/MCP machinery already used for six v0.7 entities.
2. **Identifier prefixes — RESOLVED: `AGP` / `SKL` / `GVR` are free.** Verified against the live prefix registry (the 22 in-use prefixes: CM, CNV, CONV, COP, CRM, DEP, DOM, ENG, ENT, FLD, MCF, PER, PRJ, PROC, RB, REF, REQ, SES, TST, WSK, WT, WTK). No collision; the proposals stand, to be finalized through the schema-spec process.

### Resolved/reframed in v0.3 (see §13)

4. **Profile ↔ ADO role coupling — REFRAMED by DEC-368.** A profile is keyed to a **(area × tier)** cell, not an ADO orchestration role. The PM and PI Lead remain single orchestration profiles; the former "Phase Specialist" / "Area Specialist" dissolve into per-area Architect/Developer/Tester profiles (§13.1). The 1:1-vs-compose question is settled by the keying: one profile per (area × tier).

### Still open

3. **Broker scope.** How much enforcement does the access layer already cover, and what genuinely needs a separate evaluation step? Likely small (§3.5) — most enforced rules are edge rules, CHECK constraints, lifecycle-transition validation, and the gate logic already shipped in WTK-001…006. The build should *bind* those, not re-implement them; a standalone broker is warranted only for rules the access layer cannot express.
5. **Relationship to WS-012 orchestrator retirement** (ADO §10) and the shelved `planning_item.area` column — any interaction? (The PM substrate that shipped, `pm.py`, reads dependencies from `blocked_by` edges, not the `planning_item.area` column, so the registry has no new dependency on it.)
6. **Learning retrieval at scale (§13.2).** Early, the resolver injects *all* active (area, tier) learnings into the contract; at scale this needs a relevance-retrieval step. The retrieval mechanism (and how aggressively curation must keep the active set small) is open — it doesn't block the first build, which can inject all-active.
7. **Automatic stale-learning detection (§13.2).** Curation relies on per-release expert review + contradiction/source-change triggers + human spot-checks; fully-automatic staleness detection is an open AI problem deliberately left to those pragmatic mechanisms for now.

---

## 11. Illustrative artifacts

The `illustrative/` folder holds the originating conversation's artifacts. They demonstrate the *pattern* (versioned catalog, float/pin, advisory/enforced, resolver→contract, code-asset bridge) and a passing reference broker, but they predate the ADO/governance context and are **not drop-in**: they use a generic agent roster, raw relational tables, hand-written dual-engine SQL, and a standalone Python runtime. Read them for the mechanics, not the taxonomy or the storage approach. See `illustrative/README.md`.

- `crmbuilder-v2-agent-registry-schema.md` — the detailed schema spec (engine- and pattern-illustrative).
- `migration_v2_0_sqlite.sql`, `migration_v2_0_postgres.sql` — illustrative DDL; real work is one Alembic migration.
- `seed_v2_0_agent_registry.yaml` — illustrative seed with the (wrong-layer) generic roster, kept as a pattern example.
- `agent_runtime.py` — illustrative resolver + broker; standalone, not access-layer-integrated.
- `smoke_test.py` — exercises the reference logic against the illustrative SQLite schema; passes.

---

## 12. The registry↔runtime seam (added v0.2)

ADO §10 defers **two** distinct things, and this PRD covers only the first. Keeping the boundary explicit prevents the registry from being mistaken for the whole job.

- **The registry (this PRD) *holds and resolves*.** It is a data store + a read path: profiles, shared skill/rule catalogs, bindings, and a resolver that composes a profile identifier into a *contract* (system prompt + tool set + enforced ruleset + version stamp). Building it makes capability **queryable, versioned, and centrally editable**. It does not, by itself, make any agent run.
- **The runtime (a separate §10 follow-on) *injects and runs*.** It is the executor: take a contract, **spin up an actual agent session** (a Claude Code instance, a Claude.ai conversation, or an API-driven Anthropic-SDK loop) with that system prompt and those tools bound, point it at a claimed Work Task or a dispatched Planning Item, and let it drive the substrate endpoints (`decompose`, `scope`, `start-execution`, `complete-phase`, `dispatch`, `phase-overview`, `backlog`). The runtime is where the `session_works_work_task` edge, the claim/release lifecycle, and the pull-based dispatch (ADO §4.5) actually fire.

**Why this matters for sequencing.** A registry with no runtime is an inert catalog nothing reads; a runtime with no registry can run off hardcoded prompts (less clean, but functional). The cheapest way to de-risk the whole layer is therefore **not** to build the registry first, but to prove **one** agent end-to-end: hand-write one role's system prompt (e.g. the Development Phase Specialist or a storage Area Specialist), bind it to the substrate tools it needs, wire the contract by hand (no registry), and run it for real against a throwaway Planning Item. Once an agent prompt is shown to correctly drive the substrate, the registry has a *proven* artifact to catalog and version — and several open questions (§10.3–10.4) answer themselves from real use. Recommended order: **prove one agent (runtime slice) → then build this registry to hold the proven prompts.**

**The tool-skills are concrete now.** When v0.1 was written the substrate did not yet exist, so "tool skill (a capability with an I/O contract and a backing callable)" was abstract. As of v0.2 the backing callables are the shipped endpoints/MCP tools from WTK-002…006. A worked binding: the **Development Phase Specialist** profile's tool-skills are `GET /workstreams/{id}/prior-phase-outputs` (read its feed-forward context) and `POST /workstreams/{id}/scope` (record its Work Tasks); the **PI Lead** profile's are `phase-overview` + `start-execution` + `complete-phase`; the **Project Manager** profile's are `backlog` + `dispatch`. The registry binds these per profile; the runtime makes them callable inside a live agent.

---

## 13. v0.3 scope expansion — the registry as a living, system-level learning memory

This section folds in the agent-layer evolution (`agent-delivery-organization-evolution.md` v0.2; governed as **DEC-367…373**, recorded via SES-149). It **supersedes §3.1** (roster) and **extends** §4 (model), §5 (governance), §6 (versioning), and §10 (open questions). The driving reframe, in one line: **the registry is not a static catalog of prompts/skills/rules — it is the organization's living, curated, system-level memory that the area experts grow each release** (DEC-369).

### 13.1 The roster is per-(area × tier), not per-ADO-role (DEC-368)

The "agents" the registry serves are the cells of a **matrix** — passes (Plan/Design/Develop/Test) × **areas** — where the areas *are* the discipline vocab (`vocab.SYSTEM_AREA_RANKS` + per-engagement Engagement areas). A profile is keyed to a **(area × tier)** cell:

| Area kind | Areas | Tiers (profiles) |
|---|---|---|
| **build** | `storage`(1), `access`(2), `api`(3), `mcp`(4), `ui`(4), `espo`, `automation`, `infrastructure`, `programs` | **Architect · Developer · Tester** |
| **design / methodology** | `methodology-product` / `-process` / `-interviews` / `-templates` | **Architect only** (the design artifact *is* the deliverable) |

- The **PM** and **PI Lead** remain single orchestration profiles (cross-PI/portfolio and per-PI, from ADO v0.3).
- The former generalist **Phase Specialist / Area Specialist dissolve** into these per-area experts.
- **Only Architects are standing, portfolio-aware, reconciling, and learning at the design level**; Developers and Testers are per-task executors of clean specs (but they *also* write implementation learnings — §13.2). Reconciliation knowledge lives **only** in the design tier.
- The **Tester** is a spec-driven test-*implementer* parallel to the Developer (derives tests from the Architect's test-spec, blind to the Developer's code). **Staff incrementally** — stand up Architect + Developer first, add the Tester when rigor warrants (profiles are system-level + sparsely instantiated, so this is a staffing choice, not a model change).
- **Sub-disciplines** (Web/Mobile/Desktop UI) are modeled per-engagement as **Engagement areas** (`ui-web`/`ui-mobile`/…) — no model change; a universal two-level System sub-area model is a deferred upgrade.

**Registry impact:** profiles multiply along (area × tier) but are *defined once at system level* (§13.3) and instantiated only for the cells a release touches. Skills/rules are shared across the cells that need them.

### 13.2 A fourth registry entity — `learning` (`LRN-`) — and the write-back lifecycle (DEC-369)

The registry gains a **third knowledge store below the skill/rule catalog**, with increasing governance:

```
1. Learnings (LRN-)  — append-mostly, evidence-tagged. Written freely by experts. Advisory only.
2. Skills (how-to)   — versioned catalog (§4). Experts may PROPOSE updates; float/pin governs adoption.
3. Rules (must/must-not) — versioned, governed. Promoting a learning to an ENFORCED rule = HUMAN review, always.
```

**The `learning` entity:**

```
learning (LRN-):  area, tier {architect|developer}, category {gotcha|pattern|constraint|preference},
                  content (situation → guidance), status {active|stale|retired|promoted},
                  confidence (derived from evidence count/spread), scope {system | <engagement>}   (§13.3)
edges:  learning_derived_from    → Work Task / finding / Decision / test-failure   (the evidence)
        learning_contradicted_by → Work Task / observation                          (counter-evidence)
        learning_promoted_to     → skill / governance_rule                           (if promoted)
```

**Lifecycle — capture → accumulate → propose → promote:**
- **Capture** at *every* Work-Task close (a lightweight "what did I learn?" retro), plus from reconciliation **findings** (`FND-`, the ADO build's reconciliation entity) and test failures. Free, append-mostly, evidence-tagged. Most tasks yield 0–2.
- **Accumulate** — a recurring observation links new evidence to the *existing* learning (confidence rises), never a duplicate. **Evidence is the promotion currency:** seen once = a hunch; confirmed across many Work Tasks = institutional knowledge; contradicted = confidence falls + triggers curation.
- **Propose** — when well-evidenced (or judged important), the expert proposes refining a **skill** or adding/changing a **rule**.
- **Promote** — gated (§13.4); `learning_promoted_to` links it; status → `promoted`.

**Curation / decay** (the part that usually kills these systems): a **per-release "curate" Work Task** per (release, area) — each Architect sweeps its discipline's learnings at the start of the release's Design pass (retire stale, promote well-evidenced, merge duplicates) — plus **triggered re-validation** when a learning is contradicted or its evidence-source is refactored. Auto-detecting staleness is left to expert review + triggers + human spot-checks (open question §10.7).

**Resolver impact:** the contract the resolver composes (§4) now also injects the expert's **active (area, tier) learnings** — "all active" early, a retrieved relevant subset at scale (open question §10.6).

### 13.3 Every row is scope-aware: `system | engagement`, with cross-engagement learning (DEC-373)

**The work is per-engagement; the *workforce* is system-level.** A Database Architect's expertise is universal — defining it inside every engagement is wasteful duplication. So the registry is a **system-level service with engagement overlays**, following the exact precedent of `SYSTEM_AREA_RANKS` (universal-in-code) + `engagement_areas` (per-engagement):

```
SYSTEM REGISTRY      universal (area × tier) profiles + their SYSTEM skills / rules / learnings
ENGAGEMENT OVERLAY   + engagement-specific skills / rules / learnings (additions)
                     + overrides / disables of specific system rules    (changes)
EFFECTIVE CONTRACT   = System ∪ engagement-additions − engagement-disabled ⊕ engagement-overrides   (resolver merges)
```

**Concretely:** every registry row (`agent_profile` / `skill` / `governance_rule` / `learning`) carries an explicit **`scope` discriminator** — `system`, or a specific engagement. **Design it scope-aware now** and the future unified DB (§13.5) needs *no registry rework*; build it scope-blind and you rewrite it.

**The multiplier — cross-engagement learning.** A *system* Database Architect accumulates learnings across **every** engagement (a DBA with 50 projects, not one). The learning loop gains a **scope axis**: system learnings (universal) vs. engagement learnings (local), and a new promotion path — a learning seen *independently across multiple engagements* is evidence it's universal → **cross-engagement promotion** from engagement-scope to system-scope. Promoting to a **system enforced rule** is the **top gate** (human review **plus** cross-engagement evidence).

### 13.4 The promotion gate — graded by stakes, conservative-then-earned (DEC-369 + DEC-373)

Reusing the registry's hybrid governance (no new safety system), the gate is graded and *earned*:

```
Learning        → FREE always (advisory observation; never blocks).
Skill (how-to)  → expert-proposed; versioned + float/pin as the safety net.
                  Human-reviewed EARLY; self-promotable once the expert earns trust.
Advisory rule   → expert-proposed; light human ack early; loosens with track record.
Enforced rule   → HUMAN REVIEW REQUIRED, ALWAYS — the permanent hard line. An agent must never
                  self-grant or self-loosen a blocking constraint (the Needs Attention path).
System enforced rule → top gate: human review + cross-engagement evidence (§13.3).
```

**The learning loop measures exactly the trust that loosens the gate** — a discipline with a long, clean track record of correct promotions is an evidenced candidate for more autonomy. The system earns its own slack. This is the same conservative-then-earned principle as the reconciliation automation boundary (DEC-367).

### 13.5 The unified multi-engagement DB — a prerequisite PI (DEC-373 / evolution item 8)

The current **per-engagement-DB** architecture (one `…/engagements/X.db` each, routed by a meta layer) is a dev-stage convenience, not a production architecture (Alembic chain per engagement, no cross-engagement queries, multiplied ops). A future migration to a **single multi-tenant DB with row-level `engagement_id`** is the **natural home** for the system/engagement registry — in one DB the scope model collapses to row scope and cross-engagement learning becomes one `GROUP BY content across engagement_ids` query.

**Sequencing consequence:** the registry's biggest payoff (cross-engagement learning) genuinely needs the unified DB to be practical. So the **unified-DB migration is a strong prerequisite for the registry build and is scoped as its own PI that PI-122 depends on** (§14). It belongs to a production-architecture Project, not the ADO Project. PI-122 is built **scope-aware** regardless, so it works on either foundation and gains nothing-rework when the migration lands.

### 13.6 The standing-agent runtime sharpens the §12 seam (DEC-372)

§12's registry↔runtime boundary is unchanged but clarified: **no agent is a perpetual process.** Because of DB-backed statelessness, *every* agent — Architect, Developer, Tester, PM, Lead — is **spawned on demand and ephemeral**: it reads its state/queue/learnings from the DB, does its unit, writes back, exits. So **"standing" is a *contract scope*, not a process lifetime** — a standing Architect's resolved contract grants portfolio-wide queue access + reconciliation + learning-curation; a Developer's grants one Work Task; both spawn fresh each time. This means the registry has **no daemon to model** — it resolves contracts; the runtime scheduler (a separate §10 follow-on) injects them and spawns the ephemeral agent (build agents in a fresh worktree from current `main` HEAD). The registry is **runtime-ready** when its resolver returns a complete contract (prompt + tools + ruleset + **active learnings** + version + scope-merge).

### 13.7 Revised implementation checklist (extends §9)

Beyond §9's three-entity set, the v0.3 build must:

1. Add the **fourth entity `learning` (`LRN-`)** + its three edge kinds (`learning_derived_from`, `learning_contradicted_by`, `learning_promoted_to`) to the schema spec set, the Alembic migration, `REFERENCE_RELATIONSHIPS`, `_kinds_for_pair`, and the `relationship_kind` CHECK.
2. Carry a **`scope` discriminator** (`system | engagement`) on every registry row (`agent_profile` / `skill` / `governance_rule` / `learning`) — the one design choice that makes the unified-DB migration rework-free.
3. Model profiles per **(area × tier)** (§13.1), seeded with the two proven prompts (Development-area Architect-tier ≈ the proven "Development Phase Specialist"; an Area-Specialist ≈ a Developer-tier profile) mapped onto the new axis.
4. Implement the **resolver** to compose the **effective contract** = System ∪ engagement-overlay, including active (area, tier) learnings.
5. Implement the **write-back lifecycle** — a capture step at Work-Task close, the propose/promote workflow reusing the skill/rule catalog + float/pin + `needs_attention` human gate, and the per-release **curate** Work Task.
6. (Schema-only in PI-122; *driven* by the runtime follow-on.) Keep the resolver runtime-ready per §13.6.

The reconciliation `finding` entity (`FND-`) is an **ADO-substrate build concern** (it lives in the org's delivery model, not the registry), but the learning loop *consumes* findings as evidence — so the two builds are coupled at the `learning_derived_from → finding` edge. Sequence accordingly.

---

## 14. Build sequencing (v0.3)

The evolution's §10 NEXT items resolve into this order:

1. **Govern the design decisions** — ✅ done: DEC-367…373 recorded via SES-149 (06-01-26).
2. **Fold the expanded scope into this PRD / PI-122** — ✅ done: §13 above; PI-122's description updated to the v0.3 scope.
3. **Scope the unified multi-engagement-DB migration as its own PI** (§13.5) — a production-architecture PI that **PI-122 depends on** (`blocked_by`). To author next.
4. **Build PI-122** (the registry, now scope-aware + learning-capable) — onto the unified-DB foundation once (3) lands; the schema is built scope-aware either way.
5. **Wire the runtime scheduler** (§13.6 / §12) — the separate §10 follow-on that injects contracts and spawns ephemeral agents — after the registry can resolve them.

Once (3)–(5) land, the ADO runs its own subsequent PIs with registry-supplied contracts instead of hand-written prompts.
