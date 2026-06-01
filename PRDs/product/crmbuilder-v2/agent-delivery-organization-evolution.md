# Agent Delivery Organization — Evolution: Matrix Org, Expert Agents, and the Learning Registry

**Document type:** Design evolution / direction note (the next iteration of the ADO's *agent layer*).
**Status:** v0.1 — DRAFT. Captures a design conversation (06-01-26). Nothing here is built. This is the **overview + rationale**; each decision below is to be detailed (and recorded as governance Decisions) in follow-up passes.
**Relationship to other docs:**
- Baseline: `agent-delivery-organization-design.md` (v0.3) — the locked ADO model, whose **substrate is built** (PI-114 / WTK-001…006). This document **evolves the agent layer that sits on that substrate**; it does **not** change the data-model substrate.
- Forward: `agent-profile-registry/agent-profile-registry-PRD-v0.1.md` (v0.2, scoped as **PI-122**) — the registry that holds the agent prompts/skills/rules. This conversation **significantly expands what that registry must be** (see §9). It is fortunate PI-122 is not yet built.
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

## 1. The shape: a matrix organization (passes × areas)

The ADO is reframed as a **matrix**:

- **Vertical axis — areas (disciplines):** Data, API, Web UI, Mobile UI, Desktop UI, … — keyed to the existing `vocab.SYSTEM_AREA_RANKS` plus per-engagement Engagement areas. Each area is a *discipline* with genuinely different expertise (designing a schema ≠ writing optimized SQL; Web ≠ Mobile ≠ Desktop), so each gets its own skills and its own governing rules.
- **Horizontal axis — passes:** **Plan → Design → Develop → Test** (plus cross-cutting Documentation / Data Migration / Deployment). These map onto the existing canonical "phases" — *phases **are** passes*.

The unit of work is a **(pass × area) cell**, each performed by a **distinct expert** (e.g. *Data Architect* in the Design pass for the Data area; *Data Developer* in the Develop pass). You instantiate **only the cells a PI/release actually touches** — the matrix is sparse.

### The four core phases (passes)

- **Plan** — read the PI(s) and lay out the work **by area**: determine which disciplines are touched and create the structure. (This is the area-decomposition step, given its own phase rather than smuggled into the Architecture Specialist.)
- **Design** — the area **Architects** each produce a **precise, testable development spec** for their area (it defines *what to develop* **and** *how it will be tested*).
- **Develop** — the area **Developers** execute the reconciled specs into code.
- **Test** — the test definitions from Design are executed (by Test Developers / per-area testers).

Documentation, Data Migration, and Deployment remain as cross-cutting passes layered on, often sparse.

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

---

## 7. Learning / Experience agents — the registry becomes the organization's **memory**

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

Pipeline: **observe → learn (free) → propose skill/rule (gated).**

### The danger, and the resolution

A self-updating agent can (a) learn a *wrong* pattern and entrench it, (b) accumulate contradictory learnings, or (c) — worst — quietly **loosen a rule that blocked it** (reward-hacking its own governance). The resolution **reuses the registry's existing hybrid governance** rather than inventing a new safety system: the agent **proposes**; a **human gates** the high-stakes promotions (enforced-rule changes), exactly via the `enforced_with_override` → Needs Attention path. Learnings remain advisory/append-mostly/auditable.

### The hard part: curation / decay

Every learning system rots — the codebase changes and a learning becomes *wrong*; learnings pile up and contradict. So **curation is mandatory**: learnings must be **re-validated and retired**, not merely accumulated. The stewardship skill therefore includes "*before relying on a learning, check it's still true; flag stale ones.*" Without this, an expert gets **confidently wrong over time** instead of smarter. **This is where such systems usually fail and is the part to design most carefully.**

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

## 10. Open decisions to detail next (each → a future governance Decision)

These were surfaced but not fully settled; detail them before/while building:

1. **Reconciliation mechanism** — ✅ **DETAILED (06-01-26), see §4.** Settled: Reconcile-as-Work-Task; `finding` entity (`FND-`); detect-vs-resolve with a `complete-phase` blocking-findings precondition; Lead-resolves-vertical / Architect-detects-PM-arbitrates-horizontal; efficiencies flag-and-propose; conservative-then-earned automation; findings feed learning. **One residual dependency:** the *horizontal* Reconcile task's structural home is (release, area) → waits on the **Release entity** (item 4).
2. **Expert taxonomy** — which disciplines/areas are first-class; how UI sub-areas (Web / Mobile / Desktop) map onto the area vocab (`SYSTEM_AREA_RANKS` vs. Engagement areas); architect-vs-developer profile pairs per area.
3. **Learning store + loop** — the experience entity schema; the capture/propose/promote lifecycle; the human-gate boundary (proposed default: human review required to promote to an *enforced* rule); whether developers learn implementation knowledge; **curation cadence** (per-release review vs. continuous).
4. **Release model mechanics** — how a release batches PIs; how the PM sequences a release; the relationship between a "Release" and the Project/PI entities (is a Release a new entity, or a Project-level grouping?).
5. **Phases-vs-cross-cutting** — confirm the four core passes (Plan/Design/Develop/Test) and where Documentation / Data Migration / Deployment attach.
6. **Standing-agent runtime** — how standing experts are hosted/woken (pull-based), distinct from the per-task spawn; ties to the registry↔runtime seam (registry PRD §12) and the worktree-from-HEAD requirement.

---

## Provenance

This document captures a design conversation between Doug Bower and Claude (Claude Code), 06-01-26, that followed the landing of the ADO substrate (PI-114 / WTK-001…006) and the first end-to-end ADO planning run (PI-122 / SES-148). It is an **overview to anchor future work**; the decisions above are to be deepened and governed individually. Nothing here is built.
