# Agent Delivery Organization — Design

**Document type:** Application development design (the agent organization that delivers Planning Items)
**Proposed path:** `PRDs/product/crmbuilder-v2/agent-delivery-organization-design.md`
**Status:** v0.3 — renamed to Agent Delivery Organization; all §9 forks resolved; lockable.
**Last Updated:** 05-31-26

---

## Status

This document specifies the **Agent Delivery Organization** (ADO) that DEC-343 adopted
as the target and that PI-112 deliberately scoped *out* ("a separate downstream
build, specified once the data model is locked"). The data model is now locked
(PI-112, Alembic head `0033`): `Project → Planning Item → Workstream (delivery
phase) → Work Task (single-area unit)`, with the six-state Planning Item
lifecycle and the Workstream/Work Task entities. This is the **behavior layer**
that *populates and drives* those entities. It is a design document; nothing
here is built yet.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 05-31-26 | Doug Bower / Claude | Initial draft. Three-tier model, always-all-phases, scope-as-Work-Tasks, the Project Manager lifecycle, Needs Attention, DB-backed statelessness. §9 open. |
| 0.3 | 05-31-26 | Doug Bower / Claude | Renamed *Agent-Delivery Runtime* → **Agent Delivery Organization** (ADO) — "runtime" was jargon; this is an organization of role-specialized agents that delivers Planning Items. No model changes. |
| 0.2 | 05-31-26 | Doug Bower / Claude | Resolved all eight §9 forks. Renamed the Architecture phase; split orchestration into a **Project Manager** (project) + **PI Lead** (per-PI) — now four tiers; made **Needs Attention** an orthogonal flag rolled up to the PI; added the **Not Applicable** terminal Workstream status for recorded no-work; expanded the Workstream lifecycle to `Planned → Scoping → Ready → In Progress → Complete | Not Applicable | Blocked`; fixed concurrency (serial phases, parallel PIs and parallel Work Tasks); defined replanning (additive-automatic, contradictory-escalates). |

## Change Log

**Version 0.2 (05-31-26):** Folded the resolved §9 decisions into the model.
The biggest is #4: a **Project Manager** owns a Project's PI backlog and
sequencing and spawns a **PI Lead** per ready PI; the Lead runs that one PI's
plan→gate→execute lifecycle. This adds a tier and is what enables parallel PIs.

---

## 1. The shift, in one picture

**Today (session-driven):** a human opens a session against a Work Ticket and
executes a whole Planning Item end-to-end in one conversation. Scope, plan, and
execution all happen implicitly inside one agent's head. This is how every v2
PI — including PI-112 itself — has been delivered. The Workstream/Work Task
tables are empty because nothing decomposes work into them.

**Target (this document):** work is **pulled** by a standing organization of
specialized agents. A **Project Manager** owns a Project, sequences its Planning
Items, and spawns a **PI Lead** for each ready PI. The Lead drives that PI
through an explicit **plan → gate → execute** lifecycle. Scope is determined by
**phase specialists** who are experts at their phase, and work is executed by
**area specialists**. Every step is a governance record, so the state of all
work is queryable, auditable, and restartable.

The point is to move judgment to where the expertise is, make scope an explicit
recorded artifact (Work Tasks), and make the whole pipeline resumable.

---

## 2. The agent tiers (four)

| Tier | Agent | Scope | Job | Produces |
|------|-------|-------|-----|----------|
| 1 | **Project Manager** | one **Project** | Own the Project's PI backlog; sequence PIs by `blocked_by`; prioritize; spawn a PI Lead per ready PI; handle cross-PI concerns | PI ordering; Leads dispatched |
| 2 | **PI Lead** | one **Planning Item** | Run this PI's lifecycle: planning loop → gate → execution loop; verify phase outcomes; replan or escalate (§3.2–3.4) | a delivered, `Resolved` PI |
| 3 | **Phase Specialist** | one **Workstream** (delivery phase) | Evaluate the PI's requirements *through this phase's lens*; **determine and document scope = create the Work Tasks** (possibly zero) | Work Tasks, or a recorded `Not Applicable` |
| 4 | **Area Specialist** | one **Work Task** (single area) | Do the single-area work | code / docs / tests / the deliverable |

The separations are deliberate. Tier 1 vs 2 = **project-level orchestration**
(which PI next, in what order) vs **per-PI orchestration** (drive one PI to
done); splitting them bounds each agent's context and is what lets independent
PIs run in parallel under different Leads. Tier 3 vs 4 = **who decides what to
do** vs **who does it**.

### 2.1 The phase specialists (one per phase)

Every PI gets the **full set** of phase Workstreams (§4.1). Each has a
specialist that is an expert at scoping *its* phase. The canonical, always-
created set (§8) is:

- **Architecture** — evaluates whether the PI requires new/changed **entities,
  processes, requirements, personas** (the methodology layer) and the system
  architecture. Its Work Tasks are literally "add entity X", "modify process Y".
  **It runs first and its findings feed every downstream phase.** A frequent,
  valid outcome is `Not Applicable` ("no entity/process changes → no work").
- **Development** — scopes code changes by area (`storage`, `access`, `api`,
  `mcp`, `ui`, `espo`, `automation`, …), one Work Task per area, sequenced by
  layer rank (storage → access → api → ui).
- **Testing** — scopes test work against what Development will change.
- **Documentation** — scopes doc / methodology-artifact updates.
- **Data Migration** — scopes Alembic / data-rewrite work (often `Not Applicable`).
- **Deployment** — scopes release / deploy / verification work.

A phase specialist's **deliverable is the Work Task set**, not prose. Determining
scope *is* creating Work Tasks.

---

## 3. The lifecycle

### 3.1 Project level — the Project Manager
The PM watches its Project's Planning Items and their `blocked_by` edges. A PI is
eligible to start when its upstream dependencies are satisfied. The PM orders
eligible PIs by priority and **spawns a PI Lead** for each one it starts.
Independent PIs (no `blocked_by` between them) may run concurrently under
separate Leads (§5). The PM does no per-PI planning itself — it dispatches.

### 3.2 Per-PI planning loop (the Lead — sequential, feed-forward)
1. Create all phase Workstreams for the PI (structural; §4.1).
2. Assign the **Architecture** specialist → it scopes (creates Work Tasks, or
   records `Not Applicable`) → reports back.
3. Feed Architecture's results to **Development** → it scopes *against that* →
   reports.
4. Continue Testing → Documentation → Data Migration → Deployment, each scoping
   on the **accumulated output of the prior phases**.
5. When every phase is `Ready` or `Not Applicable`, proceed to the gate.

### 3.3 The gate (the Lead)
- **All phases scoped cleanly →** initiate execution (§3.4).
- **Planning surfaced a problem the Lead can't resolve →** raise **Needs
  Attention** (§5) on the offending Workstream (rolled up to the PI) and stop for
  a human.

### 3.4 Per-PI execution loop (the Lead — with verification gates)
For each phase in order (skipping `Not Applicable` phases):
1. Execute its Work Tasks — area specialists claim and do them. Work Tasks within
   the phase run in parallel where their areas / layer ranks allow (§5).
2. The Lead **verifies the phase outcome**.
3. Then one of:
   - **advance** to the next phase, or
   - **adjust the plan** — *additively* (§6): add Work Tasks to the current or
     downstream phases, recorded as new `WTK-` records with a reason, or
   - **Needs Attention** — when the outcome contradicts a prior recorded
     (especially Architecture) decision, or can't be resolved automatically.
When the last phase verifies, the Lead drives the PI to `Resolved` via the normal
close-out / `resolves` edge, and reports completion to the PM.

### 3.5 Two ways a Work Task gets executed — pulled vs scheduled
A Work Task is run by a **session** (the area-specialist sitting), linked to it by
a **`session_works_work_task`** edge. Two paths to that session:

- **Pulled (autonomous end-state):** a standing area-specialist agent watches for a
  `Ready` Work Task and pulls it — claims it, opens its session, executes. No one
  pre-creates the session; dispatch is emergent (§4.5).
- **Scheduled (human-initiated / bootstrap):** a session is **pre-created in
  `planned` status** (sessions are schedulable per PI-073/DEC-314, optionally with
  `session_scheduled_for`) and wired to the Work Task via `session_works_work_task`,
  carrying the execution kickoff in its description. This is the governed handoff
  for human-driven work and for bootstrapping the ADO itself; the V2 desktop UI's
  scheduling surface is for exactly this.

Both produce the same shape. Note: a *scheduled* (not-yet-run) session still
requires a `session_executive_summary` (NOT NULL) — supply a forward-looking
summary, updated to actuals at close (a relaxation for `planned` sessions is a
possible follow-on).

---

## 4. Principles

### 4.1 Always create all phases; specialists determine scope
The structural step creates **every** phase Workstream for **every** PI — no
generalist decides which phases "matter." Scope judgment belongs to the phase
specialist, the only agent with the expertise to make it. A phase with no work is
the **expert's recorded conclusion** (`Not Applicable`), not a generalist's
omission.

### 4.2 Scope determination = Work Task creation
A phase is scoped when its specialist has produced its Work Tasks. There is no
separate scoping artifact; the Work Tasks *are* the scope.

### 4.3 An empty phase is a positive assertion (`Not Applicable`)
A Workstream the specialist evaluates as having no work reaches the terminal
status **`Not Applicable`** — distinct from `Complete` (work was done and
verified). "Evaluated, nothing to do" is first-class and queryable, mirroring the
deploy engine's deliberate `NO_WORK` ≠ `SKIPPED`.

### 4.4 DB-backed statelessness (restartable)
No agent holds lifecycle state in its head. The PM and Leads reconstruct "where
are we" entirely from the records (which Workstream is `Scoping` vs `In Progress`,
which Work Tasks are `Complete`) and write status back. Any agent can die and
another picks up exactly where the DB says things stand — what makes the
pull-based design resumable.

### 4.5 Pull-based, not pushed
Standing agents watch the governance DB for work in the state they handle (a PI
reaching `Ready`, a Work Task reaching `Ready`) and pull it. Dispatch is emergent
from the records, not a central scheduler.

### 4.6 The audit trail is append-mostly
Completed Work Tasks are never silently rewritten (§6) — they are the record of
what was done. Re-scoping adds new records; contradicting a prior expert decision
escalates to a human rather than overwriting it.

---

## 5. State-model additions

The PI-112 lifecycle vocabulary needs these additions (to be implemented when the
organization is built):

- **Workstream lifecycle (expanded).** From `Planned/In Progress/Complete/Blocked`
  to: **`Planned`** (created, awaiting scoping) → **`Scoping`** (specialist
  evaluating) → **`Ready`** (Work Tasks created, awaiting execution) →
  **`In Progress`** (executing) → **`Complete` | `Not Applicable` | `Blocked`**.
  This mirrors the Work Task's own `Ready/Claimed/In Progress` and gives the Lead
  unambiguous gate signals.
- **Needs Attention (a flag, not a status).** `needs_attention` (bool) +
  `needs_attention_reason` (text) on the **Workstream** (so you know *which phase*
  is stuck), **rolled up to the Planning Item** for "which PIs need a human?"
  queries. It is a flag rather than a status because attention can be needed at
  *any* lifecycle point — a status would erase the underlying progress state. Set
  by the Lead/PM; cleared by a human after resolving, and the lifecycle resumes
  from where it was. This is the most trust-critical signal in the system.
- **Architecture phase.** Rename the Workstream phase-type vocab value `Design`
  (DEC-349) to **`Architecture`**.

> **Implemented (WTK-001, migration `0036`, 05-31-26).** All three additions
> landed as vocab + model + Alembic migration + tests: `WORKSTREAM_PHASE_TYPES`
> renamed `Design → Architecture`; `WORKSTREAM_STATUSES` /
> `WORKSTREAM_STATUS_TRANSITIONS` expanded to the gate model above
> (`Planned → {Scoping, Blocked}`, `Scoping → {Ready, Not Applicable, Blocked}`,
> `Ready → {In Progress, Blocked}`, `In Progress → {Complete, Blocked}`,
> `Blocked → {Planned, Scoping, Ready, In Progress}`, `Complete`/`Not Applicable`
> terminal); and `workstream_needs_attention` (bool) +
> `workstream_needs_attention_reason` (text) added to the model with
> create/update/patch support. Only `In Progress`/`Complete` carry dedicated
> lifecycle timestamps; the intermediate `Scoping`/`Ready` and terminal
> `Not Applicable` do not. The **Needs Attention → Planning Item rollup is
> derived** (a query over `needs_attention` Workstreams), not a stored PI column
> (DEC-361) — lighter and avoids denormalization, per the §5 recommendation.

---

## 6. Replanning rules

Mid-execution, the Lead may **adjust the plan** under two rules:

- **Additive is automatic.** Adding Work Tasks to the current or downstream
  (not-yet-executed) phases is allowed without escalation — recorded as new
  `WTK-` records carrying a reason that links to the triggering outcome.
- **Contradictory escalates.** A re-scope that would invalidate a *completed*
  Work Task, or that contradicts a recorded **Architecture** decision, does **not**
  get applied unilaterally — it sets **Needs Attention** and pulls in a human.

So the plan is append-mostly and self-extending for foreseeable elaboration, but
significant deviations are gated on human judgment.

---

## 7. Relationship to the data model (PI-112) and DEC-343

- **Reused as-is:** the `Project → PI → Workstream → Work Task` containment chain
  and its `belongs_to` edges; `blocked_by` between sibling PIs / Workstreams /
  Work Tasks; the Work Task single-area constraint and `claimed_by`/`claimed_at`;
  the Workstream `phase_type` vocabulary; the area layer ranks for ordering.
- **Refines DEC-343:** the four tiers extend DEC-343's three (general-purpose →
  discipline-manager → area-specialist) by splitting the general-purpose role into
  a **Project Manager** (project) and a **PI Lead** (per-PI); the
  discipline-manager becomes the **phase specialist** whose job is
  *scope-and-decompose*, not just oversight.
- **New (this document):** the PM/Lead lifecycle, always-all-phases, scope-as-Work-
  Tasks, the `Not Applicable` status, the Needs Attention flag, the expanded
  Workstream lifecycle, and DB-backed statelessness.

---

## 8. The bootstrap problem

This system cannot govern its **own** construction — there is no Project Manager
yet to decompose "build the Agent Delivery Organization." So the organization is built the
old session-driven way, under a Planning Item with hand-authored Workstreams and
Work Tasks, and **once it exists it governs every PI after it.** The deferred
"Workstream/Work Task UI panels" PI is a good candidate for the **first PI the
finished organization decomposes** end-to-end.

---

## 9. Resolved decisions (was §9 open forks; resolved v0.2)

1. **Phase naming** — *resolved:* rename `Design` → **`Architecture`** (precise to
   the phase's job; "Design" drifts toward UI mockups).
2. **Needs Attention placement** — *resolved:* an **orthogonal flag** + reason on
   the Workstream, rolled up to the PI; not a status (keeps it independent of
   lifecycle progress). Cleared by a human.
3. **No-work representation** — *resolved:* a distinct terminal Workstream status
   **`Not Applicable`** (≠ `Complete`), for an auditable "evaluated, nothing to do."
4. **Project Manager unit** — *resolved:* **two levels — Project Manager + per-PI
   Lead.** PM owns backlog/sequencing/priority and dispatches Leads; the Lead runs
   one PI's lifecycle. Adds a tier; enables parallel PIs.
5. **Execution concurrency** — *resolved:* **serial phases** within a PI (verify
   gate between each, via `blocked_by` between Workstreams), **parallel PIs**
   (separate Leads), and **parallel Work Tasks** within a phase (by area/layer rank).
6. **Replanning scope** — *resolved:* **additive automatic, contradictory
   escalates** (§6); never silently rewrite a completed Work Task.
7. **Workstream lifecycle** — *resolved:* expand to `Planned → Scoping → Ready →
   In Progress → Complete | Not Applicable | Blocked` + the `needs_attention` flag
   overlay (§5).
8. **Phase set** — *resolved:* `{Architecture, Development, Testing, Documentation,
   Data Migration, Deployment}` is canonical and always-created; extensible later
   via the DEC-006 vocab gate.

---

## 10. Out of scope (for this document)

- The concrete agent prompts / skill definitions for each specialist (follow-on,
  once the model is locked).
- The retirement of the shelved WS-012 orchestrator (target-model §9 step 6) —
  this organization supersedes it.
- An "agent profile" registry (skill definitions per phase/area) — deferred.
