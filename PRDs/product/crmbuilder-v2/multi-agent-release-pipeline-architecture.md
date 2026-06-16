# Multi-Agent Release Pipeline & Source-Locking Architecture

> **Status:** Design concept — captured for review. Authored 2026-06-16 from a single
> in-depth design conversation (Claude Code session) between Doug Bower and Claude.
> **Origin decisions:** DEC-448 (Multi-Agent Coordination must be enforced cross-process)
> and DEC-449 (supplement git with pessimistic check-out/check-in locking), both recorded
> 2026-06-15. **Founding projects:** PRJ-029 (Multi-Agent Coordination, planned),
> PRJ-030 (Source Check-in/Check-out — pessimistic locking over git, planned).
>
> **Purpose of this document:** to be the *source of truth* for the concept we agreed,
> capturing not only what we decided but **every option we considered and why we chose
> what we did**, so that the database records and the eventual implementation can be
> checked against it for drift. The full conversation is reproduced in Appendix A.

---

## 1. Purpose & Origin

On 2026-06-15, roughly six independent Claude sessions were active on the shared `main`
working tree at once. Two of them worked PI-131 in parallel without either knowing. The
ADO rollback path (`git reset --hard`) was able to discard a concurrent session's
committed work. Two governing decisions came out of that day:

- **DEC-448** — multi-agent coordination must be **enforced cross-process**, not advisory
  inside one orchestrator. Every deliverable unit (Planning Item, Work Task) must carry an
  authoritative claim an agent *must* acquire; no silent out-of-band path may bypass it.
  *(This is PRJ-029.)*
- **DEC-449** — git is **optimistic by design** (it permits divergence and resolves by
  merge), so it cannot be the mechanism that *prevents* concurrent-edit collisions. Build a
  pessimistic check-out/check-in lock layer over git. *(This is PRJ-030.)*

This document is the concept worked out for how those two projects — and the larger
machinery they imply — fit together into one coherent, efficient, reliable process.

---

## 2. Problem Statement

Doug's framing (adopted over the author's initial framing — see Decision D-01) is that
there are **two distinct collision problems that must work together as one process**:

1. **Planning/specification collisions** — multiple agents authoring the spec (processes,
   requirements, and the entities/personas/relations they define) without colliding.
2. **Development collisions** — development agents editing source code without stepping on
   each other.

The author's earlier framing — two *failure modes*, (A) concurrent-edit interleaving and
(B) destructive-rollback blast radius from `git reset --hard` — is retained here as useful
analysis (it shows why a pure file lock is insufficient for B), but the **work** is
organized by Doug's planning-vs-development cut, not by failure mode.

The key realization that shapes everything below: **the solution is not primarily a lock.
It is a pipeline whose structure makes collisions impossible at every grain except one, and
a file-level lock is the seatbelt for that one grain.**

---

## 3. The Concept (Consolidated)

**One sentence:** Collisions are prevented *structurally* at every grain by a single-track
release pipeline; the only judgment-based grain — an area expert's intra-area parallel
fan-out — is backstopped by file-level locks.

The concept has five nested rings of collision control, from coarsest to finest:

1. **Releases** flow through a staged pipeline; only **one release is in the
   Development→Shipped lane at a time** (fully serial). Releases at different stages touch
   different artifacts at different maturities, so cross-release collisions cannot happen.
2. **Areas** inside the development lane: **one owner per area**, areas open in dependency
   order, and an area is not "complete" until it passes its own QA and testing, which
   **freezes** it. Downstream areas build only on frozen areas.
3. **The area owner** is a domain **expert decomposer**: it breaks its area's work into
   small focused work tasks and fans out parallel sub-agents **only where it judges them
   independent**.
4. **File-level locks** (PRJ-030): when sub-agents run in parallel, each checks out
   (locks) the specific files it will touch; overlapping check-outs are refused and forced
   serial. This is the backstop under ring 3's judgment.
5. **Two temperatures on the planning side**: conceptual work runs **optimistic and
   parallel** (nothing is committed yet); the instant work is scheduled into a release and
   frozen, the temperature flips to **pessimistic, single-threaded by area**.

---

## 4. The Structural Model

### 4.1 Organizers (timeless, purely organizational, off to the side)

- **Domain** — organizes **Processes**, aligned to business units. Purely organizational;
  drives nothing. Example: a "Mentor Recruitment" domain.
- **Topic** — organizes **Requirements**, broader and cross-cutting than a Domain. Purely
  organizational. Example: "Contact Management."

Domains and Topics are filing systems on two different axes. Neither causes change.

### 4.2 The change spine (what actually drives change)

```
Process (versioned, filed under a Domain)   ← the engine of change
  → Requirements (filed under Topics)        ← what the change demands
    → Entities / Personas / Relations        ← the shared model the requirements define
```

- The **unit of change is the Process.** The first gesture is always: *decide to change a
  process (or a cross-domain process), then define the requirements for that change.*
- Those requirement changes cascade into changes to entities, personas, and relations.
- **Processes are versioned.** A change bumps the process version, and the system tracks
  the whole chain: process vN → these requirement changes → these entity/persona/relation
  changes.
- **Entities, personas, and relations are shared across processes.** The Contact entity is
  defined by requirements from many processes. This sharing is the source of planning-side
  collisions (the mirror of the dev side's shared-base-file problem) and is resolved by the
  **reconciliation** stage (§5).

### 4.3 The delivery hierarchy

```
Release → Project → Requirement → Planning Item (PI) → Workstream → Work Task
```

- A **requirement** has two homes: a *thematic* one (its **Topic**, forever) and a
  *delivery* one (the **Project** under a **Release** that schedules it).
- A **Release** is the scheduling/batching container; it literally contains Projects.
  Example: Release #23 contains a "Basic Contact Management" project and a "Basic Company
  Management" project.
- **Work Task** is the leaf — the single-area unit an agent actually executes.

> **Project-model reconciliation (§16.2, RESOLVED — DEC-478/479/480, REQ-211/212/213).**
> Target model:
> - **A Project is *release-scoped*** (R-1): it belongs to exactly one Release and is the
>   bundle delivered in that release. The long-lived/timeless grouping role moves to
>   **Topic/Domain** — there is no long-lived Project container. *(Supersedes the live
>   Project-as-long-lived-container model; reclassifying existing `PRJ-` records is a
>   separate migration.)*
> - **A Requirement keeps two homes:** its timeless **Topic** (and defining Process), plus a
>   **delivery scheduling overlay** into a release-scoped Project when scheduled. It is never
>   moved out from under its Topic.
> - **Work larger than one project** = a sequence of release-scoped projects linked by
>   **`blocked_by`** (project→project) and grouped by a **shared Topic**. No parent-project
>   field (that would re-introduce the long-lived container).

### 4.4 Glossary of coined terms

| Term | Meaning |
|---|---|
| **Area** | The unit of ownership and segmentation of the code/work (e.g. Data Structure, API, Business Logic, UI). Only one owner per area at a time. |
| **Area = freeze unit** | An area is not "complete" until it passes area-level QA + testing, which *freezes* its output. |
| **Never build on unfrozen ground** | A downstream area (e.g. API) may not start until its upstream area (e.g. Data Structure) is developed, QA'd, tested, and frozen. |
| **Exclusive development lane** | The whole Development→QA→Testing→Deployment→Shipped chain, held by exactly one release until it ships. |
| **Two temperatures** | Planning is *optimistic/parallel* while conceptual, and *pessimistic/single-threaded-by-area* once scheduled into a release and frozen. |
| **Planned completely (the gate)** | A release may enter the development lane only when: spec frozen + all requirements decomposed to work tasks + all tasks sequenced with prerequisites. |
| **Rework loop** | A QA/Testing/Deployment failure bounces the release *backward* to Development; the lane stays locked the whole time. |
| **Expert decomposer** | The area owner is a domain expert that decides what to parallelize, not a forced serializer. |
| **Frozen (release)** | A release's process versions and requirements are committed to the release and closed to further *conceptual* change. Freeze locks the processes and requirements (the demands), not the derived model; reconciliation and architecture planning then operate on the frozen set. Freeze triggers the temperature flip to single-threaded-by-area, and is the first of the three "planned completely" conditions. Distinct from **area freeze** (§7.1), which is a development-side area passing its own QA + testing. |
| **Reopen** | The governed reverse of a freeze (§14). The only in-flight reopen is of a frozen *area* (D2), triggered by a downstream area's discovered need; it re-serializes (pause → reopen → re-freeze → resume). Frozen *plans* are never reopened — plan corrections go to a new Release. |
| **Blast radius** | The set of areas downstream of a reopen point — everything that re-flows through its QA/test gate when an area is reopened. Larger the lower the reopen; the measure that sizes reopen approval (RW5). |
| **Facet** | The grain at which reconciliation detects conflict: a single attribute of a field or model element (`email.required`, `contactType.options`, `phone.type`), not the whole entity. Two demands collide only if they set the *same facet* to contradictory values (§5.4). |
| **Reconciliation conflict** | A typed record emitted when two requirements demand contradictory values on one facet. It is resolved by a governed decision (pick / synthesize / amend a requirement), never by the reconciler silently choosing (§5.4, D-35). |
| **Reconciled delta-set** | Reconciliation's output for a release: per touched artifact, the conflict-free merged change against the live base, every change traced to its demanding requirement(s). Architecture planning consumes it to author vN+1 (§5.4, D-36). |
| **Three-way merge (model)** | Reconciliation's merge shape: base = the artifact's live (latest-shipped) definition; each demanding requirement = a delta against that base; merged = base + the N deltas (§5.4, D-33). |

---

## 5. The Release Pipeline (the conveyor)

```
[ Conceptual planning ]   ← PARALLEL & FREE (optimistic), many releases' worth of ideas
        │  schedule into a Release + freeze   ← TEMPERATURE FLIPS to pessimistic
        ▼
[ Reconciliation ]        ← single-threaded by area
        ▼
[ Architecture planning ] ← single-threaded by area
        ▼
====== GATE: "planned completely" (frozen + decomposed + sequenced) ======
        ▼
[ Development ] → [ QA ] → [ Testing ] → [ Deployment ] → [ Shipped ]   ← ONE release, fully serial
        ▼
   next release enters the lane
```

### 5.0 The Release entity (§16.6)

Designed in conversation **CNV-105**, decisions **DEC-476/477**; fully specifies and
supersedes the coarse `REL-` cadence sketch from DEC-370/371. Built by **PI-205**.

- **Identifier `REL-`.** A Release is **born early** (in `preliminary_planning`) as a
  **mutable forming container** that work is scheduled *into* as concepts mature — not a
  frozen-at-birth bundle (DEC-476 / REQ-209).
- **Status = its pipeline stage:** `preliminary_planning → development_planning →
  reconciliation → architecture_planning → ready → development → qa → testing → deployment →
  shipped` (+ `cancelled` / `superseded`), with **three gated transitions**: freeze (→
  reconciliation), planned-completely (→ ready/the lane), and single-occupancy across the
  lane states (`development…deployment`).
- **Lane entry = explicit order + `blocked_by`** (DEC-477 / REQ-210): a human-set sequence;
  a release `blocked_by` another can't enter the lane until its blocker ships; the lane takes
  the next ready, unblocked release in order.
- It is the anchor the **plan-freeze** (§4.4) and **version-tying** (§9) attach to.
- **What a Release contains** (§16.2, resolved): release-scoped **Projects** (`blocked_by`-
  sequenced, Topic-grouped); each Project gathers the **PIs** that implement the
  **Requirements** scheduled into the release. Requirements keep their timeless Topic home.

### 5.1 Planning side — two phases

**Phase 1 — Conceptual (process-driven), parallel & free.**
- Change processes → define requirements → which define entity/persona/relation changes.
- Runs **optimistic and parallel** because nothing is committed: concepts are independent
  drafts, and some mature slower than others. This is the preliminary-planning backlog
  (which may hold many releases' worth of work, or none — it does not matter to the
  development side).
- When a set of frozen processes/requirements is **scheduled into a release and frozen**,
  the temperature flips.

**Reconciliation — single-threaded by area.**
- Resolves the overlapping impacts of a release's process changes on the **shared model**
  (entities/personas/relations) into one coherent, conflict-free model.
- This is the planning-side answer to collisions: *optimistic-then-reconcile*, rather than
  the dev side's hard single-owner lock. Different medicine, because the two halves work on
  different material at different times.

**Phase 2 — Architecture planning — single-threaded by area.**
- Begins only on the frozen release. An **Architect Planning Agent** reads *all* the
  requirements and produces:
  - the **versioned design** — e.g. a Contact entity definition **vN+1, tied to the
    release**, with the field changes (delegating to a **Data Structure Planning Agent**
    when it is complex), then
  - the **workstreams and work tasks** that implement those requirements, **sequenced with
    prerequisites** ("you need a database field before you can code an API").
- Output satisfies the gate.

### 5.2 The gate: "planned completely"

A release may enter the development lane only when **all three** hold:
1. the spec is **frozen**;
2. every requirement is **decomposed down to work tasks**;
3. every work task is **sequenced with its prerequisites**.

**All dependency reasoning happens in planning, none in development.** By the time a
release enters the lane, the work tasks form a finished prerequisite graph; development just
*walks* it. The **area order** (Data Structure before API) is *not authored separately* —
it falls out of the work-task prerequisite graph.

### 5.3 The back half: Development → QA → Testing → Deployment → Shipped

- **QA ≠ Testing.** QA is a **conformance** gate — did the development meet the quality
  specs (build what the spec said, to the required standard)? Testing is **functional**
  verification — does it actually work? QA comes first on purpose.
- See §7 for the two levels (area vs release) of QA/testing.

### 5.4 The reconciliation-merge algorithm (§16.5, resolved)

This is the **algorithm/agent contract** for the reconciliation stage (§5.1): how the
overlapping demands of a release's process changes on one **shared model artifact** (an
entity, persona, or relation) merge into one coherent definition. Designed in conversation
**CNV-108**, decisions **DEC-483…487** (D-33…D-37). It is the planning-side mirror of the
dev-side shared-base-file problem, solved by structure-first merging with judgment reserved
for the one place it is unavoidable — exactly the philosophy of the file-lock backstop (§7.3),
one ring out.

**The setup.** Under the two temperatures (§5.1), Phase-1 concepts are drafted optimistically
and in parallel; nobody locks the model. So when a set of frozen processes/requirements is
scheduled into a release, several requirements — born in different processes — may each demand
changes to the **same** artifact (e.g. "Mentor Recruitment" and "Donor Management" both touch
**Contact**). Reconciliation resolves those superimposed demands into one conflict-free model.

**It is a three-way / N-way merge (D-33).** Each touched artifact is merged like a
three-way merge:
- **Base** = the artifact's **live definition** — its latest *shipped* version (per §16.4).
- **Sides** = each demanding requirement's **delta** expressed against that same base.
- **Merged** = base + the set of deltas. N demanding requirements → an N-way merge over **one
  common base**, so the result is order-independent and every merged change keeps a clean line
  back to the demand(s) that produced it.

**The conflict unit is the facet, not the entity (D-34).** Two requirements both "touching
Contact" is *not* a conflict. The unit is the **facet** of a field or attribute —
`email.required`, `contactType.options`, `phone.type`. The reconciler classifies every
overlapping demand on the same facet by a fixed taxonomy; the first four classes **auto-merge
without judgment** and are recorded, and **only `CONFLICT` escalates**:

| Class | When | Resolution |
|---|---|---|
| **NONE** | demands touch disjoint facets/fields | union — both apply |
| **IDENTICAL** | same facet, same value (both want `email` required) | dedupe — apply once |
| **COMPOSE** | different facets of one field (A: `email.required`; B: `email.maxLength`) | apply all facets |
| **ADDITIVE-UNION** | set-valued facet (both add `contactType` enum options) | union the set |
| **CONFLICT** | same facet, contradictory values (`required` true vs false; `phone.type` phone vs varchar; add-vs-remove of one field) | **escalate (D-35)** |

Most parallel-drafted overlaps fall in the first four classes and merge mechanically
(machine-verifiable, fast). Judgment is spent only on the rare genuine contradiction.

**A contradiction is a governed requirements decision — never a silent reconciler pick
(D-35).** When two confirmed requirements demand contradictory values on one facet, the
reconciler does **not** choose. It emits a typed **reconciliation-conflict** (artifact, facet,
the competing demands and their requirements) and routes it to a governed `decision`, whose
outcome — pick A, pick B, synthesize a third value, or **amend** one requirement via a
`requirement_changed_by_decision` edge (sending it back to candidate/needs-review) — is applied
into the reconciled delta. Approval weight scales with impact, consistent with the
reopen-approval principle (RW5). Choosing between two business processes' demands is a
*requirements* decision, not a merge mechanic; a silent pick would violate "inferences require
positive support" and bury a real trade-off. The project's existing decision + requirement-amend
machinery (the provenance/Review work) governs it.

**Output is a conflict-free reconciled delta-set; vN+1 is authored downstream (D-36).**
Reconciliation's deliverable is the **conflict-free reconciled delta-set** per touched artifact
(the merged logical target + every resolved conflict), **not** the version snapshot. Architecture
planning (§5.1) consumes that delta-set and authors/snapshots the release-tied **vN+1** (§16.4).
Reconciliation never writes a `*_versions` row — version authoring stays a single-writer
(architecture) concern, and the stage boundary in §5.1 is preserved exactly.

**One single writer, dependency-ordered, deterministic, fully traced (D-37).** Reconciliation
is single-threaded by area (§10), so **one reconciler owns the whole model (Data Structure)
area** and processes artifacts in **intra-model dependency order — entities and personas first,
then the relations that reference them** — over the *static* frozen requirement set. That makes
the merge **deterministic and re-runnable**: a re-freeze after a reopen (§14) or a requirement
amendment reproduces the same reconciled delta-set from the same inputs. Every auto-merged or
resolved change links to the requirement(s) that demanded it, and every conflict resolution
links to its decision — extending the §9 provenance spine **down to the single field**.

**Reconciliation invariants (RC-1…RC-7 — REQ-217…223, ai-derived, candidate):**

- **RC-1** (REQ-217) — A release cannot leave reconciliation with any open (unresolved) model conflict. *(the gate)*
- **RC-2** (REQ-218) — Reconciliation merges each requirement's demand as a delta against the live (latest-shipped) base (an N-way three-way merge over one common base).
- **RC-3** (REQ-219) — The conflict unit is the (artifact, field/attribute, facet); disjoint, identical, orthogonal-facet, and additive-union overlaps auto-merge without judgment and are recorded.
- **RC-4** (REQ-220) — A same-facet contradiction is a typed conflict resolved by a governed decision; the reconciler never silently chooses between two requirements' demands.
- **RC-5** (REQ-221) — Reconciliation produces a conflict-free reconciled delta-set; vN+1 is authored downstream by architecture planning, not by reconciliation.
- **RC-6** (REQ-222) — The model area is reconciled by a single writer in intra-model dependency order, making the merge deterministic and re-runnable from the frozen requirement set.
- **RC-7** (REQ-223) — Every reconciled change links to its demanding requirement(s) and every conflict resolution links to its decision (provenance to the field by construction).

---

## 6. The Exclusive Development Lane (fully serial)

- The **entire** Development→QA→Testing→Deployment→Shipped chain is **one exclusive lane,
  held by a single release until it ships** (Decision D-07, "Way 2").
- It is fully serial **because of rework loops**: a failure in QA, Testing, or Deployment
  can send the release **back** to Development to fix. Because the release can reclaim the
  Development station at any moment, the whole lane must be reserved for it — if another
  release were in Development, the bounce-back would be a head-on collision. **Exclusivity
  is what makes rework safe**, not an arbitrary throttle.
- **"Left Development" is not a release point — only "Shipped" is.** The lane stays locked
  the entire time.
- **Accepted cost:** freezing makes a back-half bounce-back expensive — if release testing
  sends a frozen Data Structure area back to change, everything downstream built on it may
  have to be redone. This is the price the serial lane pays for safety, and it is accepted.

---

## 7. Inside an Area

### 7.1 Area ownership & the freeze handoff

- **One owner per area.** Within the single development release there is exactly one Data
  Structure owner, one API owner, etc. (Global exclusivity falls out for free from
  one-release-in-the-lane — there is no second release to collide with.)
- **Area-level handoff, not task-level** (Decision D-08): the *whole* upstream area must be
  developed, QA'd, tested, and **frozen** before the dependent area opens. The reason is
  freeze: if API work started before the Data Structure work was frozen, a field could
  change out from under it. **You never build on unfrozen ground.**
- The pipeline pattern **recurses** at the area level: *area develop → area QA → area test
  → frozen → hand to next area.* Same shape as the release, one level down.

### 7.2 Expert decomposition & the file-lock backstop

- The area owner is the **domain expert decomposer**. It breaks the area's work into small,
  focused work tasks and decides what is safe to parallelize. Example: it may judge that
  "add fields to Contacts" and "add fields to Companies" are independent and run them as two
  parallel sub-agents — or judge it risky and run one at a time.
- **Small focused pieces pay twice:** they make independence easy to judge correctly, *and*
  they keep each sub-agent's context small and fast.
- **This intra-area fan-out is the ONLY place in the whole system where collision-safety
  rests on judgment rather than structure.** Everywhere else, collisions are impossible by
  construction.
- **The backstop (Decision D-10 = Option B, PRJ-030's literal mechanism):**
  **file-level locking by specialist agents.** Before fanning out, each sub-agent declares
  and checks out (locks) the specific files it will touch. If two declarations overlap, the
  system **refuses to run them in parallel and forces them serial.** This catches the case
  where the expert mis-judges independence (e.g. two "separate" tasks that actually share a
  base model file or both generate a colliding Alembic migration).

---

### 7.3 File-lock mechanism (PRJ-030, resolves §16.1)

Mechanism for the backstop above (REQ-194), designed in conversation **CNV-103**, decisions
**DEC-469…474** (FL-1…FL-6). It is narrow by construction: one area active, one owner, a few
sub-agents — so it resists heavyweight global infrastructure.

- **FL-1 — the check-out unit is a *named resource*** (DEC-469): a file path *or* a named
  logical resource (the migration chain, a shared registry). Path-only locking would miss
  non-path collisions (two migrations are different files but collide on the chain).
- **FL-2 — logical resources are defined by *detection rules*** over the actual diff
  (DEC-470). A rule both *tells* an agent what to check out and *detects* an undeclared touch.
  The lock has two moments: **acquire** (declare + lock before work; planned overlap →
  serialize) and **verify** (recompute touched resources from the real diff, confirm the
  actor held each — the owner-independent backstop).
- **FL-3 — worktree per sub-agent** (DEC-471): each works isolated; merge-back to the area
  branch is serialized and conflict-free (disjoint locks). A `reset --hard` can only hit the
  actor's own throwaway worktree — this is what actually closes the DEC-449 wound. `verify`
  runs at merge-back.
- **FL-4 — locks live in a V2 DB table** (DEC-472): atomic acquire via the existing
  `BEGIN IMMEDIATE` + unique-constraint machinery; cross-process, owner-independent,
  queryable by `verify`, audited. One source of truth.
- **FL-5 — verify failure → retroactive acquire/serialize + record** (DEC-473): a merge whose
  diff touched an unheld resource is rejected; acquire the missed resource (free → merge; held
  → serialize behind the holder, rebase if co-touched). All in the throwaway worktree; the
  miss is recorded and feeds learning.
- **FL-6 — dead sub-agent → owner-supervised reclaim** (DEC-474): the owner releases the
  dead child's locks and discards its unmerged worktree; a TTL backstops owner death.

Made testable as child requirements refining REQ-194: **REQ-203…207 (FLR-1…5)**, all built
by **PI-203**.

---

## 8. QA & Testing — two levels

- **Area-level** — each area verified **in isolation**: does this piece work on its own?
  (e.g. "the create-contact API does what it should.") Includes area conformance QA + area
  functional test. Passing this is what *freezes* the area.
- **Release-level** — the **assembled whole** verified end-to-end: do the **key processes
  and requirements** hold together across areas? A green create-contact API does not mean
  the create-Mentor process (UI → API → business logic → data) works. Release QA =
  conformance to quality specs; Release Testing = end-to-end function of key processes &
  requirements.
- **The requirement is the through-line.** The same requirements decomposed into work tasks
  on the way *in* are what the release is tested against on the way *out*. Nothing ships
  that wasn't required; nothing required goes unverified.

---

## 9. Versioning & Provenance (the governance win)

Everything is **versioned and release-tied, top to bottom**:

```
Process vN → its Requirements → Entity-definition vN+1 (release-tied) → Workstreams/Tasks → built code
```

Stand at any release and read exactly what changed and why — all the way from "we changed
this process" down to the single field that moved. This is **end-to-end provenance by
construction**, and it is the reason this concept is a governance win and not merely a
workflow.

**Versioning mechanism (§16.4 — DEC-481/482, REQ-214/215/216, built by PI-208):**
- **Full-definition snapshots.** Each versioned artifact keeps a per-artifact `*_versions`
  child table; every release-change appends a complete-definition snapshot **vN+1** that
  **supersedes** the prior. "The Contact entity as shipped in R23" is a *direct read*, not a
  log replay. The existing `change_log` retains the granular field-level edit trail beneath.
- **Numbering:** per-artifact, monotonic (Contact v1 → v2 → v3), independent of other
  artifacts.
- **Release tie + live rule:** each version is tied to the release that introduced it; the
  **live/current definition is the latest version whose release has *shipped*.** Versions in
  an in-flight release are **frozen drafts** — locked by the freeze, but not yet live.
- **Scope:** processes and the model definitions (entity, persona, relation, field) are
  versioned; **requirements are governed by their lifecycle** (candidate/confirmed/reopened),
  not by version numbers.

---

## 10. The Agent Orgs — two, same shape

- **Planning org:** Architect Planning Agent → area planning specialists (e.g. Data
  Structure Planning Agent).
- **Development org:** lead → area build specialists → sub-agents.

The planning org mirrors the development org. The same single-owner-per-area collision
medicine applies to Phase-2 planning (it is one release at a time there too) — but with one
deliberate asymmetry: **Phase-2 area planning is serial *within* an area** (it does not fan
out parallel sub-agents the way development does), because an area's design is holistic and
tightly coupled and it edits already-row-safe DB records, not git files. So planning needs
**no intra-area lock backstop** — the file-lock backstop (§7.3) is development-only.
(DEC-475, REQ-208; resolves §16.3.)

> **Grounding note:** much of the development org already exists as the **ADO** substrate
> (areas, workstreams, work tasks, area specialists, claim/lifecycle, the runtime
> scheduler) and the **Agent Profile Registry**. This concept *extends* that work; it does
> not rebuild it. The genuinely new pieces are flagged in §15.

---

## 11. Invariants (the hard, testable rules)

These are the collision-prevention rules stated as invariants. They double as the QA
conformance spec for the system itself.

1. **At most one release is in the Development→Shipped lane at any time.**
2. **The development lane stays locked until the release is Shipped** (not when it leaves
   Development).
3. **A release enters the lane only when "planned completely"** (frozen + decomposed +
   sequenced).
4. **At most one owner per area** within the development release.
5. **An area opens only after every area it depends on is frozen** (never build on unfrozen
   ground).
6. **An area freezes only after passing area-level QA + testing.**
7. **Parallel sub-agents inside an area must hold non-overlapping file locks; overlapping
   check-outs are refused and serialized.**
8. **Conceptual planning is unrestricted and parallel; the instant work is scheduled into a
   release and frozen, it becomes single-threaded by area** (reconciliation onward).
9. **Every change is a versioned, release-tied chain: process → requirements → model →
   tasks → code.**
10. **A release freeze is a deliberate gate** that closes its processes and requirements to
    conceptual change, triggers the flip to single-threaded-by-area planning, and is the
    first of the three "planned completely" conditions. *(Defines the "frozen" term used in
    invariants 3 and 8. Freeze locks the requirements, not the derived model. Enforcement
    mechanism deferred — §16.7.)*

---

## 12. Design Decisions (with options & rationale)

Each decision below should become a DEC record with `alternatives_considered` and
`rationale` populated.

### D-01 — Frame the work by planning-vs-development, not by failure-mode
- **Options:** (a) the author's *failure-mode* cut — concurrent-edit interleaving (A) vs
  destructive-rollback blast radius (B); (b) Doug's *work-domain* cut — planning/spec
  collisions vs development collisions, working together as one process.
- **Chosen:** (b). **Why:** the work is naturally organized by domain; the failure-mode
  analysis is useful (it proves a pure file lock can't solve B) but is not how the solution
  is structured.

### D-02 — Solve by structure (a pipeline), not primarily by a lock
- **Options:** (a) build a lock layer (file/area/repo) as the primary mechanism;
  (b) build a staged pipeline whose structure makes collisions impossible at every grain,
  with a lock only at the one residual grain.
- **Chosen:** (b). **Why:** git's optimism (DEC-449) means a lock alone is a category-fit
  problem; structure prevents collisions wholesale, and a lock is needed only as a seatbelt.

### D-03 — The unit of possession is the Area, not the file
- **Options:** repo-level lock; file/path-glob lock; **area-level ownership**; work-task
  scope.
- **Chosen:** area-level ownership (one owner per area), with file-level locking reserved
  for the intra-area backstop (D-10). **Why:** coarse, structurally collision-proof,
  matches how work is already partitioned; file-level alone is fiddly and doesn't address
  cross-cutting work.

### D-04 — The area owner is an expert decomposer, not a forced serializer
- **Options:** (a) area owner strictly serializes all area work; (b) area owner is a domain
  expert that fans out parallel sub-agents where it judges them independent.
- **Chosen:** (b). **Why:** extracts safe parallelism and keeps sub-agent context small and
  fast; the residual risk (mis-judgment) is handled by D-10.

### D-05 — Global area exclusivity via "one release in development at a time"
- **Options:** per-release area exclusivity (two releases could each run a Data Structure
  owner); **global exclusivity** (only one release in development).
- **Chosen:** global, achieved by serializing development to one release. **Why:** with two
  concurrent releases, each area expert fans out blind to the other and collisions re-enter
  across releases where no expert can see them. One-release-in-development makes the area
  boundary airtight for free.

### D-06 — The whole thing is a staged release pipeline with stage separation
- **Options:** ad-hoc concurrent releases; **a conveyor** where each release occupies one
  stage and stages narrow to a single development occupant.
- **Chosen:** the conveyor. **Why:** releases at different stages touch different artifacts
  at different maturities, so cross-release work cannot collide; this is also what unifies
  the two problems (planning and development are always different releases in different
  rooms).

### D-07 — The development lane is fully serial ("Way 2"), because of rework loops
- **Options:** **Way 1 (assembly line)** — only the Development station is one-at-a-time, so
  R24 can start Development while R23 is in Testing/Deployment; **Way 2 (fully serial)** —
  only one release anywhere in Development→Shipped at a time.
- **Chosen:** Way 2. **Why:** QA/Testing/Deployment failures bounce a release *back* to
  Development; if another release were in Development, the bounce-back collides. Exclusivity
  of the whole lane is what makes rework safe.

### D-08 — Area handoff is area-level, not task-level
- **Options:** **task-level** — an API task fires the moment its own prerequisites are done,
  even while other Data Structure tasks run (more parallelism); **area-level** — the whole
  upstream area must be frozen before the dependent area opens.
- **Chosen:** area-level. **Why:** an area is "complete" only after passing area QA +
  testing, which *freezes* it; starting API on unfrozen Data Structure risks a field
  changing mid-API. Never build on unfrozen ground.

### D-09 — Two levels of QA/testing (area = isolation, release = integration)
- **Options:** single release-level QA/test; **two levels** (area-in-isolation +
  release-integration).
- **Chosen:** two levels. **Why:** a green area in isolation does not prove the assembled,
  cross-area processes work end-to-end.

### D-10 — File-level locking by specialist agents as the intra-area backstop (Option B)
- **Options:** **Option A** — trust the expert + small pieces, no mechanical net;
  **Option B** — sub-agents declare/lock the files they'll touch; overlap → forced serial.
- **Chosen:** Option B. **Why:** the intra-area fan-out is the one judgment-based grain;
  a hard net under it closes the last hole. *This is PRJ-030's literal mechanism, located
  precisely.*

### D-11 — Process is the unit of change; everything is versioned & release-tied
- **Options:** edit entities/requirements directly; **drive all change from a versioned
  Process change** that cascades to requirements → entities/personas/relations.
- **Chosen:** process-driven, versioned. **Why:** gives end-to-end provenance and
  change-tracking by construction (the governance win).

### D-12 — Planning collisions use optimistic-then-reconcile; two temperatures
- **Options:** lock the shared model during planning; **let conceptual work run parallel &
  free, then reconcile single-threaded by area once frozen into a release.**
- **Chosen:** two temperatures. **Why:** conceptual work is exploratory and uncommitted, so
  locking is wasteful; once committed to a release, reconciliation resolves shared-model
  conflicts deterministically.

### D-33 — Reconciliation is a three-way merge against the live (latest-shipped) base
- **Options:** **(a)** pairwise merge of requirement demands with no common base;
  **(b)** three-way merge where base = the artifact's live definition and each requirement is a
  delta against it (N requirements → N-way over one base).
- **Chosen:** (b). **Why:** a single common base makes the N-way structured merge well-defined
  and order-independent, ties to the §16.4 live=latest-shipped rule, and keeps clean per-change
  provenance. *(§5.4, DEC-483.)*

### D-34 — The conflict unit is the (artifact, field, facet); a typed taxonomy auto-merges non-contradictory overlaps
- **Options:** **(a)** entity-grain (any two requirements touching one entity conflict/serialize);
  **(b)** facet-grain with a fixed taxonomy (NONE/IDENTICAL/COMPOSE/ADDITIVE-UNION/CONFLICT) where
  the first four auto-merge and only CONFLICT escalates.
- **Chosen:** (b). **Why:** most parallel-drafted overlaps are non-contradictory; facet-grain lets
  the structural majority merge mechanically and reserves judgment for the rare true contradiction
  — structure-first, judgment-only-where-unavoidable. *(§5.4, DEC-484.)*

### D-35 — A same-facet contradiction is a governed requirements decision; never a silent reconciler pick
- **Options:** **(a)** the reconciler agent auto-resolves with recorded rationale;
  **(b)** it emits a typed reconciliation-conflict and a governed `decision` resolves it
  (pick/synthesize/amend a requirement via `requirement_changed_by_decision`).
- **Chosen:** (b). **Why:** choosing between two business processes' contradictory demands is a
  requirements decision, not a merge mechanic; a silent pick would violate "no silent inferences"
  and bury a real trade-off. The existing decision + amend machinery governs it. *(§5.4, DEC-485.)*

### D-36 — Reconciliation outputs a conflict-free delta-set; vN+1 is authored downstream by architecture planning
- **Options:** **(a)** reconciliation writes vN+1 directly; **(b)** reconciliation produces the
  conflict-free reconciled delta-set and architecture planning snapshots vN+1.
- **Chosen:** (b). **Why:** preserves the §5.1 stage separation and keeps version authoring a
  single-writer (architecture) concern; reconciliation never writes a `*_versions` row.
  *(§5.4, DEC-486.)*

### D-37 — The model area is reconciled by a single writer, dependency-ordered, deterministically, fully traced
- **Options:** **(a)** per-artifact parallel reconcilers; **(b)** one model-area reconciler
  processing entities/personas before the relations that reference them, over the frozen set.
- **Chosen:** (b). **Why:** a single writer over a frozen base removes cross-artifact races;
  dependency order matches "data structure before API"; determinism makes the rework/amend paths
  safe; per-change provenance is the governance win. *(§5.4, DEC-487.)*

---

## 13. Non-Goals / Out of Scope

- Not a general-purpose distributed lock service.
- Not changing git's branching/merge model; this layers *over* git.
- Not enabling concurrent-release development (the serial lane is deliberate).
- Not rebuilding the existing ADO substrate or Agent Profile Registry — this extends them.
- Mechanism-level choices (lock store, TTL/heartbeat, enforcement implementation, worktree
  details) are deliberately **not** decided here — see §16.

---

## 14. Rework & Reopen — the exception / backward path

Sections 3–13 are the **forward / happy path**: structure that prevents collisions and
freezes that guarantee stable foundations. This section is its **dual** — how a previously
frozen step is reopened *under control* when a late problem demands it. (Project **PRJ-034**;
design recorded in conversation **CNV-102**, decisions **DEC-465…468** = D-15…18.)

A freeze with no governed reverse is brittle; the goal is **"frozen, but reopenable under
control"** — not forbidden (too rigid), not free (defeats the freeze).

### 14.1 Scope (deliberately narrow)

The depth of a problem is *which freeze gate it traces to*:

| Depth | Problem traces to… | Handling |
|---|---|---|
| **D1 — shallow** | a code defect found in QA/Test/Deploy | back to Development — the existing dev-lane rework loop (D-07) |
| **D2 — the real concern** | a **frozen area** is insufficient for a downstream area | **in-lane area reopen** (this section) |
| **deeper** | a **frozen plan** (processes/requirements/model) is wrong | **a new Release** — *frozen plans are never reopened* (RW1) |

So the only genuinely new capability is **D2: an in-lane reopen of a frozen area**, triggered
by a downstream area discovering the upstream area is insufficient (the Contact-entity →
Business-Logic case). Frozen plans are inviolable; a wrong frozen/shipped plan is corrected by
a revised requirement in a *new Release*, never by cracking the current plan (DEC-465).

### 14.2 D2 mechanics — a re-serialization

1. The downstream area **pauses** — it can't build on an area that's thawing (preserves
   "never build on unfrozen ground").
2. The upstream area is **reopened** — its single owner re-acquired, the change made.
3. It is **re-QA'd / re-tested / re-frozen**.
4. **Cascade:** *every* area downstream of the reopen point thaws and **re-passes its QA/test
   gate — no suspected-no-impact exemption** (DEC-467). Blast radius = all downstream areas, so
   reopening the lowest layer is the most expensive.
5. **Approval:** recorded, **sized to the blast radius** (DEC-468) — deep reopens need heavy
   sign-off; shallow ones are lighter. Deliberately makes deep reopens expensive to authorize,
   which pressures good up-front planning.
6. The downstream area **resumes** on the re-frozen upstream.

### 14.3 Rework invariants

- **RW1** (REQ-198) — A frozen plan is never reopened; plan corrections go to a new Release.
- **RW2** (REQ-199) — The only in-flight reopen is of a frozen *area*, triggered by a
  downstream area's discovered need.
- **RW3** (REQ-200) — Reopening an area pauses dependent downstream work until it re-freezes.
- **RW4** (REQ-201) — Reopening an area re-validates *every* downstream area through its
  QA/test gate; no exemption.
- **RW5** (REQ-202) — A reopen requires recorded approval sized to its blast radius.

---

## 15. New vs Existing — what actually has to be built

- **New:** the staged release pipeline + single-occupancy dev lane + rework loops; the
  two-phase planning model (conceptual parallel + reconciliation/architecture
  single-threaded-by-area) and the freeze gates; area-as-freeze-unit with area-level
  QA/testing; process & entity-definition versioning tied to releases; the Architect
  Planning Agent / planning org; **file-level locking backstop (PRJ-030)**.
- **Extends existing (ADO / Agent Profile Registry):** areas, workstreams, work tasks, area
  specialists, claim/lifecycle, the runtime scheduler; the development org shape.

---

## 16. Open Questions / Deferred

These were deliberately *not* decided in the conversation. Do not assume answers.

1. ~~**Mechanism of the file lock (PRJ-030).**~~ **RESOLVED** — designed in §7.3 (FL-1…FL-6,
   DEC-469…474, REQ-203…207): named-resource check-out, detection rules with acquire+verify,
   worktree-per-sub-agent with serialized merge-back, V2 DB lock table, retroactive-acquire on
   verify failure, owner-supervised reclaim.
2. ~~**DB shape reconciliation.**~~ **RESOLVED** (DEC-478/479/480, REQ-211/212/213; §4.3) —
   R-1: Project is release-scoped (belongs to one Release); timeless grouping → Topic/Domain;
   requirements keep their Topic home + a delivery scheduling overlay; larger work =
   `blocked_by`-sequenced, Topic-grouped projects, no parent container. *(Migrating existing
   `PRJ-` records is a separate build concern.)*
3. ~~**Whether Phase-2 planning needs the file-lock backstop too.**~~ **RESOLVED** (DEC-475,
   REQ-208) — **no.** Phase-2 area planning is *serial within an area* (no parallel sub-agent
   fan-out), so there is no judgment grain to backstop; it also edits already-row-safe DB
   records, not git files. Single-owner-per-area + DB row-safety suffices.
4. ~~**Versioning model details.**~~ **RESOLVED** (DEC-481/482, REQ-214/215/216; §9) —
   full-definition snapshots per version in a `*_versions` child table, per-artifact monotonic
   numbering, each version release-tied and superseding the prior, live = latest *shipped*
   version, scope = processes + model definitions (requirements stay lifecycle-governed).
5. ~~**How reconciliation actually merges** two process changes that both touch one entity
   (the algorithm/agent contract).~~ **RESOLVED** — designed in §5.4 (DEC-483…487, REQ-217…223,
   built by PI-215): a three-way / N-way merge of each requirement's demanded delta against the
   live (latest-shipped) base, a facet-grain typed conflict taxonomy that auto-merges every
   non-contradictory overlap, same-facet contradictions escalated to a governed requirements
   decision (never a silent reconciler pick), a conflict-free reconciled delta-set output (vN+1
   authored downstream by architecture planning), and a single-writer, dependency-ordered,
   deterministic, fully-provenance-linked model pass.
6. **The Release entity — fully designed (§5.0 + §16.2 resolved), not yet built.** Intrinsic
   shape (DEC-476/477, REQ-209/210): born-early forming container, pipeline-stage lifecycle,
   explicit-order + `blocked_by` lane entry. Composition (DEC-478/479/480, REQ-211/212/213):
   contains release-scoped Projects (blocked_by-sequenced, Topic-grouped). Building it is
   PRJ-031 / PI-205. Until built, projects are grouped via
   `project_planned_in_reference_book → RB-014`; literal Release-record organization waits on
   the build.
7. **Freeze enforcement mechanism.** The *semantics* of "frozen" are defined (§4.4, invariant
   10, REQ-197); *how* the system performs and enforces a freeze — a status flag, a lock, who
   may set/reverse it — is deferred to the PRJ-031 design pass.
8. **Reopen approval mechanism (§14).** The *principle* is set — approval sized to blast
   radius (RW5) — but the concrete tiers/thresholds, who approves at each, and how the blast
   radius is computed and surfaced before approval are deferred to the PRJ-034 build.

---

## 17. Proposed Project Partition + Release Organization

*(Proposed — to be reacted to, then turned into DB records.)*

- **PRJ-030 — Source Check-in/Check-out:** the **file-level locking by specialist
  sub-agents** (ring 4 / D-10). Its literal charter.
- **PRJ-029 — Multi-Agent Coordination:** the **structural locks above file level** —
  release-lane single-occupancy enforcement, area-ownership exclusivity, and the enforced
  claims on PIs/Work Tasks (DEC-448).
- **New project — Release Pipeline / Staged Delivery:** the conveyor, the stages and gates
  (planned-completely, freeze, QA/Test stations), the two-temperature planning model,
  reconciliation, architecture planning, area-as-freeze-unit handoff.
- **New project — Versioned Process/Model & Provenance:** process versioning,
  entity-definition versioning tied to releases, the change-tracking spine (D-11). *(May be
  folded into the pipeline project — open.)*
- **New project (or extend ADO) — Planning Agent Org:** the Architect Planning Agent +
  area planning specialists.

**Created projects (2026-06-16):**
- **PRJ-029** — Multi-Agent Coordination *(existing)* — single-occupancy + area-ownership + claims.
- **PRJ-030** — Source Check-in/Check-out *(existing)* — file-level locking backstop.
- **PRJ-031** — Release Pipeline & Staged Delivery *(new)*.
- **PRJ-032** — Versioned Process/Model & Provenance *(new)*.
- **PRJ-033** — Planning Agent Org *(new)*.
- **PRJ-034** — Rework & Reopen (Exception Handling) *(new — §14)* — the backward/exception path.

All six are `execution_mode = interactive` so the background ADO runtime cannot
auto-dispatch this design work before you choose to hand it over.

**Release organization — and the Release-entity gap.** There is **no Release entity in the
system today** (the `REL-` entity designed in DEC-370/371 was never built). Building it is
*part of this scope* (PRJ-031, PI-205). Until it exists, the five projects are grouped via
the **`project_planned_in_reference_book` edge to RB-014** (this PRD registered as a
governance reference book). When the Release entity lands, the projects/PIs can be organized
into a literal Release record. This is logged as Open Question §16, item 6.

---

## 18. Traceability Matrix

**Governance anchor (2026-06-16):** Session **SES-192**, Conversation **CNV-101**, Topic
**TOP-094**, Reference book **RB-014** (this PRD). All 13 decisions (DEC-451…463) are
`decided_in` SES-192; all 10 requirements (REQ-188…197) are
`requirement_defined_in_conversation` CNV-101 and `requirement_belongs_to_topic` TOP-094,
origin `ai_derived` (REQ-190…196 confirmed via Review-panel sign-off; REQ-188, REQ-189,
REQ-197 still `candidate`). Every PI `planning_item_implements_requirement` and
`planning_item_belongs_to_project`.

**§16.5 follow-on (2026-06-16):** after SES-192 closed, the reconciliation-merge design pass
was recorded under a new session **SES-193** (`session_belongs_to_project` PRJ-031),
conversation **CNV-108** (`conversation_belongs_to_session` SES-193, `_belongs_to_topic`
TOP-094). Decisions **DEC-483…487** are `decided_in` SES-193; requirements **REQ-217…223** are
`requirement_defined_in_conversation` CNV-108 and `requirement_belongs_to_topic` TOP-094, origin
`ai_derived`, status `candidate` (awaiting Review-panel sign-off); **PI-215**
`planning_item_belongs_to_project` PRJ-031, implements REQ-217…223, `blocked_by` PI-208 + PI-205.

**Decisions:**

| # | Concept / Decision | PRD § | Decision | Primary REQ | Primary PI |
|---|---|---|---|---|---|
| D-01 | Frame by planning-vs-development | §2, §12 | DEC-451 | — | — |
| D-02 | Solve by structure, not primarily a lock | §3, §12 | DEC-452 | (all) | (all) |
| D-03 | Unit of possession is the Area | §7, §12 | DEC-453 | REQ-191 | PI-204 |
| D-04 | Area owner is expert decomposer | §7.2, §12 | DEC-454 | REQ-194 | PI-203 |
| D-05 | Global area exclusivity via one-release-in-dev | §6, §12 | DEC-455 | REQ-188 | PI-204 |
| D-06 | Staged release pipeline w/ stage separation | §5, §12 | DEC-456 | REQ-190 | PI-205 |
| D-07 | Fully serial dev lane (Way 2) + rework loops | §6, §12 | DEC-457 | REQ-188/189 | PI-205 |
| D-08 | Area-level (not task-level) handoff | §7.1, §12 | DEC-458 | REQ-192 | PI-206 |
| D-09 | Two levels of QA/testing | §8, §12 | DEC-459 | REQ-193 | PI-206 |
| D-10 | File-level locking backstop (PRJ-030) | §7.2, §12 | DEC-460 | REQ-194 | PI-203 |
| D-11 | Process is unit of change; versioned & tied | §9, §12 | DEC-461 | REQ-196 | PI-208 |
| D-12 | Optimistic-then-reconcile; two temperatures | §5.1, §12 | DEC-462 | REQ-195 | PI-207 |
| D-13 | Model the freeze as its own gate requirement (additive, not reopen) | §4.4, §11.10, §16.7 | DEC-463 | REQ-197 | PI-205/207 |

**Requirements (the §11 invariants) → Planning Items → Projects:**

| REQ | Invariant | PRD § | Implemented by | Project |
|---|---|---|---|---|
| REQ-188 | (1) One release in the lane at a time | §11.1 | PI-204 | PRJ-029 |
| REQ-189 | (2) Lane locked until Shipped | §11.2 | PI-205 | PRJ-031 |
| REQ-190 | (3) Enter lane only when planned completely | §11.3 | PI-205 | PRJ-031 |
| REQ-191 | (4) One owner per area | §11.4 | PI-204 | PRJ-029 |
| REQ-192 | (5) Open only after upstream areas frozen | §11.5 | PI-206 | PRJ-031 |
| REQ-193 | (6) Freeze only after area QA + testing | §11.6 | PI-206 | PRJ-031 |
| REQ-194 | (7) Non-overlapping file locks | §11.7 | PI-203 | PRJ-030 |
| REQ-195 | (8) Conceptual parallel → committed single-threaded | §11.8 | PI-207, PI-209 | PRJ-031, PRJ-033 |
| REQ-196 | (9) Versioned, release-tied change chain | §11.9 | PI-208 | PRJ-032 |
| REQ-197 | (10) Release freeze is a deliberate gate | §11.10 | PI-205, PI-207 | PRJ-031 |

**Rework & Reopen (§14) — decisions and requirements:**

| # | Decision | Decision id | Requirement | Implemented by | Project |
|---|---|---|---|---|---|
| D-14 | Pipeline needs a first-class reopen capability | DEC-464 | — | PI-210 (design) | PRJ-034 |
| D-15 | Narrow scope; frozen plans inviolable | DEC-465 | REQ-198 | PI-211 | PRJ-034 |
| D-16 | Reopen re-serializes (pause/refreeze/resume) | DEC-466 | REQ-199, REQ-200 | PI-212 | PRJ-034 |
| D-17 | Conservative full cascade, no exemption | DEC-467 | REQ-201 | PI-213 | PRJ-034 |
| D-18 | Blast-radius-sized approval | DEC-468 | REQ-202 | PI-214 | PRJ-034 |

| REQ | Rework invariant | PRD § | Implemented by | Project |
|---|---|---|---|---|
| REQ-198 | RW1 Frozen plan never reopened (→ new Release) | §14.3 | PI-211 | PRJ-034 |
| REQ-199 | RW2 Only a frozen area reopens, on downstream need | §14.3 | PI-212 | PRJ-034 |
| REQ-200 | RW3 Reopen pauses downstream until re-freeze | §14.3 | PI-212 | PRJ-034 |
| REQ-201 | RW4 Reopen re-validates every downstream area | §14.3 | PI-213 | PRJ-034 |
| REQ-202 | RW5 Reopen approval sized to blast radius | §14.3 | PI-214 | PRJ-034 |

**File-lock mechanism (§7.3, PRJ-030) — decisions and child requirements (refine REQ-194):**

| # | Decision | Decision id | Requirement | Built by |
|---|---|---|---|---|
| FL-1 | Check-out unit is a named resource | DEC-469 | REQ-203 | PI-203 |
| FL-2 | Detection rules; acquire + verify | DEC-470 | REQ-204 | PI-203 |
| FL-3 | Worktree per sub-agent, serialized merge-back | DEC-471 | REQ-205 | PI-203 |
| FL-4 | Locks in a V2 DB table | DEC-472 | REQ-206 | PI-203 |
| FL-5 | Verify failure → retroactive acquire + record | DEC-473 | REQ-206 | PI-203 |
| FL-6 | Dead sub-agent → owner-supervised reclaim | DEC-474 | REQ-207 | PI-203 |

| REQ | File-lock requirement (refines REQ-194) | PRD § | Built by |
|---|---|---|---|
| REQ-203 | FLR-1 Check-out unit is a named resource | §7.3 | PI-203 |
| REQ-204 | FLR-2 Logical resources defined by detection rules | §7.3 | PI-203 |
| REQ-205 | FLR-3 Worktree-isolated, serialized merge-back | §7.3 | PI-203 |
| REQ-206 | FLR-4 Owner-independent DB locks, verified on diff | §7.3 | PI-203 |
| REQ-207 | FLR-5 Dead sub-agent reclaimed, worktree discarded | §7.3 | PI-203 |

**Reconciliation-merge algorithm (§5.4, §16.5) — decisions and requirements (SES-193 / CNV-108):**

| # | Decision | Decision id | Requirement | Built by |
|---|---|---|---|---|
| D-33 | Three-way merge against the live (latest-shipped) base | DEC-483 | REQ-218 | PI-215 |
| D-34 | Facet-grain conflict unit; typed taxonomy auto-merges non-contradictory overlaps | DEC-484 | REQ-219 | PI-215 |
| D-35 | Contradiction → governed requirements decision, never a silent pick | DEC-485 | REQ-220 | PI-215 |
| D-36 | Output is a conflict-free delta-set; vN+1 authored downstream | DEC-486 | REQ-221 | PI-215 |
| D-37 | Single-writer, dependency-ordered, deterministic, fully traced | DEC-487 | REQ-222, REQ-223 | PI-215 |

| REQ | Reconciliation invariant | PRD § | Built by |
|---|---|---|---|
| REQ-217 | RC-1 No open conflict may leave reconciliation (the gate) | §5.4 | PI-215 |
| REQ-218 | RC-2 Three-way merge against the live base | §5.4 | PI-215 |
| REQ-219 | RC-3 Facet-grain conflict unit + mechanical auto-merge | §5.4 | PI-215 |
| REQ-220 | RC-4 Contradictions escalate to a governed decision | §5.4 | PI-215 |
| REQ-221 | RC-5 Output is a conflict-free delta-set; vN+1 downstream | §5.4 | PI-215 |
| REQ-222 | RC-6 Single-writer, dependency-ordered, deterministic pass | §5.4 | PI-215 |
| REQ-223 | RC-7 Every reconciled change is provenance-linked | §5.4 | PI-215 |

*(REQ-217…223 are `ai_derived` / `candidate`, awaiting Review-panel sign-off; PI-215 belongs to
PRJ-031 and is `blocked_by` PI-208 (versioning base) and PI-205 (the reconciliation stage).)*

**Resolved open questions (decisions):**

| Open Q | Resolution | Decision | Requirement | Built by |
|---|---|---|---|---|
| §16.1 | File-lock mechanism designed | DEC-469…474 | REQ-203…207 | PI-203 |
| §16.3 | Planning serial within area; no backstop | DEC-475 | REQ-208 | PI-209 |
| §16.6 | Release entity designed (intrinsic; composition → §16.2) | DEC-476, DEC-477 | REQ-209, REQ-210 | PI-205 |
| §16.2 | Project-model: R-1 release-scoped + two-home reqs + blocked_by/Topic | DEC-478…480 | REQ-211…213 | PI-205 |
| §16.4 | Versioning: full-definition snapshots, release-tied, live=latest-shipped | DEC-481, DEC-482 | REQ-214…216 | PI-208 |
| §16.5 | Reconciliation-merge: three-way against live base, facet-grain taxonomy, governed-decision conflicts, delta-set output, single-writer traced | DEC-483…487 | REQ-217…223 | PI-215 |

---

## Appendix A — Conversation Transcript (faithful to every turn)

> User turns are reproduced verbatim. Assistant turns are reproduced faithfully in
> substance (the full structured reasoning, options, and questions of each turn), lightly
> condensed from the original prose.

**Turn 1 — User:** "I would like to plan on PRJ-030 - Lets have an indepth discussion where
you repeatedly question me to make sure we have captured all of the options, and made a
decision on what is the best path forward. then we will write the requirements and planning
items to implement this functionality. This will be a good test of the overall governance."

**Turn 1 — Assistant:** Oriented against the V2 DB. Found PRJ-030 = "Source
Check-in/Check-out (pessimistic locking over git)," planned, execution_mode ado. Found the
founding decisions DEC-449 (git is optimistic; build pessimistic check-out/check-in) and
DEC-448 (multi-agent coordination must be enforced cross-process), and the sibling project
PRJ-029 (Multi-Agent Coordination). Laid out the scope boundary (PRJ-029 = who works what;
PRJ-030 = who edits which files; DEC-336 worktrees already isolate orchestrator children),
then offered four foundational mechanism questions (lock granularity, enforcement, lock
store, stale-lock policy) — *which the user declined in favor of a deeper discussion.*

**Turn 2 — User:** "Since this is a critical function, I want to have an in depth
conversation that discusses all options and the strength and weaknesses of each before
making a decision."

**Turn 2 — Assistant:** Agreed to go decision-area by decision-area. Proposed sharpening the
threat model first into two failure modes: **A** concurrent-edit interleaving (solved by a
file lock) and **B** destructive-rollback blast radius from `git reset --hard` (NOT solved
by a file lock — needs isolation). Noted the *who* dimension (orchestrator children already
isolated; human Claude Code sessions and out-of-band work are the real collision surface).
Asked whether B is in scope, what failure mode C might be missing, and how much friction the
human path can absorb.

**Turn 3 — User:** "I think we are talking about two different problems. The first is
assuring that multiple agents can work on the planning/specification side of the equation
without colliding with each other. The second is assuring that the development agents never
step on each other. I think they need to work together, to make sure that the process is
efficient and reliable."

**Turn 3 — Assistant:** Adopted the planning-vs-development framing. Characterized each
side's medium and current protection (planning = governance DB, row-safe but semantically
unprotected; development = git, worktrees for children only). Offered a pivotal scope fork:
**Option X** (one unified locking layer for both) vs **Option Y** (two projects + a handoff
contract). Leaned Y. *(The user redirected away from solution-options toward concept.)*

**Turn 4 — User:** "I would like to discuss the solution, and you keep jumping to solving
the problem before we have a concept."

**Turn 4 — Assistant:** Reset to the concept level. Defined "concept" as the organizing
idea in plain language, free of mechanism. Handed the user the pen and asked for the
everyday analogy / picture in their head.

**Turn 5 — User:** Established hierarchy: 1 Release at top; a Release has one or more
Projects; a Project has one or more Requirements; a Requirement has one or more PIs; a PI
has one or more Workstreams. "Does that make sense so far?"

**Turn 5 — Assistant:** Confirmed, and flagged two spots where the proposed hierarchy
diverged from the live DB (requirement as a *container* of PIs vs today's topic-hung,
implements-edge model; Release *containing* Projects vs today's batch model). Confirmed Work
Task at the leaf.

**Turn 6 — User:** Clarified Topics are cross-release organizers, not release-related; a
requirement is *defined off* a topic but *scheduled via* a release and grouped in a project.
Example: "Contact Management" topic; "Basic Contact Management" + "Basic Company Management"
projects in Release #23.

**Turn 6 — Assistant:** Reflected the **two-structure** model (timeless Topic axis vs
scheduled Release→Project→…→Work Task delivery axis), with the requirement as the hinge.
Asked (1) confirm Work Task at the leaf, (2) the hinge question: can the same requirement /
same topic be live in two projects/releases at once?

**Turn 7 — User:** "1 yep. And it will be broken down by 'Area' and assigned to a single
Area agent…" — described the Data Structure agent being called first for a release, planning
all contact/company data work as the sole writer in that area; UI work allowed in parallel
only if not blocked; then API, then Business Logic. "We segment the code by Area, and only
allow agent or agents that are working off a coordinated work stream to execute."

**Turn 7 — Assistant:** Named the concept: "You don't lock files. You own an Area. Only one
agent owns an Area at a time, and an Area can't start until the Areas it depends on are
done." Two tiers (mechanical area boundary + dependency order; expert judgment within).
Asked (1) is area-ownership exclusive globally or per release, (2) does the same concept
govern the planning side.

**Turn 8 — User:** "Well, almost. The Data Structure agent is an expert on the work task,
and could decide that using multiple sub agents is safe and efficient… adding fields to
contacts and Companies could be done in parallel… Or decide it is risky so only use one. I
think if we break the work tasks into small, focused pieces we should be able to prevent
collisions and keep the agent context small and fast."

**Turn 8 — Assistant:** Corrected the model: the area owner is an **expert decomposer**, not
a forced serializer. Two tiers of collision control (mechanical area boundary;
judgment-based intra-area fan-out). Noted the boundary is the system's one hard guarantee,
so it must be airtight (re-raised global vs per-release exclusivity) and the inside-area
guarantee rests on judgment (raised the backstop question).

**Turn 9 — User:** "Only one release can be in development at a time….."

**Turn 9 — Assistant:** Recognized this as the airtight boundary — global area exclusivity
falls out for free. Three nested rings (releases serial / areas single-owner / expert
fan-out). Asked the seam question: while R23 is in development, can R24 be in planning? —
the plan-N+1-while-build-N pipeline.

**Turn 10 — User:** "Yes, absolutely. Release 24 is in reconciliation, release 25 is in
development planning and releases y-X are in preliminary planning."

**Turn 10 — Assistant:** Named the **staged pipeline / conveyor** with stage separation as
the unifying concept that makes the two problems work together (different releases in
different rooms). Asked for the complete ordered stage list (what comes after development;
does the next release enter only when the prior leaves) and per-stage occupancy.

**Turn 11 — User:** "After development comes testing, then deployment, then shipped, then
the process starts all over… The Planning side may have multiple releases backlogged, or
none. Doesn't matter to the development side… I really think that bottleneck will be getting
the releases planned completely not the development."

**Turn 11 — Assistant:** Completed the conveyor; banked the strategic steer (planning is the
bottleneck). Asked single-track scope (just development one-at-a-time vs whole chain serial)
and the definition of "planned completely," plus whether the planning side has its own
internal collision problem.

**Turn 12 — User:** "You left out QA: Development - QA - Testing… QA is checking to make sure
the development met quality specs not testing."

**Turn 12 — Assistant:** Inserted QA; banked QA≠Testing (conformance vs functional, QA
first). Noted "planned completely" must include the quality specs QA measures against. Kept
the upstream questions open.

**Turn 13 — User:** "I don't understand what you mean by single-track?"

**Turn 13 — Assistant:** Explained single-track plainly: Way 1 (assembly line, only the
Development station one-at-a-time) vs Way 2 (fully serial, one release anywhere in the whole
chain).

**Turn 14 — User:** "Way 2 - fully serial, one release through the whole chain. If there are
problems with deployment, we may have to send the release back to development to fix
problems. So we would be creating a conflict if there was another release already in
development."

**Turn 14 — Assistant:** Confirmed Way 2, and that **rework loops** are the reason — the lane
must be reserved so a bounce-back can't collide. "'Left Development' is not a release point —
only 'Shipped' is." Pivoted to the planning gate.

**Turn 15 — User:** "The spec must be frozen, all requirements decomposed to work tasks and
all work tasks sequenced with prerequisites (Need a database field before you can code an
API!)"

**Turn 15 — Assistant:** Banked the gate (frozen + decomposed + sequenced). Noted all
dependency reasoning moves to planning; area order *emerges* from the work-task prerequisite
graph. Asked the area-level vs task-level handoff question.

**Turn 16 — User:** "Area level. because part of the area level being completed is it passing
area level QA and testing. If you start API work before the database work is frozen, it
could change before you are done."

**Turn 16 — Assistant:** Banked **area = freeze unit** and **never build on unfrozen
ground**; the pipeline recurses at the area level. Asked whether the two QA/test levels split
as area-isolation vs release-integration, and flagged the cascade-rework cost.

**Turn 17 — User:** "Yes. Release level would test the function of the key processes and
requirements. Just because the create contact API works, does not mean that the create
Mentor UI doesn't fail."

**Turn 17 — Assistant:** Banked the two-level split and the requirement-as-through-line.
Declared the back half concept-complete; pivoted to the planning side's internal collision
model (the stated bottleneck). Asked whether the same single-owner-per-segment medicine
applies and what the segment is (Area vs topic/project).

**Turn 18 — User:** "Yes eventually it will break down by areas. But we need to start at the
Process/Feature/entity/persona planning that has to be completed before we can begin to break
it down by area."

**Turn 18 — Assistant:** Recognized planning has a conceptual-definition phase
(Process/Feature/Entity/Persona) preceding area decomposition. Asked the user to lay out the
relationship and order among Process, Feature, Entity, Persona.

**Turn 19 — User:** "Domains are the top organizer. Each domain can have multiple Processes or
Subprocesses. Each process has requirements that define entities, personas, relations.
Processes have version numbers… whenever we change a process the system would track what
changes were made to the requirements that result in changes to the entities/personas/
relations. So the first decision is to make a change to a process (Or cross domain process)
and then define the requirements for the change."

**Turn 19 — Assistant:** Laid out the process-driven change spine (Domain → Process[v] →
Requirements → Entities/Personas/Relations); the unit of change is the Process; versioning is
the provenance spine. Asked the Domain-vs-Topic vocabulary question and surfaced the
shared-resource (entities shared across processes) collision point.

**Turn 20 — User:** "Domains are business process specific topics. Topics are a bit broader
and really just act as an organizer of requirements. Domains are used to align processes
with business units, so they are purely organizational."

**Turn 20 — Assistant:** Locked the vocabulary (Domain organizes Processes by business unit;
Topic organizes Requirements; both purely organizational; only the Process drives change).
Asked whether the **reconciliation** stage is where shared-model conflicts get resolved —
i.e. optimistic-then-reconcile rather than a hard lock.

**Turn 21 — User:** "yep. Once all of the processes and requirements are frozen and organized
into a Release then the planning process can begin. The architect planning agent would look
at ALL of the requirements and decide that the contact entity needed to be revised. It would
then create a VN+1 version of the entity definition tied to the release with the field
changes. Or it could call a Data Structure Planning Agent if it was complex. Then it would
start creating work streams and tasks based on the requirements."

**Turn 21 — Assistant:** Assembled the two-phase planning (Phase 1 conceptual/process-driven;
Phase 2 architecture planning by the Architect Planning Agent producing versioned design +
workstreams/tasks). Named the versioning/provenance governance win and the planning-org/
dev-org mirror. Asked the last two questions: does the planning org get the same
single-owner-per-area medicine, and re-explained the intra-area backstop question (Option A
trust vs Option B mechanical net).

**Turn 22 — User:** "I think the Conceptual planning phase can and should be free to work in
parallel. Some concepts will take longer to mature than others. However, once they are
scheduled into a release, and frozen the reconciliation can start. And that is single
threaded by area. I do not understand question 2."

**Turn 22 — Assistant:** Banked the **two temperatures** (conceptual parallel & free →
reconciliation single-threaded by area once scheduled+frozen). Re-explained Q2 concretely
with the Contacts/Companies example: the intra-area fan-out is the one judgment-based grain;
Option A (trust + small pieces) vs Option B (file locks; overlap → forced serial).

**Turn 23 — User:** "Absolutely B. I just had not discussed that yet. File level locking by
specialist agents!!!"

**Turn 23 — Assistant:** Banked **Option B** — file-level locking by specialist agents as the
backstop, the literal PRJ-030 mechanism precisely located. Played back the entire
consolidated concept and asked for confirmation plus a go-ahead on the project partition.

**Turn 24 — User:** Requested this PRD documenting the full discussion (options + why), then
DB records breaking scope into projects organized into a release, plus anything else to
prevent drift.

**Turn 24 — Assistant:** Proposed anti-drift mechanisms (traceability matrix, read-back diff,
governance-native provenance + Review-panel sign-off, transcript appendix, decisions with
alternatives+rationale, glossary, invariants, non-goals, open-questions register) and the
order of operations (PRD → reconcile → DB records → verification).

**Turn 25 — User:** "First I want to create a PRD file documenting in detail all of our
discussion… Then create the database records… I will then compare the PRD, and my copy of
this context to verify that we do not drift… Is there anything else we can do to make sure we
deliver exactly what we discussed?"

**Turn 26 — User:** "Yes to all three, go ahead and write the PRD with whatever name you
like."

*(This document is the result.)*
