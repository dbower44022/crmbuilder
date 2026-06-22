# Agent System — Phase 4 Scoping (the matrix back half)

> **Status:** SCOPING DRAFT, **2026-06-21**. Turns the implementation plan's Phase 4
> sketch into a concrete, decomposed, buildable plan. **This is design work that
> precedes the requirement(s)** — per the repo `CLAUDE.md` governance precondition,
> no Phase 4 code is written until its requirement is confirmed and an implementing
> PI exists. This document proposes that decomposition; it does not authorize a build.
>
> **Companions:** `Agent-System-Target-Model.md` §4.5–§4.8 (the target), `Agent-System-
> Implementation-Plan.md` §3 Phase 4 (the sketch), `Agent-System-Technical-Reference.md`
> (built reality). Phases 0, 1, 3 are complete; Phase 4 depends on 0 (task contract)
> + 3 (the per-(area,tier) profile catalog), both done.

---

## 1. Goal

Replace **per-PI** execution with a **per-area matrix**: across one release, each
touched area is taken through **Design → (Design Review) → Develop → Test** by that
area's Architect / Developer / Tester Agents, sequenced by area layer rank and run
in parallel where independent. Two novel guarantees: a **testable spec** the Tester
implements **blind** to the Developer's code, and **front-loaded human review** of
the designs (no per-area review after build).

This is the redesign's **core, highest-risk build (XL)**. It is built **beside** the
live per-PI path and cut over only after it ships a real release (Phase 5).

---

## 2. Built vs target — the load-bearing shift

**Built (per-PI):** a release's dev lane delegates each in-scope PI to the ADO
scheduler (`ado_scheduler.py`); that PI was decomposed (`decompose_planning_item_direct`)
into serial **Design → Develop → Test** phase Workstreams (the four-step model,
PI-129/DEC-392), each holding **single-area Work Tasks**. The scheduler walks a PI's
phases; `parallel_scheduler.py` spawns one Claude Code agent per Work Task in a git
worktree off `main`, verifies by result, merges, with a file-lock backstop.

**Target (per-area):** the **area** is the primary axis **across the whole release**.
The scheduler fans out **one Design task per touched area** (→ impl + testable spec),
gates on **one consolidated Design Review**, then **one Develop task per area** (build
to spec, self-verify, merge), then **one Test task per area** (implement the testable
spec **blind**, bounce to Develop on fail). Per-area Test sits under the existing
release-level QA/Test gates (two-level).

**The shift is the unit of fan-out**, not the D/D/T vocabulary (which already exists).
The single-area Work Tasks the per-PI decomposition already produces are the raw
material; Phase 4 **re-aggregates them by area across all in-scope PIs** and drives
each area through D/D/T as a release-wide pass.

---

## 3. Gap analysis (REUSE / CHANGE / NEW)

| Piece | Built today | Phase 4 |
|---|---|---|
| Agent spawn runtime (worktree off `main`, `claude -p`, verify-by-result, merge, file-lock backstop) | `parallel_scheduler` / `coordinating_scheduler` | **REUSE** |
| Registry contract resolution (`select_profile_id` + `resolve_contract`) per (area,tier) | dispatcher + resolver; **catalog now seeded (Phase 3)** | **REUSE** |
| Work Tasks as single-area units | exist (`work_tasks`, `area`) | **REUSE** (re-aggregated by area) |
| Release-level QA gate + Test gate + Release-gate Agent (AGP-005) | exist | **REUSE** |
| Findings (`finding`, PI-134) + area-reopens (PI-212) for rework | exist | **REUSE** (the Test→Develop bounce substrate) |
| D/D/T phase vocab | exists (Design/Develop/Test) | **REUSE** |
| Per-area **implementation + testable spec** artifact | **does not exist** (only product-design snapshots in `artifact_versions`) | **NEW** |
| Scheduler **per-area fan-out** (route by area, sequence by rank, parallel) for D/D/T | per-PI phase walk | **CHANGE** (big) — the new back-half driver |
| **Design Review** (one consolidated human sign-off over all area specs) | none (planned-completely is deterministic) | **NEW** (reuses the PI-238 sign-off pattern) |
| Per-area **Develop** to an approved spec | generic per-Work-Task build | **CHANGE** (key on area + spec input) |
| Per-area **blind Test** + bounce-to-Develop | test phase is thin; tests written by the builder | **NEW** (big) — the blind-independence guarantee |
| Two-level testing (per-area Test under release QA/Test) | release-level gates only | **EXTEND** |
| Parallel-lane / cutover safety | single per-PI path | **NEW** (a flag / separate lane; Phase 5 cuts over) |

**Headline:** the runtime, contract resolution, Work Tasks, release gates, and the
rework substrate are all **REUSE**. The genuinely new build is (a) the **testable-spec
artifact**, (b) the **per-area fan-out driver**, (c) **blind Test + bounce**, and
(d) the **Design Review** gate. The Developer tier is the smallest change (reuses the
runtime, keyed by area + spec).

---

## 4. Proposed decomposition (PIs)

Sequenced; each ends with a concrete verification. Built **parallel to the live
per-PI path** throughout — nothing here removes the per-PI path (that is Phase 5).

- **4a — Testable-spec artifact (NEW, foundation).** A per-(release, area) durable,
  versioned, reviewable **implementation spec + testable spec** record (schema +
  access + API), alongside `artifact_versions`. *Areas:* storage/access/api.
  *Verify:* author + read back a spec for an area; survives re-run.

- **4b — Per-area Design fan-out (CHANGE/NEW).** The scheduler driver that, for a
  release, computes the **touched areas** (from the in-scope Work Tasks), fans out
  **one Design task per area** to the `(area, architect)` contract, sequences them by
  layer rank via `blocked_by`, runs independent areas in parallel, and persists each
  area's spec (4a). *Areas:* scheduler + access. *Verify:* a small release fans out
  the right per-area Design tasks and persists their specs in rank order.

- **4c — Design Review gate (NEW).** One **consolidated** human sign-off over the full
  set of per-area specs (reuses the PI-238 freshness-checked sign-off pattern); the
  back half does not proceed to Develop until it is signed. *Areas:* access/api/ui.
  *Verify:* Develop is blocked until a fresh design sign-off exists; a spec change
  re-opens review.

- **4d — Per-area Develop to spec (CHANGE).** One Develop task per area, on the
  approved spec, reusing the worktree/spawn/verify/merge runtime keyed by `(area,
  developer)` + the spec as work input; self-verify (lint + don't break affected
  tests). *Areas:* scheduler + build areas. *Verify:* a per-area Develop task builds
  to a spec and merges, self-verified.

- **4e — Per-area blind Test + bounce (NEW).** One Test task per area on the `(area,
  tester)` contract, implementing the **testable spec blind** to the Developer's code,
  verifying behaviour; on `failed` it **bounces to that area's Develop** (reusing the
  findings/area-reopen substrate). *Areas:* scheduler + build areas. *Verify:* a
  seeded defect is caught by the blind Tester and bounced to Develop.

- **4f — Two-level wiring + parallel-lane proof (EXTEND).** Wire per-area Test under
  the existing release-level QA/Test gates; put the whole per-area back half behind a
  **release-level flag / separate lane** so it runs beside the per-PI path; prove it
  end-to-end on **one small real release**. *Areas:* scheduler/api/release. *Verify:*
  a small release is delivered end-to-end through the per-area back half with an
  independent Tester catching a seeded defect — the plan's Phase 4 acceptance.

*(Cutover to per-area-by-default and retiring the per-PI path is **Phase 5**, not here.)*

---

## 5. Key design decisions to settle (before authoring requirements)

These materially shape the build; each is a one-issue discussion.

1. **Testable-spec artifact shape** — a new `artifact_type` on the existing
   `artifact_versions` spine (reuse versioning/review/live-resolution), or a new
   dedicated entity (`area_spec`)? Trade-off: reuse vs a cleaner per-(release,area)
   keying that isn't a product-artifact.
2. **Touched-area derivation** — "the areas a release touches" = the distinct `area`
   of the in-scope Work Tasks (from the per-PI decomposition that still runs upstream).
   Confirm Phase 4 **consumes** the existing decomposition's Work Tasks rather than
   replacing decomposition. (Lowest-risk; keeps Architecture-Planning unchanged.)
3. **Parallel-lane mechanism** — a boolean on the release (e.g. `back_half = per_pi |
   per_area`) routing the dev lane to the new driver, vs a separate scheduler entry
   point. Determines blast radius and how we A/B the two paths.
4. **Blind-test enforcement** — the Tester is an LLM agent; "doesn't read the
   Developer's code" is enforced by **contract + work-inputs** (give it the spec + the
   running build, not the diff), not a hard sandbox. Confirm contract-level enforcement
   is acceptable for the guarantee.
5. **Bounce mechanism** — reuse `finding` + area-reopen for Test→Develop bounce, or a
   lighter in-pass retry (Test `failed` → re-dispatch that area's Develop with the
   findings). Affects how rework is recorded vs how fast the loop turns.

---

## 6. Risk & sequencing

- **Highest-risk phase.** Mitigation: every PI above is **additive beside the live
  per-PI path**; the flag (4f) keeps the old path the default until a real release
  ships on the new one. No removal until Phase 5.
- **Critical path:** 4a → 4b → 4c → 4d → 4e → 4f (4d can start once 4a's spec shape is
  fixed; 4c can be built in parallel with 4d). 
- **The load-bearing dependency** (plan §5): the testable spec's quality. If specs are
  weak, blind Test regresses to checking code. 4a + the `(area, architect)` contract
  quality are where that risk lives.

---

## 7. Governance

One requirement — **"per-area matrix execution (Architect/Developer/Tester) with a
testable spec and blind test"** — under topic **TOP-009 "Delivery Passes"**, traced to
target-model decisions **D7** (WHAT/HOW design split), **D8** (blind test), and the
§4.5–§4.8 task definitions, with implementing PIs **4a–4f** under **PRJ-041**. The
requirement + its human approval + the first implementing PI must exist before any
Phase 4 code. This document is the input to that authoring step.
