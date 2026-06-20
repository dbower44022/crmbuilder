# PI-157 — ADO runtime: resume a phase left In Progress between runs, and persist verify-failure output

Status: **Design spec** (WTK-093, automation area). Delivers the spec only —
implementing the change (Develop) and writing the test code (Test) are separate
Work Tasks in the same Workstream and are **out of scope here**.

Scope of this PI: `runtime/ado_runtime.py` (the `decide_next` decision + a new
RESUME handler in the driver loop), `runtime/coordinating_runtime.py` (the one
shared verify site, `_run_affected_tests`, gains failure-output persistence),
and `config.py` (one new log-path helper beside `api_log_path`). No schema
change, no migration, no new entity, no API-surface change. The fix is
**bounded** — it adds a third adoption path to the existing SCOPE/START
decision and a log write to the existing test-run step; it does not change
dispatch eligibility, the merge mechanism, the reconciliation gate (PI-134),
the migration lock (PI-133), or the PI-145 rollback.

## 1. The problem

The PI-level driver (`ado_runtime.py`) is documented as DB-backed-stateless
("every iteration re-reads `phase-overview` and continues from wherever the
records say things stand", §4.4) — but `decide_next` only *adopts* a phase in
two states: `Planned` → `SCOPE` and `Ready` → `START`
(`ado_runtime.py:114`–`117`). A phase Workstream found `In Progress` between
runs falls through to the catch-all:

```text
return AdoStep(
    StepKind.BLOCKED, workstream=wsid, phase_type=ptype,
    reason=f"phase {wsid} is {p['status']!r} (unexpected between iterations)",
)
```

so the driver refuses exactly the state every interrupted run leaves behind.
Every verify-failure pause **exits the runtime process** (the pool drains, the
driver returns `paused`), and the phase it was executing stays `In Progress` —
meaning every operator resume currently requires manual governance gymnastics.
Hit twice on 06-11-26, in the first production runs:

- **PI-153 / WSK-072 — all tasks complete.** The pool finished every Work Task
  but the run ended before `complete-phase` was issued. On relaunch the driver
  reported BLOCKED; the operator had to call
  `POST /workstreams/WSK-072/complete-phase` by hand, then relaunch.
- **PI-150 / WSK-076 — partial completion after a verify pause.** 1 of 2 tasks
  was Complete; the pool had paused on a verify failure. On relaunch: BLOCKED.
  The operator had to rewind the Workstream `In Progress → Blocked → Ready`
  through the lifecycle escape hatch so `START` would re-adopt it, then
  relaunch.

A related diagnosability gap shares the build surface: when verification fails
the affected-tests run, the runtime logs only pass/FAIL
(`coordinating_runtime.py:691`) and **discards the captured pytest output** —
`TestRunResult.output` (the stdout+stderr tail, `:174`) is dropped on the
floor. The operator learns *that* tests failed but not *which* test or *why*,
and must reproduce the run to find out. On 06-11-26 that reproduction cost was
paid on top of the manual rewind.

## 2. Part 1 — the RESUME step

### 2.1 The chosen approach

`decide_next` gains one new `StepKind` and one new branch; the driver loop
gains one handler that performs a **recovery pass** over the phase's recorded
Work Task states and then re-enters the *existing* pool-run → `complete-phase`
tail that `START` already uses. No Workstream status is ever rewound — the
phase stays `In Progress` throughout, which is truthful (it *is* in progress;
the previous run was just interrupted).

```text
class StepKind(str, Enum):
    SCOPE = "scope"
    START = "start"
    RESUME = "resume"      # NEW: re-enter an In Progress phase from recorded task states
    DONE = "done"
    PAUSE = "pause"
    BLOCKED = "blocked"
```

In `decide_next`, the per-phase dispatch becomes a three-way status switch
(the surrounding precedence — attention PAUSE first, then `all_terminal` DONE,
then first-non-terminal-phase with the `predecessors_terminal` guard — is
**unchanged**):

```text
if p["status"] == "Planned":
    return AdoStep(StepKind.SCOPE, workstream=wsid, phase_type=ptype)
if p["status"] == "Ready":
    return AdoStep(StepKind.START, workstream=wsid, phase_type=ptype)
if p["status"] == "In Progress":
    return AdoStep(StepKind.RESUME, workstream=wsid, phase_type=ptype)   # NEW
return AdoStep(StepKind.BLOCKED, workstream=wsid, phase_type=ptype, reason=…)
```

State table after the change (first non-terminal phase, in canonical order):

| Phase status | Predecessors terminal? | Step |
|---|---|---|
| any | `needs_attention` set on any phase | `PAUSE` (precedence unchanged — see §2.5) |
| `Planned` | yes | `SCOPE` |
| `Ready` | yes | `START` |
| `In Progress` | yes | `RESUME` (new) |
| `Scoping` | yes | `BLOCKED` (unchanged — see below) |
| any non-terminal | no | `BLOCKED` ("blocked by non-terminal predecessors", unchanged) |

`Scoping` stays BLOCKED deliberately: `scope_workstream` drives
`Planned → Scoping → Ready` inside one call, so a `Scoping` row persisted
*between* runs is anomalous (a crash mid-scope) and has no recorded Work Task
basis to resume from — a person should look at it. `decide_next` remains a
pure function of the overview payload; `phase_overview` already supplies
everything the decision needs (`status`, `predecessors_terminal`) — the
per-task reads happen in the driver's handler, not in the decision.

### 2.2 The RESUME recovery pass (driver handler)

In `AdoRuntime.run`, a new branch beside the SCOPE handler. The handler
reads the phase's Work Tasks (the same edge query
`develop_gate_open`/`_workstream_members` already use:
`GET /references?target_id={ws}&relationship=work_task_belongs_to_workstream`,
then `GET /work-tasks/{id}` per edge) and reconciles each task by its recorded
state:

| Task state found | Action | Rationale |
|---|---|---|
| `Complete` | skip (subject to the §2.6 guard) | already done |
| `Ready`, unclaimed | leave — the pool will dispatch it | already eligible |
| `Ready`, `claimed_by` set | release the stale claim (§2.3) | pre-PI-137-shaped row: claim attached without the `Claimed` status |
| `Claimed` | release the stale claim, then PATCH `Claimed → Ready` | direct rewind transition exists in `WORK_TASK_STATUS_TRANSITIONS` |
| `In Progress` | release the stale claim, then PATCH `In Progress → Failed`, then `Failed → Ready` | `In Progress → Ready` is not a legal transition; `Failed` records the dead attempt and `Failed → Ready` is the vocab's retry path |
| `Failed` | PATCH `Failed → Ready` | the retry transition; re-dispatch |
| `Planned` | PATCH `Planned → Ready` | mirrors `start_phase`'s readying (a task scoped after the phase started was never readied) |
| `Blocked` | **do not auto-unblock** — pause (see below) | a person parked it; RESUME must not override human judgment |

After the pass:

- **All tasks `Complete`** → `POST /workstreams/{ws}/complete-phase`
  immediately, log `✔ {pi}: phase {ws} resumed — all tasks already complete`,
  append to `report.completed_phases`, and `continue` the loop. **No pool run,
  no `start-execution`.** This is the PI-153/WSK-072 shape.
- **Any task `Blocked`** → return `paused` with reason
  `"resume: {ws} has Blocked task(s) {ids}; a person parked them — unblock or
  fail them, then relaunch"`. The driver must not guess.
- **Otherwise** (≥1 task now `Ready`) → run the pool against the phase and
  complete it via the **same tail the START path uses** — `pool_runner(cfg, ws)`,
  the `pool_report.paused` check, `complete-phase`, the Design-reconcile
  follow-on — but **without** the `POST /workstreams/{ws}/start-execution`
  call (`start_phase` requires `Ready` and would 409 on an `In Progress`
  Workstream; the phase is already open). The Develop reconciliation gate
  check **is** repeated for a `Develop` phase before the pool runs (§2.5).

Implementation shape: extract the existing START tail (gate check → pool →
pause check → complete-phase → reconcile-after-Design) into a private
`_execute_phase(ws, phase_type, *, open_phase: bool)` so START passes
`open_phase=True` (issues `start-execution`) and RESUME passes
`open_phase=False` after its recovery pass — the two paths share one tail
rather than duplicating it.

Idempotency: the recovery pass is re-runnable. Release is idempotent when
unclaimed; every status PATCH is conditional on the observed state; a resume
that pauses again (a second verify failure) leaves the phase `In Progress`
with the remaining task states recorded, and the next launch RESUMEs again
from exactly there. The driver's existing `max_phases * 2 + 1` iteration
budget needs **one** widening note: a phase can now take up to *three*
decision iterations (scope, start, resume-after-pause is a fresh run so it
does not count) — the budget formula is unchanged; RESUME consumes an
iteration exactly as START does.

### 2.3 Stale-claim detection criteria

**A claim observed during the RESUME recovery pass is stale by definition.**
Precisely: a Work Task in the resuming phase with `work_task_claimed_by`
non-null has no live agent behind it, because

1. a phase Workstream belongs to exactly one PI
   (`workstream_belongs_to_planning_item`) and one `AdoRuntime` drives one PI,
   so no *sibling pool in the same process* can hold claims on this phase's
   tasks (parallel-PI pools under `ProjectRuntime` are scoped per-PI via
   `target_workstream`);
2. the resuming driver performs the recovery pass **before** dispatching any
   agent for this phase, so the claim cannot be from an agent it spawned; and
3. a claim from a *previous* run cannot be live: agents are synchronous
   children of the runtime process (`spawn_claude_agent` is a blocking
   `subprocess.run` with a kill-at-deadline timeout), so when the runtime
   process is gone, its agents are gone.

No `claimed_at`-age heuristic (TTL window) is used, and the design explicitly
rejects one: under the process model above, age adds nothing — a 5-second-old
claim found at RESUME time is exactly as dead as a 5-hour-old one, and a TTL
would only introduce a false-negative window. The single assumption this
rests on is **one operator/runtime per PI at a time** — the same assumption
the rest of the runtime (the repo lock, the merge path) already makes; two
operators concurrently driving the same PI is out of scope and noted as such.

Release mechanics: `POST /work-tasks/{id}/release` with
`{"claimed_by": <the row's recorded work_task_claimed_by>}` — read the value
from the task row and echo it back, because `release_work_task` rejects a
mismatched claimant. Do **not** hardcode `"AGP-runtime"`; the recorded value
is authoritative (a registry-profile agent may claim under another identity).
Release clears `claimed_by`/`claimed_at` only — the status rewind (§2.2 table)
is a separate PATCH (or two) after it.

Worktree/branch residue from the dead attempt needs no recovery action:
`Worktree.create` already deletes a stale same-name `ado/<wtk-id>` branch
before re-creating it (`coordinating_runtime.py:325`), so a re-dispatched
task's fresh agent forks cleanly from the current base.

### 2.4 Interaction with the SCOPE/START adoption paths

RESUME is a third, peer adoption path — not a modifier on the other two:

- **Precedence is positional, unchanged.** `decide_next` still walks phases in
  canonical order and acts on the *first* non-terminal one; the new branch
  only widens which statuses of that phase are actionable. A run that was
  interrupted mid-PI therefore resumes mid-sequence: earlier terminal phases
  skip, the `In Progress` phase RESUMEs, later phases follow normally
  (SCOPE/START) once it completes.
- **PI-level idempotent pre-steps are already correct.** A resumed PI is
  `In Progress`, which is not in `_STARTABLE`, so the dispatch step skips; the
  overview reports `decomposed`, so decompose skips. No change.
- **START is unchanged.** A `Ready` phase still gets `start-execution` (which
  also readies its `Planned` tasks); RESUME never calls `start-execution`.
- **The Develop gate is re-checked on RESUME.** A `Develop` phase resuming
  after an interruption consults `gate_checker` exactly as START does, before
  the pool runs. Rationale: a blocking finding may have been raised between
  the original start and the resume (the gate is cheap, and the pool's
  per-task gate in `_eligible_candidates` would withhold the tasks anyway —
  the phase-level check just pauses with the clearer reconciliation reason,
  preserving the existing behavior split).

### 2.5 Interaction with `needs_attention` (the PI-150/WSK-076 operator flow)

A verify failure flags the owning Workstream `needs_attention`
(`_flag_needs_attention`), and `decide_next`'s attention check runs **before**
everything else — deliberately unchanged. So the post-fix operator protocol
for the PI-150 shape is:

1. read the persisted verify log (Part 2) to see which test failed;
2. fix the cause (or decide the agent must retry);
3. clear the flag — `PATCH /workstreams/{ws}` with
   `{"workstream_needs_attention": false, "workstream_needs_attention_reason": null}`
   — the **single human acknowledgment act** (the flag is set by the runtime,
   cleared by a human, per the DEC-359 overlay model);
4. relaunch the runtime. `decide_next` now passes the attention check, finds
   the phase `In Progress` with terminal predecessors → `RESUME` → the
   recovery pass releases the dead claim, re-readies the failed task, the pool
   re-runs it, and the phase completes.

One PATCH replaces the previous three-PATCH Workstream rewind
(`In Progress → Blocked → Ready`) *plus* flag clear, and — critically — the
rewind path through `start_phase` is no longer involved at all, so its
`Ready`-only precondition stops mattering.

### 2.6 PI-145 interaction — the Complete-but-rolled-back guard

The one place "Complete tasks skipped" is not trivially safe: under PI-145, a
failed phase **rolls back every sibling merge** (`_reset_base_to`), but the
rolled-back siblings' Work Task rows stay `Complete`. A naive RESUME would
skip them, re-run only the failed task, and `complete-phase` a phase whose
earlier deliverables are **not on the base branch** — silent loss.

The recovery pass therefore includes a cheap, detection-only guard: for each
`Complete` task, if its conventional branch `ado/<wtk-id>` still exists
(`git rev-parse --verify --quiet ado/<id>`) **and** carries commits not
reachable from `base_branch` (`git rev-list --count {base}..ado/<id>` > 0),
the task's verified work was un-merged by a rollback. RESUME then returns
`paused` with reason
`"resume: {ws} has Complete task(s) {ids} whose branch is not merged into
{base} (PI-145 rollback residue) — re-merge or re-open them, then relaunch"`.
No auto-re-merge: re-landing a rolled-back branch interleaved with a sibling's
re-run is an ordering judgment this bounded fix does not take (noted as a
future PI). A `Complete` task whose branch is absent or fully merged passes
the guard silently — the common case costs two fast local git reads per
Complete task.

The guard is an injectable seam on `AdoRuntime`
(`unmerged_check: Callable[[AdoRuntimeConfig, str], bool]`, default = the two
git commands against `cfg.repo_root`), mirroring the existing
`pool_runner`/`scope_runner`/`gate_checker` seams so the loop tests stay
git-free.

## 3. Part 2 — persist verify-failure output

### 3.1 Location and naming

A new helper in `config.py`, beside `api_log_path` and following its
repo-rooted shape:

```text
def verify_log_dir() -> Path:
    """Directory for persisted verify-failure pytest output.

    Repo-rooted like ``api_log_path`` so one durable location collects every
    runtime's verify failures regardless of engagement or launch mode.
    """
    return _repo_root() / "crmbuilder-v2" / "data" / "logs" / "verify"
```

`crmbuilder-v2/data/logs/` is already gitignored (the PI-110 API-log entry),
so verify logs are runtime diagnostics, not tracked artifacts — consistent
with `api.log`. The directory is created at write time
(`mkdir(parents=True, exist_ok=True)`), so the no-failure path creates
nothing (mirroring `_build_api_log_config`'s "no log file on `--check-only`"
property).

File naming: `{work_task_id}-{UTC timestamp}.log`, e.g.
`WTK-094-20260612T014530Z.log` (`datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")`).
Timestamped so a retry of the same task after a fix writes a second file
rather than overwriting the evidence of the first failure.

### 3.2 What is written, and where the write happens

The single hook point is `CoordinatingRuntime._run_affected_tests` — already
the one shared verify-test site for **both** the serial loop and the parallel
pool (`_integrate` calls `self._l1._run_affected_tests`), so one change covers
both production paths. On a red run it writes:

```text
work_task:  WTK-094
target:     tests/crmbuilder_v2/runtime
returncode: 1
worktree:   /tmp/ado-ado-wtk-094-…
branch base: main
captured:   2026-06-12T01:45:30Z (tail of combined stdout+stderr, last 20000 chars)
--------------------------------------------------------------------
<TestRunResult.output>
```

Two supporting adjustments:

- **Widen the captured tail.** `run_pytest` currently keeps the last 2000
  chars of `stdout + stderr` — enough for `-q`'s short summary line but often
  not the traceback. Raise the capture to the last **20000** chars
  (`output=(proc.stdout + proc.stderr)[-20_000:]`). The in-memory cost is
  negligible; flag/finding text stays short regardless (§3.3). The
  `TestRunResult` dataclass shape is otherwise unchanged.
- **Thread the task id in.** `_run_affected_tests` needs the Work Task
  identifier for the filename; widen its signature to
  `_run_affected_tests(worktree, work_task_id)` (both call sites already have
  it in hand: `assignment.work_task_id` serial, `a.work_task_id` parallel).

The write is best-effort with the same discipline as `_flag_needs_attention`:
an `OSError` on the log write is itself logged (`(warning) could not persist
verify output: …`) and never masks the `TESTS_FAILED` verdict.

Return shape: `_run_affected_tests` returns
`tuple[VerifyOutcome, str | None]` — the verdict plus the absolute log path
(`None` on a green run or a failed write). Both call sites unpack it; the
explicit return keeps the runtime stateless rather than stashing the path on
an instance attribute that the serialized-but-shared `_l1` would carry between
parallel integrations.

A green run writes **nothing** — persistence is failure-only by design (the
PI names the diagnosability gap on failure; success output has no operator).
`NOT_COMPLETE`/`NO_COMMITS` verdicts never reach the test step and also write
nothing.

### 3.3 What is surfaced to the operator

The log path rides every existing failure surface, so the operator never has
to know the directory convention:

| Surface | Change |
|---|---|
| runtime log line | `  affected-tests: {target} → FAIL (output: {path})` |
| `needs_attention` reason (both sites) | `verification failed: tests_failed (agent rc={rc}) — output: {path}` — the reason string the Workstream carries and the desktop panel shows |
| finding summary (parallel `_record_finding`) | same suffix appended |
| `IterationReport` (serial) | new field `verify_log_path: str | None = None` |
| `TaskReport` (parallel) | new field `verify_log_path: str | None = None` |
| pool `pause_reason` → driver `report.reason` → CLI exit line | unchanged format; the path is reachable through the flag reason and the report fields above (the CLI's `run complete: paused — execution paused in WSK-NNN` line stays stable for the operator scripts that parse it) |

`NOT_COMPLETE`/`NO_COMMITS` failure messages are unchanged (there is no test
output to point at).

## 4. Scope boundary — what this does and does not do

- **Does:** adopt an `In Progress` phase with terminal predecessors; release
  provably-stale claims; rewind stale task states along legal lifecycle
  transitions only; auto-complete an all-Complete phase; detect (not repair)
  PI-145 rollback residue; persist red pytest output to a gitignored log with
  the path on every failure surface.
- **Does not:** rewind any Workstream status (the phase stays `In Progress`
  until `complete-phase`); auto-unblock `Blocked` tasks; auto-clear
  `needs_attention` (human acknowledgment stays mandatory — the PAUSE
  precedence in `decide_next` is untouched); re-merge a rolled-back Complete
  branch (detection-only, §2.6); resume a `Scoping` phase; handle two
  concurrent operators on one PI; persist green-run output; change
  `verify_result`, dispatch eligibility, `select_to_dispatch`, the merge
  mechanism, PI-133, PI-134, or PI-145.

## 5. Verification plan — acceptance criteria for Develop/Test

Mechanism pinned with the existing seams in
`tests/crmbuilder_v2/runtime/test_ado_runtime.py` (`_phase`/`_ov` for the pure
decision; `_World`/`_FakeDriver` for the loop — extend `_World` to carry
per-task state dicts and record release/PATCH calls) and the
`test_runner_fn` fakes in `test_coordinating_runtime.py` /
`test_parallel_runtime.py`. The two 06-11-26 production shapes are the named
acceptance cases.

**(a) Pure decision — `decide_next` unit tests (no I/O):**
- `In Progress` phase, predecessors terminal → `RESUME` with the right
  workstream/phase_type;
- `In Progress` phase, predecessors **not** terminal → `BLOCKED` (unchanged
  guard still wins);
- `Scoping` phase → `BLOCKED` (unchanged);
- attention flag set on an `In Progress` phase → `PAUSE` (precedence over
  RESUME);
- the existing six `decide_next` tests pass unchanged.

**(b) PI-153/WSK-072 shape — all tasks Complete:**
world: one phase `In Progress`, predecessors terminal, every Work Task
`Complete`, branches merged (guard seam returns "merged"). Assert: the driver
issues `complete-phase` for the phase **without** `start-execution` and
**without** invoking `pool_runner`; the phase lands in
`report.completed_phases`; the loop proceeds to DONE and the PI is PATCHed to
`In Review`; no Workstream status write other than the one inside
`complete-phase`.

**(c) PI-150/WSK-076 shape — partial completion after a verify pause:**
world: one phase `In Progress`, predecessors terminal, task A `Complete`
(merged), task B stale-claimed (`Claimed`, `claimed_by` set). Assert: B's
release was POSTed **with B's recorded `claimed_by` value**; B PATCHed
`Claimed → Ready`; `pool_runner` invoked for the phase; `start-execution`
**never** POSTed; **no Workstream rewind PATCH** (`Blocked`/`Ready`) issued;
`complete-phase` issued after the pool returns clean; phase completes.

**(d) Stale `In Progress` task — the two-step rewind:**
task in `In Progress` with `claimed_by` set → release + PATCH
`In Progress → Failed` + PATCH `Failed → Ready`, in that order (the recorded
call sequence proves no illegal `In Progress → Ready` PATCH is attempted).
A `Failed` (unclaimed) task → single `Failed → Ready` PATCH, no release.
A `Planned` task → single `Planned → Ready` PATCH.

**(e) Blocked task and rollback residue pause, not guess:**
- a `Blocked` task in the resuming phase → driver returns `paused` with the
  Blocked-task reason; no pool run, no PATCH on the Blocked task;
- guard seam reports task A `Complete` with an unmerged `ado/`-branch →
  `paused` with the PI-145-residue reason naming the task; no
  `complete-phase`.

**(f) Resume idempotency:** drive the (c) world, have the injected pool pause
again; relaunch a fresh driver against the resulting world → a second RESUME
adopts it again and completes. (DB-backed statelessness, §4.4, now actually
holds across interruptions.)

**(g) Verify-output persistence — both sites, fake runner:**
serial and parallel: a failing fake `test_runner_fn`
(`TestRunResult(passed=False, output="…FAILED test_x…")`) with `verify_log_dir`
pointed at `tmp_path` (monkeypatch the config helper). Assert: exactly one log
file exists, named `{work_task_id}-*.log`, containing the output text and the
header fields; `IterationReport.verify_log_path` / `TaskReport.verify_log_path`
hold the path; the `needs_attention` reason recorded via the flag seam
contains the path. Passing runner → **no file created, directory not created**.
`NOT_COMPLETE` path → no file.

**(h) Real runner construction (DEC-410 — at least one real run):**
extend the existing real-`run_pytest` integration test: a trivially failing
pytest file → `run_pytest(...)` result persisted through
`_run_affected_tests` writes a real file whose content includes pytest's
failure output; assert the tail-widening (a >2000-char synthetic output is
preserved up to 20000).

**(i) No regression — the existing 114 runtime tests stay green.**
All current `tests/crmbuilder_v2/runtime/` tests (114 collected as of this
spec) pass unchanged — in particular the six existing `decide_next` tests, the
full `_FakeDriver` loop suite, `test_resume_without_redispatch_and_dry_run`,
and both verify-failure routing suites. `ruff check` clean on every touched
file is part of the gate.

## 6. Implementation checklist (for the Develop Work Task)

1. `ado_runtime.py`: add `StepKind.RESUME`; add the `In Progress` branch to
   `decide_next` (§2.1); update the module docstring's step list.
2. `ado_runtime.py`: extract the START tail into `_execute_phase(ws,
   phase_type, *, open_phase)` and rewire START through it (§2.2).
3. `ado_runtime.py`: add the RESUME handler — the recovery pass (per-task
   reconciliation table §2.2, release-then-rewind mechanics §2.3), the
   all-Complete short-circuit, the Blocked pause, the §2.6 guard via a new
   injectable `unmerged_check` seam, then `_execute_phase(open_phase=False)`.
4. `config.py`: add `verify_log_dir()` beside `api_log_path()` (§3.1).
5. `coordinating_runtime.py`: widen `run_pytest`'s output tail to 20000 chars;
   change `_run_affected_tests` to `(worktree, work_task_id) ->
   tuple[VerifyOutcome, str | None]` with the failure-only, best-effort log
   write (§3.2); update the serial call site, flag reason, and
   `IterationReport.verify_log_path`.
6. `parallel_runtime.py`: update the `_integrate` call site, flag/finding
   text, and `TaskReport.verify_log_path` (§3.3). No other pool change.
7. Extend the test harnesses (`_World` task states + recorded calls; the
   `verify_log_dir` monkeypatch) and add the §5 cases.
8. Self-verify: `ruff check` + the full `tests/crmbuilder_v2/runtime/` suite,
   including the two named production-shape tests (§5b, §5c).
