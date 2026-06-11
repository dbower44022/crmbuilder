# PI-147 — Phase verification runs the affected test package and blocks merge on any broken pre-existing test

Status: **Design spec** (WTK-086, methodology-process area). Delivers the spec
only — implementing the change (Develop) and writing the test code (Test) are
separate Work Tasks in the same Workstream and are **out of scope here**.

Scope of this PI: `runtime/coordinating_runtime.py` (the serial Layer-1 verify
site + one new pure helper + one new I/O helper) and `runtime/parallel_runtime.py`
(the pool's `_integrate` verify site). No schema change, no migration, no new
entity, no API-surface change. The fix is **bounded** — it adds a test-run gate
to the existing verify step; it does not change dispatch, the merge mechanism,
the reconciliation gate, or the PI-145 rollback.

## 1. The problem

The ADO runtime verifies an agent's work before merging it. Today verification
is `verify_result(work_task, branch_has_commits)`
(`coordinating_runtime.py:105`), which returns `OK` on exactly two conditions —
the Work Task is `Complete` **and** the branch carries commits — and **runs no
tests**. Both runtime sites act on that verdict:

- serial Layer 1, `CoordinatingRuntime.run_one`: `verdict = verify_result(...)`
  then `if verdict is not OK:` flag + pause, else `_merge`
  (`coordinating_runtime.py:494`–`513`);
- the parallel pool, `ParallelCoordinatingRuntime._integrate`:
  `verdict = verify_result(...)` then `if verdict is not OK:` flag + finding +
  `VERIFY_FAILED`, else `_merge` (`parallel_runtime.py:472`–`498`).

So a Work Task whose agent **compiles, commits, and marks the task `Complete`**
merges **green even if it broke a test in another file**. "Compiles + commits +
self-marked Complete" is not "the suite still passes." This is the coverage gap
that let **PI-118 dead-hover** and the **PI-121 cross-file menu** regressions
through: each agent's own change looked done, the runtime had no test signal, and
the breakage landed on `main` for a human to find later.

The merge path that follows is itself sound — a clean merge of a branch that
breaks a sibling file's test still merges cleanly (git has no opinion about test
outcomes). Nothing downstream re-runs tests before advancing the phase. The gap
is precisely that **verification asserts lifecycle state, not test health**.

## 2. The chosen approach (PI-147 bounded design)

**After** the existing `verify_result` `OK` checks pass, and **before** the
merge, run the **affected test package** in the agent's own worktree. If it
fails, produce a new `TESTS_FAILED` verdict and route it through the **existing
non-`OK` fail path** — which already flags `needs_attention`, records a finding
(parallel), and (parallel) triggers the PI-145 atomic phase rollback. The merge
is never reached, so the broken branch never lands.

1. **Keep `verify_result` pure and unchanged.** It still returns only `OK` /
   `NOT_COMPLETE` / `NO_COMMITS` over `(work_task, branch_has_commits)` — no
   I/O. Its five existing direct unit tests stay valid (§9d).
2. **Add a test-run step** after an `OK` verdict: resolve which test package the
   task's source changes affect, run it in the worktree via an **injectable
   runner**, and fold the result back into the verdict — `OK` stays `OK` on a
   green run, becomes `TESTS_FAILED` on a red run.
3. **Reuse the existing fail path verbatim.** Because the combined verdict is
   re-checked by the **same** `if verdict is not OK:` block that already exists
   at both sites, a `TESTS_FAILED` verdict drives exactly the established
   behavior — serial: `_flag_needs_attention` + `PAUSED`; parallel:
   `_flag_needs_attention` + `_record_finding` + `TaskOutcome.VERIFY_FAILED`,
   which `run()` already turns into `paused` and a phase rollback (PI-145).
4. **Tests run on the agent's branch, in isolation from base** — the worktree is
   forked from `base_branch` and carries only this task's commits, so a failure
   is attributable to *this* task. This catches a cross-file pre-existing test
   the task broke; it does not attempt to catch a post-merge interaction between
   two siblings (§7, scope boundary).

Why fold into the existing verdict rather than add a parallel gate: the two
sites already branch once on `verdict is not OK`, already flag, already (parallel)
rollback. Mapping a test failure onto a new `VerifyOutcome` member reuses **all**
of that wiring with no new fail/flag/rollback code — the smallest change that
closes the gap, mirroring PI-145's "reuse the existing pause/flag path, add only
what was missing" shape.

## 3. The new `VerifyOutcome` member and how it routes

Add one member to the existing enum (`coordinating_runtime.py:60`):

```text
class VerifyOutcome(str, Enum):
    OK = "ok"
    NOT_COMPLETE = "not_complete"
    NO_COMMITS = "no_commits"
    TESTS_FAILED = "tests_failed"   # NEW: Complete + commits, but affected tests red
```

`TESTS_FAILED` is **produced by the new test-run step, never by `verify_result`**
— `verify_result` is pure and cannot run a subprocess. The loop computes a
*combined* verdict:

```text
verdict = verify_result(refreshed, has_commits)      # OK / NOT_COMPLETE / NO_COMMITS
if verdict is VerifyOutcome.OK:
    verdict = self._run_affected_tests(worktree)     # OK or TESTS_FAILED
if verdict is not VerifyOutcome.OK:
    <existing fail path — unchanged>
```

Routing, by site:

| Site | `TESTS_FAILED` flows to | Net effect |
|---|---|---|
| serial `run_one` | the existing `if verdict is not OK:` block → `_flag_needs_attention` + `IterationReport(result=PAUSED, verify=TESTS_FAILED, …)` | loop pauses for a human; branch unmerged |
| parallel `_integrate` | the existing `if verdict is not OK:` block → `_flag_needs_attention` + `_record_finding` + `TaskReport(outcome=VERIFY_FAILED, verify=TESTS_FAILED, …)` | `run()` sets `paused`; at phase end PI-145 `_reset_base_to(pre_phase_head)` undoes every sibling merge; branch unmerged |

Note the two enums stay distinct: `TESTS_FAILED` is a **`VerifyOutcome`**
(the verdict); the parallel pool's coarse **`TaskOutcome`** still has only
`MERGED` / `VERIFY_FAILED` / `MERGE_CONFLICT`, and any non-`OK` verdict maps to
`TaskOutcome.VERIFY_FAILED` exactly as `NOT_COMPLETE` / `NO_COMMITS` do today.
This is why the PI-145 rollback predicate (`any r.outcome is not MERGED`) fires
on a test failure with **no change to PI-145**.

## 4. The pure test-selection helper (§ mapping)

A new **pure** decision helper on `coordinating_runtime.py`, beside the other
pure helpers (`verify_result`, `pause_reason_for`, `interpret_merge`), so it is
unit-tested directly with no I/O:

```text
# The src subtrees that mirror a tests/ package, 1:1.
_MIRRORED_SUBTREES = frozenset(
    {"access", "api", "bootstrap", "mcp_server", "migration", "runtime", "ui"}
)
_SRC_PREFIX = "crmbuilder-v2/src/crmbuilder_v2/"
_TEST_ROOT = "tests/crmbuilder_v2"

def select_test_target(touched_paths: Iterable[str]) -> str:
    """Map the source files a task touched to the pytest target to run.

    Returns a single, conservative pytest target:

    * the mirroring package ``tests/crmbuilder_v2/<sub>`` **iff** every touched
      file under the v2 source tree resolves to the *same* mirrored subtree;
    * the full ``tests/crmbuilder_v2`` suite otherwise — the conservative
      fallback when the change is ambiguous (spans >1 subtree, touches a
      top-level module such as ``cli.py``/``config.py`` with no mirroring
      package, touches files outside the v2 source tree, or the touched set is
      empty/unknown).
    """
```

Mapping rules (the Develop task must encode exactly these):

- A touched path counts toward selection only if it starts with
  `crmbuilder-v2/src/crmbuilder_v2/` (`_SRC_PREFIX`). Its subtree is the first
  path segment after the prefix.
- If **all** in-scope touched files share one subtree **and** that subtree is in
  `_MIRRORED_SUBTREES`, the target is `tests/crmbuilder_v2/<sub>`.
  (E.g. only `…/runtime/coordinating_runtime.py` touched →
  `tests/crmbuilder_v2/runtime`; only `…/ui/foo.py` →
  `tests/crmbuilder_v2/ui`.)
- **Otherwise → full suite `tests/crmbuilder_v2`.** This covers, deliberately:
  - **two or more distinct subtrees** touched (a change that spans `runtime` and
    `ui` could break either package — run both, i.e. the whole suite);
  - a touched **top-level src module** (`cli.py`, `config.py`) that has no
    mirroring package directory;
  - any touched path **outside** `crmbuilder-v2/src/crmbuilder_v2/` (docs, the
    parent app, a `.md` spec — a source change we cannot localize);
  - an **empty / unreadable** touched set.

Path note — the spec's shorthand "`src/crmbuilder_v2/ui/ → tests/crmbuilder_v2/ui/`"
elides two real facts the Develop task must respect: (1) the source tree is
nested under `crmbuilder-v2/` while the **tests live at the repo root**
(`tests/crmbuilder_v2/…`, *not* `crmbuilder-v2/tests/…`); (2) `git diff
--name-only` yields paths relative to the worktree (repo) root, so they carry the
full `crmbuilder-v2/src/crmbuilder_v2/…` prefix. The mapping transforms
`crmbuilder-v2/src/crmbuilder_v2/<sub>/…` → `tests/crmbuilder_v2/<sub>`.

Why an allowlist constant rather than a filesystem probe: keeping the helper pure
makes it trivially unit-testable (the §9 mapping cases are pure-function
assertions, no tmp repo) and deterministic. The allowlist is the set of src
subtrees that mirror a tests package today; a touched subtree *not* in the
allowlist (a future src package with no tests yet, e.g.) conservatively falls
back to the full suite rather than naming a non-existent target. The Develop task
keeps `_MIRRORED_SUBTREES` beside the source/test trees it describes, with a
comment to update it when a new mirrored package lands.

## 5. The injectable test-runner seam

Mirror the established `spawn_fn` seam (`coordinating_runtime.py:298`,
injected on the runtime, defaulting to the real implementation):

```text
@dataclass
class TestRunResult:
    passed: bool
    returncode: int
    target: str
    output: str = ""        # tail of combined stdout+stderr, for the flag/finding

TestRunnerFn = Callable[[str, str], TestRunResult]   # (worktree_path, pytest_target)

def run_pytest(worktree_path: str, target: str, *, timeout: int = 1800) -> TestRunResult:
    """Default runner: ``uv run pytest <target>`` from the worktree root.

    The repo's tests run from the repo root with ``uv run pytest
    tests/crmbuilder_v2/…`` (there is no ``crmbuilder-v2/pyproject.toml`` — v2 is
    bundled into the root distribution), so the worktree root *is* the correct
    cwd and ``target`` is a repo-root-relative path.
    """
    proc = subprocess.run(
        ["uv", "run", "pytest", target, "-q"],
        cwd=worktree_path, capture_output=True, text=True, timeout=timeout,
    )
    return TestRunResult(
        passed=proc.returncode == 0, returncode=proc.returncode,
        target=target, output=(proc.stdout + proc.stderr)[-2000:],
    )
```

The seam is a field `test_runner_fn: TestRunnerFn | None = None` on
**`CoordinatingRuntime`** (beside `spawn_fn`), defaulting to `run_pytest`.
Single-sourcing it on the Layer-1 runtime is what lets the **parallel** site
reuse it without a second seam: `ParallelCoordinatingRuntime` already composes a
Layer-1 `self._l1` and reuses `_l1._merge` / `_l1._flag_needs_attention`; it adds
its own pass-through field and forwards it in `__post_init__`
(`self._l1.test_runner_fn = self.test_runner_fn`), exactly as it forwards
`log`. **Both required sites then call the one helper** —
`self._l1._run_affected_tests(worktree)`:

```text
def _run_affected_tests(self, worktree) -> VerifyOutcome:
    """Run the affected test package in ``worktree``; OK if green, else TESTS_FAILED.

    Resolves the touched source files (git, I/O), maps them to a single pytest
    target (pure ``select_test_target``), and runs it through the injectable
    runner. A non-zero pytest exit blocks the merge.
    """
    touched = worktree.changed_files(self.config.base_branch)   # §6
    target = select_test_target(touched)                         # §4 (pure)
    runner = self.test_runner_fn or run_pytest
    result = runner(worktree.path, target)
    self.log(f"  affected-tests: {target} → {'pass' if result.passed else 'FAIL'}")
    return VerifyOutcome.OK if result.passed else VerifyOutcome.TESTS_FAILED
```

Unit tests inject a fake `test_runner_fn` that returns a `TestRunResult` of the
desired `passed` value without shelling out — the §9 control-flow cases. The
**real** `run_pytest` is exercised by the DEC-410 construction test (§9, real
runner).

## 6. Touched-files detection (the one new I/O helper on `Worktree`)

Add a method beside `Worktree.has_commits_beyond` (`coordinating_runtime.py:257`),
matching its shape (a single `_git` call on `self.path`, parse in Python):

```text
def changed_files(self, base_ref: str) -> list[str]:
    """Source paths this branch changed since it forked from ``base_ref``.

    Uses the three-dot merge-base diff so sibling merges that advanced
    ``base_ref`` after this worktree forked are NOT counted as this task's
    changes — only commits on this branch since the fork point appear.
    """
    out = _git(self.path, "diff", "--name-only", f"{base_ref}...HEAD").stdout
    return [line.strip() for line in out.splitlines() if line.strip()]
```

Design note the Develop task must honor — **three-dot (`{base}...HEAD`), not
two-dot**. On the parallel path, a sibling's merge can advance `base_branch`
*after* this worktree forked; a two-dot `base..HEAD` diff would then surface the
sibling's files as spurious "changes" here and could wrongly widen (or, via the
ambiguity fallback, just widen to the full suite — still safe, but noisy and
wrong about attribution). The three-dot diff is taken against the **merge base**
(the fork point), so it reports exactly this branch's own changes. This mirrors
the intent of `has_commits_beyond`'s `rev-list base..HEAD` (commits unique to the
branch) but for the *file* set, and must run **inside `self._repo_lock`** on the
parallel site for the same reason `has_commits_beyond` does
(`parallel_runtime.py:455`) — it is a git read on a shared repo.

## 7. Hook points, ordering, and lock scope

### 7.1 Serial Layer 1 — `CoordinatingRuntime.run_one`

The test run goes immediately after the `verify_result` call
(`coordinating_runtime.py:494`), before the existing `if verdict is not OK:`
block. The worktree is still live (it is removed only in the method's `finally`,
`:541`):

```text
verdict = verify_result(refreshed, has_commits)
if verdict is VerifyOutcome.OK:
    verdict = self._run_affected_tests(worktree)     # NEW
self.log(f"  verify: {verdict.value} (branch_has_commits={has_commits})")
if verdict is not VerifyOutcome.OK:
    self._flag_needs_attention(
        assignment.work_task_id,
        f"verification failed: {verdict.value} (agent rc={returncode})",
    )
    return IterationReport(result=StepResult.PAUSED, verify=verdict, …)
merge = self._merge(assignment.branch)
…
```

No lock on the serial path (Layer 1 is single-threaded). The existing flag
message string already interpolates `verdict.value`, so `tests_failed` flows into
the human-visible reason with no new format code.

### 7.2 Parallel pool — `ParallelCoordinatingRuntime._integrate`

Same insertion after `verify_result` (`parallel_runtime.py:472`), before the
existing non-`OK` branch. The worktree (`run.worktree`) is still live here — it
is removed on the fail branch (`:485`) and after merge (`:500`); the test run
must precede both:

```text
verdict = verify_result(run.refreshed_task, run.has_commits)
if verdict is VerifyOutcome.OK:
    with self._repo_lock:
        verdict = self._l1._run_affected_tests(run.worktree)   # NEW (git read under lock)
if verdict is not VerifyOutcome.OK:
    self._l1._flag_needs_attention(a.work_task_id, f"verification failed: {verdict.value} …")
    self._record_finding(a.work_task_id, f"verification failed: {verdict.value}")
    run.worktree.remove()
    return TaskReport(outcome=TaskOutcome.VERIFY_FAILED, verify=verdict, …)
with self._repo_lock:
    merge = self._l1._merge(a.branch)
    …
```

Lock scope, stated precisely:

| Step | Under `self._repo_lock`? | Why |
|---|---|---|
| `changed_files` git read (inside `_run_affected_tests`) | **yes** | git read on the shared repo, like `has_commits_beyond` |
| `select_test_target` (pure) | n/a | no I/O |
| `run_pytest` subprocess | **see note** | runs in the isolated **worktree**, touches no shared `.git` index of the parent |

Lock-scope decision the Develop task must settle: the **pytest subprocess itself
runs in the worker's own worktree directory** and does not mutate the shared
parent repo, so holding `self._repo_lock` across the (possibly long) test run
would needlessly serialize otherwise-independent test runs and erode the pool's
parallelism. The recommended shape is therefore: take the lock for the brief
`changed_files` git read, **release it**, run pytest **without** the lock, then
re-take the lock for `_merge`. The simplest correct first cut (lock held across
the whole `_run_affected_tests`, as written above for clarity) is acceptable for
the bounded fix but is called out here as the one place the Develop task may
tighten the lock for throughput — and the Test task should not assert the lock is
held during the subprocess. Running the test in `_integrate` (main thread,
serialized) rather than in `_worker` is per the Work Task's explicit instruction;
hoisting it into `_worker` for full test-run parallelism is a noted, **out-of-scope**
future optimization.

## 8. Scope boundary — what this does and does not catch

- **Catches:** a task whose branch breaks a test in the **affected package**
  (the mapped subtree, or any package when the change is ambiguous → full suite).
  This is the PI-118 / PI-121 class: an agent edits a file and breaks a
  pre-existing test elsewhere in (or beyond) the same package, then self-marks
  Complete. The pre-merge run in the agent's own worktree fails → `TESTS_FAILED`
  → no merge.
- **Does not catch (deliberately, bounded):** a *post-merge interaction* defect
  that only manifests once two siblings' branches are combined on `main` — each
  branch passes its own affected package in isolation, but the merged result
  breaks. PI-147 verifies each branch **pre-merge, in isolation from base**;
  re-running tests on `main` after each merge is a heavier, separate change and
  is **not** in scope. (PI-145's atomic phase rollback already bounds the blast
  radius of a *merge* failure; a post-merge *test* failure across siblings is the
  residual gap a future PI may close by re-running on the integrated `main`.)
- **Does not change** dispatch, the reconciliation gate (PI-134), the migration
  lock (PI-133), or the PI-145 rollback mechanism — it only adds a verdict input
  upstream of the merge that those mechanisms already react to.

The conservative full-suite fallback is the safety valve: whenever the affected
package cannot be unambiguously localized, the **whole** `tests/crmbuilder_v2`
suite runs, so a localization miss never silently narrows coverage — it widens
it.

## 9. Verification plan — acceptance criteria for Develop/Test

Mechanism pinned with the existing injected seams in
`tests/crmbuilder_v2/runtime/`. The Develop/Test task **must** extend the two
shared harnesses so the existing tests stay green by construction (§9d):

- `tests/crmbuilder_v2/runtime/test_parallel_runtime.py`'s `_make_runtime`
  (`:229`) and `_FakeWorktree` (`:194`): inject a **passing** fake
  `test_runner_fn` by default (returns `TestRunResult(passed=True, …)`), and give
  `_FakeWorktree` a `changed_files(base_ref)` stub (default `[]` → full-suite
  target, harmless under the fake runner). This mirrors how PI-145 added stubbed
  `_base_head` / `_reset_base_to` so the pool-loop tests stay git-free.
- `tests/crmbuilder_v2/runtime/test_coordinating_runtime.py`'s serial helper
  (`:168` area) and its `_FakeWorktree` (`:140`): same — default passing runner +
  `changed_files` stub.

**(a) Mapping — pure-function unit tests for `select_test_target`** (no repo):
- only `crmbuilder-v2/src/crmbuilder_v2/runtime/foo.py` →
  `tests/crmbuilder_v2/runtime`;
- only `…/ui/bar.py` → `tests/crmbuilder_v2/ui`;
- `…/runtime/foo.py` **and** `…/ui/bar.py` (two subtrees) →
  `tests/crmbuilder_v2` (ambiguous → full suite);
- a top-level `crmbuilder-v2/src/crmbuilder_v2/cli.py` → `tests/crmbuilder_v2`
  (no mirroring package);
- a path outside the v2 src tree (`PRDs/…/foo.md`) → `tests/crmbuilder_v2`;
- empty touched set → `tests/crmbuilder_v2`.

**(b) OK pass-through (fake runner green) — both sites.**
Serial: an otherwise-clean task with a fake runner returning `passed=True`
verifies `OK` and **merges** (the existing serial all-clean assertion is
unchanged; add an assertion that the runner was invoked). Parallel: an
all-clean two-task run with a passing fake runner yields both
`TaskOutcome.MERGED`, `report.paused is False`, `report.rolled_back is False`.

**(c) TESTS_FAILED routing → fail path / rollback — both sites.**
Serial: fake runner returns `passed=False` for an otherwise-clean task
(`Complete` + commits). Assert: `verdict`/`IterationReport.verify is
VerifyOutcome.TESTS_FAILED`; `result is StepResult.PAUSED`;
`_flag_needs_attention` fired (owning Workstream in `rt._flagged`); **no `_merge`
call** (record-and-assert-not-called, or assert `report.merge is None`).
Parallel: one of two tasks gets a failing fake runner; assert that task's
`TaskReport.outcome is TaskOutcome.VERIFY_FAILED` with `verify is TESTS_FAILED`,
`_record_finding` and `_flag_needs_attention` fired, and — proving the PI-145
tie-in — `report.paused is True`, `report.rolled_back is True`,
`report.rolled_back_to == pre_phase_head` (the clean sibling's merge is **also**
undone), via the existing recorded-`_reset_base_to` seam. This reuses, not
duplicates, PI-145's `test_verify_failure_triggers_same_rollback_as_conflict`
shape.

**(d) `verify_result` purity preserved — no regression.**
The five existing direct `verify_result` unit tests
(`test_coordinating_runtime.py:43`–`:59`: OK, NOT_COMPLETE on In Progress /
Claimed, NO_COMMITS) **must pass unchanged** — `verify_result` is not touched and
still returns only its three outcomes. `TESTS_FAILED` is asserted only through
the new `_run_affected_tests` step, never as a `verify_result` return.

**(e) Real runner construction — per DEC-410 (at least one real run).**
A `tmp_path` integration test that exercises the **actual** `run_pytest`
default (no fake): write a throwaway directory containing one trivially
**passing** pytest file and assert `run_pytest(path, "<that file>").passed is
True` and `returncode == 0`; write one trivially **failing** file and assert
`passed is False`, `returncode != 0`, and that `_run_affected_tests` maps that to
`VerifyOutcome.TESTS_FAILED`. This proves the real subprocess construction and
the green/red→verdict mapping, analogous to PI-145's real-git integration tests
(`test_real_git_clean_merges_land_then_reset_undoes_them`). It need not invoke
the heavy v2 suite — a tiny target keeps it fast while still exercising the real
`uv run pytest` command path.

**(f) No regression — the existing 104 runtime tests stay green.**
All current `tests/crmbuilder_v2/runtime/` tests
(`test_ado_runtime.py` 27, `test_coordinating_runtime.py` 20,
`test_dispatcher.py` 8, `test_migration_lock.py` 9,
`test_parallel_runtime.py` 25, `test_reconciliation.py` 15 = **104**) continue
to pass. In particular the existing serial merge test, the parallel
`test_two_agents_run_in_parallel_and_both_merge`,
`test_merge_conflict_pauses_dispatch_and_flags`,
`test_verify_failure_pauses_and_flags`, the PI-145 rollback tests, and
`test_drains_cleanly_when_no_work` must stay green — the all-clean ones now run
through the injected passing runner (added in `_make_runtime` / the serial
helper, §9 preamble); their existing assertions must not change. The
`--max-concurrent 1` serial-path happy run must show identical all-clean
behavior. (New tests added by this PI raise the count above 104; the **existing**
104 must not regress.)

`ruff check` clean on every touched file (`coordinating_runtime.py`,
`parallel_runtime.py`, and the two test modules) is part of the gate.

## 10. Implementation checklist (for the Develop Work Task)

1. `coordinating_runtime.py`: add `VerifyOutcome.TESTS_FAILED` to the enum (§3).
2. `coordinating_runtime.py`: add the pure `select_test_target(touched_paths)`
   helper + `_MIRRORED_SUBTREES` / `_SRC_PREFIX` / `_TEST_ROOT` constants,
   beside the other pure helpers (§4).
3. `coordinating_runtime.py`: add `TestRunResult`, the `TestRunnerFn` alias, and
   the default `run_pytest` runner, beside `spawn_claude_agent` / `SpawnFn`
   (§5).
4. `coordinating_runtime.py`: add `Worktree.changed_files(base_ref)` beside
   `has_commits_beyond` (three-dot merge-base diff, §6).
5. `coordinating_runtime.py`: add `test_runner_fn: TestRunnerFn | None = None`
   to `CoordinatingRuntime`, and the `_run_affected_tests(worktree)` method
   (§5).
6. `coordinating_runtime.py`: in `run_one`, fold the test run into the verdict
   after `verify_result`, before the `if verdict is not OK:` block (§7.1). Do
   **not** otherwise change the fail/flag/merge wiring.
7. `parallel_runtime.py`: add a pass-through `test_runner_fn` field and forward
   it to `self._l1` in `__post_init__`; in `_integrate`, fold the test run into
   the verdict after `verify_result`, before the existing non-`OK` branch
   (§7.2). Do **not** change `_merge`, the merge loop, `select_to_dispatch`, the
   PI-145 rollback, or any flagging/finding path.
8. Extend `_make_runtime` / the serial test helper to inject a default passing
   `test_runner_fn` and give the `_FakeWorktree`s a `changed_files` stub (§9
   preamble) — the non-regression mechanism.
9. Self-verify: `ruff check` + the runtime test suite (§9f), including the new
   mapping unit tests, the both-sites routing tests, and the real-runner
   construction test (§9e, DEC-410).
