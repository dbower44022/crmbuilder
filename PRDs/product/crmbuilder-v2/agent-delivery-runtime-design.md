# Agent-Delivery Runtime — Design

**Document type:** Application development design (the runtime that consumes the PI-112 data model)
**Proposed path:** `PRDs/product/crmbuilder-v2/agent-delivery-runtime-design.md`
**Status:** v0.1 DRAFT — for review. Iterating; not yet locked, not yet built.
**Last Updated:** 05-31-26

---

## Status

This document specifies the **runtime agent organization** that DEC-343 adopted
as the target and that PI-112 deliberately scoped *out* ("a separate downstream
build, specified once the data model is locked"). The data model is now locked
(PI-112, Alembic head `0033`): `Project → Planning Item → Workstream (delivery
phase) → Work Task (single-area unit)`, with the six-state Planning Item
lifecycle and the Workstream/Work Task entities. This is the **behavior layer**
that *populates and drives* those entities. It is a design document; nothing
here is built yet.

Provisional calls are marked **(proposed)**. Genuine forks are collected in §9.

---

## Revision Control

| Version | Date | Author | Summary |
|---------|------|--------|---------|
| 0.1 | 05-31-26 | Doug Bower / Claude | Initial draft from the design conversation following the PI-112 close-out and the `planning_item_belongs_to_project` fix. Captures the three-tier model (Project Manager / Phase Specialist / Area Specialist), the always-all-phases principle, scope-determination-as-Work-Task-creation, the Project Manager lifecycle (PI sequencing → per-PI planning loop → gate → execution loop with verification), the Needs Attention state, and DB-backed statelessness. |

---

## 1. The shift, in one picture

**Today (session-driven):** a human opens a session against a Work Ticket and
executes a whole Planning Item end-to-end in one conversation. Scope, plan, and
execution all happen implicitly inside one agent's head. This is how every v2
PI — including PI-112 itself — has been delivered. The Workstream/Work Task
tables are empty because nothing decomposes work into them.

**Target (this document):** work is **pulled** by a standing organization of
specialized agents. A **Project Manager** owns a Project, sequences its Planning
Items, and drives each one through an explicit **plan → gate → execute** lifecycle.
Scope is determined by **phase specialists** who are experts at their phase, and
work is executed by **area specialists**. Every step is a governance record, so
the state of all work is queryable, auditable, and restartable.

The point is to move judgment to where the expertise is, make scope an explicit
recorded artifact (Work Tasks), and make the whole pipeline resumable.

---

## 2. The agent tiers

| Tier | Agent | Scope | Job | Produces |
|------|-------|-------|-----|----------|
| 1 | **Project Manager** | one **Project** | Own all the Project's Planning Items; sequence them (`blocked_by`); drive each through its lifecycle; verify outcomes; escalate | status transitions; orchestration |
| 2 | **Phase Specialist** | one **Workstream** (delivery phase) of a PI | Evaluate the PI's requirements *through this phase's lens*; **determine and document the scope = create the Work Tasks** (possibly zero) | Work Tasks (or a recorded no-work outcome) |
| 3 | **Area Specialist** | one **Work Task** (single area) | Do the single-area work | code / docs / tests / the deliverable |

The separation is deliberate: **who decides what to do** (phase specialist),
**who does it** (area specialist), and **who runs the show and checks the work**
(Project Manager) are three different competencies and three different agents.

### 2.1 The phase specialists (one per phase)

Every PI gets the **full set** of phase Workstreams (see §4.1). Each has a
specialist that is an expert at scoping *its* phase:

- **Architecture/Design** *(naming: §9)* — evaluates whether the PI requires
  new/changed **entities, processes, requirements, personas** (the methodology
  layer) and the system architecture. Its Work Tasks are literally "add entity
  X", "modify process Y". **It runs first and its findings feed every downstream
  phase.** A frequent, valid outcome is "no entity/process changes → no work."
- **Development** — scopes the code changes by area (`storage`, `access`, `api`,
  `mcp`, `ui`, `espo`, `automation`, …), one Work Task per area, sequenced by
  layer rank (storage → access → api → ui).
- **Testing** — scopes test work against what Development will change.
- **Documentation** — scopes doc/methodology-artifact updates.
- **Data Migration** — scopes Alembic / data-rewrite work (often no-work).
- **Deployment** — scopes release / deploy / verification work.

A phase specialist's **deliverable is the Work Task set**, not prose. Determining
scope *is* creating Work Tasks.

---

## 3. The Project Manager lifecycle

The Project Manager is the stateful orchestrator. It operates at the Project
level and, for each Planning Item, runs two loops with a gate between them.

### 3.1 Planning Item sequencing (Project level)
The PM watches its Project's Planning Items and their `blocked_by` edges. A PI
is eligible to start planning when its upstream dependencies are satisfied. The
PM sequences PIs accordingly (and may run independent PIs concurrently — §9).

### 3.2 Planning loop (per PI, sequential, feed-forward)
1. Create all phase Workstreams for the PI (structural; §4.1).
2. Assign the **Architecture** phase specialist → it plans (scopes → Work Tasks)
   → reports results back.
3. Feed Architecture's results to the **Development** specialist → it plans
   *against that* → reports.
4. Continue Testing → Documentation → Data Migration → Deployment, each planning
   on the **accumulated output of the prior phases**.
5. When **every** phase is Planned, proceed to the gate.

### 3.3 The gate
- **All phases planned cleanly →** initiate execution (§3.4).
- **Planning surfaced a problem the PM can't resolve →** set **Needs Attention**
  (§5) and stop for a human.

### 3.4 Execution loop (per PI, with verification gates)
For each phase in order:
1. Execute its Work Tasks (area specialists claim and do them).
2. The Project Manager **verifies the phase outcome**.
3. Then one of:
   - **advance** to the next phase, or
   - **adjust the plan** (re-scope / add / modify Work Tasks) when the outcome
     demands it, or
   - **Needs Attention** when it can't be resolved automatically.
When the last phase verifies, the PI is driven to `Resolved` (via the normal
close-out / `resolves` edge).

---

## 4. Principles

### 4.1 Always create all phases; specialists determine scope
The structural step creates **every** phase Workstream for **every** PI — no
generalist decides which phases "matter." Scope judgment belongs to the phase
specialist, which is the only agent with the expertise to make it. A phase with
no work is the **expert's recorded conclusion**, not a generalist's omission.

### 4.2 Scope determination = Work Task creation
A phase is "planned" when its specialist has produced its Work Tasks. There is no
separate scoping artifact; the Work Tasks *are* the scope.

### 4.3 An empty Workstream is a positive assertion
A Workstream with zero Work Tasks means "this phase was evaluated and is N/A" —
recorded and auditable, mirroring the deploy engine's deliberate `NO_WORK` (≠
`SKIPPED`). **(proposed)** represent it as the Workstream reaching `Complete`
with a recorded no-work note, so "evaluated, nothing to do" is queryable.

### 4.4 DB-backed statelessness (restartable)
No agent holds lifecycle state in its head. The PM reconstructs "where are we"
entirely from the records (which Workstream is `Planned` vs `In Progress`, which
Work Tasks are `Complete`) and writes status back. A PM (or any agent) can die
and another picks up exactly where the DB says things stand. This is what makes
the pull-based design resumable.

### 4.5 Pull-based, not pushed
Standing agents watch the governance DB for work in the state they handle (a PI
reaching `Ready`, a Work Task reaching `Ready`/`Claimed`) and pull it. Dispatch
is emergent from the records, not a central scheduler.

---

## 5. State-model additions needed

The PI-112 lifecycle vocabulary does not yet express everything this runtime
needs:

- **Needs Attention** — the human-in-the-loop escape hatch, set by the PM when
  planning or execution hits something it can't resolve. **(proposed)** a
  first-class status on the **Planning Item** and/or the specific **Workstream**
  that hit the snag, so "stuck, needs a human" is queryable rather than buried in
  prose. This is arguably the most trust-critical state in the system. (Today:
  PI statuses `Draft…Resolved`; Workstream statuses `Planned/In Progress/Complete/
  Blocked` — neither has it.)
- **Phase planning vs execution** — the Workstream lifecycle may need to
  distinguish "specialist is scoping" from "area specialists are executing" from
  "evaluated, no work." See §9.

---

## 6. Relationship to the data model (PI-112) and DEC-343

- **Reused as-is:** the `Project → PI → Workstream → Work Task` containment chain
  and its `belongs_to` edges; `blocked_by` between sibling PIs / Workstreams /
  Work Tasks; the Work Task single-area constraint and `claimed_by`/`claimed_at`;
  the Workstream `phase_type` vocabulary; the area layer ranks for ordering.
- **Refines DEC-343:** the three tiers map to DEC-343's general-purpose →
  discipline-manager → area-specialist, but with sharpened roles — the
  general-purpose agent is elevated to a **Project**-level **Project Manager**,
  and the discipline-manager is the **phase specialist** whose job is
  *scope-and-decompose*, not just oversight.
- **New (this document):** the Project Manager lifecycle loops, the
  always-all-phases rule, scope-as-Work-Tasks, the Needs Attention state, and
  DB-backed statelessness.

---

## 7. The bootstrap problem

This system cannot govern its **own** construction — there is no Project Manager
yet to decompose "build the agent-delivery runtime." So the runtime is built the
old session-driven way, under a Planning Item with hand-authored Workstreams and
Work Tasks, and **once it exists it governs every PI after it.** The deferred
"Workstream/Work Task UI panels" PI is a good candidate for the **first PI the
finished runtime decomposes** end-to-end.

---

## 8. Build sequence (proposed)

1. Lock this design (resolve §9, record the decisions).
2. Build the **structural decomposer** (creates all phase Workstreams for a PI)
   + the **Architecture phase specialist** (the most consequential; the one that
   bridges to the methodology layer).
3. Add the remaining phase specialists (Development first).
4. Build the **Project Manager** orchestration loop + the Needs Attention state.
5. Add the **area specialists** / execution wiring.
6. Dogfood end-to-end on the UI-panels PI under PRJ-014.

---

## 9. Open decisions

1. **Naming — Architecture vs Design.** The phase vocab value is `Design`
   (DEC-349); the conversation uses "Architecture." Same phase renamed, or
   distinct?
2. **Needs Attention placement.** PI-level, Workstream-level, or both? A new
   status value, or a separate flag/field? What clears it?
3. **No-work representation.** `Complete` + note (§4.3), or a dedicated
   `no_work`/`not_applicable` Workstream status?
4. **Project Manager unit.** One PM agent orchestrating all of a Project's PIs
   directly, or a PM that spawns a per-PI sub-orchestrator (lead) for each ready
   PI?
5. **Execution concurrency.** Strictly sequential phases (Architecture → … →
   Deployment) with verify gates, or may some phases (or some PIs) run in
   parallel? Within a phase, Work Tasks are already orderable by layer rank.
6. **Replanning scope.** When the PM "adjusts the plan" mid-execution, can it add/
   modify Work Tasks freely, or only within guardrails? How is a mid-flight
   re-scope recorded (new Work Tasks vs amended)?
7. **Workstream lifecycle.** Does the current `Planned/In Progress/Complete/
   Blocked` set need a "Scoping" / "Planned-no-work" / "Needs Attention" state to
   model the planning-vs-execution distinction (§5)?
8. **Phase set completeness.** Is `{Architecture/Design, Development, Testing,
   Documentation, Data Migration, Deployment}` the canonical always-created set,
   or are any conditional?

---

## 10. Out of scope (for this document)

- The concrete agent prompts / skill definitions for each specialist (follow-on,
  once the model is locked).
- The retirement of the shelved WS-012 orchestrator (target-model §9 step 6) —
  this runtime supersedes it.
- An "agent profile" registry (skill definitions per phase/area) — deferred.
