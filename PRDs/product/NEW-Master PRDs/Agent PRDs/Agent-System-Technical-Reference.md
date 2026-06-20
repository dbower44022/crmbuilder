# Agent System — Technical Reference (component by component)

> **Scope.** Precise, code-anchored documentation of every component of the
> CRMBuilder v2 **Agent Delivery Organization (ADO)** and the **multi-agent
> release pipeline**. For plain-language explanations of any term, see the
> glossary in `Agent-System-Overview.md` (this doc does not re-explain basics).
>
> **Ground-truth rule.** Every nontrivial claim below is anchored to a real
> code path/symbol or a live-DB read. Where a design doc describes something not
> (or not yet) reflected in code, it is marked **[DESIGNED — not built]** or
> **[PARTIAL]**. All paths are repo-relative to
> `/home/doug/Dropbox/Projects/crmbuilder/`.
>
> **Verified against** the live V2 DB (`http://127.0.0.1:8765`,
> `X-Engagement: CRMBUILDER`) on **2026-06-20**.

---

## 0. Orientation — the layer cake

```
Release pipeline (PRJ-031)        release_runtime.py        ← outermost conductor
  └─ ADO PI driver (PI-143)       ado_runtime.py            ← drives ONE Planning Item
       └─ Parallel pool (PI-139)  parallel_runtime.py       ← runs ONE phase's Work Tasks
            └─ Serial loop (PI-132) coordinating_runtime.py ← spawn→verify→merge ONE agent
                 └─ Worker agent   agent_runtime.py + dispatcher.py
```

> 📐 **Diagram files:** [`Agent-System-Runtime-Layers.svg`](Agent-System-Runtime-Layers.svg)
> — an editable SVG (renders on GitHub *and* opens for editing in
> [draw.io](https://app.diagrams.net) / the VS Code Draw.io extension); raw
> source: [`Agent-System-Runtime-Layers.drawio`](Agent-System-Runtime-Layers.drawio).
> (The end-to-end pipeline flow is `Agent-System-Flow.svg`, shown in
> `Agent-System-Overview.md` §2.)

Each runtime composes the one below it. Around the edges sit the **substrate
repositories** (the deterministic REST/access functions the runtimes call), the
**registry** (which supplies each spawned agent its contract), and the
**concurrency primitives** (locks).

**Two distinct things both called "reconciliation"** — keep them apart:
1. **ADO Design→Develop reconciliation gate** — `runtime/reconciliation.py` +
   `repositories/findings.py` + `lead.complete_phase`. Within one PI; gates
   Develop on a settled Design + zero open blocking findings.
2. **Release reconciliation engine** — `access/reconciliation.py` (pure merge) +
   `repositories/reconciliation.py` (orchestration + conflict store). Across a
   frozen release; merges demand-sets into a conflict-free delta-set.

**Naming convention.** Every agent's display name ends in the word **"Agent"**
(Project Manager Agent, PI Lead Agent, Phase Specialist Agent, Area Specialist
Agent, Architect Agent, Developer Agent, Tester Agent, Release Lead Agent,
Reconciliation Agent, Architect Planning Agent). The converse holds: a thing
whose name does *not* end in "Agent" is *not* an agent — e.g. the
runtime/conductor/orchestrator is the scheduler that *spawns* agents, and the
substrate repositories below are the deterministic functions agents call. **This
convention applies to display names only.** The *code* spelling is unchanged and
unsuffixed — tier enum values stay lowercase (`AGENT_PROFILE_TIERS = {architect,
developer, tester, orchestrator, pi_lead}`), as do module names (`pm.py`,
`lead.py`) and identifiers.

**The four agent tiers and their substrates** (verified):

| Tier | Agent (display name) | Substrate module | Evolution name |
|---|---|---|---|
| 1 | Project Manager Agent | `access/repositories/pm.py` | (unchanged) |
| 2 | PI Lead Agent | `access/repositories/lead.py` | (unchanged) |
| 3 | Phase Specialist Agent | `access/repositories/decomposition.py` + `scoping.py` | → **Architect Agent** (per-area) |
| 4 | Area Specialist Agent | `access/repositories/work_tasks.py` (claim lifecycle) | → **Developer Agent** / **Tester Agent** (per-area) |

The Architect Agent / Developer Agent / Tester Agent per-area split is the design direction in
`Archive/agent-delivery-organization-evolution.md` (DEC-368); the *built*
runtime still drives the four-tier shape with a single generic worker prompt
(see §11, Registry — live state).

---

## 1. State machines (read these first)

All status enums and legal transitions live in
`crmbuilder-v2/src/crmbuilder_v2/access/vocab.py`. Quoted exactly.

### 1.1 Planning Item (`PI-NNN`) — `PLANNING_ITEM_STATUS_TRANSITIONS`

| From | Legal to |
|---|---|
| `Draft` | `Decomposed`, `Ready`, `In Progress`, `In Review` (+ terminals) |
| `Decomposed` | `Ready`, `In Progress`, `In Review` (+ terminals) |
| `Ready` | `In Progress`, `In Review` (+ terminals) |
| `In Progress` | `In Review` (+ terminals) |
| `In Review` | `In Progress` (+ terminals) |
| `Deferred` | `Draft`, `Decomposed`, `Ready`, `In Progress`, `In Review`, `Cancelled` |
| `Resolved` | — (terminal) |
| `Cancelled` | — (terminal) |

Terminals reachable from any non-terminal: `Resolved`, `Cancelled`, `Deferred`.
A PI flips to `Resolved` only via a governance `resolves` close-out edge, **not**
by the runtime. The ADO marks a finished PI `In Review` (`ado_runtime._DONE_STATUS`).

### 1.2 Workstream (`WSK-NNN`, the delivery phase) — `WORKSTREAM_STATUS_TRANSITIONS`

| From | Legal to |
|---|---|
| `Planned` | `Scoping`, `Blocked` |
| `Scoping` | `Ready`, `Not Applicable`, `Blocked` |
| `Ready` | `In Progress`, `Blocked` |
| `In Progress` | `Complete`, `Blocked` |
| `Blocked` | `Planned`, `Scoping`, `Ready`, `In Progress` |
| `Complete` | — (terminal) |
| `Not Applicable` | — (terminal) |

Phase types: new `{Design, Develop, Test}` + retained legacy
`{Architecture, Development, Testing, Documentation, Data Migration, Deployment}`
(both generations coexist live; see §1.6). Orthogonal flag
`workstream_needs_attention` (+ `_reason`) overlays status without erasing it
(DEC-359). Timestamps `workstream_started_at`/`_completed_at` auto-set on
`In Progress`/`Complete`.

### 1.3 Work Task (`WTK-NNN`) — `WORK_TASK_STATUS_TRANSITIONS`

| From | Legal to |
|---|---|
| `Planned` | `Ready`, `Blocked`, `Failed` |
| `Ready` | `Claimed`, `Blocked`, `Failed` |
| `Claimed` | `In Progress`, `Ready`, `Blocked`, `Failed` |
| `In Progress` | `Complete`, `Blocked`, `Failed` |
| `Blocked` | `Ready`, `Claimed`, `In Progress` |
| `Failed` | `Ready` |
| `Complete` | — (terminal) |

`claim_work_task` performs `Ready → Claimed` (PI-137). Carries `work_task_area`
(validated against System ∪ Engagement areas), `work_task_claimed_by`/`_claimed_at`.

### 1.4 Project (`PRJ-NNN`) — `PROJECT_STATUS_TRANSITIONS`

Five-status: `planned → in_flight → {complete, cancelled, superseded}`. Terminals
are truly terminal (per project memory: `complete` is irreversible via API — a
new project is created to carry unfinished PIs forward). `superseded` requires a
`supersedes` edge.

### 1.5 Release (`REL-NNN`) — `RELEASE_STATUS_TRANSITIONS` (the pipeline spine)

12 statuses. The single mutator is `releases.transition`.

| From | Legal to | Gate predicate on the key forward move |
|---|---|---|
| `preliminary_planning` | `development_planning`, `cancelled`, `superseded` | — |
| `development_planning` | `reconciliation`, `cancelled`, `superseded` | **`_check_freeze`** (the plan freeze) |
| `reconciliation` | `architecture_planning`, `cancelled`, `superseded` | `_check_no_open_conflicts` |
| `architecture_planning` | `ready`, `cancelled`, `superseded` | `_check_planned_completely` |
| `ready` | `development`, `cancelled`, `superseded` | `_check_single_occupancy` |
| `development` | `qa`, `cancelled`, `superseded` | — |
| `qa` | `testing`, **`development`**, `cancelled`, `superseded` | `_check_qa_passed` |
| `testing` | `deployment`, **`development`**, `cancelled`, `superseded` | `_check_test_passed` |
| `deployment` | `shipped`, **`development`**, `cancelled`, `superseded` | `_check_revalidations_complete` |
| `shipped` / `cancelled` / `superseded` | — (terminal) | — |

`RELEASE_LANE_STATUSES = {development, qa, testing, deployment}` — the exclusive
single-occupancy dev lane. A bounce-back to `development` (from qa/testing/
deployment) **clears** `release_qa_passed_at` and `release_test_passed_at`
(re-QA/re-test required). "Plan freeze = a transition, not an object": there is
no freeze flag — freeze is the `development_planning → reconciliation` move,
recorded only as the `release_frozen_at` stamp.

### 1.6 Finding (`FND-NNN`) — `FINDING_STATUS_TRANSITIONS`

`open → {referred, resolved}`; `referred → {open, resolved}`; `resolved → {}`.
`FINDING_OPEN_STATUSES = {open, referred}` are the statuses that hold the gate.
Types `{conflict, gap, dependency, overlap}`; severities `{blocking, advisory}`;
resolution methods `{revise, order, combine, refer}`.

### 1.7 Registry record statuses

- `agent_profile` / `skill` / `governance_rule`: `REGISTRY_STATUSES = {active, retired}`.
- `learning`: `LEARNING_STATUSES = {active, stale, retired, promoted}`.
- Tiers: `AGENT_PROFILE_TIERS = {architect, developer, tester, orchestrator, pi_lead}`;
  `LEARNING_TIERS = {architect, developer, tester}` (only these carry learnings).

### 1.8 Reconciliation conflict & area-reopen

- `RECONCILIATION_CONFLICT_STATUSES = {open, resolved}`; types
  `{facet_value, remove_vs_modify, field_redefinition}`.
- `area_reopen.status`: `open → resolved`. Approval tiers
  `(lead_auto, lead, pm, human)`.

### 1.9 Execution mode (the ADO interactive gate, PI-183/PI-190)

`EXECUTION_MODES`, ranked `EXECUTION_MODE_RANK = {ado:0, ado_with_approval:1, interactive:2}`.
Effective mode of a PI = `max(pi_mode, project_mode)`. Every ADO tier
(`decompose`, `scope`, `start_phase`, work-task `claim`) refuses when the owning
PI resolves to `interactive`; `ado_with_approval` requires `dispatch_approved`
(set only via `planning_items.approve_dispatch`, DEC-424).

---

## 2. Component: Project Manager Agent (PM) substrate

- **Name & purpose.** Tier-1 substrate. Deterministic, dependency-aware backlog
  over one Project; computes PI eligibility and dispatches an eligible PI.
- **Functionality.** `project_backlog` (PIs partitioned into eligible / in_flight
  / blocked / resolved with `unresolved_blockers` + effective execution mode);
  `eligible_planning_items`; `dispatch_planning_item`. Also hosts the shared
  PI-190 effective-execution-mode resolvers (`effective_execution_mode`,
  `is_ado_interactive`, `workstream_is_ado_interactive`,
  `work_task_is_ado_interactive`) used as the interactive backstop by every
  other tier.
- **Triggers.** `GET /projects/{id}/backlog`, `GET /projects/{id}/eligible-planning-items`,
  `POST /planning-items/{id}/dispatch`; the interactive resolvers are called
  internally by lead/decomposition/scoping/work_tasks.
- **Inputs.** `planning_item` rows; `project` rows (for `project_execution_mode`);
  edges `planning_item_belongs_to_project`, `blocked_by` (PI→PI),
  `workstream_belongs_to_planning_item`, `work_task_belongs_to_workstream`.
- **Outputs.** Only `dispatch_planning_item` writes: `planning_items.update(status="In Progress")`.
- **States.** Startable `_STARTABLE = {Draft, Decomposed, Ready}` → `In Progress`,
  gated on (a) startable status, (b) every `blocked_by` PI `Resolved`, (c) mode
  dispatchable.
- **Where it lives.** `crmbuilder-v2/src/crmbuilder_v2/access/repositories/pm.py`.
  Router `api/routers/projects.py` (`backlog`, `eligible_planning_items`),
  `api/routers/planning_items.py` (`dispatch`).
- **Interactions.** `planning_items`, `projects`, `references`. Consumed by
  `ado_runtime.ProjectRuntime` (the `crmbuilder-v2-ado-pm` PM loop).

---

## 3. Component: PI Lead Agent substrate

- **Name & purpose.** Tier-2 substrate. Per-PI phase state machine.
- **Functionality.** `phase_overview` (every phase Workstream in canonical order
  with status, Work Task `total`/`complete`, `predecessors_terminal`,
  `executable_now`, plus `decomposed`/`all_scoped`/`all_terminal`/
  `needs_attention`/`next_executable`); `start_phase`; `complete_phase`.
- **Triggers.** `GET /planning-items/{id}/phase-overview`,
  `POST /workstreams/{id}/start-execution`, `POST /workstreams/{id}/complete-phase`.
- **Inputs.** `planning_item`; phase `workstream` rows via
  `workstream_belongs_to_planning_item`; `work_task` rows via
  `work_task_belongs_to_workstream`; serial predecessors via `blocked_by` (WSK→WSK).
- **Outputs.** `start_phase` → Workstream `Ready → In Progress` + each `Planned`
  Work Task → `Ready`. `complete_phase` → Workstream `In Progress → Complete`.
  (PI resolution to `Resolved` is explicitly **not** done here.)
- **States.** `_SCOPED = {Ready, Not Applicable}`; `_TERMINAL = {Complete, Not Applicable}`.
  `start_phase` gated: must be `Ready`, not interactive, all `blocked_by`
  predecessors terminal. `complete_phase` gated: must be `In Progress`, every
  Work Task `Complete`.
- **Where it lives.** `access/repositories/lead.py` (imports `PHASE_SEQUENCE`
  from `decomposition`). Router `api/routers/workstreams.py`
  (`start_execution`, `complete_phase`), `planning_items.py` (`phase_overview`).
- **Interactions.** `planning_items`, `pm` (interactive backstop), `references`,
  `workstreams`, `work_tasks`. Driven by `ado_runtime.AdoRuntime`.

---

## 4. Component: Phase Specialist Agent substrate — Decomposition

- **Name & purpose.** Tier-3, the structural decomposer. Once-only step that
  creates all phase Workstreams and chains them serially.
- **Functionality.** `decompose_planning_item` (create every Workstream in
  `PHASE_SEQUENCE = ("Design", "Develop", "Test")`, wire membership + serial
  `blocked_by` chain); `existing_phase_workstreams`. *(The fourth "pass" — Plan —
  is the decomposition act itself; it has no Workstream.)*
- **Triggers.** `POST /planning-items/{id}/decompose`.
- **Inputs.** `planning_item` (existence + title); existing
  `workstream_belongs_to_planning_item` edges (idempotency guard); pm interactive
  check.
- **Outputs.** Creates 3 `workstream` rows in status `Planned`; edges
  `workstream_belongs_to_planning_item` (each → PI) and `blocked_by` (each phase →
  prior phase).
- **States.** Every created Workstream starts `Planned`. Raises `ConflictError`
  if the PI is effective-`interactive`, or if any phase Workstream already exists
  (re-decomposition is a bug, **not** idempotent).
- **Where it lives.** `access/repositories/decomposition.py`. Router
  `api/routers/planning_items.py` (`decompose`).
- **Interactions.** `planning_items`, `pm`, `references`, `workstreams`.

---

## 5. Component: Phase Specialist Agent substrate — Scoping

- **Name & purpose.** Tier-3, the scoping substrate. Records a phase's scope
  decision and feeds forward prior-phase output.
- **Functionality.** `scope_workstream` (create the phase's Work Tasks + drive
  `Planned → Scoping → Ready`, or `Planned → Scoping → Not Applicable` for an
  empty scope); `prior_phase_outputs` (the Work Tasks of this PI's earlier phases,
  ordered by `PHASE_SEQUENCE` — the feed-forward context).
- **Triggers.** `POST /workstreams/{id}/scope`, `GET /workstreams/{id}/prior-phase-outputs`.
- **Inputs.** `workstream` row; its PI via `workstream_belongs_to_planning_item`;
  sibling phase workstreams + their Work Tasks; pm interactive check.
- **Outputs.** `workstreams.patch_workstream` (Planned→Scoping→final);
  `work_tasks.create_work_task(status="Planned")` + `work_task_belongs_to_workstream`
  edge per task. All in the caller's transaction (atomic).
- **States.** Workstream `Planned → Scoping`, then `Scoping → Ready` if any Work
  Tasks created, else `Scoping → Not Applicable` (the §4.3 empty-phase
  assertion). Gated: must be `Planned`, not interactive. Created Work Tasks are
  `Planned`.
- **Where it lives.** `access/repositories/scoping.py`. Router
  `api/routers/workstreams.py` (`scope`, `prior_phase_outputs`).
- **Interactions.** `pm`, `references`, `workstreams`, `work_tasks`.

---

## 6. Component: Area Specialist Agent substrate — Work Task lifecycle

- **Name & purpose.** Tier-4 substrate is the claim/lifecycle on the single-area
  `work_task` entity — the unit a worker agent actually executes.
- **Functionality.** CRUD + `claim_work_task` / `release_work_task`. `area`
  validated against `engagement_areas.valid_area_names` (System ∪ Engagement).
- **Triggers.** `POST /work-tasks/{id}/claim`, `POST /work-tasks/{id}/release`,
  `/work-tasks` CRUD. `create_work_task`/`patch_work_task` also driven by scoping
  and lead.
- **Inputs.** `WorkTask` rows; `work_task_belongs_to_workstream` edges.
- **Outputs.** Writes `WorkTask`; `claim_work_task` sets `work_task_claimed_by`/
  `_claimed_at` and advances `Ready → Claimed`; status timestamps
  `work_task_started_at`/`_completed_at` on `In Progress`/`Complete`.
- **States.** See §1.3. **Claim gates** (all no-op when not release-scoped):
  interactive-PI backstop (`pm.work_task_is_ado_interactive`); idempotent for the
  same claimant, `ConflictError` for a different claimant; PI-204
  single-owner-per-area (`coordination.assert_area_owner`); PI-212
  paused-area-while-thawing (`reopen.assert_area_not_paused`).
- **Where it lives.** `access/repositories/work_tasks.py`. Router
  `api/routers/work_tasks.py`.
- **Interactions.** `_governance`, `change_log`, `engagement_areas`, `pm`,
  `coordination`, `reopen` (last three lazy-imported).

---

## 7. Component: Coordinating runtime (Layer 1, serial)

- **Name & purpose.** PI-132 / DEC-395. The serial spawn → verify → test-gate →
  merge loop, one agent at a time, each in a throwaway git worktree.
- **Functionality.** Pull the next Ready Work Task (`_next_assignment`), resolve
  its contract (`_assignment_for` → `agent_runtime.build_agent_prompt`), spawn one
  `claude` agent on branch `ado/<wtk-id>`, verify by **result** (`verify_result`:
  Work Task is `Complete` *and* the branch has commits), run affected tests
  (`select_test_target` → `run_pytest`), and merge `--no-ff` into `base_branch`.
- **Triggers.** CLI `crmbuilder-v2-runtime` (`coordinating_runtime:main`); also
  composed as `_l1` inside `parallel_runtime`.
- **Inputs.** API via `dispatcher` (`/work-tasks?status=Ready`,
  `/agent-profiles`, `/references`, `/workstreams/{id}`); the reconciliation gate
  (`reconciliation.develop_gate` via `_reconciliation_gate_open`); git worktree
  state; `config.verify_log_dir()`.
- **Outputs.** One spawned agent/iteration; git worktrees (created/removed);
  `--no-ff` merge commit `"ado: merge {branch} (coordinating runtime)"`; PATCH
  `/workstreams/{id}` to set `workstream_needs_attention`/`_reason` on failure;
  red-run pytest logs to `verify_log_dir()` as `{wtk}-{UTC}.log`.
- **States.** Enums `VerifyOutcome {ok, not_complete, no_commits, tests_failed}`,
  `StepResult {merged, paused, drained}`, `MergeStatus {clean, conflict}`. The
  spawned agent (per `operating_protocol`) drives its own Work Task
  `claim → In Progress → Complete`; the runtime gates on the *result*, not the
  agent's exit code (DEC-396).
- **Where it lives.** `crmbuilder-v2/src/crmbuilder_v2/runtime/coordinating_runtime.py`.
- **Interactions.** `dispatcher`, `reconciliation`, `agent_runtime.build_agent_prompt`,
  `config.verify_log_dir`. Reused wholesale (composition) by `parallel_runtime`.

---

## 8. Component: Parallel runtime (Layer 2, pool)

- **Name & purpose.** PI-139 / DEC-397. A capped, concurrency-safe pool of
  agents (each its own worktree), merge-as-complete in completion order, plus
  API-process ownership, the migration lock, the all-or-nothing phase rollback
  (PI-145), and file locks (PI-220).
- **Functionality.** `slots_available` + `select_to_dispatch` (cap +
  no-double-dispatch + blocker-aware) drive `_fill_slots` → `_spawn_one` →
  `_worker`; `_integrate` merges a completed branch; `_coordinate_locks_on_merge`
  / `_reclaim_locks` run the file-lock protocol; `_record_finding` POSTs a
  finding (falling back to `needs_attention`). On any non-MERGED task it pauses
  dispatch, drains in-flight, then **hard-resets `base_branch` to `pre_phase_head`**
  (PI-145 all-or-nothing rollback).
- **Triggers.** CLI `crmbuilder-v2-runtime-pool` (`parallel_runtime:main`);
  instantiated by `ado_runtime.run_pool_for_workstream` (one pool per phase
  Workstream).
- **Inputs.** API via `dispatcher` (eligible Work Tasks, `blocked_by` edges,
  `/health`); reconciliation gate via `_l1._reconciliation_gate_open`;
  `migration_lock.ExclusiveMigrationLock`; git worktree state;
  `access.db.session_scope` + `sub_agent_locks` for file locks; optional shared
  `repo_lock` (set when ADO drives several PIs in parallel).
- **Outputs.** Up to `max_concurrent` spawned agents in parallel worktrees;
  `--no-ff` merges in completion order; `POST /findings`; Workstream
  `needs_attention`; phase rollback (reset to `pre_phase_head`); API process
  management; file-lock acquire/verify/release/reclaim.
- **States.** `TaskOutcome {merged, verify_failed, merge_conflict}`. Migration
  window phased through the lock (§9). `PoolRunReport` carries `pre_phase_head`,
  `rolled_back`, `migrations`, `.merged`.
- **Where it lives.** `crmbuilder-v2/src/crmbuilder_v2/runtime/parallel_runtime.py`.
- **Interactions.** `dispatcher`, `coordinating_runtime` (reuses
  `CoordinatingRuntime`, `Worktree`, `spawn_claude_agent`, `verify_result`,
  `interpret_merge`), `migration_lock`, `sub_agent_locks` + `access.db`
  (lazy). Driven by `ado_runtime`.

---

## 9. Component: Migration lock

- **Name & purpose.** PI-133 / DEC-399. Exclusive migration window over the
  Layer-2 pool — pause-drain-run-resume so a schema migration runs with zero
  concurrent writers.
- **Functionality.** `request` (enqueue a migration callable), `dispatch_allowed`,
  `pending_or_running`, `maybe_run(active_count)`; pure predicates
  `dispatch_allowed(phase)`, `can_enter_exclusive(phase, active_count)`.
- **Triggers.** Consulted each pool tick by `parallel_runtime` (`_fill_slots`
  checks `dispatch_allowed`; the loop calls `maybe_run`/`pending_or_running`).
  Enqueued via `ParallelCoordinatingRuntime.request_migration` → `lock.request`.
- **Inputs.** A `migration_fn` callable + label; the pool's live in-flight
  `active_count`.
- **Outputs.** Runs the migration on the main thread; appends a `MigrationRecord`
  (`requested_at`/`drained_at`/`finished_at`/`active_at_run`/`error`) surfaced
  into `PoolRunReport.migrations`.
- **States.** `MigrationPhase {open, pending, exclusive}`. `OPEN → PENDING`
  (request, pauses dispatch); `PENDING → EXCLUSIVE` once `active_count == 0`;
  runs `fn()`; `EXCLUSIVE → OPEN` in `finally` (resumes even on failure).
  `active_at_run` records `0` as proof of exclusion.
- **Where it lives.** `crmbuilder-v2/src/crmbuilder_v2/runtime/migration_lock.py`.
- **Interactions.** Imported only by `parallel_runtime`.

---

## 10. Component: ADO Design→Develop reconciliation gate + Finding entity

### 10.1 The gate — `runtime/reconciliation.py`

- **Name & purpose.** PI-134 / DEC-400. Withhold Develop Work Tasks until the
  PI's Design phase is settled and there are zero open blocking findings.
- **Functionality.** Pure `evaluate_develop_gate(phase_type, design_complete, findings)`
  + `is_open_blocking(finding)`; I/O resolvers `_owning_workstream`,
  `_planning_item_of`, `_sibling_workstreams`, `_findings_for_targets`,
  `develop_gate(api_base, engagement, work_task)`.
- **Triggers.** `coordinating_runtime._reconciliation_gate_open` and
  `parallel_runtime` (via `_l1`) at dispatch; `ado_runtime.develop_gate_open` at
  the phase level before running a Develop pool.
- **Inputs.** Owning Workstream (`work_task_belongs_to_workstream`), PI
  (`workstream_belongs_to_planning_item`), sibling Workstreams, findings via
  `finding_relates_to` edges; `FINDING_OPEN_STATUSES` from vocab.
- **Outputs.** A `GateDecision {allow, reason, design_complete, open_blocking}`
  (no writes).
- **States.** Design "settled" = Workstream `Complete` or `Not Applicable`;
  a finding holds the gate iff `finding_severity == "blocking"` and
  `finding_status ∈ {open, referred}`.
- **Where it lives.** `crmbuilder-v2/src/crmbuilder_v2/runtime/reconciliation.py`.
- **Interactions.** `dispatcher`, `access.vocab`. Consumed by both coordinating
  runtimes and `ado_runtime`.

### 10.2 The `finding` (`FND-NNN`) entity — `repositories/findings.py`

- **Purpose.** First-class governance record of a cross-area coherence problem
  raised at end of Design (REQ-031..036 / TOP-010).
- **Columns.** `finding_identifier`, `finding_type`, `finding_severity`,
  `finding_summary`, `finding_description`, `finding_status`, `finding_resolution`,
  `finding_resolution_method`, `finding_notes`, `finding_resolved_at`. Required on
  create: type, severity, summary.
- **Vocab.** Types `{conflict, gap, dependency, overlap}`; severities
  `{blocking, advisory}`; statuses `{open, referred, resolved}` (§1.6); resolution
  methods `{revise, order, combine, refer}`.
- **Edges.** `finding_relates_to`, `finding_resolved_by`.
- **Where it lives.** `access/repositories/findings.py`; router
  `api/routers/findings.py` (CRUD only — no custom-action routes).
- **Live state.** 7 findings (FND-001 resolved/blocking; FND-002..007 advisory,
  open).

---

## 11. Component: ADO PI driver (`ado_runtime.py`)

- **Name & purpose.** PI-143. The PI-level scheduler — the deterministic outer
  loop driving one Planning Item `dispatch → decompose → (per phase: scope →
  start → run pool → complete) → In Review`. Plus a PM-level loop
  (`ProjectRuntime`) over a Project's backlog.
- **Functionality.** Pure `decide_next(overview) -> AdoStep` (kinds
  `scope / start / resume / done / pause / blocked`). `AdoRuntime.run()` is the
  per-PI loop (`_execute_phase`, `_resume_phase`, `_patch_pi_status`).
  `run_pool_for_workstream` is the pool seam (delegates to `parallel_runtime`).
  Agent seams: `scope_phase_agent` (Architect Agent scoping), `reconcile_phase_agent`
  (raises findings over a completed Design), `develop_gate_open` (phase-level
  Develop-gate consult), `review_close_pi` (closure reviewer). `task_branch_unmerged`
  is the PI-145 rollback-residue detector. `ProjectRuntime` adds `select_next_pi`,
  `eligible_batch`, `drive_planning_item` (PM auto-dispatch, slice 3).
- **Triggers.** CLI `crmbuilder-v2-ado` (`main`, per-PI) and `crmbuilder-v2-ado-pm`
  (`project_main`, PM loop). Also called as a library by `release_runtime.ado_pi_runner`.
- **Inputs.** Live REST API via `dispatcher` (PI record, `/phase-overview`,
  `/backlog`, edges, `/work-tasks/{id}`, project `execution_mode`); git locally
  (`task_branch_unmerged`).
- **Outputs.** POSTs `/dispatch`, `/decompose`, `/start-execution`,
  `/complete-phase`, `/work-tasks/{id}/release`; PATCHes Work Task and PI status;
  spawns real `claude -p ... --permission-mode bypassPermissions` agents for
  scope/reconcile/review; merges happen inside the delegated pool.
- **States.** Dispatch flips a `_STARTABLE = {Draft, Decomposed, Ready}` PI →
  `In Progress`; on all-phases-terminal, PATCHes PI → `_DONE_STATUS = "In Review"`
  (PM's `review_close_pi` can reach `Resolved`). `_TERMINAL_PHASE = {Complete, Not Applicable}`;
  `_DEVELOP_PHASE = "Develop"` gated via `develop_gate_open`; a completed
  `"Design"` phase triggers the reconcile runner. RESUME rewinds Work Tasks via
  legal transitions only (skips `Complete` with the PI-145 residue guard;
  `Blocked` → pause).
- **Where it lives.** `crmbuilder-v2/src/crmbuilder_v2/runtime/ado_runtime.py`.
- **Interactions.** `dispatcher`, `reconciliation` (`develop_gate`); composes
  `parallel_runtime.ParallelCoordinatingRuntime`. Consumed by `release_runtime`.

---

## 12. Component: Release runtime / conductor (`release_runtime.py`)

- **Name & purpose.** PI-219. The release-pipeline orchestration loop — walks a
  Release through its stage machine (§1.5), delegating the judgment steps
  (demands authoring, decomposition) and the dev lane to injectable
  providers/runners. Optionally drives a release concept → shipped.
- **Functionality.** Pure `decide_next(status, ...) -> ReleaseStep` over step
  kinds `AWAIT_FREEZE, AUTHOR_DEMANDS, RESOLVE_CONFLICTS, ADVANCE_RECONCILIATION,
  PLAN, FINALIZE, ENTER_LANE, DEVELOP, TO_QA, RUN_QA, TO_TESTING, RUN_TEST,
  TO_DEPLOYMENT, SHIP, DONE, BLOCKED`. `ReleaseRuntime.run` / `_execute` /
  `_author_demands` / `_plan` / `_finalize` / `_transition` / `_develop_step` /
  `_gate`. Provider seams: `DemandsProvider`, `DecompositionProvider`, `PiRunner`,
  `GateRunner`. Real wirings: `anthropic_providers(model="claude-opus-4-8")`
  (the LLM demands/decomposition authors), `ado_pi_runner` (returns a `PiRunner`
  that runs `AdoRuntime` with `enable_file_locks=True`),
  `release_gate.anthropic_gate_runner`. `_HALTS = {AWAIT_FREEZE, RESOLVE_CONFLICTS,
  DONE, BLOCKED}`.
- **Triggers.** CLI `crmbuilder-v2-release` (`main`); `--dev-lane` enables the
  development lane, `--manual-gates` skips the LLM gate.
- **Inputs.** Direct DB via `access.db.session_scope` (not HTTP): release row,
  `release_demands`, `reconciliation`, `planning.planning_readiness`, in-scope
  projects/PIs/requirements, `blocked_by` edges. The Anthropic SDK for the two
  LLM providers; the registry for system prompts.
- **Outputs.** Writes release demands (`clear_demands`/`add_demands`), runs
  reconciliation + architecture planning + PI decomposition + `finalize_planning`
  (all via `access.release_orchestration as orch`), release status transitions
  (`releases.transition`), QA/test pass stamps (`releases.qa_pass`/`test_pass`).
  Delegates PI delivery to the ADO runtime and gates to `release_gate`.
- **States.** Drives the §1.5 release lifecycle. `_PRE_FREEZE = {preliminary_planning,
  development_planning}`. Pre-freeze halts (waits for the human). Dev lane:
  `ready → development → qa → testing → deployment → shipped`. PI delivery target
  statuses `delivered_statuses = (In Review, Resolved)`.
- **Where it lives.** `crmbuilder-v2/src/crmbuilder_v2/runtime/release_runtime.py`.
- **Interactions.** `access.planning`, `access.release_orchestration`, `access.db`,
  `access.engagement_scope`, `access.vocab`; lazily the release repos; wires
  `ado_runtime.AdoRuntime` and `release_gate.anthropic_gate_runner`.

---

## 13. Component: Release-level QA/Test gate (`release_gate.py`)

- **Name & purpose.** PI-223. The LLM "Release Lead Agent" judge over the assembled
  release, with a deterministic fail-closed floor; supplies the `gate_runner`
  seam for the dev lane.
- **Functionality.** `release_gate_context(release_identifier, stage)` (deterministic
  grounding: requirements, designs, delivered PIs+areas); `make_gate_runner(judge)`
  (context + fail-closed floor + judge → `(rid, stage) -> bool`);
  `anthropic_gate_runner` (the real structured-output judge, registry prompt
  `AGP-005` / `("release","pi_lead")`, inline `_GATE_SYSTEM` fallback). Output
  schema `_Verdict {passed, summary, findings}`.
- **Triggers.** Wired by `release_runtime.main` when `--dev-lane` and not
  `--manual-gates`; called from `ReleaseRuntime._gate` for stages `"qa"` and
  `"testing"`.
- **Inputs.** Direct DB: in-scope projects/PIs/requirements, Work-Task areas,
  `artifact_versions.versions_for_release`; the Anthropic SDK; the registry
  resolver.
- **Outputs.** Returns a bool pass/fail (logs verdict + findings). The pass
  *stamp* is written by `ReleaseRuntime._gate` (`releases.qa_pass`/`test_pass`).
- **States.** Gates the `qa → testing` and `testing → deployment` transitions.
  **Fail-closed:** no confirmed requirements or no authored designs → automatic
  FAIL.
- **Where it lives.** `crmbuilder-v2/src/crmbuilder_v2/runtime/release_gate.py`.
- **Interactions.** `access.db`; lazily `artifact_versions`, `planning_items`,
  `releases`, `work_tasks`; `release_runtime._registry_system_prompt`.

---

## 14. Component: Release entity (`repositories/releases.py`)

- **Name & purpose.** PRJ-031 keystone. A born-early forming container whose
  `release_status` *is* its pipeline stage; one guarded mutator `transition`
  running the gate predicates + lifecycle stamps.
- **Columns.** `release_identifier` (`REL-`), `release_title`, `release_description`,
  `release_notes`, `release_status`, `release_lane_order`, `engagement_id`, +
  stamps `release_frozen_at`, `release_planned_completely_at`, `release_shipped_at`,
  `release_cancelled_at`, `release_superseded_at`, `release_qa_passed_at`,
  `release_test_passed_at`.
- **Functionality.** `create_release` (born `preliminary_planning`, REQ-209);
  `transition(identifier, to_status)` (the only status mutator — validates the
  pair, runs the gate, stamps); `qa_pass`/`test_pass`; `composition`;
  `planning_item_status_counts`; `set_lane_order`; `patch_release`
  (`_PATCHABLE_FIELDS = {title, description, notes, lane_order}` — status barred);
  `open_correction_release` (creates a `release_corrects_release` edge);
  `delete_release` (soft).
- **Triggers.** `/releases` REST + `/releases/{id}/transition`, `/qa-pass`,
  `/test-pass`, `/composition`; driven by the Release Lead Agent and the desktop
  Releases hub panel (PI-224).
- **Inputs.** Edges read: `project_belongs_to_release`,
  `planning_item_belongs_to_project`, `planning_item_implements_requirement`,
  `workstream_belongs_to_planning_item`, `work_task_belongs_to_workstream`,
  `blocked_by`. Outputs: `release_corrects_release`; `supersedes` required → superseded.
- **States.** §1.5. **Gate predicates** (`_GATE_PREDICATES`, keyed by `(from,to)`):
  - `(development_planning, reconciliation)` → `_check_freeze`: ≥1 project edge AND
    every in-scope requirement `confirmed`. Stamps `release_frozen_at`. **(plan freeze)**
  - `(reconciliation, architecture_planning)` → `_check_no_open_conflicts`.
  - `(architecture_planning, ready)` → `_check_planned_completely`: frozen + every
    in-scope PI decomposed + acyclic work-task `blocked_by`. Stamps
    `release_planned_completely_at`.
  - `(ready, development)` → `_check_single_occupancy`: no other live lane release,
    every `blocked_by` release shipped, lane-order respected.
  - `(qa, testing)` → `_check_qa_passed`; `(testing, deployment)` → `_check_test_passed`;
    `(deployment, shipped)` → `_check_revalidations_complete` (+ `_complete_delivered_projects`).
  - Bounce-back to `development` clears qa/test stamps.
- **Where it lives.** `access/repositories/releases.py`.
- **Interactions.** `_governance`, `planning_items`, `projects`, `reconciliation`,
  `reopen`, `references`. **Live state:** 4 releases — REL-002 `shipped`, REL-003
  `preliminary_planning`, REL-004 `cancelled`, REL-005 `development`.

---

## 15. Component: Reconciliation engine + conflict store (release)

- **Name & purpose.** PRJ-031 release reconciliation (distinct from §10). Merge a
  frozen release's demanded deltas against each artifact's live base into a
  conflict-free delta-set; persist typed conflicts.
- **Functionality.**
  - Pure engine `access/reconciliation.py:reconcile_artifact(base, deltas)` →
    `{merged, conflicts, provenance}`. Deterministic, order-independent N-way
    three-way merge. Facets auto-merge (NONE/IDENTICAL/COMPOSE/ADDITIVE-UNION);
    conflicts only on `facet_value` (competing `set`, or `set`+`add` on same
    facet) and `remove_vs_modify`.
  - Orchestration `access/repositories/reconciliation.py`: `reconcile_release`
    (requires release `reconciliation` status; processes artifacts in
    `_ARTIFACT_RANK` order; merges each against `artifact_versions.live`; upserts
    conflicts); `resolve_conflict` (`open → resolved`, stamps
    `resolving_decision_identifier`/`resolved_value`/`resolved_at`);
    `has_open_conflicts`; `list_conflicts`.
- **Triggers.** `release_orchestration.run_reconciliation` (from
  `release_runtime`); conflict-resolution endpoints.
- **Inputs.** `Release` row (status gate); `ReconciliationConflict` rows;
  `artifact_versions.live` snapshots; demand dicts from `release_demands`.
- **Outputs.** `ReconciliationConflict` rows; resolution fields.
- **States.** Conflict `open → resolved` (§1.8). The `reconciliation →
  architecture_planning` release move is gated on no open conflicts.
- **Where it lives.** `access/reconciliation.py` (engine),
  `access/repositories/reconciliation.py` (store).
- **Interactions.** `artifact_versions`, `_governance`, the release transition gate.

---

## 16. Component: Demand set (`release_demands.py`)

- **Name & purpose.** PI-207. Persist the model-area Reconciliation Agent's
  structured requirement→design deltas ("demands") as a stable, replayable
  reconciliation input.
- **Columns.** `release_demand` keyed by `(release_identifier, requirement_identifier,
  artifact_type, artifact_identifier, field, facet)`; `op`, `value` (JSON),
  `authored_by`.
- **Functionality.** `add_demands` (validate + persist), `list_demands`,
  `clear_demands` (re-author replaces, not duplicates), `as_reconcile_input` (the
  exact shape `reconcile_release` consumes), `_validate`.
- **Triggers.** `POST/GET /releases/{id}/demands`; consumed by
  `release_orchestration.run_reconciliation`.
- **States.** None (plain store). `op ∈ {set, add, remove}`; `artifact_type ∈
  VERSIONED_ARTIFACT_TYPES = {entity, field, persona, process, association}`.
- **Where it lives.** `access/repositories/release_demands.py`.
- **Interactions.** `_governance`, `releases`, `release_orchestration`.

---

## 17. Component: Versioning spine (`artifact_versions.py`)

- **Name & purpose.** PI-208. The versioned, release-tied change spine — one
  generic store, each row a full JSON `snapshot` of one artifact at one
  `version_number`, tied to the release that introduced it.
- **Columns.** `artifact_type`, `artifact_identifier`, `version_number` (per-artifact
  monotonic), `release_identifier`, `snapshot` (JSON), `engagement_id`. Unique on
  `(engagement_id?, artifact_type, artifact_identifier, version_number)`.
- **Functionality.** `snapshot` (append next version, server-assigned `max+1`,
  SAVEPOINT-retry); `live` (**the highest version whose release is `shipped`** —
  in-flight versions are frozen drafts, never returned); `list_versions`,
  `get_version`, `versions_for_release`.
- **Triggers.** Authored by `planning.author_designs` (architecture-planning
  stage); read by `reconciliation` (live base) and the release QA gate.
- **States.** No status of its own; "live" derived from the tied release's
  `shipped` status. `artifact_type ∈ VERSIONED_ARTIFACT_TYPES` (requirements
  excluded by design, REQ-216).
- **Where it lives.** `access/repositories/artifact_versions.py`.
- **Interactions.** `_governance`, `Release`, `planning.py`.

---

## 18. Component: Architecture-planning substrate (`access/planning.py`)

- **Name & purpose.** PI-209. Author each touched artifact's versioned design
  (vN+1) from reconciled delta-sets, and report planned-completely readiness.
- **Functionality.** `author_designs` (snapshot each reconciled delta-set as a
  release-tied vN+1; requires release `architecture_planning`; idempotent —
  skips already-versioned artifacts); `planning_readiness` (deterministic report:
  `frozen`, `in_scope_planning_items`, `undecomposed_planning_items`,
  `designs_authored`, `sequencing_ok`, `ready`, `missing[]`); `plan_release`.
- **Triggers.** `POST /releases/{id}/run-architecture-planning`,
  `GET /releases/{id}/planning-readiness`; called by
  `release_orchestration.run_architecture_planning` / `finalize_planning`.
- **States.** Gates on `release_status == "architecture_planning"`; computes the
  predicate that backs `architecture_planning → ready` (mirrors
  `releases._check_planned_completely`).
- **Where it lives.** `access/planning.py`.
- **Interactions.** `artifact_versions`, `releases` (reuses `_in_scope_*`,
  `_has_cycle`).

### 18.1 Release orchestration plumbing (`access/release_orchestration.py`)

Deterministic stage drivers (no judgment, AL-5): `run_reconciliation` (PI-217,
feeds the demand-set to `reconcile_release`); `reconciled_delta_sets` (pure
re-derivable merge); `run_architecture_planning` (PI-218); `decompose_planning_item_direct`
(AL-3 / DEC-425 — create a PI's workstreams + work-tasks directly, drive each
phase to `Ready`/`Not Applicable`; rejects duplicate phase types, REQ-258);
`finalize_planning` (AL-4 — assert readiness, flip in-scope PIs
`execution_mode interactive → ado`, transition `architecture_planning → ready`).

**Two decomposition paths (reconciled).** Decomposition happens in *one* of two
places, never both: (a) **release-driven** — `decompose_planning_item_direct`
here, during Architecture Planning, drives each phase Workstream to `Ready`/`Not
Applicable` so the ADO later just **executes** (DEC-529: "dev EXECUTES not
re-scopes"); (b) **standalone ADO** — `crmbuilder-v2-ado` on a single PI calls
the §4 `decomposition.decompose_planning_item` + §5 `scoping.scope_workstream`
itself. §11's `dispatch → decompose → scope → …` describes path (b); under a
release, those steps are already done here.

---

## 19. Component: Concurrency — file/resource locks (`access/locks.py`)

- **Name & purpose.** PRJ-030 (FL-1..FL-6). File-level / named-resource check-out
  locks — the backstop under an area owner's intra-area parallel sub-agent
  fan-out.
- **Columns.** `resource_lock`: `resource_name`, `holder`, `acquired_at`,
  `released_at` (NULL = held). Active uniqueness on `resource_name` where
  `released_at IS NULL`.
- **Functionality.** `acquire` (idempotent same-holder; refused if held by another
  — FL-1; concurrent → `ConflictError`); `acquire_many` (all-or-nothing — FL-2);
  `release` (holder-only); `release_all`; `reclaim` (owner-supervised dead-agent
  reclaim — FL-6); `reclaim_stale(ttl)` (TTL backstop); `verify(holder,
  touched_paths)` → `{held, retroactively_acquired, conflicts}` (recompute touched
  resources from the real diff — FL-5); `detect_resources(paths)` (`_DETECTION_RULES`
  maps `migrations/*.py → "migration-chain"`); `held_locks`.
- **Triggers.** The sub-agent runtime (worktree-per-sub-agent + serialized
  merge-back) via `runtime/sub_agent_locks.py`; the Resource Locks monitor panel
  (Reclaim/Release operator actions — PI-225).
- **States.** A lock is **held** (`released_at IS NULL`) or **released**. No
  reacquire of a released row — a fresh acquire creates a new row.
- **Where it lives.** `access/locks.py`. **Endpoint:** `GET /locks` (live — empty
  now; **`/resource-locks` does not exist**). Live: no locks held.
- **Interactions.** `_governance`; wrapped by `runtime/sub_agent_locks.py`.

### 19.1 Runtime wrapper (`runtime/sub_agent_locks.py`)

PI-220. Wraps the lock substrate into acquire/verify/release/reclaim for sub-agent
fan-out; **a no-op outside a dev-lane release** (`dev_lane_release` gates on
`release_status ∈ RELEASE_LANE_STATUSES`). `acquire_declared` (FL-2 all-or-nothing),
`verify_and_release` (FL-5), `reclaim` (FL-6). Called by `parallel_runtime` only
when `config.enable_file_locks` (turned on by `release_runtime.ado_pi_runner`).

### 19.2 Single-owner-per-area (`access/coordination.py`)

REQ-191. Derives lane occupancy + the single-owner gate **from existing Work Task
claims** (no new store). `lane_holder`, `release_of_work_task`, `area_ownership`,
`area_owner`, `assert_area_owner` (the gate: within a lane release, a claim on a
task whose `(release, area)` is already owned by a *different* claimant raises
`ConflictError` — one owner per area, who then fans out sub-agents). No-op outside
a lane release.

---

## 20. Component: Area reopen + cascade revalidation (`access/reopen.py`)

- **Name & purpose.** PI-212/213/214. In-lane reopen of a frozen *area* — pause
  downstream areas while it thaws, with blast-radius-derived approval tiering +
  cascade re-validation. (Frozen *plans* are never reopened; plan corrections go
  to a new Release via `releases.open_correction_release`.)
- **Columns.** `area_reopen`: `release_identifier`, `area`, `reason`, `status`,
  `created_at`, `resolved_at`, `cascade_areas` (JSON), `revalidated_areas` (JSON),
  `approval_tier`, `approval_decision_identifier`, `triggering_finding_identifier`.
- **Functionality.** `reopen_area` (open a reopen; release must be in a lane;
  area must be a ranked spine area; gated by an approval decision unless tier is
  `lead_auto`); `refreeze_area` (`open → resolved`, RW3 resume); `revalidate_area`
  (record a downstream area re-passed its gate — RW4; appends to
  `revalidated_areas`); `outstanding_revalidations` (areas still owed
  re-validation — release can't ship while non-empty); `paused_areas` /
  `is_area_paused` / `assert_area_not_paused` (refuse work on a paused downstream
  area — RW3); `downstream_areas` (higher `SYSTEM_AREA_RANKS` rank);
  `reopen_tier` / `reopen_impact` (blast-radius approval tier).
- **Triggers.** `POST /releases/{id}/area-reopens`, `GET /releases/{id}/reopen-impact`,
  refreeze/revalidate endpoints; `assert_area_not_paused` from `claim_work_task`;
  `_check_revalidations_complete` (ship gate) reads `outstanding_revalidations`.
- **States.** `area_reopen.status`: `open → resolved`. Approval tiers
  `(lead_auto, lead, pm, human)`, index = `max(breadth, depth)`, +1 for a repeat
  reopen of the same area (capped at 3=human). Breadth: 0 downstream → `lead_auto`,
  1-2 → `lead`, ≥3 → `pm`. Depth: foundational rank 1 (`storage`) → `human`.
- **Where it lives.** `access/reopen.py`.
- **Interactions.** `coordination`, `SYSTEM_AREA_RANKS`, `RELEASE_LANE_STATUSES`,
  the release ship gate, `claim_work_task`.

---

## 21. Component: Two-temperature planning claims (`access/repositories/planning_claims.py`)

- **Name & purpose.** PI-207 / DEC-462. Single-threaded-by-area *planning*
  ownership for a frozen release (the planning-lane lock; distinct from the
  dev-lane single-owner in §19.2).
- **Functionality.** `temperature(release_status)` → `"conceptual"` (pre-freeze,
  free/parallel) / `"committed"` (frozen planning, single-threaded) / `None`;
  `area_claims`; `claim_area` (acquire a `(release, area)` planning claim,
  SAVEPOINT + unique-violation → `ConflictError`); `release_area`.
- **States.** `CONCEPTUAL_STATUSES = {preliminary_planning, development_planning}`
  (no enforcement); `COMMITTED_PLANNING_STATUSES = {reconciliation,
  architecture_planning}` (single-threaded-by-area enforced). Claim only allowed
  when `temperature == "committed"`.
- **Where it lives.** `access/repositories/planning_claims.py`.
- **Interactions.** `engagement_areas`, `PlanningAreaClaim`, `Release`.

---

## 22. Component: Agent Profile Registry

### 22.1 Entities

| Entity | Prefix | Key columns | Module |
|---|---|---|---|
| `agent_profile` | `AGP-` | `engagement_id` (nullable scope), `area`, `tier`, `description`, `status` | `repositories/agent_profiles.py` |
| `skill` | `SKL-` | `engagement_id`, `name`, `kind` {instruction,tool}, `description`, `io_contract` (JSON), `backing_callable`, `version`, `status` | `repositories/skills.py` |
| `governance_rule` | `GVR-` | `engagement_id`, `rule_type` (nullable; overlay-match key + `disable:` carrier), `enforcement`, `severity`, `body`, `predicate` (JSON), `version`, `status` | `repositories/governance_rules.py` |
| `learning` | `LRN-` | `engagement_id`, `area`, `tier`, `category` {gotcha,pattern,constraint,preference}, `content`, `status`, `confidence` (int) | `repositories/learnings.py` |

All four are system/shared with a **nullable `engagement_id`** (NULL = system
row, set = engagement overlay) — plain `Base`, not `EngagementScopedMixin`; the
resolver does the scope merge explicitly. Binding edges: `agent_profile_has_skill`,
`agent_profile_governed_by_rule`. Learning edges: `learning_derived_from`,
`learning_contradicted_by`, `learning_promoted_to`.

### 22.2 Resolver (`repositories/registry_resolver.py`)

- **Purpose.** Compose an `agent_profile` id into a runtime-ready **effective
  contract** + a deterministic version stamp.
- **Function.** `resolve_contract(session, profile_id, *, engagement_id=None,
  min_confidence=1) -> dict`. Composition:
  - **system_prompt** = `profile["description"]` + each **instruction**-skill
    description + each advisory rule rendered `RULE (advisory): {body}`, joined by
    `\n\n`.
  - **tools** = the **tool**-kind skills, each `{identifier, name, io_contract,
    backing_callable}`.
  - **enforced_ruleset** = rules with `enforcement ∈ {enforced, enforced_with_override}`,
    each `{identifier, enforcement, severity, body, predicate}`.
  - **advisory_rules** = `{identifier, body}` per advisory rule.
  - **active_learnings** = in-scope evidenced `(area, tier)` learnings with
    `confidence >= min_confidence` (default 1 excludes confidence-0 hunches);
    empty unless `profile.tier ∈ LEARNING_TIERS`.
  - **version_stamp** = `sha256(...)[:16]` over profile + bound items' ids/versions/updated_at.
- **Scope merge.** `_visible(record, engagement_id)`: `status == "active"` AND
  (`engagement_id IS NULL` OR `== active`) — the `WHERE engagement_id IS NULL OR
  == active` rule. `_resolve_rule_overlay` adds engagement **override** (same
  `rule_type` drops the system rule) and **disable** (`rule_type = "disable:<target>"`
  suppresses a matching system rule).
- **Triggers.** `GET /agent-profiles/{id}/contract`; the MCP resolve-contract
  tool; consumed at runtime by `agent_runtime.build_agent_prompt` (§23).
- **Where it lives.** `access/repositories/registry_resolver.py`.

### 22.3 Write-back lifecycle (`repositories/registry_lifecycle.py` + `learnings.py`)

The capture → accumulate → promote → curate loop:

| Stage | Function | Effect |
|---|---|---|
| **Capture** | `learnings.capture(...)` | confidence 1 with evidence (+ `learning_derived_from`), else 0 (bare hunch). |
| **Accumulate** | `learnings.add_evidence(..., contradicts=)` | supporting evidence `+1` (`learning_derived_from`); contradicting `-1` floored at 0 (`learning_contradicted_by`, must target a `work_task`). |
| **Promote → skill** | `registry_lifecycle.promote_to_skill` | create a skill inheriting scope; `learning_promoted_to` edge; learning → `promoted`. |
| **Promote → rule** | `registry_lifecycle.promote_to_rule` | create a governance_rule; **`enforced`/`enforced_with_override` requires `human_approved=True`** (else `UnprocessableError("human_review_required")` — the Needs-Attention hard line). |
| **Cross-engagement** | `cross_engagement_candidates(min_engagements=2)` → `promote_to_system` | group active engagement learnings by `(area, tier, content)` across ≥2 engagements; flip `engagement_id → NULL` (system scope). |
| **Curate** | `curate_area(area, scope=)` | active learnings with a `learning_contradicted_by` edge AND confidence 0 → `stale`. |

### 22.4 Seed (`repositories/registry_seed.py`)

`seed_system_profiles` idempotently seeds the proven prompts as system rows.
`_SEED_PROFILES`: `(storage, architect)`, `(storage, developer)` (incl. one
**enforced** self-verify rule: `ruff` clean + `pytest` green before Complete),
`(model, architect)` (Reconciliation Agent), `(planning, architect)` (Architect
Planning Agent), `(release, pi_lead)` (Release Lead Agent). Per-invocation placeholders
`{AREA}/{WORKSTREAM_ID}/{WORK_TASK}/{API_BASE}/{RELEASE}/{PI}`.

### 22.5 Live state (2026-06-20)

5 agent profiles (AGP-001..005, all system, active: storage×architect,
storage×developer, model×architect, planning×architect, release×pi_lead). 23
skills — **all `kind=tool`** (no `instruction` skills live). 18 governance rules
(17 advisory, 1 enforced). 1 learning (LRN-001, constraint, confidence 1). This
confirms the **[PARTIAL]** note: the registry's *capacity* is built but the
"living knowledge base" is barely populated, and a single generic worker prompt
is string-substituted across areas.

---

## 23. Component: Agent runtime + dispatcher (the spawn path)

### 23.1 `runtime/agent_runtime.py`

- **Purpose.** Resolve a registry contract + a Work Task into the full system
  prompt a spawned worker boots from.
- **Function.** `build_agent_prompt(api_base, engagement, profile_id,
  work_task_id) -> AgentInvocation` — read-only string assembly over
  `GET /agent-profiles/{id}/contract` (system_prompt, tools, enforced_ruleset,
  active_learnings) + `GET /work-tasks/{id}` (area, title, description), with
  placeholder substitution. No writes.
- **Where it lives.** `runtime/agent_runtime.py`. Called by `dispatcher` and
  `coordinating_runtime`.

### 23.2 `runtime/dispatcher.py`

- **Purpose.** Auto-pull the next eligible Work Task, select its agent profile,
  resolve a ready-to-spawn assignment; also the shared HTTP I/O
  (`_get`/`_post`/`_patch`, envelope-unwrapping, `X-Engagement` header) for all
  runtimes.
- **Functions.** `is_work_task_eligible` (status `Ready` + unclaimed + all
  `blocked_by` `Complete`); `select_profile_id(profiles, area, tier)`;
  `eligible_work_tasks`; `next_assignment` (resolution only, no writes);
  `claim_and_start` (Work Task `Ready → Claimed → In Progress`); `complete`
  (→ `Complete`). Constants `_CLAIMABLE_STATUS="Ready"`, `_COMPLETE_STATUS="Complete"`,
  `_DEFAULT_TIER="developer"`.
- **Where it lives.** `runtime/dispatcher.py`. The shared substrate for every
  other runtime module.

---

## 24. Component: Work-unit governance records (Work Ticket, close-out, deposit event)

These are the records the agents and sessions produce/consume; full specs in
`Archive/governance-schema-specs/`.

- **Work Ticket (`WT-NNN`)** — `repositories/work_tickets.py`. A kickoff/handoff
  ticket (`kind ∈ WORK_TICKET_KINDS`, typically `kickoff_prompt`) carrying a
  summary + a repo-relative `work_ticket_file_path` to the canonical kickoff
  `.md`, with an `addresses` edge to its PI. Five-status lifecycle drafted →
  ready → consumed (+ cancelled/superseded). Single-use (≤1 consumption edge);
  `consumed` requires exactly one consumption edge; `superseded` requires a
  `supersedes` edge. **Distinct from a Work Task (`WTK-`).**
- **Close-out payload** — the nine-section JSON (`session`, `conversation`,
  `work_tickets`, `planning_items`, `commits`, `decisions`, `references`,
  `resolves_planning_items`, `addresses_planning_items`) authored at session
  close; applied by `scripts/apply_close_out.py`, which lazy-creates the
  `close_out_payload` + `deposit_event` entities. In Claude Code, governance is
  recorded in **real time** via direct API POST; the close-out path is the
  claude.ai-sandbox fallback (retaining only the git-tracked deposit-event log
  role under the Model A branch protocol).
- **Deposit event** — born-terminal, append-only record of an apply; tees a
  git-tracked `PRDs/product/crmbuilder-v2/deposit-event-logs/dep_NNN.log` (the
  only git-tracked governance trail after PI-β removed snapshots).

---

## 25. CLI entrypoints (how it's actually launched)

From the root `pyproject.toml` `[project.scripts]`:

| Script | → module:function | Launches |
|---|---|---|
| `crmbuilder-v2-api` | `crmbuilder_v2.cli:run_api` | FastAPI/uvicorn REST API on `127.0.0.1:8765` (the server all runtimes hit). |
| `crmbuilder-v2-ado` | `runtime.ado_runtime:main` | Drives **one** Planning Item through its phases → `In Review`. |
| `crmbuilder-v2-ado-pm` | `runtime.ado_runtime:project_main` | PM auto-dispatch over a **Project's** eligible PIs. |
| `crmbuilder-v2-release` | `runtime.release_runtime:main` | Drives a **Release** through the pipeline (LLM agent layer); `--dev-lane` continues development→shipped, `--manual-gates` skips LLM gates. |
| `crmbuilder-v2-runtime` | `runtime.coordinating_runtime:main` | Layer-1 serial loop (one agent at a time). |
| `crmbuilder-v2-runtime-pool` | `runtime.parallel_runtime:main` | Layer-2 parallel pool (one phase's Work Tasks). |

`dispatcher.py` and `agent_runtime.py` have `python -m` CLIs but no console
scripts.

---

## 26. Desktop UI surfaces (read/operate)

Built monitoring/operation panels (per project memory + CLAUDE.md), all under the
desktop app's sidebar:
- **Workstreams** / **Work Tasks** monitoring panels (`ui/panels/workstreams.py`,
  `work_tasks.py`) — read-only ADO state (PI-114).
- **Releases hub** (`ui/panels/releases.py`, PI-224/226) — Overview / Composition
  / Conflicts / Reopens tabs + lifecycle action row; the human planning workbench
  (New Release, Add/Remove projects pre-freeze, Edit title/desc/notes). Freeze =
  the hand-off transition.
- **Resource Locks monitor** (PI-225) — Reclaim (FL-6) + Release operator actions;
  acquire/verify stay agent-side.

(UI confirmations must use `CopyableMessageBox`, not raw `QMessageBox` — PI-124
guard greps `ui/`.)

---

## 27. The agent-system spec in the DB (`TOP-005` tree)

The authoritative *spec* (per DEC-393, specs live in the DB as topic/requirement
records, not `.md`). **TOP-005 "Agent System"** has 12 direct children:
TOP-006 Engagement & Defaults, TOP-007 Agent Roster & Tiers, TOP-008 Agent
Learning & Self-Governance, TOP-009 Delivery Passes, TOP-010 Reconciliation,
TOP-011 Releases, TOP-012 Runtime & Scheduling, TOP-013 Governance Recording
Method, TOP-014 Functionality Intake & PI Creation, TOP-071 Build History
(Retired & Superseded Approaches), TOP-092 Multi-Agent Coordination, TOP-093
Source Check-in/Check-out. Query: `GET /topics/TOP-005` then
`GET /references?target_id=TOP-005&relationship=is_about` (`X-Engagement: CRMBUILDER`).

---

## 28. Evolution / rename notes (so old docs don't confuse you)

| Formerly | Now | Where |
|---|---|---|
| "Workstream" (long-running container, `WS-`) | **Project** (`PRJ-`) | PI-112, DEC-341/345 |
| (the word reused) | **Workstream** = a delivery phase of one PI (`WSK-`) | PI-112, DEC-343/349 |
| `*_belongs_to_workstream` edges | `*_belongs_to_project` | PI-112 |
| Phase Specialist Agent (tier 3, generalist) | **Architect Agent** (per-area) [DESIGNED] | evolution.md §3, DEC-368 |
| Area Specialist Agent (tier 4, generalist) | **Developer Agent** (per-area) [DESIGNED] | evolution.md §3, DEC-368 |
| (none) | **Tester Agent** (new per-area tier) [DESIGNED] | evolution.md §3.1, DEC-368 |
| Phase value "Design" | "Architecture" (legacy 6-phase vocab) | DEC-349 |
| Six phases (Architecture/Development/Testing/Documentation/Data Migration/Deployment) | Four passes (Plan/Design/Develop/Test); `PHASE_SEQUENCE = (Design, Develop, Test)` | evolution.md §1 |
| `SES-NNN` = session | now identifies a **conversation** (PI-073) | DEC-314 |
| `CONV-NNN` = conversation wrapper | now identifies a **session** (PI-073) | DEC-314 |
| new conversations | `CNV-NNN` | DEC-314 |
| Static catalog registry | **Living learning knowledge base** [PARTIAL] | evolution.md §7, registry PRD v0.3 |
| Per-engagement DB files | **Single unified multi-engagement DB** (row `engagement_id`) | PI-123 / PRJ-019 |
| WS-012 Parallel Agent Orchestrator | superseded by the ADO | design.md §10 |
| `db-export/` JSON snapshots | removed; deposit-event logs are the git trail | PI-β |

---

## Sources

**Code (ground truth):**
- `crmbuilder-v2/src/crmbuilder_v2/runtime/`: `ado_runtime.py`,
  `coordinating_runtime.py`, `parallel_runtime.py`, `release_runtime.py`,
  `dispatcher.py`, `agent_runtime.py`, `migration_lock.py`, `reconciliation.py`,
  `release_gate.py`, `sub_agent_locks.py`, `exceptions.py`.
- `crmbuilder-v2/src/crmbuilder_v2/access/repositories/`: `pm.py`, `lead.py`,
  `decomposition.py`, `scoping.py`, `workstreams.py`, `work_tasks.py`,
  `work_tickets.py`, `findings.py`, `reconciliation.py`, `planning_items.py`,
  `projects.py`, `planning_claims.py`, `releases.py`, `release_demands.py`,
  `artifact_versions.py`, `registry_resolver.py`, `registry_lifecycle.py`,
  `registry_seed.py`, `agent_profiles.py`, `skills.py`, `governance_rules.py`,
  `learnings.py`.
- `crmbuilder-v2/src/crmbuilder_v2/access/`: `reconciliation.py`, `coordination.py`,
  `locks.py`, `reopen.py`, `planning.py`, `release_orchestration.py`, `vocab.py`.
- `crmbuilder-v2/src/crmbuilder_v2/api/routers/`: `projects.py`, `planning_items.py`,
  `workstreams.py`, `work_tasks.py`, `findings.py`.
- Root `pyproject.toml` `[project.scripts]`.

**Live V2 DB** (`http://127.0.0.1:8765`, `X-Engagement: CRMBUILDER`, 2026-06-20):
`/projects` (39), `/releases` (4), `/agent-profiles` (5), `/skills` (23),
`/governance-rules` (18), `/learnings` (1), `/findings` (7), `/planning-items`
(234), `/workstreams` (122), `/work-tasks` (150), `/locks` (0), `/topics/TOP-005`.

**Archived design docs** (`PRDs/product/NEW-Master PRDs/Agent PRDs/Archive/`):
`agent-delivery-organization-design.md`, `agent-delivery-organization-evolution.md`,
`agent-pipeline-annotated-map.md`, `multi-agent-release-pipeline-architecture.md`,
`release-pipeline-agent-layer-architecture.md`, `pi-203…216` architecture docs
(`pi-203-file-lock`, `pi-204-coordination`, `pi-205-release-entity`,
`pi-206-qa-test-levels`, `pi-207-two-temperature-planning`, `pi-208-versioning-spine`,
`pi-209-planning-org`, `pi-211-plan-freeze-inviolability`, `pi-212-area-reopen`,
`pi-213-cascade-revalidation`, `pi-214-reopen-approval`, `pi-215-reconciliation-engine`,
`pi-216-freeze-enforcement`), `pi-122-agent-profile-registry-architecture.md`,
the registry PRD, `coordinating-runtime-layer1/2-build-notes.md`,
`ado-orchestration-driver-slice1/2/3-build-notes.md`, `migration-lock-build-notes.md`,
`findings-entity-build-notes.md`, `pi-145-atomic-phase-merge-design.md`,
`pi-147-phase-verification-runs-affected-tests-design.md`,
`pi-157-ado-runtime-resume-design.md`, `governance-schema-specs/*`.

**Cross-references read in place** (`PRDs/product/crmbuilder-v2/`):
`governance-redesign-target-model.md`, `pi-112-execution-plan.md`, the unified-DB
+ Postgres + RBAC foundation docs, and the root `CLAUDE.md` ADO/registry sections.
