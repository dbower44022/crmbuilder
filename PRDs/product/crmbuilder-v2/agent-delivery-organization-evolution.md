# Agent Delivery Organization — Evolution: Matrix Org, Expert Agents, and the Learning Registry

**Document type:** Design evolution / direction note (the next iteration of the ADO's *agent layer*).
**Status:** v0.3 — **DESIGN COMPLETE + GOVERNED & EXECUTION-PLANNED (06-01-26)**, nothing built. Captures the full agent-layer evolution; all design decisions (§10 items 1–7) are decided with rationale and **now governed as DEC-367…373 (SES-149)**. The execution-planning follow-through is **done**: the registry PRD is expanded to v0.3 + PI-122 rescoped; the unified-DB migration is scoped as **PI-123** under a new Production Architecture project **PRJ-019** with **PI-122 `blocked_by` PI-123** (DEC-374 / SES-150); the build sequence is recorded (registry PRD §14). The next move is **building PI-123, then PI-122** (§10).
**Relationship to other docs:**
- Baseline: `agent-delivery-organization-design.md` (v0.3) — the locked ADO model, whose **substrate is built** (PI-114 / WTK-001…006). This document **evolves the agent layer that sits on that substrate**; it does **not** change the data-model substrate.
- Forward: `agent-profile-registry/agent-profile-registry-PRD-v0.1.md` (**v0.3**, scoped as **PI-122**, now **`blocked_by` PI-123**) — the registry that holds the agent prompts/skills/rules. This conversation **significantly expanded what that registry must be** (see §9); v0.3 §13/§14 fold that expansion in. PI-122 is not yet built.
**Last Updated:** 06-01-26

---

## 0. Why this document exists — the originating seam

This evolution started from one concrete question while preparing to execute PI-122's Architecture phase:

> The Architecture Phase Specialist analyzed the requirements, decided the system needs a new entity `agent_profile`, and created a Work Task *"author the agent_profile schema spec"* — but it did **not** write the spec. Does that split make sense? Doesn't the architect have to figure out the whole schema just to *decide* the entity is needed? If so, wouldn't it be trivial to write the spec itself — and by not writing it, isn't the architect's reasoning lost when a separate Area Specialist later writes it?

The realization: **the ADO's tier split between "decide the work" (Phase Specialist) and "do the work" (Area Specialist) has variable width depending on the phase.**
- It is **widest and most valuable in Development**: "decide we need a storage change" vs. "write 400 lines of migration + repository code" are genuinely different activities, parallelizable across areas.
- It is **narrowest, arguably collapsible, in Architecture**: the architect's design analysis *already is* most of the artifact (a schema spec is a formalization of the design decision, not a separate act). Forcing a thin Work Task handoff there risks **losing the architect's reasoning** between "decide the entity" and "spec the entity."

Applying one flat rule (§4.2 of v0.3: "scope = Work Task creation; do = Area Specialist") uniformly to all six phases strains exactly at design. Pulling on that thread produced the redesign below.

> **Why this lands in the not-yet-built layer.** Everything in this document is an **agent-layer / registry change**, not a substrate change (see §8). The substrate built in PI-114 — entities, areas + layer ranks, the decompose/scope/gate/execute endpoints, DB-backed statelessness — accommodates all of it unchanged. This is the direct payoff of the "prove the agents end-to-end *before* building the registry" sequencing: we are discovering the registry must be a *learning organization's memory*, not a config table, while it is still only a PRD.

---

## The thesis — *why* this shape (the payoff, decided 06-01-26)

Everything below is in service of one trade: **front-load the coherence so you can unleash the parallelism.**

The **design + reconciliation phases are deliberately rigid and serial**, gated **all-or-nothing**: *no development begins on a release until **all** its design reconciliation — review and resolution — is complete and clean* (the **coarse gate**; see §4 and §6 for the structural + principled reasons). That rigidity is the *investment*. The **payoff** is that the moment the gate opens, **a large number of build agents can spin up at once and develop in parallel with little or no issues** — because reconciliation has handed them:

1. a **locked, stable design** (no moving target);
2. **precise, mutually-consistent specs** — complete per-area contracts that reconciliation has *proven* don't contradict; and
3. the **dependency-ordered build plan** (`blocked_by` edges) — so agents parallelize maximally along the DAG.

This **eliminates the "ping-pong" effect by construction** — the failure mode where independent workers/agents make breaking changes in each other's work and only discover it at integration. Here, every cross-cutting decision that *would* collide is surfaced and resolved **once, up front, at design time** (cheap — change a spec) instead of at integration time (expensive — rip up code).

**The economics:** you **serialize the cheap thing (design/coherence — judgment + documents) and parallelize the expensive thing (build).** That puts the rigid serial bottleneck on the inexpensive phase and lets the costly phase explode into N parallel agents — the opposite of the common failure of rushing design and serializing rework at the end.

**Two honest qualifiers:**
- It eliminates the **class** of failure from *independent design* (structural/breaking conflicts), **not** implementation bugs — those are still caught by the **Test** pass. Defects shift *left* to where they're cheap.
- It **concentrates risk in the design phase**: a *wrong* design is now parallel-built fast and consistently. That is exactly why the high-leverage investments are the **deep area experts**, the **reconciliation gate**, and the **learning loop** that improves each release's design — the org's intelligence must live at the *front* of the pipeline.

---

## 1. The shape: a matrix organization (passes × areas)

The ADO is reframed as a **matrix**:

- **Vertical axis — areas (disciplines):** Data, API, Web UI, Mobile UI, Desktop UI, … — keyed to the existing `vocab.SYSTEM_AREA_RANKS` plus per-engagement Engagement areas. Each area is a *discipline* with genuinely different expertise (designing a schema ≠ writing optimized SQL; Web ≠ Mobile ≠ Desktop), so each gets its own skills and its own governing rules.
- **Horizontal axis — passes:** **Plan → Design → Develop → Test** — exactly four (the original six "phases" reduce to these; Documentation / Data Migration / Deployment *dissolve* into discipline concerns + release-level activities, see §1's "core passes"). *Phases **are** passes.*

The unit of work is a **(pass × area) cell**, each performed by a **distinct expert** (e.g. *Data Architect* in the Design pass for the Data area; *Data Developer* in the Develop pass). You instantiate **only the cells a PI/release actually touches** — the matrix is sparse.

### The four core passes (DECIDED 06-01-26)

There are **exactly four** core passes; the original six "phases" reduce to these plus dissolved concerns (below).

- **Plan** — the **area-determination / decomposition** step: read the PI, decide *which disciplines it touches*, and create the structure the other passes populate. It has **no area Work Tasks of its own** — it produces the others, and moves "which areas?" to one coherent up-front call (instead of each phase specialist deciding its own areas).
- **Design** — the area **Architects** each produce a **precise, testable development spec** for their area (defines *what to develop* **and** *how it will be tested*). The phase Workstreams with per-area Work Tasks begin here.
- **Develop** — the area **Developers** execute the reconciled specs into code.
- **Test** — the area **Testers** implement the Architect's test-spec (§3.1) against the built feature.

### Documentation / Data Migration / Deployment are *not* passes — they dissolve (DECIDED 06-01-26)

Each belongs somewhere specific, with a **forced-consideration checkpoint** so nothing is silently dropped (preserving the §4.1 "never silently drop it" benefit):

- **Data Migration → a storage-discipline concern, surfaced as a Design checkpoint.** The storage Architect must explicitly scope a data-migration Work Task **or assert Not Applicable**; the work itself is a **Develop / storage** task. (Usually N/A.)
- **Documentation → woven, not a pass.** Design docs (schema specs, entity definitions) *are* Design output; feature/code docs are part of **"done"** for each Develop task (a Definition-of-Done rule); **release-level** docs (release notes, how-tos, CLAUDE.md) are a **release-finalization** activity at *Shipped*, produced by a documentation discipline.
- **Deployment → the Release lifecycle's *Shipped* stage**, plus the deploy *mechanism* (scripts/config) is **Develop / infrastructure·espo·automation** work. (You deploy a *release*, not individual PIs.)

The Design pass requires storage to address data-migration; the Develop DoD requires code docs; the Release *Shipped* gate requires deployment + release docs (or an explicit waiver) — the checkpoints live where the work actually is.

**Substrate consequence:** `WORKSTREAM_PHASE_TYPES` shrinks from the current 6 to **3 phase-Workstream types** (`Design`/`Develop`/`Test` — keeping the current `Architecture`/`Development`/`Testing` names is fine) **+ Plan as the decompose act**, with Documentation/Data Migration/Deployment removed as phases. A phase-vocab migration, part of *building* the evolution (rides along with the other substrate changes it needs).

---

## 2. Phase-major vs. area-major — **DECISION: phase-major, with reconciliation**

The same grid can be sliced two ways into Workstreams. This was the first fork settled.

- **Phase-major (chosen):** a Workstream = a **pass (row)**; the gate sits **between passes**. *All* areas Design → gate → *all* areas Build → gate → *all* areas Test. Areas run in parallel *within* a pass.
- **Area-major (rejected):** a Workstream = an **area (column)**; each area is its own Design→Build→Test pipeline; gate sits inside each column. Areas ordered by layer dependency; independent areas pipeline in parallel.

### Rationale

**The three passes want different orderings**, and that asymmetry decides it:
- **Design wants global-first coherence.** Design decisions ripple across areas (schema → API → UI). If areas design in isolation and you build before reconciling, you build on an inconsistent design and rework it. So the Design pass benefits from "all areas design → reconcile → gate." That is phase-major, and it is where the verification gate earns the most.
- **Build wants layer-pipelining** (storage → access → api → ui) — but **the substrate already provides this *inside* a phase** (Work Tasks carry `area`; areas carry layer ranks; tasks run in parallel where ranks allow). So the parallelism area-major buys, phase-major already has.
- **Test follows build.**

So area-major's only real win — pipelining independent verticals — is already available within phase-major, while phase-major's win — one moment where the *whole design* is verified coherent before any build — area-major gives up (it fragments into many per-(area,pass) gates, with no point that checks cross-area coherence). **Phase-major optimizes for coherence (catch cross-area mistakes before building); area-major optimizes for flow (finish/ship one vertical at a time).** For coupled v2 work, coherence wins.

**Area-major rejected** as a default: it only pays off for *truly independent* verticals (e.g. three unrelated UI surfaces with no shared data/API), where forcing global design is pure latency. A hybrid (Design global-gated; Build/Test pipelined per area) remains available if independent-vertical PIs ever dominate, but is not the default.

### The one new concept: the reconciliation gate

Going multi-specialist trades a single architect's free coherence for depth, so coherence must become an **explicit step**: at the **end of the Design pass, before its gate**, a **reconciliation** verifies the area specs cohere (no field the UI assumed that the data spec didn't define) before Build begins. This is the within-PI reconciliation; see §4 for its horizontal twin.

---

## 3. The expert tiers — Architects (steward) vs. Developers (execute)

The generalist "Phase Specialist" of v0.3 dissolves into **per-area experts**, split by responsibility:

- **Area Design Experts ("Architects") — standing, portfolio-aware, reconciling, learning.** One per discipline (Data Architect, API Architect, Web Architect, …). They:
  - produce their area's precise, testable spec;
  - **steward a shared resource** (the schema, the API contract, the UI design system) — they own its coherence;
  - **reconcile** — within a PI (across areas, via the Lead's gate) and within their area (across PIs, §4/§5);
  - **review then dispatch** — they hand clean, reconciled, sequenced specs to the Developers (DECISION, see below);
  - **learn** — accumulate experience into the V2 DB (§7).
- **Area Developers — executors of clean specs.** One per discipline (Data Developer, API Developer, …). They take a complete, reconciled spec and implement it (e.g. write the performant SQL). **They do not reconcile** — reconciliation is a *design* skill; a developer needs no portfolio context, only its one well-defined spec. (Open: developers likely *learn* implementation knowledge too — see §7/§10 — but they never reconcile.)
- **PI Lead** and **Project Manager** are retained from v0.3 as the orchestration tiers (per-PI and cross-PI/portfolio respectively).

**DECISION (review-then-dispatch):** the Architect reviews/reconciles the batch and dispatches cleaned-up specs; the Developer executes. Reconciliation knowledge lives only in the design tier. *(Doug, 06-01-26.)*

### 3.1 The discipline taxonomy (DETAILED 06-01-26 — one fork open)

**The disciplines *are* the area vocab — there is no separate taxonomy to invent.** The 13 System areas (`vocab.SYSTEM_AREA_RANKS`) + per-engagement Engagement areas already define the disciplines; the layer ranks already give the within-pass ordering; a Work Task's `area` routes it to exactly one expert. The registry adds only **profiles per (area × tier)**.

**The tier set is area-kind-dependent — the §0 "variable-width tier split" made concrete:**

| Area | Kind | Tiers |
|---|---|---|
| `storage`(1), `access`(2), `api`(3), `mcp`(4), `ui`(4), `espo`, `automation`, `infrastructure`, `programs` | **build** | Architect · Developer · Tester |
| `methodology-product` / `-process` / `-interviews` / `-templates` | **design** | **Architect only** (the design artifact *is* the deliverable — nothing to build or test) |

The tiers **align to the passes** (Design→Architect, Develop→Developer, Test→Tester); the **standing / portfolio-aware / reconciling** property sits **only on Architects** (Developers, Testers are per-task executors).

**Sub-disciplines (Web / Mobile / Desktop UI):** for CRMBuilder, `ui` = the PySide6 desktop surface — one discipline, the flat System area suffices. An engagement with multiple UI surfaces models them as **Engagement areas** (`ui-web`/`ui-mobile`/`ui-desktop`) — no model change. A two-level System sub-area model (for *universal* cross-engagement Web-vs-Mobile knowledge) is the **deferred** upgrade path.

**Refinement to flag:** the layer ranks order the code areas (storage→access→ui) but leave `methodology-*`/`espo`/`infrastructure`/`programs` at `rank=None`; the Design pass wants the **methodology disciplines first** (entity/process design precedes the code design that realizes it) and `espo` **last** (it maps the built model into EspoCRM config) — so the rank vocab likely needs a light extension to place the rank-less areas.

**DECISION (06-01-26): three tiers — Architect / Developer / Tester** (for build disciplines). The test *design* lives in the Architect (the spec defines "what to develop *and* how it will be tested"); the fork was only who *implements* the tests, and as what. Three wins because:
1. **Independent verification** — the model's DNA. The Tester derives its tests from the Architect's test-spec, **blind to the Developer's implementation**, so it verifies the *specified behavior* not what the dev built — catching dev blind spots that same-agent-writes-its-own-tests structurally can't.
2. **Distinct skills/rules** — boundary/failure-mode coverage, the codebase's fixtures/idioms (`v2_env`/`TestClient`, "don't require a live server"), "test the spec not the code" — a real, learnable discipline.
3. **Pass-aligned + cleaner learning** — tier per pass (the Test pass gets its owner); a Tester discipline accumulates test-specific learnings instead of blurring them into dev knowledge.
4. **Low cost** — profiles are system-level (defined once), share skills, sparsely instantiated.

Two clarifications: the **Tester is a test-*implementer* parallel to the Developer** (both execute the Architect's specs — feature-spec vs. test-spec), with the independence rule *"derive test cases from the Architect's test-spec, not the Developer's code; use the built feature only to run them."* And: **adopt the three-tier model, staff incrementally** — because profiles are system-level + instantiated-as-needed, stand up Architect + Developer first and **add the Tester when rigor warrants** (the model doesn't force all three on day one).

---

## 4. Reconciliation mechanism (DETAILED — decided 06-01-26)

A clean symmetry falls out: the same coherence check runs in two directions, both at the **Design→Develop boundary**.

```
within a PI, across areas    →  the PI Lead         (VERTICAL)   "do this feature's Data/API/UI specs cohere?"
within an area, across PIs    →  the standing Architect (HORIZONTAL) "do all the release's schema changes cohere?"
```

### 4.1 It is a Work Task (DECISION: A)

Reconciliation is performed as a **dedicated "Reconcile" Work Task that runs *last* in the Design phase**, `blocked_by` all of that phase's area-design Work Tasks. Its **deliverable is the set of findings** it emits. This makes the review a tracked, claimable, auditable unit (not an invisible gate action).

- **Vertical reconcile** = one Reconcile task **per PI**, owned by the **PI Lead**, cross-area (reviews that PI's Data/API/UI specs against each other). Clean home: the PI's Design Workstream.
- **Horizontal reconcile** = one Reconcile task **per (release, area)**, owned by the standing **Area Architect** (the Database Architect reviews *every* storage spec across the release's PIs). **Structural home depends on the Release entity (still open, §10.4)** — the mechanism is fully specified; only where this task hangs awaits that decision.

### 4.2 The `finding` record (DECISION: Y — a new governance entity)

A finding is a first-class, queryable, auditable governance entity (not an overloaded `needs_attention`), because findings relate *multiple* Work Tasks across PIs, carry their own lifecycle, and are **the learning loop's raw data** (§7).

```
finding (prefix FND-):
  type      {conflict | gap | dependency | efficiency}
  severity  {blocking | advisory}            ← only BLOCKING holds the gate
  area, description, raised_by, resolution_summary
  status    {open | resolved | accepted | deferred | escalated}
edges:
  finding_relates_to   → Work Task / Workstream / PI / entity   (what it implicates)
  finding_resolved_by  → Decision                               (how it was settled)
```

Finding types and default severity: **conflict** (mutually incompatible specs — e.g. two PIs define `Contact.status` with different enums) = *blocking*; **gap** (a spec assumes something nobody provides) = *blocking* if it breaks coherence; **dependency** (A relies on B) = advisory→blocking if unmet; **efficiency/overlap** (both add a column to `Contact`; both want it indexed) = *advisory*.

### 4.3 Detect vs. resolve — and the gate

Completing the Reconcile Work Task means **"review done, findings emitted"** — it does *not* mean the design is clean. Resolution is separate work. The **gate** is the existing `complete-phase` check on the Design Workstream (rolled up to the release), with **one added precondition**:

> Design phase may complete  ⟺  all its Work Tasks are Complete **AND** it has no **open blocking** findings.

So emitting a blocking finding **holds the gate** until that finding is resolved. (`complete-phase` is the only substrate change — a precondition.)

### 4.4 Resolution menu + who owns it

A blocking finding is resolved by one of: **revise** (one spec yields — often an additive design Work Task), **sequence** (`blocked_by` edge; the PM orders), **merge** (combine into one change/shared task), **accept** (advisory only — keep the redundancy knowingly), **defer** (push a PI out of this release), **escalate** (to a human). Each resolution is recorded as a **Decision** linked by `finding_resolved_by`, which flips the finding to `resolved`.

- **Vertical findings** the **PI Lead** can usually resolve itself (add a Work Task to fill a gap, pick the coherent option). If it can't → `needs_attention` on the Workstream (→ rolls up to the PI).
- **Horizontal findings** the Architect **must not** resolve unilaterally — choosing which PI's approach wins, or making a PI wait, is a **cross-PI priority call the PM owns**. The Architect **detects and proposes**; routes to the **PM** to arbitrate; `needs_attention` at the release level when a human must decide. *The Architect is the expert advisor on the shared resource; the PM is the arbiter of whose timeline bends* — which is what stops a discipline expert from silently hijacking another PI's plan.

### 4.5 Efficiencies — flag-and-propose (DECISION: 3)

When an Architect spots "merge these two migrations," it emits an **advisory** finding and **proposes** to the PM; it does **not** auto-restructure another PI's Work Tasks. (Same caution as conflicts: one expert never silently rewrites another PI's plan.)

### 4.6 Automation boundary — conservative, then earned (DECISION: 4)

Conflict **detection** is agent work (compare the specs). Conflict **resolution** starts **conservative**: any **cross-PI blocking** conflict goes to a **human** (the PM/human). The boundary **loosens as the experts earn trust** — and conveniently, the **learning loop measures exactly that** (a discipline with a long clean track record of correct reconciliations is a candidate for more autonomy).

### 4.7 The loop-closer: findings feed learning

Because findings are first-class records, the standing Architect mines them — *"storage conflicts cluster on `Contact` because it's heavily extended"* becomes a **learning**, proposable as an **advisory rule** (*"before scoping a `Contact` change, check existing extensions"*). Reconciliation is therefore not just a gate; it is a **primary source of the experience the experts accumulate** (§7).

### Substrate impact (small)

One new entity (`finding`, `FND-`), two edge kinds (`finding_relates_to`, `finding_resolved_by`), and one `complete-phase` precondition. Everything else — `needs_attention`, `blocked_by`, `Decision`, the per-area Work-Task queries — is existing machinery.

---

## 5. Cross-PI Expert Agents — the horizontal axis (the matrix org)

This is the most significant structural addition. v0.3 had only the vertical axis (PM → Lead → phases → tasks, delivering *one* PI). That axis has a **blind spot: shared resources.** The schema, the API contract, the UI design system, shared modules are *common goods* many PIs touch at once; per-PI isolation executes each PI's storage task alone and hopes they don't collide at merge.

**The fix: standing per-discipline experts with portfolio-wide visibility.** A single **Database Architect** sees *every* pending database Work Task across the whole portfolio — not one task in one PI. With four database specs pending across four PIs, it reviews them **as a set** to:
- **detect conflicts** — "PI-A and PI-C both alter `Contact` incompatibly";
- **find efficiencies** — "PI-B and PI-D both want the same index — do it once; batch these migrations; this change subsumes that one";
- **keep the shared resource coherent** — one steward per discipline, not a fresh contractor per ticket (the real-org DBA / discipline-lead model).

**Detection vs. arbitration.** The area expert **detects** conflicts/efficiencies; it does **not** unilaterally gate other PIs' timelines. Cross-PI sequencing/priority is the **Project Manager's** call (it already owns cross-PI concerns, v0.3 §3.1). So a conflict or batching opportunity surfaced by the Database Architect flows **up to the PM**, which arbitrates whether a PI waits.

**Substrate already supports it:** "all pending work in area X across PIs" is just a Work-Task query filtered by `area` + status — no data-model change. And DB-backed statelessness (§4.4) makes a *standing* expert resumable: it reconstructs its whole queue from that query, not from memory, so it can die and respawn with full portfolio context. That is what lets these be **standing, pull-based** agents (v0.3 §4.5) rather than spawned-fresh-per-task.

---

## 6. The Release model — **DECISION: planned, release-batched delivery is the default**

**DECISION (Doug, 06-01-26):** prefer **investing more time in Design to produce larger, planned "Releases"** — batch a set of well-defined PIs and execute them as a planned release — over a continuous, small-batch innovation cadence. **Rationale:** very few users need new enhancements every day; a coherent, well-defined batched release makes for a better user experience than a stream of small changes. **Caveat:** early-stage products may rationally move faster with smaller releases; **the methodology is cadence-agnostic** — it works either way and does not *care* whether you go fast/small or slow/large.

**Why this is load-bearing, not incidental:** the release model is the *condition under which the cross-PI area expert (§5) is most valuable.* The project-vs-functional tension I raised — "batching across PIs delays an individual PI" — only bites under continuous delivery, where each PI optimizes its own speed. Under release-batching you optimize the **release's coherence**, not any single PI's speed, so "the Database Architect reviews every schema change in the release together" stops being a tension and becomes **the whole point.** The horizontal expert and the release model reinforce each other.

### 6.1 The gate semantics (DECIDED 06-01-26) — see the thesis above

- **Coarse / all-or-nothing gate.** No development begins on a release until **all** its design reconciliation (review *and* resolution) is complete and clean. Two reasons it holds: (1) **structural** — the horizontal (cross-PI) reconcile for an area *cannot run* until every PI's design for that area is in, so any shared-resource area is unbuildable until then; (2) **principled** — resolving a conflict is itself a design change that can *ripple* into specs that looked clean, so you have no stable target to build against until every blocking finding is resolved. The only theoretical early-build candidate (a single-PI area whose vertical reconcile is clean) is held anyway because of the ripple risk. The **fine-grained** alternative (let provably-isolated clean items build while a conflict resolves) is available only if it also re-gates items a resolution touches, and is *not* the default.
- **Hard sync at Design; flow after.** The lockstep barrier is **only** the Design→Develop gate. Once it opens, Develop/Test **flow under the reconciled plan** (honoring the `blocked_by` sequencing) — they are not lockstep-gated. This is the payoff in the thesis: rigid serial design → massively parallel, conflict-free build.

### 6.2 Release as an entity (DECIDED 06-01-26)

The remaining Release-model details, all confirmed:
- **Release = a new entity (`REL-`), orthogonal to Project.** A PI carries two memberships: its **Project** (long-running *theme*) and its **Release** (*shipping batch*, via `planning_item_assigned_to_release`). A Release can batch PIs from **several Projects** (what ships together isn't one theme). Reusing Project conflates theme with cadence; a tag is too thin to carry a lifecycle, a gate, and the horizontal reconcile's home.
- **Lifecycle:** `Open (intake) → Design → Develop → Test → Shipped (+ Cancelled)`. The PM **closes intake** before Design (you can't reconcile a moving target); a not-ready PI **defers to a future release** rather than stalling the batch.
- **Horizontal-reconcile home (resolves §4's residual dependency):** generalize **Workstream parentage** so a Workstream belongs to a **PI** (delivery phases) *or* a **Release** (per-area **reconciliation Workstreams** that hold the horizontal Reconcile Work Tasks). Alternatives (a reconciliation-PI per release; relaxing "reconciliation is a Work Task") were weaker.
- **PM gains a release-management layer:** assign eligible PIs to a release, close intake, drive the release gates, arbitrate horizontal-reconcile conflicts, defer troubled PIs; `dispatch` becomes release-scoped (PIs dispatched to Leads when the release enters Design).

---

## 7. Learning / Experience agents — the registry becomes the organization's **memory** (DETAILED 06-01-26)

**DECISION direction (Doug, 06-01-26):** the experts should **gain experience over time and write it back into the V2 database, becoming smarter/more experienced after each Work Task.** This reframes the registry entirely: it is **not a static catalog of prompts/skills/rules — it is a living, curated institutional knowledge base** that the experts grow each release. (A senior DBA's value is years of "how *this* company's schema actually behaves"; the Database Architect should accumulate exactly that, queryable and auditable in the V2 DB.)

**Consistency with ADO principles.** This does *not* introduce a stateful-agent problem. The expert stays **stateless** (v0.3 §4.4): it **reads** its accumulated learnings from the DB and **writes** new ones back; the store is **append-mostly** (§4.6). A learning agent is just *a stateless agent reading from a growing store* — resumable, auditable.

### The three knowledge stores (increasing governance)

```
1. Learnings / observations  — append-mostly, evidence-tagged (which Work Task produced it).
                                Written freely by the expert. Advisory only.
2. Skills (how-to)           — versioned catalog. Expert may PROPOSE updates;
                                float/pin propagation (registry §6) governs adoption.
3. Rules (must / must-not)    — versioned, governed. Promoting a learning to an
                                ENFORCED rule requires HUMAN review (the existing
                                enforced_with_override / Needs Attention path).
                                Advisory rules can float; hard constraints can't be self-granted.
```

Pipeline: **observe → learn (free) → propose skill/rule (gated).** Detailed mechanism below.

### 7.1 The `learning` entity (`LRN-`)

The raw observation layer is a distinct entity (DECISION) — *below* the curated skill/rule catalog, because a learning can be wrong/stale and accumulates evidence before it earns promotion (a flat "learnings are just advisory rules from birth" loses that distinction).

```
learning (LRN-):  area, tier {architect|developer}, category {gotcha|pattern|constraint|preference},
                  content (situation → guidance), status {active|stale|retired|promoted},
                  confidence (derived from evidence count/spread)
edges:  learning_derived_from    → Work Task / finding / Decision / test-failure   (the evidence)
        learning_contradicted_by → Work Task / observation                          (counter-evidence)
        learning_promoted_to     → skill / rule                                      (if promoted)
```

**Evidence is the spine of trust (DECISION — evidence is the promotion currency):** a learning seen *once* is a hunch; one confirmed across many Work Tasks is institutional knowledge. Confidence rises with confirming evidence and falls when contradicted — which is what **gates promotion** (no one-off → rule) and **triggers curation** (re-check the contradicted). Learnings are keyed by **(area, tier)** so design knowledge and implementation knowledge never blur.

### 7.2 The lifecycle: capture → accumulate → propose → promote

- **Capture** — at *every* Work Task close (a lightweight retro: "what did I learn?"), and also from §4.7 reconciliation findings and test failures. Free, append-mostly, evidence-tagged. Most tasks yield 0–2.
- **Accumulate** — a recurring observation links new evidence to the *existing* learning (confidence rises), not a duplicate.
- **Propose** — when a learning is well-evidenced (or judged important), the expert proposes promoting it: refine a **skill**, or add/change a **rule**.
- **Promote** — gated (§7.3); `learning_promoted_to` links it; status → `promoted`.

This is the engine of "smarter each release": findings + task experience → learnings → (promoted) skills/rules → next release's experts design with them baked in.

### 7.3 The promotion gate — graded by stakes, conservative-then-earned (DECISION)

A self-updating agent can entrench a wrong pattern or — worst — quietly **loosen a rule that blocked it** (reward-hacking its own governance). The gate **reuses the registry's hybrid governance** (no new safety system) and is graded; reusing the reconciliation #4 principle, it **starts conservative and is *earned*:**

```
Learning        → FREE always (an advisory observation; never blocks).
Skill (how-to)  → expert-proposed; versioned + float/pin as the safety net.
                  Human-reviewed EARLY; self-promotable once the expert earns trust.
Advisory rule   → expert-proposed; light human ack early; loosens with track record.
Enforced rule   → HUMAN REVIEW REQUIRED, ALWAYS — the permanent hard line. An agent must
                  never self-grant or self-loosen a blocking constraint (the Needs Attention path).
```

The elegant part: **the learning loop measures exactly the trust that loosens the gate** — a discipline with a long, clean track record of correct promotions (few contradicted learnings) is a demonstrated, *evidenced* candidate for more autonomy. The system earns its own slack.

### 7.4 Both tiers learn; only architects reconcile (DECISION)

Architects accumulate **design** knowledge (patterns, conflict-prone spots, shared-resource gotchas); developers accumulate **implementation** knowledge (how performant SQL actually behaves here, build/test idioms). Both write learnings (statelessly, at task close — so even an *ephemeral* developer learns, because the knowledge persists in the DB). Only architects *reconcile* — that's design.

### 7.5 Curation / decay — the part that usually kills these systems (DECISION)

Every learning system rots — the code changes and a learning becomes *wrong*; learnings pile up and contradict. Two mechanisms:
- **Per-release review (scheduled sweep):** at the start of each release's Design pass, each Architect runs a **"curate" Work Task** over its discipline's learnings — retire stale, promote well-evidenced, merge duplicates. Natural, because the expert is already loading its knowledge to design; tracked/auditable like the Reconcile task.
- **Triggered re-validation (reactive catch):** a learning is flagged when **contradicted** (new counter-evidence) or its **evidence-source changed** (the pattern it described got refactored).

**Honest about the hard part:** *automatically* detecting a stale learning is the genuinely difficult AI problem. The pragmatic answer is expert review + contradiction/source-change triggers + human spot-checks — plus that a learning relied on at design time and later found wrong becomes itself a high-value (meta-)learning. Without curation an expert gets **confidently wrong over time** instead of smarter.

### 7.6 How learnings reach the expert, and the loop closing

At contract-resolution (the registry resolver), the expert's contract includes its **active (area, tier) learnings** — "all active" early, a **retrieved relevant subset** at scale (another reason curation must keep the set small). The loop closes with reconciliation (§4.7): **finding → learning → rule → sharper next design.**

### 7.7 Substrate / registry impact (the biggest expansion to PI-122)

One new entity (`learning`, `LRN-`) + its edges; a **capture step** at Work-Task close; a **"curate" Work Task** per (release, area); the **promote workflow** reusing the existing skill/rule catalog + float/pin + `needs_attention` for the human gate. Everything else is existing machinery. See §9.

---

## 8. What changes vs. what stays (the boundary)

**STAYS (the built substrate — unchanged):**
- The data model: `Project → Planning Item → Workstream (delivery phase) → Work Task (single-area unit)`, the Planning Item lifecycle, the Workstream gate lifecycle + `needs_attention`.
- Areas + layer ranks; the decompose / scope / phase-overview / start-execution / complete-phase / dispatch / backlog endpoints.
- DB-backed statelessness (§4.4); append-mostly audit (§4.6); pull-based standing agents (§4.5); serial phases + verification gates (§5).

**CHANGES (all in the agent / registry layer):**
1. The generalist **Phase Specialist → per-area Design Experts (Architects)** + **Area Developers** (the (pass × area) matrix).
2. **Ephemeral per-task agents → standing, portfolio-aware, learning experts** (at least the design tier).
3. The **registry → a living, curated learning knowledge base** (catalog + experience store + write-back lifecycle + curation), not a config table.
4. A new **horizontal cross-PI coordination axis** (discipline experts) with **two-axis reconciliation**.
5. An explicit **Plan phase** and an explicit **Design-reconciliation gate**.
6. The **release-batched delivery model** as the default cadence.

---

## 9. Implications for the registry build (PI-122)

PI-122's scope expands materially. The Agent Profile Registry is now:
- the **profile catalog** (`agent_profile` / `skill` / `governance_rule`) — as already scoped; **plus**
- a **per-area learning / experience store** (a new entity) that grows;
- a **write-back lifecycle** (capture-learnings at Work-Task close → propose skill/rule updates → human-gated promotion);
- a **curation mechanism** (re-validate / retire learnings);
- the area experts modeled as **standing** agents (not spawned-per-task);
- the **cross-PI portfolio-review** capability (query + the Architect's reconciliation responsibility) and its **PM escalation** path.

PI-122's Architecture-phase specs (the `agent_profile`/`skill`/`governance_rule` schemas) should be authored **against this model**, not the v0.2 catalog-only framing. The v0.2 PRD's §10 open questions (broker scope, profile↔role coupling) now sit inside a larger picture.

---

## 9A. Registry scope — System vs. Engagement, and the unified-DB direction (DECIDED 06-01-26)

**The work is per-engagement; the *workforce* is system-level.** The governance entities (Project, PI, Workstream, Work Task, finding) are engagement-specific work and stay per-engagement. But the **agents are not** — a Database Architect's expertise is universal, and defining/managing one *inside every engagement* is wasteful duplication. So:

**DECISION (Doug, 06-01-26): the agent registry is a SYSTEM-level service with engagement overlays** — following the exact precedent that already exists for areas (`SYSTEM_AREA_RANKS` universal-in-code + `engagement_areas` per-engagement):

```
SYSTEM REGISTRY (shared across all engagements)
  the universal (area × tier) profiles + their SYSTEM skills / rules / learnings
ENGAGEMENT OVERLAY (per engagement)
  + engagement-specific skills / rules / learnings   (additions)
  + overrides / disables of specific system rules     (changes)        ← overlays do BOTH add and change
EFFECTIVE CONTRACT (what an agent runs with, in an engagement)
  = System  ∪  engagement additions  −  engagement-disabled  ⊕  engagement-overrides   (the resolver merges)
```

A "Database Architect" is defined **once** at the system level; in CRMBuilder it picks up CRMBuilder's overlay on top.

**The multiplier — cross-engagement learning (the real leverage).** A *system* Database Architect accumulates learnings across **every** engagement — a DBA with 50 projects of experience, not one. So the learning loop (§7) gains a **scope axis**: **system learnings** (universal → benefit all engagements) vs. **engagement learnings** (local). And a new promotion path: a learning seen *independently across multiple engagements* is evidence it's universal → **cross-engagement promotion** from engagement-scope to system-scope. This raises the stakes (a wrong *system* rule affects everyone), so promoting to a **system enforced rule** is the **top gate**: human review **plus** cross-engagement evidence. The §7.3 graded gate simply gains this second (scope) dimension.

### The unified multi-engagement DB (forward direction + constraint)

**DECISION direction (Doug, 06-01-26):** the current **per-engagement-DB** architecture (one `…/engagements/X.db` each, routed by a meta layer) is a **dev-stage convenience, not a production architecture** — an Alembic chain per engagement, no cross-engagement queries, multiplied ops/backup, no SaaS scale. A future migration moves to a **single multi-engagement DB with a row-level `engagement_id`** (standard multi-tenant).

**This is the *natural home* for the system/engagement registry — they're the same decision from two directions.** In the per-engagement-DB world the system registry is awkward (a separate physical store) and cross-engagement learning is near-impossible (querying across DB files). In a single DB it collapses to row scope:

```
system definition         →  registry row, engagement_id = NULL        (applies to all)
engagement overlay        →  registry row, engagement_id = X           (applies to X)
effective contract        →  one query:  system rows ∪ engagement-X rows
cross-engagement learning →  one query:  GROUP BY content across engagement_ids
```

Two consequences:
1. **Design the registry scope-aware *now*.** Every registry row (`agent_profile`/`skill`/`governance_rule`/`learning`) carries an explicit **scope discriminator** (`system` | an engagement). Build it scope-aware and the unified-DB migration needs **no registry rework** — it just collapses the stores into one. Build it scope-blind and you rewrite it.
2. **Sequencing flag (PI-122 dependency).** The registry's biggest payoff — cross-engagement learning — genuinely *needs* the unified DB to be practical. So the **unified-DB migration is a strong prerequisite/enabler for the registry build**, and probably wants to be **its own PI that PI-122 depends on** (rather than building the registry on the impractical foundation and migrating it).

---

## 9B. The standing-agent runtime (DECIDED 06-01-26)

**The runtime is the automation of the orchestration loop already demonstrated by hand.** In the 06-01-26 session Claude Code *was* the runtime: it dispatched PI-122 (PM), decomposed it, spawned six phase-specialist sub-agents to scope it, drove the gates (`start-execution`/`complete-phase`), spawned a worktree build agent, and integrated its commit. The runtime makes that loop run itself, **driven by governance-DB state, with the registry supplying contracts** instead of hand-written prompts.

**No agent is a perpetual process (the key simplification, DECISION #1).** Because of DB-backed statelessness (v0.3 §4.4), *every* agent — Architect, Developer, Tester, PM, Lead — is **spawned on demand and ephemeral**: it reads its state/queue/learnings from the DB, does its unit, writes back, exits. So **"standing" is a *contract scope*, not a process lifetime** — the difference between a standing Architect and a per-task Developer is that the Architect's resolved contract grants **portfolio-wide queue access + reconciliation + learning-curation** while the Developer's grants **one Work Task**; both spawn fresh each time. The Architect's standing-ness lives in its persistent identity + queue + accumulated knowledge *in the DB*, not a daemon. This dissolves the "standing vs. per-task spawn" tension and means **no long-running agent processes to manage.**

**Runtime = deterministic scheduler + invoked judgment-agents (DECISION #2).**

```
SCHEDULER (control loop, driven by governance-DB state)
  finds ready work → resolves the (area,tier) contract from the registry (system + engagement overlay)
                   → spawns ONE agent to do it, honoring blocked_by + a concurrency cap
                   → (file-editing/build agents) in a FRESH worktree from current main HEAD
  drives the lifecycle: eligible PI → invoke PM; phase ready → invoke Architect;
                        tasks done → invoke Lead to verify+advance; gate clean → open it
REGISTRY  resolves the contract (prompt + tools + ruleset + learnings + version)   ← the registry↔runtime §12 seam
AGENT     a Claude Code session / Anthropic-SDK loop launched with that contract + the substrate tools;
          does its one unit, writes records/learnings back, exits.
```

The scheduler is deterministic (find-work, dispatch, honor dependencies, cap concurrency); the *judgment* lives in the agents it invokes. The **registry resolves; the scheduler injects** (the §12 seam). The build-agent **worktree-from-current-main-HEAD** rule (surfaced by the Area Specialist proof) is the scheduler's responsibility.

**Integration of parallel builds (DECISION #3).** Post-design-gate, N build agents run in parallel, each in its own worktree-from-HEAD → N branches the runtime **merges**. Per the thesis these merge *cleanly* because reconciliation already proved the specs don't conflict — and a merge conflict that *does* occur is **a finding reconciliation missed → it becomes a learning** that sharpens the next reconciliation. (This session that integration was done by hand — cherry-picking the worktree agent's commit.)

**Human-in-the-loop at the gated points (DECISION #4) — the autonomy boundary.** The runtime is **not fully autonomous**: it **pauses for a human** exactly where we've gated — promoting to an *enforced* rule (§7.3), a cross-PI *blocking* conflict the PM can't auto-resolve (§4.4 of this doc / §5), a design-contradiction escalation. These are the `needs_attention` stops. Crucially, the **conservative-then-earned** trust governs *how often* it pauses: early it stops a lot; as the experts accumulate a clean track record, it stops less. **The runtime's autonomy grows with the learning loop** — the system earns its own slack, with evidence.

---

## 10. Open decisions to detail next (each → a future governance Decision)

**Status as of 06-01-26: the DESIGN is COMPLETE.** All design decisions (items **1–7**) are ✅ DECIDED — see §4 (reconciliation), §3.1 (taxonomy), §7 (learning), §6 (release), §1 (four passes), §9A (registry scope + unified-DB), §9B (runtime). What remains is **execution planning, not design**:

> **▶ NEXT — ✅ ALL DONE (06-01-26):**
> - **Govern the decisions** — ✅ recorded as **DEC-367…373** via **SES-149** / CNV-051 (close-out applied DEP-144), and **folded the expanded scope into the registry PRD (→ v0.3, new §13/§14) + PI-122** (description PATCHed to the four-entity, scope-aware, learning-capable scope).
> - **Item 8 — scope the unified multi-engagement-DB migration** — ✅ scoped as **PI-123** (Draft) under a **new Production Architecture project (PRJ-019)**, with **PI-122 `blocked_by` PI-123**; project-home choice recorded as **DEC-374** via **SES-150** / CNV-052 (DEP-145). (Per §9A it belongs to a production-architecture Project, not the ADO Project — PRJ-019 is that project.)
> - **Sequence the build** — recorded in registry PRD §14. Order: **PI-123** (unified-DB migration) → **PI-122** (registry, scope-aware + learning-capable) → wire the runtime scheduler → then the ADO runs its own subsequent PIs. PI-122 is built scope-aware regardless, so it works on either foundation.
>
> With the above applied, this document is **fully governed and execution-planned**; the next move is building PI-123, then PI-122.

1. **Reconciliation mechanism** — ✅ **DETAILED (06-01-26), see §4.** Settled: Reconcile-as-Work-Task; `finding` entity (`FND-`); detect-vs-resolve with a `complete-phase` blocking-findings precondition; Lead-resolves-vertical / Architect-detects-PM-arbitrates-horizontal; efficiencies flag-and-propose; conservative-then-earned automation; findings feed learning. **One residual dependency:** the *horizontal* Reconcile task's structural home is (release, area) → waits on the **Release entity** (item 4).
2. **Expert taxonomy** — ✅ **DETAILED & fully settled (06-01-26), see §3.1** (disciplines = the area vocab; profiles per (area × tier); build areas get **Architect/Developer/Tester** [three tiers — decided], design/methodology areas Architect-only; sub-disciplines via Engagement areas; layer-rank refinement for rank-less areas; Tester is a spec-driven test-implementer, three-tier model staffed incrementally).
3. **Learning store + loop** — ✅ **DETAILED (06-01-26), see §7.** Settled: a distinct `learning` entity (`LRN-`, keyed by area+tier) below the curated skill/rule catalog; **evidence is the promotion currency** (no one-off → rule); capture→accumulate→propose→promote lifecycle (capture at every Work-Task close + from findings/test-failures); a **graded, conservative-then-earned gate** (learnings free; skills/advisory-rules earn self-promotion; **enforced rules always human**); **both tiers learn** (tier-scoped), only architects reconcile; **curation = a per-release "curate" Work Task + triggered re-validation**; the resolver injects active (area,tier) learnings into the expert's contract.
4. **Release model mechanics** — ✅ **DETAILED (06-01-26), see §6 + the thesis.** DECIDED in full: the **coarse / all-or-nothing design gate** (no build until all reconciliation is complete and clean) and **hard-sync-at-Design / flow-after**; **Release as a new entity (`REL-`) orthogonal to Project** (two memberships; cross-Project batches allowed); the `Open→Design→Develop→Test→Shipped` lifecycle with explicit intake-close + defer-to-next-release; the horizontal-reconcile home via **generalized Workstream parentage (PI *or* Release)**; the PM's release-management layer + release-scoped dispatch.
5. **Phases-vs-cross-cutting** — ✅ **DECIDED (06-01-26), see §1.** Exactly **four core passes** (Plan/Design/Develop/Test); Plan = area-determination (no Work Tasks of its own); the original Documentation/Data Migration/Deployment **dissolve** — Data Migration = a storage Design-checkpoint + Develop/storage work; Documentation = woven (Design docs + Develop DoD + release-finalization); Deployment = the Release *Shipped* stage + infra/espo/automation build. Forced-consideration via checkpoints. **Substrate consequence:** phase vocab 6 → 3 phase-types + Plan-as-decompose (a migration, part of building the evolution).
6. **Standing-agent runtime** — ✅ **DECIDED (06-01-26), see §9B.** No perpetual agents — all spawn-on-demand; "standing" = contract scope, not process lifetime. Runtime = deterministic scheduler (find-work → resolve contract → spawn one agent, honor blocked_by + concurrency + worktree-from-HEAD → drive the lifecycle) + invoked judgment-agents; registry resolves, scheduler injects. Parallel build branches merged (clean if reconciled; a conflict → a finding/learning). Human-in-the-loop at the gated points (`needs_attention`), with autonomy that grows as the learning loop earns trust.
7. **Registry scope (System vs. Engagement) + unified-DB direction** — ✅ **DECIDED (06-01-26), see §9A.** The registry is a system-level service with engagement overlays (add + override/disable); learnings gain a system/engagement scope axis with cross-engagement promotion; the registry is designed **scope-aware** (a `system | engagement` discriminator on every row) so the future unified multi-engagement DB needs no rework.
8. **Unified multi-engagement-DB migration** — ✅ **SCOPED (06-01-26) as PI-123** (Draft) under the **new Production Architecture project PRJ-019**, with **PI-122 `blocked_by` PI-123** and the project-home choice recorded as **DEC-374** (SES-150). Replaces the per-engagement-DB-files architecture with a single multi-tenant DB (`engagement_id` rows): production-readiness *and* the practical enabler of cross-engagement learning. Awaits decomposition + build.

---

## Provenance

This document captures a design conversation between Doug Bower and Claude (Claude Code), 06-01-26, that followed the landing of the ADO substrate (PI-114 / WTK-001…006) and the first end-to-end ADO planning run (PI-122 / SES-148). It is an **overview to anchor future work**; the decisions above are to be deepened and governed individually. Nothing here is built.
