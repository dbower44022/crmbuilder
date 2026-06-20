# Agent System — Target Model (under active design)

> **Status:** DRAFT, under active design with Doug (started **2026-06-20**). This
> is the **target** model — what the agent/scheduler system *should* be — built
> by describing the sensible design and **diffing it against what's actually
> built** (`Agent-System-Technical-Reference.md` is the built reality). Each item
> is marked **DECIDED** or **OPEN**. **Nothing here is built or authorized for
> build**; building anything requires the requirement-first governance in the
> repo `CLAUDE.md`.
>
> **Working method:** Doug documents what makes sense → we diff against built →
> per difference we decide *keep-built* vs *change-to-target*. Decisions are
> logged in §6.

---

## 1. Governing principles (DECIDED)

1. **Agent vs app.** An LLM-automated function is an **"Agent."** A pure-code /
   no-LLM function is an **"app."** A human performing deterministic process
   steps is **"acting as an app."** Corollary: if a name does not end in
   "Agent," it is not an agent.
2. **Uniform task contract.** Every step is a **small, focused task** with a
   uniform shape: declared **inputs**, **persisted outputs**, and a **status**
   from a fixed vocabulary. The scheduler never looks inside a task — it reads
   the **status** and decides what to do next (proceed / halt for a human /
   retry / roll back / correct).
3. **Two kinds of inputs.**
   - **Work inputs** — the data the task operates on.
   - **Contract input** — *Agent tasks only* — the Agent's contract resolved
     from the **Agent Registry**: system ∪ engagement **skills, governance
     rules, learnings**, version-stamped. **App tasks take no contract.**
4. **Status vocabulary:** `not_started → in_progress → succeeded | needs_human |
   failed`. (`needs_human` = blocked on a decision or review; `failed` =
   errored, eligible for retry/correction.)
5. **Naming.** The orchestration layer is the **"scheduler"** (not "runtime").
   Use **descriptive** names. **Every term is defined in the glossary (§7); no
   new term — in docs or code — is used without Doug's approval.**

---

## 2. End-to-end flow (Doug's target — partly DECIDED, partly OPEN)

```
Release Scheduler (app)            ← monitors FROZEN releases; runs each end-to-end,
   │                                  one at a time (single-occupancy)
   ▼
[ Reconciliation task ]            ── Agent + app        (DECIDED — §4.1)
   ▼
[ Reconciliation Review task ]     ── human-as-app       (DECIDED — §4.2)
   ▼
[ Architecture-Planning task ]     ── Agent + app        (DECIDED — §4.3)
   ▼
[ Architecture-Planning Review ]   ── human-as-app       (DECIDED — §4.4)
   ▼
[ Design task ] (per area)         ── Agent              (DECIDED — §4.5)
   ▼
[ Design Review ]                  ── human-as-app       (DECIDED — §4.6)
   ▼
[ Develop task ] (per area)        ── Agent              (DECIDED — §4.7)
   ▼
[ Test task ] (per area)           ── Agent              (DECIDED — §4.8)
   ▼
[ QA gate ]                        ── Agent + app        (DECIDED — §4.9)
   ▼
[ Test gate ]                      ── Agent + app        (DECIDED — §4.10)
   ▼
[ Ship Approval ]                  ── human-as-app       (DECIDED — §4.11)
   ▼
   deployment → shipped  🎉
```

The **full pipeline above is now defined** (tasks §4.1–§4.11). The remaining open
items are not about the pipeline shape — see §7 (the not-all-PIs-ready rule and
final per-`(area, tier)` Agent names).

---

## 3. Trigger (DECIDED — Divergence 1)

- **One human gate: freeze** (never automated). Freeze is the deliberate "I
  approve this plan" commit. The **freeze gate** requires: **(a)** all the
  release's requirements confirmed, **and (b)** every in-scope PI is **`ready`**
  — or has been **explicitly deferred** by a human to a future release (no silent
  auto-defer; no hard stall). A PI is **`ready`** = its requirements confirmed +
  no unresolved blocker *outside* this release (a dependency on another in-scope
  PI is just sequencing, not "not ready").
- **"Ready for Processing" ≡ Frozen.**
- The **Release Scheduler** (app) **monitors for frozen releases** and
  **auto-runs each end-to-end**, honoring **single-occupancy** (only one release
  in the active lane at a time; if several compete, raise `needs_human` rather
  than guess).
- **Diff vs built:** built is *pointed at one release* (no monitor) but already
  auto-runs everything *after* freeze. The only additions are the **monitor /
  scan** and **single-occupancy arbitration** across multiple frozen releases.

---

## 4. Task specs

### 4.1 Reconciliation task (DECIDED)

Settle *what the design should become*: merge every change the requirements
demand into one conflict-free change-set, and surface contradictions for human
resolution.

| | |
|---|---|
| **Type** | Agent (`(model, architect)` profile / AGP-003) **+** app (deterministic merge) |
| **Work inputs** | the release's confirmed **requirements** + the current **live designs** (merge base) |
| **Contract input** | the Reconciliation Agent's **resolved registry contract** — system ∪ engagement **skills, governance rules, learnings**, version-stamped |
| **Outputs (all persisted)** | 1) **demand-set** — every requirement→design change, traced to its requirement; 2) **reconciled change-set** — the merged, conflict-free result *(stored as a durable, reviewable artifact, not re-derived)*; 3) **conflict list** — typed, each with its resolving decision |
| **Status** | `succeeded` (zero open conflicts) · `needs_human` (open conflicts → halt for human resolution, each tied to a decision) · `failed` |

*Diff vs built:* built persists the demand-set + conflicts but **re-derives** the
merged change-set on demand; the target **persists** it as a reviewable artifact.

### 4.2 Reconciliation Review task (DECIDED)

The completion checkpoint, kept as its **own focused task** (per principle 1.2)
rather than a status flag.

| | |
|---|---|
| **Type** | human (acting as an app) |
| **Work inputs** | the reconciled change-set + conflict resolutions from §4.1 |
| **Outputs (persisted)** | a **sign-off record** (approved/rejected + reviewer + timestamp + notes) |
| **Status** | `succeeded` (approved → proceed to Architecture-Planning) · `needs_human` (awaiting review) · `failed`/rejected (→ back to Reconciliation) |

*Diff vs built:* built has no distinct reconciliation-review state — the check is
the transition guard. The target makes it an explicit reviewable task.

### 4.3 Architecture-Planning task (DECIDED)

Author the **product design** and the **work breakdown** from the approved
change-set. (Authors *what each artifact becomes* — **not** the per-area
implementation/test specs; those are the Design task, §4.5.)

| | |
|---|---|
| **Type** | Agent (`(planning, architect)` / AGP-004) **+** app (decomposition / sequencing / readiness substrate) |
| **Work inputs** | the **approved reconciled change-set** (§4.2) + current **live designs** (the versions to bump) |
| **Contract input** | the Architecture-Planning Agent's **resolved registry contract** (AGP-004; system ∪ engagement skills, rules, learnings; version-stamped) |
| **Outputs (all persisted)** | 1) **product designs** — vN+1 of each affected artifact (the blueprint), in the versioning spine; 2) **decomposition** — single-area Work Tasks (+ phase records); 3) **sequencing** — `blocked_by` dependency order; 4) **readiness result** — the "planned completely" determination |
| **Status** | `succeeded` (planned completely: designs authored + every in-scope PI decomposed + acyclic sequencing) · `needs_human` (a design/sequencing decision is needed, or it can't be planned) · `failed` |

### 4.4 Architecture-Planning Review task (DECIDED)

| | |
|---|---|
| **Type** | human (acting as an app) |
| **Work inputs** | the authored product designs + build plan + sequencing (§4.3) |
| **Outputs (persisted)** | a **sign-off record** (approved/rejected + reviewer + timestamp + notes) |
| **Status** | `succeeded` (approved → Design) · `needs_human` (awaiting review) · `failed`/rejected (→ back to Architecture-Planning) |

*Diff vs built:* built's planned-completely gate (`_check_planned_completely`) is
deterministic; the target adds an explicit human review (matching D6).

### 4.5 Design task (per area) (DECIDED)

Produce the **per-area implementation design + testable spec** — *how* each area
builds the product design, and the spec the Developer builds to and the Tester
verifies against (blind to the code). **One Design task per touched area.**

| | |
|---|---|
| **Type** | Agent — the per-area `(area, architect)` registry profile |
| **Work inputs** | the approved **product design** (§4.3) for this area's artifacts + this area's **Work Tasks** + **upstream areas' design outputs** (feed-forward) |
| **Contract input** | the area's `(area, architect)` **resolved registry contract** (system ∪ engagement skills, rules, learnings; version-stamped) |
| **Outputs (persisted)** | this area's **implementation spec** (technical approach) **+ testable spec** (acceptance criteria / test cases) — durable, versioned, reviewable, scoped to the area |
| **Status** | `succeeded` · `not_applicable` (no real design work — the bounded-overhead escape) · `needs_human` · `failed` |

**Orchestration:** the **scheduler (app)** fans out one Design task per touched
area, **routed deterministically by `area`**; sequences them by **area layer
rank** (storage→access→api→ui) via `blocked_by`, running independent areas in
parallel. **No managing Design Agent** — the work is already partitioned by area
upstream (decomposition), so routing is a deterministic app job and each area
Agent already sees its whole area's batch.

### 4.6 Design Review task (DECIDED)

| | |
|---|---|
| **Type** | human (acting as an app) — **one consolidated review**, not per-area |
| **Work inputs** | the full set of per-area implementation + testable specs (§4.5) |
| **Outputs (persisted)** | a **sign-off record** (approved/rejected + reviewer + timestamp + notes) |
| **Status** | `succeeded` (approved → Develop) · `needs_human` (awaiting review) · `failed`/rejected (→ back to the relevant area's Design task) |

### 4.7 Develop task (per area) (DECIDED)

Implement this area's Work Tasks to its approved spec. **One Develop task per
touched area.**

| | |
|---|---|
| **Type** | Agent — the per-area `(area, developer)` registry profile |
| **Work inputs** | this area's approved **implementation + testable spec** (§4.5) + this area's **Work Tasks** + the current **code** (its worktree) + **upstream areas' merged outputs** (feed-forward) |
| **Contract input** | the area's `(area, developer)` **resolved registry contract** (system ∪ engagement skills, rules, learnings; version-stamped) |
| **Outputs (persisted)** | the **implemented code** — written, **self-verified** (lint clean + affected/existing tests green), committed, and **merged** into the release's integration branch |
| **Status** | `succeeded` (code complete, self-verified, merged) · `not_applicable` (no dev work) · `needs_human` (blocked, or a gap in the spec) · `failed` |

**Orchestration:** scheduler fans out one Develop task per touched area, routed by
`area`, sequenced by area rank, parallel where independent. No managing Agent.

**Confirmed properties:**
- **The Developer does not author acceptance tests** — the **Test task** (§4.8)
  implements the testable spec **blind to the Developer's code**. Develop only
  *self-verifies* (lint + don't break affected/existing tests + meet the spec).
- **No separate human review after Develop** — reviews are front-loaded on the
  plans/designs; the build is verified by the **Test task** + the release-level
  **QA/Test gates**. Develop's `succeeded` flows straight into Test.
- **Concurrency via locks, mostly idle** — per-area ownership means area Develop
  Agents rarely collide; the file/resource **locks remain only as a backstop**
  for genuinely shared resources (e.g. the migration chain). A Develop task may
  fan out sub-agents within its area under those locks.

### 4.8 Test task (per area) (DECIDED)

Independently verify this area against its testable spec. **One Test task per
touched area.**

| | |
|---|---|
| **Type** | Agent — the per-area `(area, tester)` registry profile |
| **Work inputs** | this area's **testable spec** (§4.5) + the **running/merged build** to exercise — **not** the Developer's source as a reference (**blind**) |
| **Contract input** | the area's `(area, tester)` **resolved registry contract** (system ∪ engagement skills, rules, learnings; version-stamped) |
| **Outputs (persisted)** | the **implemented tests** + a **verification result** — pass/fail per acceptance criterion in the spec |
| **Status** | `succeeded` (every spec criterion passes) · `not_applicable` (no test work) · `needs_human` · `failed` (criteria fail → **bounce back to that area's Develop task**) |

**Orchestration:** one Test task per touched area, scheduler-routed by `area`,
sequenced by area rank, parallel where independent. No managing Agent.

**Confirmed properties:**
- **Blind verification** — the Tester implements the testable spec and checks the
  system's **behavior** against it **without reading the Developer's code**, so a
  Developer mistake can't hide in same-mind tests. On `failed` it bounces to the
  area's **Develop** task (not a human).
- **Two test levels** — per-area Test (here) proves each area meets *its own*
  spec; the release-level **QA gate** (§4.9) and **Test gate** (§4.10) verify the
  **assembled whole**. (Matches the built "QA/Test levels" design.)

### 4.9 QA gate task (release-level) (DECIDED)

Conformance check over the **assembled** release.

| | |
|---|---|
| **Type** | Agent (Release-gate Agent — `(release, pi_lead)` / AGP-005) **+** app (context assembly + fail-closed floor) |
| **Work inputs** | the **assembled release**: all in-scope **requirements** + **authored designs** + **delivered areas** |
| **Contract input** | the Release-gate Agent's **resolved registry contract** (AGP-005) |
| **Outputs (persisted)** | a **verdict** `{passed, summary, findings}` + a **QA-pass stamp** on success |
| **Status** | `succeeded` (passed → Test gate) · `failed` (findings → bounce to the back half; clears the pass) · `needs_human` (fail-closed floor — see below) |

**QA = conformance:** does the assembled design **cover every requirement**, with **no cross-area contradictions**?

### 4.10 Test gate task (release-level) (DECIDED)

End-to-end functional check over the **assembled** release.

| | |
|---|---|
| **Type** | Agent (Release-gate Agent / AGP-005) **+** app |
| **Work inputs** | the assembled release + its **end-to-end processes** to exercise |
| **Contract input** | the Release-gate Agent's resolved registry contract (AGP-005) |
| **Outputs (persisted)** | a **verdict** + a **Test-pass stamp** on success |
| **Status** | `succeeded` (passed → **Ship Approval**) · `failed` (bounce to rework) · `needs_human` |

**Test = functional/end-to-end:** do the **key processes hold end-to-end** across the assembled whole? (A green per-area unit is *not* a process.)

**Shared by both gates:**
- **Fail-closed floor (app):** no confirmed requirements **or** no authored
  designs → **automatic FAIL** → `needs_human` (the release was set up wrong, not
  a bad build).
- **Bounce on fail:** a `failed` gate returns the release to the **back half**;
  the verdict's **findings drive the rework**, and a re-run re-checks both gates.

### 4.11 Ship Approval task (DECIDED)

The final human commit — **symmetric to freeze**. A human commits at **both
ends**: *freeze* to start the run, *approve* to ship.

| | |
|---|---|
| **Type** | human (acting as an app) |
| **Work inputs** | the release with **both gate verdicts passed** |
| **Outputs (persisted)** | a **ship-approval sign-off record** (approved/held + approver + timestamp + notes) |
| **Status** | `succeeded` (approved → **deployment → shipped**) · `needs_human` (awaiting approval) · `failed`/held (do not ship) |

---

## 5. What "Reconciliation" vs "Architecture-Planning" mean (reference)

- **Reconciliation** = *conflict resolution over intent.* Merge all requirement
  demands into one conflict-free change-set; flag contradictions for a human.
  Does **not** author designs or plan work.
- **Architecture-Planning** = *design authoring + work breakdown.* Take the
  reconciled change-set and produce the next version of each affected design
  artifact (the blueprint) **and** decompose it into sequenced Work Tasks.

These are genuinely distinct (different inputs/outputs, no overlap). A third,
finer level — **per-area implementation/testable design** — is split out as its
own **Design** task (D7): Architecture-Planning authors the **product** design
(*what* each artifact becomes); the Design task authors the **implementation**
design (*how* each area builds it, plus the testable spec). Intent → product →
implementation, each layer consuming the prior, no redundancy.

---

## 6. Decisions log

| # | Date | Decision |
|---|---|---|
| D1 | 2026-06-20 | **Agent vs app** rule (principle 1.1). |
| D2 | 2026-06-20 | **Uniform task contract** + **status vocabulary** (1.2, 1.4). |
| D3 | 2026-06-20 | **Two kinds of inputs**; registry contract is a uniform **contract input** to every Agent task (1.3). |
| D4 | 2026-06-20 | **Trigger** (Divergence 1): human freeze is the only gate; "Ready for Processing" ≡ Frozen; Release Scheduler monitors frozen releases and auto-runs under single-occupancy (§3). |
| D5 | 2026-06-20 | Reconciliation **persists the reconciled change-set** as a durable, reviewable artifact (§4.1). |
| D6 | 2026-06-20 | The reconciliation **review is its own focused task** (§4.2). |
| D7 | 2026-06-20 | **Split design WHAT vs HOW** (resolves the Arch-Planning/Design boundary): Architecture-Planning authors **product design** + decomposition + sequencing; a separate **Design** task authors **per-area implementation + testable specs**. Rationale: distinct artifacts at distinct levels; the testable spec enables **independent testing** (Tester verifies the spec, blind to Dev code); trivial-task overhead bounded by `Not Applicable`. |
| D8 | 2026-06-20 | **Architecture-Planning task** (§4.3) + **Architecture-Planning Review task** (§4.4) defined; both adopt the uniform inputs/outputs/status contract. |
| D9 | 2026-06-20 | **Design task is per-area** (§4.5): the scheduler fans out one Design task per touched area to that area's `(area, architect)` Agent, routed by `area`, sequenced by area layer rank, **no managing Agent**; one **consolidated Design Review** (§4.6). This settles the **back half = organized by area** (resolves Divergence 2 toward per-area; resolves the "specialty agents" question — they're the per-`(area, tier)` Agents). |
| D10 | 2026-06-20 | **Develop task is per-area** (§4.7), `(area, developer)` Agents, same orchestration as Design. The Developer **self-verifies** but does **not** author acceptance tests (the Test task does, blind to the code); **no human review after Develop** (Test + release gates verify); **locks are a backstop only** since per-area ownership removes most collisions. |
| D11 | 2026-06-20 | **Test task is per-area** (§4.8), `(area, tester)` Agents. **Blind verification** — tests the spec, not the Developer's code; `failed` bounces to that area's Develop task. The per-area Test is the **area level**; the release-level **QA + Test gates** verify the assembled whole — **two test levels** (matches built). Completes the per-area back half (Design→Develop→Test). |
| D12 | 2026-06-20 | **Release-level QA gate (§4.9) + Test gate (§4.10)** — the Release-gate Agent (AGP-005) judges the **assembled whole**: QA = conformance (design covers every requirement, no contradictions), Test = functional (processes hold end-to-end). Deterministic **fail-closed floor** (no requirements/designs → auto-fail → `needs_human`); a `failed` gate **bounces** to the back half, findings driving rework. |
| D13 | 2026-06-20 | **Final human Ship Approval (§4.11)** — option B: shipping requires a human sign-off, **symmetric to freeze** (human commits at both ends). Test gate `succeeded` → Ship Approval → deployment → shipped. **The pipeline (§4.1–§4.11) is now fully defined.** |
| D14 | 2026-06-20 | **Not-all-PIs-ready rule** — option C: the **freeze gate** requires every in-scope PI to be **`ready`** *or* **explicitly deferred** by a human to a future release. No silent auto-defer (built's behavior); no hard stall (pure all-or-nothing). "Ready" = requirements confirmed + no blocker outside this release (§3). |

---

## 7. OPEN questions / pending divergences

- **Final per-`(area, tier)` Agent display names** — e.g. the Data / API / UI
  design-, develop-, and test-Agents (per principle 1.5).
- *(Resolved: Divergence 1 → §3, D4; Arch-Planning/Design boundary → D7;
  Divergence 2 back-half shape → per-area, D9; specialty/matrix-org agents →
  the per-`(area, tier)` Agents, D9.)*

---

## 8. Glossary (target-model terms)

> Per principle 1.5, every term used in this doc is defined here. New terms
> require Doug's approval before use.

- **Agent** — an LLM-automated function/task.
- **app** — a pure-code (no-LLM) automated function; a human doing deterministic
  steps is "acting as an app."
- **scheduler** — the orchestration layer that runs tasks and gates on their
  status (the term replacing "runtime").
- **Release Scheduler** — the app that monitors frozen releases and runs each
  end-to-end under single-occupancy.
- **freeze** — the single human action that commits a release's plan; gated on
  all its requirements being confirmed.
- **Ready for Processing** — synonym for **Frozen**; the condition the Release
  Scheduler picks up on.
- **ready (PI)** — a PI whose requirements are confirmed and which has no
  unresolved blocker outside the current release.
- **defer** — a human action at the freeze gate that moves a not-ready in-scope
  PI out of this release to a future one.
- **single-occupancy** — only one release in the active processing lane at a time.
- **task** — a small, focused unit of work with declared inputs, persisted
  outputs, and a status; either an Agent or an app.
- **work input** — the data a task operates on.
- **contract input** — an Agent task's resolved registry contract (system ∪
  engagement skills, rules, learnings; version-stamped); app tasks have none.
- **status** — one of `not_started | in_progress | succeeded | needs_human |
  failed`.
- **contract** — the effective definition of an Agent resolved from the Agent
  Registry (profile prompt + skills + rules + learnings + version-stamp).
- **Agent Registry** — the store of agent profiles, skills, governance rules, and
  learnings, scope-merged system ∪ engagement.
- **demand-set** — the structured list of every requirement→design change.
- **reconciled change-set** — the merged, conflict-free result of reconciliation
  (persisted, reviewable).
- **conflict list** — the contradictions between requirements, typed, each with
  its resolving decision.
- **Reconciliation task / Reconciliation Review task** — see §4.
- **Reconciliation** — conflict resolution over requirement intent (§5).
- **Architecture-Planning** — **product**-design authoring + work breakdown (§5).
- **product design** — the definition of *what* each artifact (entity/field/
  process…) becomes; authored by Architecture-Planning.
- **implementation design / testable spec** — the per-area *how-to-build-it* +
  *how-to-verify-it*; authored by the Design task; the spec the Developer builds
  to and the Tester tests against, blind to the code.
- **Design task** — the per-area task that produces the implementation +
  testable spec (§4.5).
- **Design Review task** — one consolidated human sign-off over all area specs
  before Develop (§4.6).
- **Develop task** — the per-area task that implements and self-verifies the code
  for an area's Work Tasks, merging it into the release integration branch (§4.7).
- **Test task** — the per-area task that independently verifies an area against
  its testable spec, blind to the Developer's code (§4.8).
- **QA gate task** — release-level conformance gate (does the assembled design
  cover every requirement?), judged by the Release-gate Agent (§4.9).
- **Test gate task** — release-level end-to-end functional gate, judged by the
  Release-gate Agent (§4.10).
- **Ship Approval task** — the final human sign-off before shipping, symmetric to
  freeze (§4.11).
