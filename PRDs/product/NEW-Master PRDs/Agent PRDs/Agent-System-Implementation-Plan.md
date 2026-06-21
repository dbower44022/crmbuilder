# Agent System — Implementation Plan (target model → build)

> **Status:** DRAFT plan, **2026-06-20**. Turns `Agent-System-Target-Model.md`
> (decisions D1–D16) into a sequenced, governance-gated build, by diffing the
> target against the built system (`Agent-System-Technical-Reference.md`).
>
> **This is not authorization to build.** Per the repo `CLAUDE.md`
> ("governance is a precondition"), every phase below needs — *before any code* —
> a **confirmed requirement** (human-approved via the decision path) and an
> **implementing PI** inside a project. This plan **proposes** those; it does not
> create them. §6 maps each phase to the requirement/PI it needs.
>
> **Companion docs (same folder):** the **target** is `Agent-System-Target-Model.md`;
> the **built reality** is `Agent-System-Technical-Reference.md`.

---

## 1. Approach & guardrails

1. **The built system keeps working throughout.** This is a migration of a live,
   working pipeline, not a greenfield build. The existing **per-PI** execution
   path stays operational until the **per-area** path is proven, then we cut over.
2. **Incremental, governance-gated.** Each phase is one (or a few) PIs under a
   single redesign **project**; nothing is built before its requirement is
   confirmed and its PI exists.
3. **Reuse the substrate.** The data/access layer, the reconciliation engine, the
   versioning spine, the registry resolver/lifecycle, the locks, the release
   stage-machine, and the QA/Test gate Agent are **kept** — most of the work is
   *additions and a back-half replacement*, not a rewrite.
4. **Verify per phase.** Every phase ends with a concrete check (tests, a demo
   run, or a live-DB read), mirroring the target's "the build is verified"
   principle.
5. **Dogfood.** Building this *is* agent-system work in the system's own areas
   (storage/access/api/ui/mcp/…). The current built pipeline + humans bootstrap
   the redesign.

---

## 2. Gap analysis (target vs built)

Action key: **REUSE** (keep as-is) · **EXTEND** (add to) · **CHANGE** (alter
behavior) · **NEW** (build from scratch).

| Target component | Built today | Action |
|---|---|---|
| "scheduler" naming | code is literally `*_runtime.py` in `runtime/` | **CHANGE** (rename) |
| Uniform task contract (status vocab + persisted outputs) | heterogeneous statuses/results across tasks | **CHANGE** (refactor to a common interface) |
| Reconciliation (Demands Agent + merge + conflicts) | exists | **REUSE** |
| Persist the reconciled change-set | re-derived on demand, not stored | **NEW** (small) |
| Reconciliation Review (human task) | deterministic gate, no review task | **NEW** |
| Architecture-Planning (designs + decompose + sequence) | exists | **REUSE** |
| Architecture-Planning Review (human task) | deterministic gate, no review task | **NEW** |
| Release Scheduler **monitor** + single-occupancy arbitration | pointed at one release; single-occupancy gate exists, no scan | **EXTEND** |
| Freeze gate: not-all-PIs-ready = ready-or-**explicitly-deferred** | defers not-ready PIs (no explicit human action) | **CHANGE** |
| Per-area **Design** task (WHAT/HOW split → implementation + testable spec) | no per-area design; no testable-spec artifact | **NEW** (big) |
| Design Review (consolidated human task) | none | **NEW** |
| Per-area **Develop** Agents | one **generic** Coding Agent for all areas | **CHANGE** (big) |
| Per-area **Test** Agents (blind, independent) | tests written by the coding agent (not blind) | **NEW** (big) |
| Two-level testing (per-area + release gates) | release-level QA/Test gates only | **EXTEND** |
| Registry catalog of 31 per-`(area,tier)` profiles | 5 profiles seeded | **EXTEND** |
| QA gate + Test gate (Release-gate Agent) | exists | **REUSE** |
| Ship Approval (human gate) | deployment→shipped, no human sign-off | **NEW** |
| Substrate: repos, reconciliation engine, versioning spine, locks, coordination, reopen, registry resolver/lifecycle, migration lock | exist | **REUSE** |

**The headline:** the front half and substrate are largely **REUSE/EXTEND**; the
genuinely large build is the **per-area matrix back half** (Design/Develop/Test)
plus the **uniform task contract** refactor.

---

## 3. Phased plan

Each phase: **goal · scope · depends-on · areas touched · risk · verification ·
proposed requirement + PI.** Sizes are rough estimates (S/M/L/XL).

### Phase 0 — Foundations (enables everything) — **L**
- **Goal.** Align the code with the target's vocabulary and task interface.
- **Scope.**
  - **0a Rename `runtime → scheduler`** (`CHANGE`): modules, symbols, the
    `runtime/` dir → `scheduler/`, CLI scripts (`crmbuilder-v2-ado` etc.
    descriptions), the commit-message string, and the DB topic "TOP-012 Runtime &
    Scheduling". Mechanical; clears the documented legacy-name debt.
  - **0b Uniform task contract** (`CHANGE`): introduce the status vocabulary
    (`not_started/in_progress/succeeded/needs_human/failed`) and the
    persisted-output-per-task discipline as the scheduler's common interface;
    retrofit existing tasks behind it.
- **Depends on.** Nothing.
- **Areas.** access, api, storage (status columns/edges), mcp.
- **Risk.** 0a is churn-heavy → do it when the runtime is **quiet** (no active
  ADO runs) to avoid merge conflicts. 0b is conceptually large → apply
  **incrementally per task**, not big-bang.
- **Verification.** Full test suite green; a dry-run ADO loop on the renamed
  modules.
- **Proposed:** REQ "scheduler vocabulary + uniform task contract" → PI(s) 0a, 0b.

### Phase 1 — Front-half completion — **M**
- **Goal.** Bring reconciliation/architecture-planning up to the target shape.
- **Scope.**
  - Persist the **reconciled change-set** as a durable, reviewable artifact
    (`NEW`, small) — alongside the existing demand-set + conflicts.
  - **Reconciliation Review** + **Architecture-Planning Review** tasks (`NEW`):
    first-class human tasks emitting sign-off records; the release transitions
    gate on the sign-off, not just the deterministic check.
  - **Freeze gate: ready-or-deferred** (`CHANGE`): replace silent auto-defer with
    the explicit human **defer** action; freeze blocks unless every in-scope PI
    is `ready` or explicitly deferred.
- **Depends on.** Phase 0 (task contract).
- **Areas.** access, api, ui (the review surfaces).
- **Risk.** Low — additive to a working front half.
- **Verification.** A frozen test release runs reconciliation → review → planning
  → review with persisted artifacts + sign-offs; a not-ready PI blocks freeze
  until deferred.
- **Proposed:** REQ "human-reviewed front half + explicit defer" → PI(s).

### Phase 2 — Release Scheduler & Ship Approval — **M**
- **Goal.** Make the release start/finish match the target's human-commit ends.
- **Scope.**
  - **Release Scheduler monitor** (`EXTEND`): scan for **frozen** releases and
    auto-run each end-to-end; **single-occupancy arbitration** when several
    compete (raise `needs_human` rather than guess). (The single-occupancy *gate*
    already exists; this adds the scan + arbitration.)
  - **Ship Approval** task (`NEW`): a human gate before `deployment → shipped`,
    symmetric to freeze.
- **Depends on.** Phase 0.
- **Areas.** api, ui, automation.
- **Risk.** Low–medium (the monitor must not double-dispatch; reuse the existing
  single-occupancy predicate).
- **Verification.** Two frozen releases → only one enters the lane; the other
  waits; ship requires a recorded approval.
- **Proposed:** REQ "release monitor + ship approval" → PI(s).

### Phase 3 — Registry catalog — **M** (prerequisite for Phase 4)
- **Goal.** Populate the registry with the per-`(area,tier)` Agent profiles the
  back half resolves.
- **Scope.** Seed the **31 per-area profiles** (§4.12 of the target): build areas
  × {architect, developer, tester} + the four methodology architect profiles —
  each with starter skills + governance rules; learnings accrue at runtime
  (`EXTEND` of `registry_seed`). The resolver/lifecycle already exist.
- **Depends on.** Phase 0.
- **Areas.** storage (rows), access (resolver wiring), mcp.
- **Risk.** Low (additive rows); the *content* of each profile prompt is the real
  effort and can start thin (one good Architect/Developer/Tester template
  per area, refined by learnings).
- **Verification.** `resolve_contract` returns a sensible contract for each
  `(area,tier)`; a spot-check spawn per tier.
- **Proposed:** REQ "per-area agent profile catalog" → PI(s).

### Phase 4 — The matrix back half — **XL** (the core build)
- **Goal.** Replace per-PI execution with per-area Architect → Developer → Tester.
- **Scope.**
  - **Per-area Design task** (`NEW`): scheduler fans out one Design task per
    touched area to the area's Architect Agent; produces the **implementation +
    testable spec** (a new versioned artifact type) + feed-forward by area rank.
  - **Design Review** (`NEW`): one consolidated human sign-off over all area specs.
  - **Per-area Develop** (`CHANGE`): per-area Developer Agents build to the spec
    and self-verify; locks become a backstop only.
  - **Per-area Test (blind)** (`NEW`): per-area Tester Agents implement the
    testable spec blind to the dev code; `failed` bounces to that area's Develop.
  - **Two-level testing** (`EXTEND`): wire per-area Test under the existing
    release-level QA/Test gates.
- **Depends on.** Phases 0 and 3 (contract + profiles).
- **Areas.** all build areas + access/api/storage (new spec artifact + scheduler
  fan-out).
- **Risk.** **Highest.** Build it **parallel to the live per-PI path** (a flag /
  separate lane), prove it on a small real release, then cut over. The blind-test
  independence and the new testable-spec artifact are the novel pieces.
- **Verification.** A real small release delivered end-to-end through the per-area
  back half, with an independent Tester catching a seeded defect.
- **Proposed:** REQ "per-area matrix execution (Architect/Developer/Tester)" →
  several PIs (Design, Develop, Test, two-level wiring).

### Phase 5 — Cutover & retire — **M**
- **Goal.** Make per-area the default; remove the superseded per-PI path.
- **Scope.** Switch the scheduler's back half from per-PI to per-area by default
  (`CHANGE`); retire the generic Coding-Agent path and the built auto-defer
  (`CHANGE`/remove); update built docs to fold target → built.
- **Depends on.** Phase 4 proven.
- **Areas.** access, api, ui, mcp.
- **Risk.** Medium (removal) — keep a revert path until a full release ships on
  per-area.
- **Verification.** A full release ships per-area; old path removed; suite green.
- **Proposed:** REQ "cut over to per-area; retire per-PI" → PI(s).

---

## 4. Dependency order

```
Phase 0 (foundations: rename + task contract)
   ├─► Phase 1 (front-half completion)        ─┐
   ├─► Phase 2 (release scheduler + ship)      ─┤  (1 & 2 can run in parallel)
   └─► Phase 3 (registry catalog) ─► Phase 4 (matrix back half) ─► Phase 5 (cutover)
```

Critical path: **0 → 3 → 4 → 5** (the back half). Phases 1 and 2 are independent
once 0 lands.

---

## 5. Risks & mitigations

- **Migrating a live system.** Mitigation: per-area path built parallel to the
  per-PI path; cutover only after a real release ships on it (Phase 5).
- **Phase 0 churn vs in-flight work.** Do the rename during a runtime-quiet
  window; land it as one isolated PI.
- **Uniform-contract refactor scope creep.** Apply per task, not big-bang;
  measure by "every task exposes the status vocabulary."
- **Thin agent profiles.** Start each `(area,tier)` profile with one solid
  template; rely on the learning write-back to improve them over releases.
- **Blind-test practicality.** The Tester needs a runnable build + a precise
  testable spec; if specs are weak, testing regresses to checking code — so the
  Design task's spec quality is the load-bearing dependency for Phase 4.

---

## 6. Governance mapping (per the precondition rule)

Recommended container: **one project — "Agent System Redesign (target model)"** —
with the phases as PIs. **Before any phase's code:** author its requirement(s),
confirm them via the decision path, and create the implementing PI(s). The
target-model decisions **D1–D16** are the design provenance each requirement
traces to.

| Phase | Proposed requirement (capability) | Proposed PI(s) |
|---|---|---|
| 0 | scheduler vocabulary + uniform task contract | 0a rename, 0b contract |
| 1 | human-reviewed front half + explicit defer | 1 |
| 2 | release monitor + ship approval | 2 |
| 3 | per-area agent profile catalog | 3 |
| 4 | per-area matrix execution | 4-Design, 4-Develop, 4-Test, 4-wiring |
| 5 | cut over to per-area; retire per-PI | 5 |

*(These are proposals. Creating the requirements/decisions/PIs in the V2 DB is
the actual governance step — human-owned — and is not done by this document.)*

---

## 7. Open questions

- **Phase 0 ordering:** rename first (clean vocabulary, but churn) vs. last (less
  churn, but the codebase contradicts the docs longer). Recommendation: early,
  in a quiet window.
- **Uniform-contract depth:** how strictly to retrofit *every* existing task vs.
  apply the contract only to new/changed tasks. Recommendation: standard for new;
  retrofit opportunistically.
- **Per-area profile authorship:** who writes the initial 31 profile prompts —
  and can the existing proven storage/model/planning/release prompts seed the
  pattern for the rest?
- **Cutover unit:** cut over all areas at once (Phase 5) vs. area-by-area.

---

## Sources

- `Agent-System-Target-Model.md` (decisions D1–D16) — the target.
- `Agent-System-Technical-Reference.md` — the built reality (gap baseline).
- Repo `CLAUDE.md` — the governance precondition this plan defers to.
