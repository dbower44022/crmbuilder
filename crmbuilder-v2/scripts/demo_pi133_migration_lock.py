"""PI-133 working demo — the runtime holds an exclusive migration window.

Runs the Layer 2 pool with **fake agents** (no server, no worktree, no real
Claude) so the *mechanism* is shown deterministically: three Work Tasks, a
concurrency cap of 2, and a migration requested while agents are in flight. The
demo prints a timeline proving the three phases (DEC-399):

1. dispatch is PAUSED the moment the migration is requested (no new agent),
2. the in-flight agents DRAIN to zero and the migration runs ALONE — the live
   agent count at that instant is 0 (no concurrent writer),
3. dispatch RESUMES and the held Work Task runs.

Run:  uv run python scripts/demo_pi133_migration_lock.py
"""

from __future__ import annotations

import subprocess
import threading
import time

from crmbuilder_v2.runtime import parallel_runtime as pr
from crmbuilder_v2.runtime.coordinating_runtime import (
    MergeResult,
    MergeStatus,
    _ResolvedAssignment,
)
from crmbuilder_v2.runtime.parallel_runtime import (
    ParallelCoordinatingRuntime,
    ParallelRuntimeConfig,
)

_T0 = time.time()


def _stamp(msg: str) -> None:
    print(f"  [{time.time() - _T0:6.3f}s] {msg}")


class _FakeWorktree:
    _n = 0

    def __init__(self, *, repo_root, branch, base_ref):
        type(self)._n += 1
        self.path = f"/tmp/demo-wt-{branch.replace('/', '-')}-{self._n}"

    def create(self):
        return self.path

    def has_commits_beyond(self, base_ref):
        return True

    def remove(self):
        return None


def main() -> int:
    live = {"n": 0, "max": 0}
    live_lock = threading.Lock()
    requested = {"done": False}
    rt_holder: dict = {}

    def fake_spawn(prompt, worktree_path):
        tid = prompt
        with live_lock:
            live["n"] += 1
            live["max"] = max(live["max"], live["n"])
            _stamp(f"agent for {tid} STARTED  (live agents now: {live['n']})")
        if not requested["done"]:
            requested["done"] = True
            _stamp(">>> migration requested (schema change: add findings table) "
                   "while agents are in flight")
            rt_holder["rt"].request_migration(_migration_fn, label="add-findings-table")
        time.sleep(0.15)
        with live_lock:
            live["n"] -= 1
            _stamp(f"agent for {tid} FINISHED (live agents now: {live['n']})")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    def _migration_fn():
        with live_lock:
            n = live["n"]
        _stamp(f"*** MIGRATION RUNNING — live agents at this instant: {n} "
               f"{'(EXCLUSIVE — no concurrent writer)' if n == 0 else '(!! UNSAFE)'}")
        time.sleep(0.05)
        _stamp("*** MIGRATION COMPLETE")

    cfg = ParallelRuntimeConfig(
        max_concurrent=2,
        target_work_tasks=["WTK-1", "WTK-2", "WTK-3"],
        poll_interval=0.02,
    )
    rt = ParallelCoordinatingRuntime(config=cfg, spawn_fn=fake_spawn, log=lambda m: None)
    rt_holder["rt"] = rt

    seen: set[str] = set()
    rt._eligible_candidates = lambda: [t for t in cfg.target_work_tasks if t not in seen]
    rt._blockers_of = lambda tid: set()

    def fake_assignment_for(tid):
        seen.add(tid)
        return _ResolvedAssignment(
            work_task={"work_task_identifier": tid, "work_task_status": "Ready"},
            work_task_id=tid,
            area="api",
            profile_id="AGP-runtime",
            branch=f"ado/{tid.lower()}",
            prompt=tid,
        )

    rt._l1._assignment_for = fake_assignment_for
    pr.Worktree = _FakeWorktree
    pr.dispatcher._get = lambda api, path, eng: {"work_task_status": "Complete"}
    rt._l1._merge = lambda branch: MergeResult(MergeStatus.CLEAN, "merged")
    rt._l1._flag_needs_attention = lambda wt, reason: None
    rt._record_finding = lambda wt, summary: None

    print("PI-133 demo — exclusive migration lock over the Layer 2 pool")
    print("  3 Work Tasks, cap 2, migration requested mid-flight\n")
    report = rt.run()

    print("\nResult")
    print(f"  tasks merged           : {len(report.merged)} / 3")
    print(f"  peak concurrent agents : {live['max']} (cap 2)")
    m = report.migrations[0]
    print(f"  migration '{m.label}': ran with {m.active_at_run} live agent(s) "
          f"→ {'EXCLUSIVE ✔' if m.active_at_run == 0 else 'UNSAFE'}")
    ok = len(report.merged) == 3 and m.active_at_run == 0 and live["max"] <= 2
    print(f"\n  DEMO {'PASSED ✔' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
