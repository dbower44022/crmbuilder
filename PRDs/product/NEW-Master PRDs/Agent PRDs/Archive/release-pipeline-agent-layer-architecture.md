# Multi-Agent Release Pipeline — Agent-Layer Architecture

**Status:** Architecture pass (design-complete pending Doug's Review-panel sign-off of the
candidate requirements). **Topic:** TOP-095 (child of TOP-094). **Session:** SES-202 / CNV-117.
**Projects:** PRJ-033 (Planning Agent Org) primarily, + PRJ-029 (coordination) / PRJ-030
(file lock) for the dev-org runtime. **Source of truth for the model:**
`multi-agent-release-pipeline-architecture.md` (RB-014), esp. §5.1, §5.4, §7, §10.

> The release-pipeline **substrate** (PI-203…216, all Resolved) is the deterministic spine:
> the Release entity + staged `transition()` with every gate, `reconcile_release` + conflict
> store, `author_designs`/`planning_readiness`, `artifact_versions`, area claims, coordination,
> freeze, reopen, and file locks. It is API-drivable and proven end-to-end (a release walked
> concept → shipped → live through every gate). **This document designs the agent layer that
> *drives* that substrate** so the pipeline runs without hand-driving each step.

---

## 1. The gap: three agent seams

The end-to-end walkthrough did three things by hand. Those three things *are* the agent layer:

1. **Demands authoring** — produce the structured requirement→design deltas
   (`{requirement_identifier, artifact_type, artifact_identifier, field, facet, op, value}`)
   that `reconcile_release` consumes. Today they are hand-written *input*. **The biggest unknown.**
2. **Work-task decomposition** — `author_designs` writes vN+1, but the judgment of *what
   workstreams + work tasks, in what order* (so `planning_readiness.ready == True`) is not done.
3. **The orchestration loop + agents** — nothing walks the stage machine: nobody calls
   `transition()` at each gate, spawns the reconciler / architect / dev agents, or drives QA/test.

The substrate's deliberate boundary (PI-209 Option A): the substrate is the **deterministic
spine**; the agent layer **wraps** it and supplies **only the judgment** — it never reimplements
reconcile / version / gate logic.

---

## 2. Stage → actor map (the spine the loop walks)

| Release stage (status) | Substrate gate (raises if unmet) | Agent-layer actor & action |
|---|---|---|
| `preliminary_planning` → `development_planning` | — | **Out of scope (Phase-1 conceptual).** Requirements authored by the existing requirements-provenance process; parallel/free. |
| `development_planning` → `reconciliation` | `_check_freeze` (≥1 release-scoped Project; every in-scope requirement `confirmed`) | **Human/PM freeze act** (deliberate, recorded actor+timestamp). The loop *surfaces readiness*; a human pulls the trigger (FE-5). |
| **`reconciliation`** (stage work) | — | **Seam 1 — Reconciliation Agent** (the Data-Structure / model-area planning specialist): claim the model area (PI-207), author demands from the confirmed in-scope requirements + each artifact's `live` base, call `reconcile_release`, route every CONFLICT to a governed `decision`, `resolve_conflict`, re-reconcile until clean. |
| `reconciliation` → `architecture_planning` | `_check_no_open_conflicts` | Loop transitions once `has_open_conflicts == False`. |
| **`architecture_planning`** (stage work) | — | **Seam 2 — Architect Planning Agent**: `author_designs(delta_sets)` (vN+1 per artifact); then create, per in-scope PI, the workstreams + sequenced work-tasks (direct CRUD, *not* the ADO decomposer — DEC-425) until `planning_readiness.ready`. |
| `architecture_planning` → `ready` | `_check_planned_completely` (frozen; every PI has ≥1 workstream; work-task `blocked_by` acyclic) | Loop confirms readiness, **flips in-scope PIs `interactive` → `ado`** (AL-4), transitions. |
| `ready` → `development` | `_check_single_occupancy` (no other live release in lane; blockers shipped; lowest `lane_order`) | **Release Lead** enters the exclusive lane. |
| **`development`** (stage work) | — | **Seam 3 (dev) — Development Org**: per in-scope PI in dependency order, run the **existing ADO runtime** (now ado-mode) — lead → area specialists → sub-agents — under the already-wired gates: area ownership (PI-204 `assert_area_owner`), file lock (PI-203 acquire/verify), serial-by-area freeze (PI-206 Lead `start_phase`/`complete_phase`), pause guard (PI-212 `assert_area_not_paused`). |
| `development` → `qa` → `testing` → `deployment` | `_check_qa_passed`, `_check_test_passed` | **Release Lead** drives the **release-level** (integration) QA + test (§8 second level): `qa_pass()` / `test_pass()`, then transitions. |
| `deployment` → `shipped` | `_check_revalidations_complete` | Ship; versions become `live`; lane frees; next release enters. |
| **rework**: `qa`/`testing`/`deployment` → `development` (bounce-back) | — | On a `finding` (FND-) against a frozen area: drive `reopen_area` + cascade re-validation + blast-radius approval (PI-212/213/214); bounce-back clears QA/test passes. |

---

## 3. Seam 1 — Demands authoring (the biggest unknown)

### 3.1 The problem

A requirement record is natural language: `requirement_name`, `requirement_description`,
`requirement_acceptance_summary`, `priority`, `status`, `origin`, `review_state`. There is **no
structured link** from a requirement to which artifact / field / facet it changes.
`reconcile_release(session, release_id, demands)` needs a list of structured deltas:

```python
demand = {
    "requirement_identifier": "REQ-NNN",   # the demanding requirement (provenance, RC-7)
    "artifact_type": "entity",             # entity | field | persona | process | association
    "artifact_identifier": "ENT-Contact",  # the methodology artifact (or agent-minted)
    "field": "email",                      # "" for an artifact-level attribute
    "facet": "required",                   # the facet (constraint/metadata key)
    "op": "set",                           # set (scalar) | add (set union) | remove (drop)
    "value": True,
}
```

Producing this from a confirmed requirement is irreducibly a judgment task — it is the
**Data-Structure Planning Agent reading the requirements and expressing the design changes**
(§5.1, §21 turn 21).

### 3.2 Options

- **A1 — single model-area Reconciliation Agent authors the demand-set per release (RECOMMENDED).**
  One LLM agent, scoped to the model (Data Structure) area, reads (a) the release's confirmed
  in-scope requirements (traverse `release → projects → PIs →`
  `planning_item_implements_requirement → requirement`) and (b) each candidate artifact's `live`
  base (`artifact_versions.live`, or the methodology entity/field/persona/process record where one
  exists). It emits the full structured demand list. The **deterministic** `reconcile_release`
  then does the N-way merge; CONFLICTs become governed decisions. This *is* the single-reconciler-
  owns-the-model-area model (RC-6 / D-37): exactly one writer, dependency-ordered, with the merge
  itself deterministic.
- **A2 — per-requirement parallel derivation (REJECTED).** One agent per requirement emits its
  own deltas. This reintroduces the parallel-collision the pipeline removes and contradicts the
  single-reconciler rule (RC-6). (It is the *Phase-1 conceptual* temperature — not reconciliation.)
- **A3 — structured demands captured at requirement-authoring time (FUTURE).** Extend the
  requirements-provenance engine so a requirement carries its structured deltas when authored/
  confirmed, made first-class and human-reviewable upstream. Best long-term (demands become
  reviewable provenance objects per RC-7), but a much larger change coupled to the requirements-
  provenance model. **A1 is the bridge; A3 is the documented end-state.**

### 3.3 Re-runnability & provenance — persist the demand-set

`reconcile_release` is deterministic, but the *demands feeding it* come from an LLM (not
deterministic). To honour D-37 ("deterministic and **re-runnable**") and RC-7 (every reconciled
change links to its demanding requirement), the agent's demand-set is **persisted as the stable,
reviewable, replayable input**: a minimal `release_demands` satellite store (engagement-scoped,
composite FK → releases; one row per `(release, requirement, artifact, field, facet)` carrying
`op`/`value` + agent attribution). The merge then replays over a frozen demand-set; the demand-set
is itself reviewable before reconciliation runs. (Providing this input store is the agent layer's
job — the substrate deliberately left demands as *input*. This is **not** rebuilding substrate.)

### 3.4 The CONFLICT loop (re-affirms RC-4 at the agent layer)

The agent **never silently resolves** a same-facet contradiction. `reconcile_release` emits a
typed `ReconciliationConflict`; the agent (or a human) opens a governed `decision`
(pick A / pick B / synthesize / amend a requirement via `requirement_changed_by_decision`) and
calls `resolve_conflict(conflict_id, decision_identifier=…, resolved_value=…)`. Re-reconcile folds
the resolved value into the delta-set (the RC-5 seam fixed in commit `22f56bf2`). Loop until
`has_open_conflicts == False`, then transition.

### 3.5 Artifact identifiers

`artifact_identifier` references the methodology artifact record where one exists (the v0.4
methodology `entity`/`field`/`persona`/`process` tables) — that is the natural source of "which
entities a requirement changes". Where the artifact does not yet exist (a first release authoring
the initial model), the agent mints the identifier and the delta is `op=set` against `base=None`
(`reconcile_artifact` handles `None` base). A decision (DEC, §7) fixes the identifier scheme.

---

## 4. Seam 2 — Work-task decomposition

After `author_designs` snapshots vN+1, the **Architect Planning Agent** must make
`planning_readiness.ready == True`: every in-scope PI has ≥1 workstream, and the work-task
`blocked_by` graph is acyclic.

### 4.1 The DEC-425 reconciliation

The ADO structural decomposer (`decompose_planning_item`) **refuses `execution_mode=interactive`
PIs** (DEC-425); the release-pipeline PIs are interactive. Two reconciliations:

- **B-dec-1 — the planning agent decomposes DIRECTLY (RECOMMENDED).** The agent creates the
  workstreams + work-tasks via the existing CRUD (`POST /workstreams`, `POST /work-tasks`,
  `blocked_by` edges) and may use the scoping substrate (`scope_workstream`) to drive
  `Planned → Ready`. It supplies the *judgment* (what tasks, what order); the substrate enforces
  the structure. This keeps interactive PIs interactive and the ADO auto-decomposer untouched —
  exactly the "interactive release-pipeline PIs are decomposed by their human/agent owner" carve-
  out the PI-209 arch doc names. (The workstream/work-task CRUD has no interactive guard; only
  `decompose_planning_item` does.)
- **B-dec-2 — flip release PIs to ado mode for the auto-decomposer (REJECTED for planning).** The
  structural decomposer only produces generic Design/Develop/Test phase workstreams and would
  route the PI to the autonomous ADO runtime — it does none of the model-area judgment and
  collides with the release scheduler. (The flip *does* belong at the planned-completely gate for
  the **development** stage — see AL-4 below.)

---

## 5. Seam 3 — Orchestration loop + agents

### 5.1 Reuse vs new runtime

- **B1 — new `runtime/release_runtime.py` + CLI `crmbuilder-v2-release` (RECOMMENDED).** A release-
  level scheduler that owns the **stage machine** and **delegates** the per-area development work
  to the *existing* `ado_runtime` / `parallel_runtime`. Wrap, don't replace. It reuses the proven
  spawn primitives: `spawn_claude_agent`, `agent_runtime.build_agent_prompt`,
  `mint_agent_principal`, the `Worktree` helper, `verify_result`.
- **B2 — extend `ado_runtime` to understand releases (REJECTED).** Pollutes the single-PI driver
  with release-stage concerns; the two loops have different grains (PI vs Release).

### 5.2 Structure (mirrors `ado_runtime`)

- A **pure** `decide_next(release_status, readiness, has_open_conflicts, lane_holder, …)` → a
  `ReleaseStep` (RECONCILE / PLAN / ENTER_LANE / DEVELOP / QA / TEST / SHIP / REOPEN / DONE /
  PAUSE / BLOCKED), unit-tested in isolation exactly like `ado_runtime.decide_next`.
- **Handlers** per step, each spawning the right agent (resolved contract + minted principal) or
  delegating to the ADO runtime, then calling the substrate `transition()`:
  - `RECONCILE` → spawn Reconciliation Agent (§3) → loop conflicts → `→ architecture_planning`.
  - `PLAN` → spawn Architect Planning Agent (§4) → `author_designs` + decompose → readiness →
    flip PIs `interactive → ado` (AL-4) → `→ ready`.
  - `ENTER_LANE` → `→ development` (single-occupancy).
  - `DEVELOP` → for each in-scope PI in dependency order, run `AdoRuntime(...).run()` (ado-mode),
    under the already-wired release gates. The dev-org agents are the **existing** ADO
    Developer/Architect/Tester profiles; sub-agents acquire file locks (§5.4).
  - `QA` / `TEST` → spawn release-level QA / test agents → `qa_pass()` / `test_pass()` →
    transitions.
  - `SHIP` → `→ shipped`.
  - `REOPEN` → on a `finding` against a frozen area, drive `reopen_area` (+ cascade PI-213 +
    blast-radius approval PI-214).

### 5.3 AL-4: the interactive→ado flip at planned-completely

At the planned-completely gate the plan is frozen and fully decomposed; development is then a
mechanical walk of a finished prerequisite graph (§5.2 of RB-014: "all dependency reasoning happens
in planning, none in development; development just *walks* it"). So in-scope PIs flip
`interactive → ado` at that gate, handing the development stage to the autonomous ADO runtime.
Planning stays interactive (judgment); development becomes autonomous (mechanical). This is a real
behavioral decision (DEC, §7).

### 5.4 Dev-org file-lock runtime (PRJ-030/029)

The PI-203 substrate (acquire/verify/release/reclaim, FL-1…6) exists; the **runtime** that wires
it into the sub-agent fan-out is the deferred piece. Net-new: in the `parallel_runtime` spawn loop,
before a sub-agent edits, `acquire_many(detect_resources(declared_paths), holder)`; on merge-back,
`verify(holder, touched_paths)` (retroactively acquire/serialize undeclared touches, FL-5); each
sub-agent already runs in an isolated `Worktree` with serialized `--no-ff` merge-back (FL-3, the
existing `parallel_runtime` behavior); dead sub-agent → owner `reclaim` + worktree discard (FL-6).

---

## 6. Profiles (PI-122 registry)

New **system-scope** profiles for the planning org, resolved by `registry_resolver.resolve_contract`
and spawned via `build_agent_prompt` + `spawn_claude_agent`:

| Profile | (area, tier) | Drives |
|---|---|---|
| **Reconciliation / Data-Structure Planning Agent** | (`model`, `architect`) | Seam 1 — demands-authoring + reconciliation loop |
| **Architect Planning Agent** | (`planning`, `architect`) | Seam 2 — design authoring + decomposition |
| **Release Lead** | (release-level, `pi_lead`) | release QA/test + PI sequencing in the dev lane |

The dev-org area specialists + sub-agents **reuse existing** PI-122 profiles (Developer / Architect
/ Tester per DEC-368). Tier/area vocab may need `model`, `planning`, and a release-level tier added
— align with `agent-delivery-organization-evolution.md` (DEC-368 already defines Architect/
Developer/Tester). For the *first slice* the planning profiles may be authored as inline prompts
(as the ADO proofs did under `agent-profile-registry/profiles/`) and promoted to formal registry
rows in PI-221.

---

## 7. Scope decisions (recorded as DEC-512…518)

| DEC | Decision | Chosen | Rejected / future |
|---|---|---|---|
| D-A1 | Demands-authoring approach | **A1**: single model-area Reconciliation Agent authors a persisted demand-set per release | A2 per-requirement parallel (collision); A3 structured-at-authoring (future end-state) |
| D-A2 | Demand-set persistence | **`release_demands` satellite store** — stable, reviewable, replayable input (D-37/RC-7) | pass-through only (loses re-runnability) |
| D-A3 | Artifact identifier scheme | reference the methodology artifact record; agent-mint where none exists (`op=set` vs `None` base) | a separate artifact-registry entity |
| D-B1 | Decomposition of interactive release PIs | **B-dec-1**: planning agent creates workstreams/work-tasks directly (DEC-425 honoured) | B-dec-2 flip-to-ado for the auto-decomposer |
| D-C1 | Runtime | **B1**: new `release_runtime.py` wrapping the substrate, delegating dev to the existing ADO runtime | B2 extend `ado_runtime` |
| D-C2 | interactive→ado flip | **AL-4**: flip in-scope PIs `interactive → ado` at the planned-completely gate (dev = mechanical walk, §5.2) | keep interactive through development |
| D-D1 | Boundary | agent layer **wraps** the PI-209 Option-A deterministic spine; never reimplements reconcile/version/gate logic | agents re-derive substrate logic |

---

## 8. Candidate requirements (AL-1…7, ai_derived / candidate — await Review-panel sign-off)

| REQ | Invariant |
|---|---|
| **AL-1** | Demands are authored by a single model-area planning agent per release, from the release's confirmed in-scope requirements + each artifact's live base, and persisted as a stable, reviewable, replayable demand-set. |
| **AL-2** | The agent never silently resolves a reconciliation CONFLICT; same-facet contradictions route to a governed decision and `resolve_conflict` (re-affirms RC-4 at the agent layer). |
| **AL-3** | Architecture-planning decomposition of interactive release-scoped PIs is performed directly by the planning agent (workstream/work-task creation), not the ADO structural decomposer (DEC-425 honoured). |
| **AL-4** | At the planned-completely gate, in-scope PIs flip `interactive → ado` so development autonomously walks the finished prerequisite graph (RB-014 §5.2). |
| **AL-5** | The release scheduler wraps the deterministic substrate (PI-209 Option A) and never reimplements reconcile / version / gate logic. |
| **AL-6** | Dev-org sub-agents acquire file locks (PI-203) before editing and merge back serialized from isolated worktrees (FL-3); the runtime reuses the ADO spawn/worktree primitives. |
| **AL-7** | Every agent run is recorded in real-time governance; each agent is a minted `service_agent` principal resolving a registry contract. |

---

## 9. PI decomposition (PI-217…221)

All `blocked_by` the (Resolved) substrate PIs.

| PI | Project | Scope | blocked_by |
|---|---|---|---|
| **PI-217** | PRJ-033 | **Demands-authoring + reconciliation-stage driver** (Seam 1). `release_demands` store; the Reconciliation Agent profile/prompt; the reconciliation loop (author demands → `reconcile_release` → conflicts→decisions→`resolve_conflict` → re-reconcile → transition). *Biggest unknown.* | PI-215, PI-207, PI-208 |
| **PI-218** | PRJ-033 | **Architecture-planning decomposition driver** (Seam 2). Architect Planning Agent profile; `author_designs` wiring; direct workstream/work-task decomposition; the planned-completely interactive→ado flip. | PI-209, PI-205, PI-217 |
| **PI-219** | PRJ-033 | **Release orchestration scheduler + CLI** (Seam 3 spine). `release_runtime.py`, pure `decide_next`, stage handlers, delegation to the ADO runtime, release QA/test drive, rework dispatch. CLI `crmbuilder-v2-release`. | PI-205, PI-217, PI-218 |
| **PI-220** | PRJ-030/029 | **Dev-org file-lock runtime.** Wire PI-203 `acquire_many`/`verify`/`reclaim` into the `parallel_runtime` sub-agent fan-out; worktree-per-sub-agent + serialized merge-back under the lock. | PI-203, PI-204 |
| **PI-221** | PRJ-033 (PI-122 registry) | **Planning-org registry profiles.** Author the AGP/SKL/GVR rows for the Reconciliation Agent, Architect Planning Agent, Release Lead (system scope). May fold into PI-217/218 for the first slice. | PI-122 |

### 9.1 Build sequence & first slice

- **First valuable slice (recommended): PI-217 + PI-218 + a thin PI-219** driving **one** release
  through `reconciliation → architecture_planning → ready` on **real agent-produced demands**, so
  the existing substrate runs end-to-end on agent input. Prove against a real release, then iterate.
- Then **PI-219 full** (dev/QA/test/ship handlers + rework) and **PI-220** (dev-org file-lock
  runtime), with **PI-221** promoting the inline planning prompts to formal registry profiles.

### 9.2 Cadence (per the substrate's rhythm)

Design-first per PI → governed candidate requirements → **Doug signs off in the Review panel** →
build on a `pi-NNN` branch (code only) → tests green + `ruff` clean → commit → merge → Model-A
build-closure (resolve the PI on `main`). Governance in real time via direct API POST.

---

## 10. What this design explicitly does NOT change

- The substrate (PI-203…216) — wrapped, never reimplemented.
- The ADO runtime / `parallel_runtime` — reused for the development stage; extended only by the
  file-lock wiring (PI-220).
- The Agent Profile Registry (PI-122) — new rows added; resolver/lifecycle untouched.
- The requirements-provenance engine — A1 reads confirmed requirements; A3 (structured demands at
  authoring) is the documented future, not this work.
</content>
</invoke>
