# Coordinating runtime — Layer 1 build notes (PI-132)

Status: **Built on branch `pi-132`** (Develop WSK-022 + Test WSK-023). Left
**In Progress** for a separate PM session to verify the working-demo bar, merge
to `main`, and resolve PI-132. Governed by SES-160.

This documents what Layer 1 is, how it is wired, and the end-to-end demo that
proves it. The spec is **DEC-395**; the requirements are **REQ-052…058** under
topic **TOP-012**.

## What Layer 1 is

The earlier "dispatcher" (`runtime/dispatcher.py`) found the next eligible Work
Task and resolved an agent's contract, then **only printed a prompt** — it never
ran an agent. Layer 1 closes that loop. It is a **serial** control loop (one
agent at a time; concurrency is Layer 2 and out of scope) that repeatedly:

1. **finds** the next ready Work Task — `Ready`, unclaimed, every `blocked_by`
   predecessor `Complete` (reuses the dispatcher's eligibility logic);
2. **resolves** that `(area, tier)` agent's contract from the registry (reuses
   `agent_runtime.build_agent_prompt`), with a **built-in minimal contract
   fallback** so the loop runs even when the registry has no matching profile;
3. **spawns one Claude Code agent** in a fresh git worktree taken from the base
   branch HEAD, with the resolved contract + an operating protocol as its prompt
   (`claude -p … --permission-mode bypassPermissions`). The agent claims the
   task, does the work, commits, and drives the task to `Complete`;
4. **waits**, then **verifies by result** — the Work Task is `Complete` in the
   DB *and* its branch carries commits (DEC-396: verification is by result, not
   by the agent's process exit);
5. **merges** the worktree's branch back into the base branch (`--no-ff`);
6. marks the step done and moves on;
7. **pauses for a human** (`needs_attention`) at the gated points — a pre-flagged
   task, a failed verification, or a merge conflict (never force-resolved).

## Where it lives

- `crmbuilder-v2/src/crmbuilder_v2/runtime/coordinating_runtime.py` — the loop.
  - Pure decisions (`verify_result`, `pause_reason_for`, `interpret_merge`) and
    prompt assembly (`operating_protocol`, `minimal_contract_prompt`) are
    separated from the git/subprocess/HTTP I/O, so the loop's behavior is
    unit-testable without a server, a worktree, or a real agent.
  - `Worktree` wraps `git worktree add/remove`; `spawn_claude_agent` runs the
    `claude` CLI non-interactively; `CoordinatingRuntime` is the loop with the
    spawn seam injectable for tests.
  - `seed_minimal_profile` seeds a system Area-Specialist `agent_profile` so the
    genuine registry contract path can be exercised (REQ-054).
- `crmbuilder-v2-runtime` — console-script entry point (in `pyproject.toml`).
- `tests/crmbuilder_v2/runtime/test_coordinating_runtime.py` — pure-decision and
  loop control-flow tests (happy path merges; not-complete / no-commits / merge
  conflict / pre-flagged all pause and flag for a human; dry-run; drained).

## How to run it

```bash
# One real Work Task, isolated demo repo, merges land on that repo's main:
crmbuilder-v2-runtime --work-task WTK-NNN \
  --repo-root /path/to/repo --base-branch main --tier developer

# Narrow to a Workstream instead of one task:
crmbuilder-v2-runtime --workstream WSK-NNN --max-iterations 5

# Resolve + report without spawning or merging:
crmbuilder-v2-runtime --work-task WTK-NNN --dry-run

# Seed the (area,tier) registry profile, then exit:
crmbuilder-v2-runtime --seed-profile api --tier developer
```

`--base-branch` defaults to `main` (DEC-395: worktrees fork from current main).
It is parameterized so a demo can point at a throwaway integration branch / repo
and never pollute `main`. `--work-task` / `--workstream` narrow the run so a demo
never grabs another session's real Ready work.

## Requirements coverage (REQ-052…058)

- **REQ-052** (scheduler runs the loop) — `CoordinatingRuntime.run()` drives
  find → spawn → verify → merge → advance with no per-step human operation.
- **REQ-053** (spawned on demand, exits when done; nothing lost if stopped) —
  one `claude -p` per task; verify-by-result (DEC-396) means a killed/stopped
  agent whose work is recorded still completes correctly.
- **REQ-054** (resolve contract from registry first) — registry contract via
  `build_agent_prompt` when a profile exists; built-in fallback otherwise.
- **REQ-055** (order + concurrency limit) — order is honored via the dispatcher's
  `blocked_by` eligibility. *The concurrency limit is Layer 2 (serial here).* 
- **REQ-056** (isolation + merge; conflict recorded) — each agent works in its
  own worktree from the base HEAD; clean results merge back; a merge conflict is
  surfaced as `needs_attention` and never force-resolved.
- **REQ-057** (verify before advancing) — `verify_result` gates the merge.
- **REQ-058** (pause at human-judgment points) — `pause_reason_for` stops the
  loop on a `needs_attention` flag and records the pause.

## Findings recorded during the build

- **PI-138** — the live unified DB's `change_log` CHECK constraint omits the
  PI-122 registry entity types, so `POST /agent-profiles` 500s on the audit-trail
  insert (the known `project_v2_changelog_check_migration_gotcha`). The demo used
  the built-in fallback contract so the loop still ran end to end; the registry
  contract-resolution path cannot be exercised on the live DB until that CHECK is
  rebuilt.
- **DEC-396** — the runtime verifies by result (DB state + git), not by agent
  exit. The first demo agent finished its work in ~1 minute but the `claude -p`
  process did not self-terminate and hit the timeout, crashing the run before
  verify/merge. The fix: kill the agent at the deadline and verify anyway; a
  completed, committed result merges regardless of exit.

## Layer 2 (explicitly NOT built here)

Many agents at once, a concurrency cap, parallel worktrees beyond one-at-a-time,
the exclusive migration lock, and the runtime owning the API process. PI-133 and
PI-134 integrate into Layer 2.

## End-to-end demo

The runtime picked up one real Work Task (`WTK-042`), spawned a real Claude Code
agent in a worktree, the agent did the task and completed it, and the runtime
verified and merged the result. Real run output:

```
── iteration 1/1 ──
▶ dispatching WTK-042 (area=api, profile=AGP-runtime) → worktree branch ado/wtk-042
  spawning agent in /tmp/claude-1000/ado-ado-wtk-042-og1v55fl …
  agent exited rc=0
  verify: ok (branch_has_commits=True)
  merge: clean
✔ WTK-042 verified + merged into main

run complete: 1 iteration(s), 1 merged. Last: merged
```

Durable result on the isolated demo repo's `main`:

```
*   a7efc1f ado: merge ado/wtk-042 (coordinating runtime)   <- runtime's --no-ff merge
|\
| * 4d15414 ado: WTK demo proof file                        <- the agent's own commit
|/
* 06d91a2 demo: initial commit

$ cat runtime-demo-proof.txt
Layer 1 coordinating runtime proof — spawned, verified, merged.
```

`WTK-042` ended `Complete` (claimed by `AGP-runtime`); the worktree was removed.

> Note on the first run: the demo agent finished its work in ~1 minute but the
> `claude -p` process did not self-terminate and hit the timeout, which crashed
> the run before verify/merge. That drove **DEC-396** (verify by result, not by
> agent exit). Run 2 above completed clean with the fix in place — and even when
> an agent overruns its deadline, verify-by-result now merges a completed,
> committed result rather than discarding it.
