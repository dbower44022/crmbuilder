# Agent Profile Registry — PRD

**Document type:** Application development design (the centralized registry of skill and governance-rule definitions that the Agent Delivery Organization's agents draw from)
**Proposed path:** `PRDs/product/crmbuilder-v2/agent-profile-registry/agent-profile-registry-PRD-v0.1.md`
**Status:** v0.1 — DRAFT proposal. Nothing built. For reconciliation against the locked ADO design and the PI-112 governance model before any implementation.
**Last Updated:** 05-31-26 18:15

---

## Status & positioning

This PRD specifies an **Agent Profile Registry**: the centrally-managed store of *what each agent knows and is allowed to do* — its skills and its governance rules — so that capabilities can be managed in one place even when agents run dispersed.

It is **the explicitly-deferred follow-on to the Agent Delivery Organization (ADO) design.** ADO v0.3 §10 lists as out of scope: "the concrete agent prompts / skill definitions for each specialist (follow-on, once the model is locked)" and "an 'agent profile' registry (skill definitions per phase/area) — deferred." The data model is locked (PI-112, Alembic head `0033`+); this document proposes the behavior-supporting registry those follow-ons call for.

This PRD is the product of a Claude.ai design conversation that ran **before** the ADO and governance model were in view. The registry *pattern* it proposes is sound and carried over; the original agent roster from that conversation (generic EspoCRM-deployment agents) was aimed at the wrong layer and has been re-pointed at the ADO tiers here. See §3 for the reconciliation and §7 for the decision history, preserved intact.

---

## Revision Control

| Version | Date (MM-DD-YY HH:MM) | Author | Summary |
|---------|------------------------|--------|---------|
| 0.1 | 05-31-26 18:15 | Doug Bower / Claude | Initial proposal. Registry pattern (versioned skill + governance-rule catalog, float/pin propagation, hybrid advisory/enforced governance, resolver→contract) re-pointed from the original generic-agent framing onto the ADO tiers/phases/areas and reconciled with the PI-112 governance model. Illustrative artifacts attached under `illustrative/`. |

## Change Log

**Version 0.1 (05-31-26 18:15):** First draft. Reframes a prior design conversation's agent-registry work as the ADO §10 agent-profile registry. Records the four design decisions made in that conversation (hybrid governance, two-kind skill taxonomy, storage path, drift-assertion pinning) with rationale and alternatives, and maps them onto V2 conventions. Implementation approach (governance entity + Alembic + access layer + REST envelope + MCP + recording rules) specified at proposal level only.

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
**Decided in conversation:** maintain portable SQLite + Postgres migrations. **Superseded by V2 reality:** V2 already runs SQLite under Alembic (head `0033`+) behind the access layer; there is no separate Postgres target to plan for at this layer. The illustrative dual-engine DDL is therefore reference-only; real implementation is a single Alembic migration consistent with the current head.

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

## 10. Open questions for the next session / Claude Code

1. **Entity vs vocab for skills/rules.** Are `skill` and `governance_rule` full governance entities (proposed here) or lighter vocab/config? The entity route is more queryable and auditable; vocab is lighter.
2. **Identifier prefixes.** `AGP` / `SKL` / `GVR` are proposals — confirm against the existing prefix registry to avoid collisions.
3. **Broker scope.** How much enforcement does the access layer already cover, and what genuinely needs a separate evaluation step? Likely small.
4. **Profile ↔ ADO role coupling.** Is a profile pinned 1:1 to an ADO role/specialization, or can a role compose multiple profiles?
5. **Relationship to WS-012 orchestrator retirement** (ADO §10) and the shelved `planning_item.area` column — any interaction?

---

## 11. Illustrative artifacts

The `illustrative/` folder holds the originating conversation's artifacts. They demonstrate the *pattern* (versioned catalog, float/pin, advisory/enforced, resolver→contract, code-asset bridge) and a passing reference broker, but they predate the ADO/governance context and are **not drop-in**: they use a generic agent roster, raw relational tables, hand-written dual-engine SQL, and a standalone Python runtime. Read them for the mechanics, not the taxonomy or the storage approach. See `illustrative/README.md`.

- `crmbuilder-v2-agent-registry-schema.md` — the detailed schema spec (engine- and pattern-illustrative).
- `migration_v2_0_sqlite.sql`, `migration_v2_0_postgres.sql` — illustrative DDL; real work is one Alembic migration.
- `seed_v2_0_agent_registry.yaml` — illustrative seed with the (wrong-layer) generic roster, kept as a pattern example.
- `agent_runtime.py` — illustrative resolver + broker; standalone, not access-layer-integrated.
- `smoke_test.py` — exercises the reference logic against the illustrative SQLite schema; passes.
