# Governance & Delivery Redesign — Target Data Model

**Document type:** Application development design (target model; migration destination)
**Repository:** `crmbuilder`
**Proposed path:** `PRDs/product/crmbuilder-v2/governance-redesign-target-model.md`
**Status:** v0.4 — all §11 open decisions resolved; model locked for migration PI-112.
**Last Updated:** 05-30-26 *(timestamp to confirm at commit)*

---

## Status

This is the **target data model** for the governance/agent-delivery redesign discussed at this session. It exists to do one thing: define the destination so that (a) new records can start conforming to it and stop drifting, and (b) the migration has a fixed target. It is a *data-model* document. The runtime agent organization (the general-purpose / discipline-manager / area-specialist agents) is named here for context but is explicitly out of scope — it is behavior, not stored shape, and it follows the model rather than gating it.

Provisional calls are marked **(proposed)**. Genuine forks are collected in §10 rather than decided unilaterally.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 05-30-26 16:15 | Doug Bower / Claude | Initial draft. Target entity set (Project, Planning Item + lifecycle, Workstream-as-phase, Work Task, two-tier Area), relationships, status models, migration sequence, open decisions. |
| 0.2 | 05-30-26 16:40 | Doug Bower / Claude | Expanded §1 with how a work ticket is used and executed today (kinds, its `addresses`-only outbound edge, indirect workstream tie, session-opens-against execution, single-use consumption) and the contrast with the target Work Task. |
| 0.3 | 05-30-26 17:00 | Doug Bower / Claude | Recorded the resolved WS-012 disposition (shelved, DEC-344) and Planning Item area roll-up (sheds live area, DEC-342) in §10 and §11; the doc is now the kickoff artifact for migration PI-112. |
| 0.4 | 05-30-26 | Doug Bower / Claude | Resolved the remaining seven §11 open decisions (#1–6, #8). Identifier scheme: Project→`PRJ-` (existing `WS-` rows migrated), Workstream-phase→`WSK-`, Work Task→new entity `WTK-` (DEC-345). PI lifecycle: phase-agnostic six-state set (DEC-346). Area priority: ordinal layer rank on System Areas (DEC-347). Engagement Areas: fully user-defined, no Domain relationship (DEC-348). Phase vocabulary: adds `Design` (DEC-349). Entity sections §2–§8 updated to the locked choices; model is now fixed for migration PI-112. |

## Change Log

**Version 0.4 (05-30-26):** Resolved the seven remaining §11 open decisions in a migration-planning conversation following the SES-132 design session. The locked calls (each now folded into its entity section): **DEC-345** — identifier scheme: `workstream`→Project takes a new `PRJ-` prefix with existing `WS-001..WS-014` rows *migrated* to it (not kept), the delivery-phase Workstream takes `WSK-`, and Work Task is a *new* entity with prefix `WTK-` (not a refit of `work_ticket`, which keeps its kickoff-pointer role); **DEC-346** — Planning Item lifecycle uses phase-agnostic state names (Draft → Decomposed → Ready → In Progress → In Review → Resolved, with Deferred/Cancelled); **DEC-347** — area priority is an ordinal layer rank on the System Areas; **DEC-348** — Engagement Areas are fully user-defined at engagement initialization with *no* relationship to methodology Domain records; **DEC-349** — the Workstream phase vocabulary adds `Design` to the front. With these, every §11 fork is closed and the data model is locked as the migration target for PI-112.

**Version 0.3 (05-30-26):** Recorded the decisions reached after drafting — WS-012 shelved (DEC-344) and the Planning Item shedding its live area (DEC-342) — in §10 (impact on in-flight work) and §11 (open decisions #7 and #9 now resolved). This document becomes the kickoff artifact for migration planning item PI-112.

**Version 0.2 (05-30-26):** Expanded §1 with a grounded account of how `work_ticket` records are used and executed today — their kinds, their single `addresses` outbound edge, their lack of any direct workstream edge, the `session_opens_against_work_ticket` execution path, and single-use consumption — followed by the contrast with the target Work Task.

**Version 0.1 (05-30-26):** Initial draft from the session that resolved the `workstream → Project` rename, the version-prefix drop on areas, the System/Engagement area tiers, and the three-tier agent-delivery direction.

---

## 1. The shift, in one picture

**Today:** the unit of dispatched work is the whole Planning Item. `area` is a multi-valued tag on the Planning Item, used only for collision avoidance. `workstream` is a long-running thematic container holding many Planning Items. One agent works a whole Planning Item end-to-end.

**Target:** a Planning Item is decomposed into **Workstreams** (delivery phases — Development, Testing, Documentation, etc.), each containing **Work Tasks** that are each scoped to a **single area**. The long-running thematic container is renamed **Project**. Work is pulled by standing agents when a Planning Item reaches a *ready* lifecycle state.

Three orthogonal axes fall out of this, and keeping them separate is the point:

- **Planning Item** = *what* (the feature / requirement)
- **Workstream** = *which phase* (the discipline: build, test, document, migrate, deploy)
- **Area** = *where* (the subsystem the work touches)

### How a work ticket is used and executed today

A `work_ticket` (WT) today is a one-shot pointer to a workflow file. It comes in a few kinds — most commonly `kickoff_prompt` (the markdown that *starts* a unit of work) and `claude_code_prompt` (an apply / execution prompt run in Claude Code), with `other` for ad-hoc cases. Every WT carries a `work_ticket_file_path` to the canonical `.md` in the repo plus a short description summary.

Its governance relationships today are narrow:

- **To the Planning Item:** a `kickoff_prompt` WT's characteristic outbound edge is `addresses`, pointing at the Planning Item it kicks off (or, for a workstream-establishing kickoff, the workstream). That `addresses` edge is essentially the WT's only outbound link — the "how to start this" pointer, paired with the Planning Item's "why / what."
- **To the workstream (soon Project):** *none directly.* A WT's tie to the workstream is purely indirect — through the Planning Item it addresses, and through the session that consumes it (the session belongs to the workstream). There is no `work_ticket → workstream` edge.

Execution is human-initiated and coarse-grained. A person opens a new Claude.ai or Claude Code session **against** the WT (the `session_opens_against_work_ticket` edge); the session reads the file at `work_ticket_file_path` as its source of truth for the work, performs it, and produces a close-out. The WT is **single-use** — opening against it consumes it (status flips `ready → consumed`), so one WT corresponds to roughly one session's worth of work, launched by hand.

That is the gap the redesign closes. Today a WT is a coarse, one-shot, human-launched *kickoff pointer that addresses a Planning Item*. In the target, a **Work Task** is a fine-grained, single-area, agent-claimable unit that *belongs to a Workstream* and is one of many beneath it. Same lineage, very different granularity and role — which is exactly why §11 #3 asks whether the Work Task refines `work_ticket` in place or becomes a new entity beneath it.

---

## 2. Entity: Project *(renamed from `workstream`)*

A long-running thematic container delivering a coherent body of functionality — many Planning Items, requirements, and decisions over weeks or months. This is a **pure rename** of today's `workstream` entity (e.g., the orchestrator workstream, WS-012); no change to its meaning or its data.

- **Contains:** Planning Items (one Project → many Planning Items).
- **Identifier:** **`PRJ-` (resolved, DEC-345).** The existing `WS-001..WS-014` rows are *migrated* to `PRJ-NNN` rather than kept — the end-state is one consistent scheme at the cost of a one-time identifier rewrite (DB rows, reference edges, close-out payloads, deposit logs, design-doc prose; git history is immutable, so historical commit messages are fix-forward only).
- **Migration character:** conceptually trivial (rename only), mechanically wide — touches the table, REST routes, MCP tools, the desktop panel, every reference-kind name containing "workstream," and the `WS-NNN` → `PRJ-NNN` identifiers.

---

## 3. Entity: Planning Item *(retained, gains a lifecycle)*

The requirement / feature unit — the "what." Largely unchanged in identity, but it gains a real **status lifecycle** to support pull-based dispatch. This is the schema gap the redesign surfaces; today the status is only Open / Resolved / Deferred, with no notion of planned-ness or readiness.

**Lifecycle (resolved, DEC-346 — phase-agnostic names, since the Workstream carries the phase):**

`Draft` → `Decomposed` → `Ready` → `In Progress` → `In Review` → `Resolved`
(with `Deferred` and `Cancelled` reachable from most states)

- **Draft:** created, not yet broken down.
- **Decomposed:** planning agents have produced its Workstreams and Work Tasks.
- **Ready:** decomposition complete and upstream `blocked_by` dependencies satisfied — **this is the trigger standing agents watch for.**
- **In Progress → In Review → Resolved:** delivery and verification.

The names were deliberately generalized off the development-specific draft (`Ready for Development` / `In Development`): not every Planning Item is a development item (some are documentation, migration, or — like SES-132 itself — design), so the phase belongs on the Workstream, not in the PI state name.

- **Area:** **does not live here in the target model** — it moves to the Work Task. A derived roll-up (a Planning Item's area = the union of its tasks' areas) is optional; see §10.
- **Relationships retained:** `blocked_by` between Planning Items (cross-feature dependencies). `belongs_to` a Project.
- **New relationship:** decomposed into Workstreams.

---

## 4. Entity: Workstream *(new meaning — a delivery phase)*

A single **phase of delivering one Planning Item**. Belongs to exactly one Planning Item (one Planning Item → many Workstreams).

- **Phase type (controlled vocabulary, resolved DEC-349):** **Design**, Development, Testing, Documentation, Data Migration, Deployment. `Design` was added to the front so design work (like the SES-132 design session itself) has a home. Not every Planning Item uses every phase.
- **Sequencing:** Workstreams within a Planning Item are ordered so a later phase never runs before its prerequisite (no testing before development). **(proposed)** each phase type carries a default order rank; explicit `blocked_by` between sibling Workstreams handles exceptions.
- **Discipline / skill profile:** the phase determines the manager-agent specialization at runtime (e.g., a Development workstream → a Web Dev Manager or iOS Dev Manager agent). The *profile* is runtime config; the *phase type* is the stored field.
- **Lifecycle (proposed):** `Planned` → `In Progress` → `Complete` (+ `Blocked`).
- **Identifier:** **`WSK-` (resolved, DEC-345).** `WS-` is taken by Project (which migrates from `WS-` to `PRJ-`, but the prefix is not recycled to avoid historical ambiguity).

---

## 5. Entity: Work Task *(single-area unit of execution)*

A single unit of executable work within a Workstream — e.g., a Development workstream might hold two data-layer tasks and one API task.

- **Single area (hard constraint):** exactly one area, not a set. This is the key change from today's multi-valued area on the Planning Item.
- **Belongs to:** one Workstream.
- **Carries:** the area (single), the executable instruction body (the kickoff/prompt content), `claimed_by` / `claimed_at` (so a specialist agent claims it), status, and a skill profile for the area specialist.
- **Cross-area sequencing within a Workstream:** the area **layer rank** (see §6) provides the default order (storage before access before api before ui), with explicit task-level `blocked_by` for exceptions.
- **Identifier:** **`WTK-` (resolved, DEC-345).**
- **Relationship to today's `work_ticket`:** **a new entity, not a refit (resolved, DEC-345).** The Work Task is its *own* entity (`WTK-`) beneath the Workstream; `work_ticket` (`WT-`) is left untouched in its current kickoff-pointer role. The two lifecycles diverge too much to overload one table — `work_ticket` is single-use (`ready → consumed`), while a Work Task is agent-claimable (`Planned → Ready → Claimed → In Progress → Complete`). Whether `work_ticket` is eventually retired once the agent organization is built is deferred (§12).

---

## 6. Area model *(two tiers; version prefix dropped; relocated to Work Task)*

`area` now lives on the **Work Task** (single-valued), and the vocabulary splits into two tiers.

**System Areas** — global, shared by every engagement, the standard set covering CRMBuilder's own product and method. Not deletable or editable through the app or engagement setup; evolvable only by deliberate developer change (the existing DEC-006 gate). Version prefix dropped per this session's decision:

`storage`, `access`, `api`, `mcp`, `ui`, `methodology-process`, `methodology-templates`, `methodology-interviews`, `methodology-product`, `infrastructure`, `espo`, `automation`, `programs`

**Engagement Areas** — a per-engagement set **fully defined by the user** during engagement initialization, capturing that engagement's own work regions. CBM's are the first real example: `mn`, `mr`, `cr`, `fu`, `services` (formerly `cbm-*`). A future client defines its own.

- **No Domain relationship (resolved, DEC-348).** Engagement Areas are *user-defined labels only* — they are **not** seeded from, derived from, or otherwise tied to the methodology's `domain` records. The two vocabularies stay fully decoupled: a Domain is a client-facing discovery artifact with its own `candidate → confirmed → deferred` lifecycle; an Engagement Area is internal work-routing plumbing. CBM's `mn/mr/cr/fu` *resemble* its domains and `services` deliberately has no domain at all, but the system treats every engagement-area label as opaque user input. This keeps governance task-scoping independent of methodology lifecycle changes.
- **Validation:** a Work Task's area must be a member of (System Areas ∪ its engagement's Engagement Areas).
- **Layer rank (resolved, DEC-347):** the platform System areas carry an ordinal encoding the dependency spine: `storage` (1) → `access` (2) → `api` (3) → `mcp` / `ui` (4, parallel). This is what makes "data before api before ui" automatic within a Workstream. The non-stack System areas (methodology, infrastructure, legacy engine) and all Engagement Areas are unranked / parallel (null rank); explicit task-level `blocked_by` handles their exceptions. A separate ordering table or edges-only scheme was rejected as over-built for a fixed spine.
- **Storage of Engagement Areas:** a per-engagement table, populated entirely from user input at engagement initialization (no Domain seed, per DEC-348).

---

## 7. Relationships (target)

| From | Edge | To |
|------|------|----|
| Planning Item | belongs_to | Project |
| Workstream | belongs_to | Planning Item |
| Work Task | belongs_to | Workstream |
| Work Task | has_area (single) | Area |
| Planning Item | blocked_by | Planning Item |
| Workstream | blocked_by (optional) | Workstream (same Planning Item) |
| Work Task | blocked_by (optional) | Work Task (same Workstream) |
| Conversation / Session | works | Planning Item / Workstream / Work Task |
| Conversation | orchestrates | Conversation (parent agent → child agent) |

Existing `*_belongs_to_workstream` reference kinds become `*_belongs_to_project`. New kinds are needed for the Planning Item → Workstream → Work Task containment chain.

---

## 8. Status models (target, proposed)

- **Planning Item:** Draft → Decomposed → Ready → In Progress → In Review → Resolved | Deferred | Cancelled *(phase-agnostic names, DEC-346)*
- **Workstream:** Planned → In Progress → Complete | Blocked
- **Work Task:** Planned → Ready → Claimed → In Progress → Complete | Blocked | Failed

---

## 9. Migration sequence (current → target)

Ordered so each step leaves the database internally consistent. No big-bang.

1. **Rename `workstream` → `Project`.** Pure rename, wide blast radius (table, routes, MCP tools, UI panel, reference-kind names, identifiers). Settle the identifier-prefix question first (§10).
2. **Restructure the Area vocabulary.** Drop the version prefix; split into immutable System Areas and per-engagement Engagement Areas; migrate `cbm-*` into the CBM engagement's Engagement Areas. (Area still attached to the Planning Item at this stage, until step 4 introduces the Work Task.)
3. **Add the Planning Item lifecycle statuses** (extend the status vocabulary and transition rules).
4. **Introduce Workstream (new meaning) and Work Task**; relocate `area` from the Planning Item onto the Work Task; add layer rank.
5. **Build the agent organization** (runtime — general-purpose, discipline-manager, area-specialist agents; standing pull dispatch). Out of scope for *this* document.
6. **Reconcile / retire the WS-012 walk-orchestrator** as the agent organization subsumes it.

---

## 10. Impact on in-flight work

- **Area backfill (PI-083) — held, superseded (DEC-342, DEC-344).** It writes `area` onto the 54 open Planning Items, but the target relocates area to the Work Task, so it is not run — the relocation supersedes it. PI-083 stays `Open` in the database, governed-as-shelved, until the Planning Item lifecycle provides a clean `Deferred` state.
- **Orchestrator driver (PI-081) / WS-012 — shelved (DEC-344).** WS-012 is set aside as a standalone tool: its §7.2 acceptance is not run, and effort goes to the agent-delivery target. PI-081 is implemented-but-superseded — its substrate (claiming, ready-batches, the per-agent conversation/session pattern) carries forward — and stays `Open`, governed-as-shelved, pending the same lifecycle `Deferred` state.

---

## 11. Open decisions

1. **Project identifier prefix** — *resolved (DEC-345):* migrate existing `WS-` rows to `PRJ-` (clean single scheme, not prefix-stability).
2. **Workstream identifier prefix** — *resolved (DEC-345):* `WSK-`. `WS-` is not recycled even though Project vacates it, to avoid historical ambiguity.
3. **Work Task = refined `work_ticket`, or a new entity beneath it?** — *resolved (DEC-345):* a **new** entity, prefix `WTK-`. `work_ticket` (`WT-`) is left in place in its kickoff-pointer role; eventual retirement deferred (§12).
4. **Planning Item lifecycle states** — *resolved (DEC-346):* the six-state set, with **phase-agnostic** names (Draft → Decomposed → Ready → In Progress → In Review → Resolved, + Deferred/Cancelled).
5. **Area priority representation** — *resolved (DEC-347):* an ordinal **layer rank** on each System area; a separate ordering table and edges-only were rejected as over-built.
6. **Engagement Area storage** — *resolved (DEC-348):* a per-engagement table, **fully user-defined**, with **no** relationship to Domains. An Engagement Area is a distinct concept from a Domain, not the same thing.
7. **Planning Item area roll-up** — *resolved (DEC-342):* the Planning Item sheds its live area; a derived roll-up from its Work Tasks may come later.
8. **Workstream phase vocabulary** — *resolved (DEC-349):* {**Design**, Development, Testing, Documentation, Data Migration, Deployment} — `Design` added to the drafted set.
9. **WS-012 disposition** — *resolved (DEC-344):* shelved for the run target; PI-081 implemented-but-superseded, PI-083 held.

**All nine open decisions are now resolved.** The data model is locked as the migration target for PI-112.

---

## 12. Out of scope (for this document)

- The runtime agent organization itself (general-purpose / discipline-manager / area-specialist agents, standing pull dispatch, skill profiles). Named for context; specified separately once the data model is locked.
- An "agent profile" registry (skill definitions per discipline/area) — deferred; runtime config, not governance data, until proven otherwise.
