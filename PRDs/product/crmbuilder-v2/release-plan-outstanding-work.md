# Outstanding-Work Release Plan

**Status:** Active planning record — not a governance record. **Model revised 2026-06-23** (see §0).
**Date:** 2026-06-22 (release-scoped model adopted 2026-06-23).
**Author:** Claude Code session (V2 governance DB snapshot, ENG-001 / CRMBUILDER).
**Purpose:** Clear all outstanding V2 work through the **release-scoped project
model** — every body of work delivered as a frozen release whose projects are
born release-scoped inside it.

**Read §0 first.** It carries the model decision now in force and **supersedes**
the old-model framing in §0a and §1–§9 (retained below as the session's planning
history — the 5-release sequence that *batched long-lived projects* is no longer
how this works).

---

## 0. Release-scoped project model — now in force (2026-06-23)

**This supersedes the old-model framing in §0a and §1–§9.** Those sections record
how the plan was first built (a 5-release sequence that *batches long-lived
projects*) and the backlog reorg that was applied; they are retained as history.
The operating model is the release-scoped one described here.

### The decision

**All development goes through a release.** A **Project is a release-scoped
deliverable bundle that belongs to exactly one Release** (REQ-211 — already
enforced at the reference layer; a second `project_belongs_to_release` edge is
rejected). There are **no long-lived parent-project containers** (REQ-213).
Coordination is the exclusive development lane — one release at a time
(REQ-188/189) — plus work-task claims and file locks *within* a release. A PI
that isn't in a frozen release's scope is **not developable**, which structurally
closes the "any session grabs a PI and builds it" hole. Shipping a release
**auto-completes its projects** (REQ-247), so project status finally becomes
honest and automatic.

**Why the old framing was wrong:** it organized the backlog into durable projects
and *batched* them into releases. Under REQ-211/213 that's inverted — a release is
created first and its projects are **born release-scoped inside it**. The timeless
grouping of work is the **Topic/Domain**, not the project.

### Scope: go-forward only

The ~31 **complete** projects are pre-model historical record and are **not**
retrofitted. The model applies to open work and everything new.

### Corrected live state (the §1 snapshot is stale)

Re-grounded 2026-06-23: much of the "outstanding work" the old plan assumed is
**already built** — concurrent sessions cleared it during this planning. **PRJ-039**
(hardening) is complete; **PRJ-040** (observability) closed; **PRJ-041** (agent
redesign) all PIs terminal; **PRJ-043** cost *recording* done — only the
estimate+ceiling gap remains (now **REQ-317/318 + PI-282/283**, pre-run estimate +
start-gate, no mid-run kill). The genuine remaining backlog is far smaller than
§1's "54 open PIs."

### Transition path (Phases A–E)

- **A — Topic is the durable home.** Ensure every open PI's requirement has a
  Topic so projects can safely become ephemeral. Mostly done via the provenance
  work; audit + backfill gaps.
- **B — Build the enforcement gate, flag-gated OFF.** A PI may enter development
  only if it's in a frozen release's scope (the "exactly one release" half is
  already enforced). Behind a flag so it doesn't freeze work in flight.
  *(Adjacent: PRJ-048's requirement-first git-hook enforcement, REQ-320.)*
- **C — Bootstrap release.** Phase B is itself development → it goes through a
  release. Create the first release-scoped release ("Adopt the release-scoped
  model") and **hand-drive it**.
- **D — Migrate the open backlog.** Create the actual delivery releases; create
  release-scoped projects inside them; move open PIs in (Topic homes from Phase A
  preserve the grouping). Retire the long-lived containers — the in_flight ones
  **and PRJ-045/046/047 created in the reorg** — as superseded once emptied.
- **E — Flip enforcement on.** Once data is migrated and free-floating In-Progress
  drains to zero, turn the gate on. From then, no PI develops outside a release.

### What survives the reorg / what changes

The reorg's **triage survives** and is model-independent: the cancels, the defers,
the REQ-148 → PI-229 re-point, REQ-317/318 + PI-282/283. What becomes **Phase-D
migration scaffolding** (to move, not keep): the long-lived containers
PRJ-045/046/047 and the project adoptions. The durable grouping survives in the
requirements' **Topics**.

### Active work during the transition

Flag-gating means active work feels almost nothing — it finishes in place under
the old model; we **drain, then enforce**. The cutover signal is objective: **no
PI `In Progress` outside a release.** Don't migrate a PI while it's actively
worked. Stale/orphaned In-Progress states (PI-161, WSK-009/070, WTK-026/087) need
**reconciling to terminal**, not "letting finish."

### First exercise: the CBM pipeline proof

The active CBM-proof session is the first hand-driven exercise of the model:
conceptual planning (confirm the slice — REQ-195) runs free; **step-3 development
onward runs inside a frozen "CBM pipeline proof" release.** It proves CRMBuilder's
pipeline *and* the release-scoped model at once. The open question it surfaces —
*does a manual driver also walk the automated lane states (`reconciliation →
architecture_planning → ready → development`), or is "frozen + build by hand" the
sanctioned manual path?* — becomes the concrete input that defines Phase B's gate.

### The old release THEMES, re-expressed

The §0a / §5 groupings survive only as *themes* for delivery releases, now built
release-scoped: **cost-controls** (PI-282/283 gap), **production** (PRJ-019/020
PIs), **features** (PRJ-017/027/018 PIs), **methodology** (PRJ-023 PIs). Each
becomes a release whose projects are born inside it — not a batch of pre-existing
long-lived projects. REL-0/REL-A are largely moot (already built).

---

## 0a. Decisions locked — the backlog reorg (2026-06-22, applied · old model)

1. **§3a cancels:** Cancel **PI-267** (redundant w/ Resolved PI-268), **PI-198**
   (bug delivered by the REQ-251 `/review/approvals` path; re-point **REQ-148 →
   PI-229**), **PI-023** (git-vs-DB reconcile utility never built, driver
   mitigated). *Also cancelling the clear-cut §3a items **PI-084** (superseded
   by PI-085), **PI-047** (benign gap), **PI-008** (obsolete watcher); parking
   **PI-033** as Deferred pending a backfill-value call.*
2. **CDS overlap:** Cancel **PI-089**, keep **PI-161**.
3. **PI-234 scope:** Operator-selected **seed/reference** export (not full clone).
4. **New projects:** Create **V2 Methodology Schema Enrichment** (parked /
   Deferred), **Cross-Engagement Reference Libraries**, and a **PRJ-042
   successor (publish/engine)**.
5. **Granularity:** Instrumentation-first — **5 releases** (REL-0 … REL-D).
6. **Bootstrap posture:** Build **REL-0 by hand**; run **REL-A → REL-D through
   the agent lanes** with instrumentation live.

---

## 1. Snapshot of the current state

> ⚠️ **Superseded by §0.** This 2026-06-22 snapshot is stale — concurrent sessions
> resolved much of "Pile 1" during planning (PRJ-039/040/041 are now done). Kept
> for history; do not plan from these counts.

Pulled live from the API on 2026-06-22:

- **43 projects total** — 31 terminal (complete/cancelled/superseded), **12 active** (in_flight/planned).
- **277 planning items total** — 211 Resolved, 6 Cancelled, 6 Deferred, **54 open** (51 Draft, 2 Ready, 1 In Progress).
- The 54 open PIs split into two very different piles:
  - **Pile 1 — live work:** 15 PIs sitting under 8 active projects (the real near-term backlog).
  - **Pile 2 — legacy orphans:** ~39 Draft PIs with **no project**, mostly created 05-11 → 05-28-26, plus PI-234 stranded under the (now complete) PRJ-024.

### The gating insight (why this isn't one step)

The release pipeline composes **projects** into a release; freeze hands each PI
to the agent lanes. But the lanes can only build a PI that satisfies the
ENG-001 precondition: **a confirmed requirement + an implementing-PI edge +
`Ready` status**. Today:

- Only **15 of 54** open PIs carry a `planning_item_implements_requirement` edge.
- Only **2 are `Ready`**, 1 `In Progress`; everything else is `Draft`.

So in front of every release there is a **human prep gate** — confirm
requirements (Review panel), then decompose each PI to `Ready`. That prep is
your work; it cannot be delegated to the lanes. The good news: 13 of the 15
live PIs already have requirement edges, so they're close — they mostly need
decompose-to-Ready, not net-new requirement authoring.

---

## 2. Active projects (Pile 1 — the live work)

| Project | Status | Open PIs | Req-ready? |
|---|---|---|---|
| **PRJ-039** Release Pipeline Agent Hardening | planned | PI-269, 270, 271, 272 (+267) | all have req edges |
| **PRJ-040** Process Pipeline Improvements | planned | PI-273 | req edge ✓ |
| **PRJ-027** Multi-Instance CRM Audit & Inventory | in_flight | PI-201, 255, 256 | 201/255 ✓, 256 ✗ |
| **PRJ-020** Multi-User & Concurrency Safety | in_flight | PI-135, 136 | both ✓ |
| **PRJ-017** YAML Schema v1.3 — RBAC | in_flight | PI-051 | ✓ |
| **PRJ-018** Agent Delivery Organization | in_flight | PI-202 (Ready) | ✓ |
| **PRJ-019** Production Database Architecture | in_flight | PI-100 | ✓ |
| **PRJ-023** Master CRMBuilder PRD consolidation + dogfood | in_flight | PI-161 (In Progress) | ✓ |
| **PRJ-041** Agent System Redesign (target model) | planned | — (no PIs decomposed) | needs scoping |
| **PRJ-043** AI Cost Estimation & Overspend Controls | planned | — (no PIs decomposed) | needs scoping |
| **PRJ-038** Preserve Failed-Run History | in_flight | — (PIs resolved) | — |
| **PRJ-028** claude.ai-web MCP connector | in_flight | — | **parked, upstream-blocked** |

Two of these (**PRJ-041**, **PRJ-043**) are real near-term intent but have **no
PIs yet** — they need a scoping/decompose pass before they can enter a release.

---

## 3. Legacy backlog triage (Pile 2 — the ~40 orphans)

Per your decision to fold triage into this plan, here is a per-PI
recommendation. Grouped by disposition. **C** = Cancel, **D** = Defer (real but
trigger-gated), **A→PRJ** = adopt into a project, **NEW** = belongs to a new
project to be created.

### 3a. Cancel — superseded, obsolete, or accepted-benign (verify, then cancel)

| PI | Title | Why cancel |
|---|---|---|
| PI-084 | Create governance-recording rules `.md` | Superseded by PI-085 (DEC-311); the rules were migrated into the DB under TOP-013 by PI-130. The `.md` was retired. |
| PI-047 | ses_030/ses_036 duplicate-session artifact | Accepted as a benign permanent identifier gap; real content lives at SES-036. No action warranted. |
| PI-008 | Inbox folder watcher for close-out payloads (v0.3 desktop) | Obsolete — DEC-383 moved governance recording to real-time direct API POST in Claude Code; the watcher pattern is dead. |
| PI-023 | Workstream-state reconciliation utility at kickoff | Likely obsolete under the Model A branch protocol + real-time recording. **Verify** before cancelling. |
| PI-033 | Back-fill historical resolutions/work_tickets/commits | Low value now; the corpus it would backfill is historical. **Verify** want vs cancel. |
| PI-198 | Fix Requirements Review Approve to stamp `approved_at` | Almost certainly already delivered by the requirements-provenance rebuild (PR #4/#5, "COMPLETE 06-13"). **Verify the code; if fixed, resolve/cancel.** |
| PI-267 | Redundant-work killers | Overlaps today's merged `pi-268-redundant-work-killers` (commit 05d77a8b, REQ-265/267/272). **Verify it isn't already delivered** — if so resolve; else it's a live PRJ-039 item. |

### 3b. Defer — real future work, gated on the CBM-redo signal (group into one parked project)

These are the v0.6+ methodology-schema-enrichment items, almost all explicitly
"gated on CBM-redo signal." They follow the multi-deferral pattern and have no
live trigger. **Recommendation: create one project `V2 Methodology Schema
Enrichment` to hold them, leave them `Deferred`, and pull them into a release
only when the CBM redo actually surfaces the need.**

PI-006 (parent-prefix retrofit), PI-007 (domain.short_code), PI-009 (Domains
column), PI-011 (process priority field), PI-012 (crm_candidate enums),
PI-054 (field re-parent UX), PI-055 (field_type vocab), PI-056 (default-value +
filters), PI-057 (required-ness rules), PI-058 (field-to-field deps), PI-059
(derived-field lineage), PI-060 (soft-delete cascade posture).

### 3c. Adopt into PRJ-023 (Master PRD / methodology dogfood)

These are the methodology/process-definition content items — the actual dogfood
work PRJ-023 exists to do. Adopt them under PRJ-023 (note the internal
dependency chain on the governance-domain group):

PI-069 (draft remaining Master-PRD phases), PI-070 (retire transitional
headers), PI-071 (store client-provided info), PI-072 (engagement-level setup
process), PI-085→086→087→088 (governance Domain → Personas → Process PRD → meta
Process PRD — serial `blocked_by` chain), PI-089 (Cross-Domain Service entity),
PI-094 (user/role participant model), PI-095 (promote Phase-2 candidate
records). *Note: PI-089 (Cross-Domain Service entity) overlaps the In-Progress
PI-161 under PRJ-023 — reconcile or cancel one.*

### 3d. New project — `Cross-Engagement Reference Libraries`

A coherent cluster (Skills / Patterns / Inventories + the store that backs
them). **Recommendation: new project; PI-062 is the architecture foundation the
other five depend on.**

PI-062 (cross-engagement reference store architecture — foundation), PI-063
(Skills), PI-064 (Patterns), PI-065 (Inventories), PI-066 (Skill
trigger/loading), PI-067 (authoring tooling/UI).

### 3e. Adopt into an existing active project (small, well-scoped)

| PI | Title | Adopt into |
|---|---|---|
| PI-103 | Edit-locking for promoted records (modify-modify protection) | **PRJ-020** (Concurrency) |
| PI-046 | vocab.py reference-target schema-vs-spec contradiction | **PRJ-020** or a tech-debt sweep — small bug, verify still present |
| PI-020 | Cross-file layout aggregation in deploy engine (V1) | A V1-engine/publish project (PRJ-042 is complete → needs a successor) |
| PI-234 | Audit record-data transfer (REQ-130, confirmed) | **PRJ-027** — but needs your all-records-vs-seed scope call first |

---

## 4. Project consolidation needed before releases

To make the backlog releasable, these structural moves come first:

1. **Create** `V2 Methodology Schema Enrichment` (parked) — adopt §3b, set Deferred.
2. **Create** `Cross-Engagement Reference Libraries` — adopt §3d.
3. **Create** a V1-engine/publish successor (PRJ-042 is complete/terminal) if PI-020 and the deferred YAML-publish R3 work are to live somewhere.
4. **Adopt** §3c PIs into PRJ-023; **adopt** §3e PIs into PRJ-020 / PRJ-027.
5. **Cancel** §3a (after the three verifies).
6. **Scope** PRJ-041 and PRJ-043 into PIs (each needs a requirement + decompose pass).

---

## 5. Proposed release sequence

> ⚠️ **Superseded by §0 (old model).** This sequence *batches long-lived projects*
> into releases — the inverted model. Under the release-scoped model a release is
> created first and its projects are born inside it. The themes below survive
> (cost / production / features / methodology); the mechanic does not. REL-0/REL-A
> are largely moot — already built.

Releases are ordered so the pipeline becomes trustworthy and the platform solid
*before* large autonomous batches and feature work. Each release = a set of
projects added in the Releases panel Composition tab; freeze hands off to lanes.

### REL-0 — Instrumentation (built BY HAND, first)
**Projects:** PRJ-040 (pipeline observability), PRJ-043 (AI cost estimation + overspend controls).
**Why first / by hand:** this is the safety net every later agent run depends
on. Running it through the lanes would mean building the cost cap and
observability with a pipeline that has neither — the highest un-instrumented
risk. So REL-0 is built directly. PRJ-040 and PRJ-043 both need scoping into PIs
(+ confirmed requirements) before build.

### REL-A — Pipeline hardening
**Projects:** PRJ-039 (agent hardening), PRJ-038 (failed-run history, already in flight).
**Why second:** fixes the REL-005 failure modes — redundant rebuilds,
over-scoped decomposition, verification spins, inherited stale decompositions —
now run **through the agent lanes** with REL-0's observability + cost ceiling
live. First release the lanes execute; watch the first run closely.
**Prep gate:** PI-269/270/271/272 already have requirement edges → decompose to Ready.

### REL-B — Production foundation
**Projects:** PRJ-019 (Production DB on Postgres), PRJ-020 (Multi-User & Concurrency, incl. adopted PI-103/PI-046).
**Why second:** concurrency safety and the Postgres substrate underpin running
many agents/users at scale — earn this before the feature releases lean on it.
**Prep gate:** PI-100/135/136 have req edges → decompose to Ready; confirm requirements for adopted PI-103/PI-046.

### REL-C — Product / feature work
**Projects:** PRJ-017 (RBAC / YAML v1.3), PRJ-027 (Multi-instance audit, incl. adopted PI-234), PRJ-018 (ADO content-work integration).
**Why third:** customer-facing capability, safe to batch once the pipeline and
platform are hardened.
**Prep gate:** PI-051/201/255/202 have req edges; **PI-256 lacks a requirement** → author + confirm. Make the PI-234 all-vs-seed scope decision.

### REL-D — Methodology + agent redesign
**Projects:** PRJ-023 (Master-PRD dogfood, incl. all adopted §3c PIs), PRJ-041 (Agent System Redesign).
**Why last:** the largest, most exploratory body of work; benefits from a fully
hardened pipeline and is naturally iterative (draft → run → refine).
**Prep gate:** heavy — most §3c PIs have no requirement yet; PRJ-041 needs full
scoping. Expect this release to be authored incrementally, not as one freeze.

### Parked / not in any release
- **PRJ-028** — claude.ai-web connector, upstream-blocked. Leave parked.
- **`V2 Methodology Schema Enrichment`** (§3b) — Deferred until CBM-redo signal.
- **`Cross-Engagement Reference Libraries`** (§3d) — sequence after REL-D or as
  a REL-E once its value is pulled forward; PI-062 architecture gates the rest.

---

## 6. Execution mechanics (per release)

For each release, in order:

1. **Triage/adopt** the relevant PIs into their project (§3–§4) — direct API writes.
2. **Confirm requirements** for every PI in the release via the Requirements
   Review panel (the human approval gate — not a status edit).
3. **Decompose each PI to `Ready`** (decompose → scope → workstreams Ready) so
   the lanes will pick it up.
4. **Releases panel → New Release**, add the release's projects in the
   Composition tab, set title/notes.
5. **Freeze** the release (freeze = the hand-off transition to lane execution).
6. **Watch** the run in the Releases panel (Overview/Conflicts/Reopens) and the
   Resource Locks monitor; intervene on Needs-Attention.
7. **Ship** when the QA/test gate (Release Lead) passes.

---

## 7. Decisions — settled (see §0 for the locked outcomes)

All six walked and locked on 2026-06-22. §0 carries the outcomes.

## 8. Application checklist (structural bookkeeping) — ✅ APPLIED 2026-06-22

Recorded under **SES-246** + **DEC-641**. New projects created: **PRJ-045**
(V2 Methodology Schema Enrichment), **PRJ-046** (Cross-Engagement Reference
Libraries), **PRJ-047** (YAML Publish & Engine). Cancelled: PI-267/198/023/089/
084/047/008. Deferred: PI-033 + §3b cluster. REQ-148 re-pointed to PI-229.
All orphan PIs adopted — **zero non-terminal PIs without a project**.

Original checklist (all done):

- **Cancel** PI-267, PI-198, PI-023, PI-084, PI-047, PI-008, PI-089 → status Cancelled.
- **Re-point** REQ-148: drop `PI-198 implements REQ-148`, add `PI-229 implements REQ-148`.
- **Defer** PI-033 (backfill — pending value call) and the 12 §3b PIs → status Deferred.
- **Create** 3 projects: `V2 Methodology Schema Enrichment`, `Cross-Engagement Reference Libraries`, PRJ-042 successor.
- **Adopt** (planning_item_belongs_to_project edges):
  - §3c → PRJ-023: PI-069, 070, 071, 072, 085, 086, 087, 088, 094, 095
  - §3b → Methodology Schema Enrichment (then Deferred): PI-006, 007, 009, 011, 012, 054–060
  - §3d → Cross-Engagement Reference Libraries: PI-062, 063, 064, 065, 066, 067
  - PI-103, PI-046 → PRJ-020; PI-020 → PRJ-042 successor; PI-234 → PRJ-027 (re-home off complete PRJ-024)

## 9. Per-release prep gate (your lane — staged after the reorg)

For each release in order (REL-0 by hand; REL-A→D through lanes):

1. Confirm every PI's requirement via the Requirements Review panel (the human gate).
2. Decompose each PI to `Ready`.
3. (REL-A→D) Compose the release in the Releases panel → freeze → watch → ship.

REL-0 and REL-A still need PIs scoped where missing: PRJ-040, PRJ-043, PRJ-041,
PRJ-043 have no PIs decomposed yet; PI-256 (PRJ-027, REL-C) lacks a requirement.
