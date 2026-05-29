"""Parallel-agent orchestrator driver (PI-081, WS-012).

Runs at the developer's terminal. Reads the open planning-item backlog via
the ready-batches API (PI-079), plans the wave structure into area-disjoint
child clusters (``planning.py``), and — in execute mode — reserves
identifiers (PI-078), claims items (PI-077), renders a kickoff per child
(PI-082 template via ``kickoff.py``), spawns one Claude Code subagent per
cluster on its own branch, waits for the wave, then records the
``conversation_orchestrates_conversation`` edge to each child and writes
its own close-out.

Two modes:

* ``--dry-run`` (DEFAULT, safe): pre-flight, fetch, plan, and render every
  child kickoff into ``--out-dir`` WITHOUT reserving, claiming, branching,
  or spawning anything. Use this to inspect exactly what a real run would
  dispatch.
* ``--execute``: actually dispatches. Per the design doc (§7) the first
  live run IS the acceptance test for the whole WS-012 foundation, so it is
  intended to be driven by a human who watches it. Spawning is guarded by a
  process-wide file lock so two orchestrators never run at once.

The pure, unit-tested cores live in ``planning.py`` and ``kickoff.py``;
this module is the I/O glue (git, subprocess, API, file lock).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[3]  # crmbuilder/
sys.path.insert(0, str(_HERE.parent))
from kickoff import (  # noqa: E402
    render_kickoff,
    render_planning_items_block,
    strip_contract_comment,
)
from planning import WavePlan, assert_clusters_disjoint, partition_wave  # noqa: E402

_LOCK_DIR = Path.home() / ".crmbuilder-v2"
_LOCK_FILE = _LOCK_DIR / "orchestrator.lock"
_TEMPLATE = (
    _REPO_ROOT
    / "PRDs"
    / "product"
    / "crmbuilder-v2"
    / "orchestrator"
    / "child-agent-kickoff-template.md"
)


class PreflightError(RuntimeError):
    """A pre-flight check failed; the run must not proceed."""


# --------------------------------------------------------------------------
# File lock — "no other orchestrator currently running"
# --------------------------------------------------------------------------


def _pid_alive(pid: int) -> bool:
    """True if a process with ``pid`` exists (signal 0 probe)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but not signalable by us
    except OSError:
        return False
    return True


@contextmanager
def orchestrator_lock():
    """Acquire the singleton orchestrator lock or raise ``PreflightError``."""
    _LOCK_DIR.mkdir(parents=True, exist_ok=True)
    if _LOCK_FILE.exists():
        try:
            stale_pid = int(_LOCK_FILE.read_text().strip() or "0")
        except ValueError:
            stale_pid = 0
        if stale_pid and _pid_alive(stale_pid):
            raise PreflightError(
                f"another orchestrator is running (pid {stale_pid}, lock "
                f"{_LOCK_FILE}). Wait for it or remove the lock if it crashed."
            )
        # stale lock — reclaim it
    _LOCK_FILE.write_text(str(os.getpid()))
    try:
        yield
    finally:
        try:
            if _LOCK_FILE.exists() and _LOCK_FILE.read_text().strip() == str(os.getpid()):
                _LOCK_FILE.unlink()
        except OSError:
            pass


# --------------------------------------------------------------------------
# Pre-flight
# --------------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=_REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout


def preflight(api_base: str, *, require_clean_git: bool = True) -> None:
    """Verify the repo + API are in a fit state to dispatch a run."""
    import requests

    if require_clean_git:
        dirty = _git("status", "--porcelain").strip()
        if dirty:
            raise PreflightError(
                "git working tree is not clean; commit or stash before a run:\n"
                + dirty
            )
    try:
        h = requests.get(f"{api_base.rstrip('/')}/health", timeout=10)
        h.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - surface any health failure
        raise PreflightError(f"API health check failed at {api_base}: {exc}") from exc

    engagement = _REPO_ROOT / "crmbuilder-v2" / "data" / "current_engagement.json"
    if not engagement.exists():
        raise PreflightError(
            "no current engagement set (crmbuilder-v2/data/current_engagement.json "
            "missing)."
        )


# --------------------------------------------------------------------------
# Fetch + plan
# --------------------------------------------------------------------------


def fetch_ready_batches(api_base: str, *, max_depth: int | None, areas: list[str] | None) -> dict:
    import requests

    params: dict[str, object] = {}
    if max_depth is not None:
        params["max_depth"] = max_depth
    if areas:
        params["area"] = areas
    r = requests.get(
        f"{api_base.rstrip('/')}/orchestration/ready-batches", params=params, timeout=30
    )
    r.raise_for_status()
    return r.json()["data"]


def plan_waves(ready_batches: dict) -> list[WavePlan]:
    waves: list[WavePlan] = []
    for batch in ready_batches.get("batches", []):
        plan = partition_wave(batch["items"], depth=batch["depth"])
        assert_clusters_disjoint(plan.clusters)
        waves.append(plan)
    return waves


def summarize_plan(ready_batches: dict, waves: list[WavePlan]) -> str:
    lines = ["Orchestrator dispatch plan", "=" * 26]
    if ready_batches.get("warnings"):
        lines.append("WARNINGS:")
        lines += [f"  - {w}" for w in ready_batches["warnings"]]
    for wave in waves:
        lines.append(f"\nWave (depth {wave.depth}): {len(wave.clusters)} parallel child agent(s)")
        for i, c in enumerate(wave.clusters, 1):
            lines.append(
                f"  child {i}: items={c.identifiers} areas={sorted(c.areas)}"
            )
        if wave.skipped_claimed:
            ids = [it["identifier"] for it in wave.skipped_claimed]
            lines.append(f"  (skipped, already claimed: {ids})")
        if wave.unclustered:
            ids = [it["identifier"] for it in wave.unclustered]
            lines.append(f"  (UNCLUSTERED — no area, cannot parallelise: {ids})")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Dry-run rendering
# --------------------------------------------------------------------------


def _load_template() -> str:
    return strip_contract_comment(_TEMPLATE.read_text(encoding="utf-8"))


def render_child_kickoff(
    template_body: str,
    *,
    cluster,
    session_identifier: str,
    conversation_identifier: str,
    orchestrator_conversation: str,
    branch_name: str,
    engagement_code: str,
    workstream_identifier: str,
    workstream_title: str,
    api_base: str,
) -> str:
    """Render one child's kickoff from the template + cluster assignment."""
    areas_sorted = sorted(cluster.areas)
    subs = {
        "operating_mode": "DETAIL",
        "engagement_code": engagement_code,
        "workstream_identifier": workstream_identifier,
        "workstream_title": workstream_title,
        "orchestrator_conversation_identifier": orchestrator_conversation,
        "session_identifier": session_identifier,
        "conversation_identifier": conversation_identifier,
        "reserved_identifiers": "(none beyond your SES/CONV)",
        "branch_name": branch_name,
        "base_branch": "origin/main",
        "commit_prefix": "v2:",
        "areas_claimed": ", ".join(areas_sorted),
        "areas_claimed_list": "\n".join(f"- `{a}`" for a in areas_sorted),
        "planning_items": render_planning_items_block(cluster.items),
        "planning_item_identifiers": ", ".join(cluster.identifiers),
        "close_out_payloads_dir": "PRDs/product/crmbuilder-v2/close-out-payloads",
        "close_out_payload_path": (
            f"PRDs/product/crmbuilder-v2/close-out-payloads/"
            f"ses_{session_identifier.split('-')[-1]}.json"
        ),
        "apply_prompt_path": (
            f"PRDs/product/crmbuilder-v2/prompts/"
            f"CLAUDE-CODE-PROMPT-apply-close-out-ses-{session_identifier.split('-')[-1]}.md"
        ),
        "api_base_url": api_base,
    }
    return render_kickoff(template_body, subs)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def _dry_run(args: argparse.Namespace) -> int:
    preflight(args.api_base, require_clean_git=False)
    ready = fetch_ready_batches(
        args.api_base, max_depth=args.max_depth, areas=args.area
    )
    waves = plan_waves(ready)
    print(summarize_plan(ready, waves))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    template_body = _load_template()
    rendered = 0
    for wave in waves:
        for i, cluster in enumerate(wave.clusters, 1):
            # Dry-run placeholders for not-yet-reserved identifiers.
            text = render_child_kickoff(
                template_body,
                cluster=cluster,
                session_identifier="SES-XXX",
                conversation_identifier="CNV-XXX",
                orchestrator_conversation="CNV-ORCH",
                branch_name=f"orch-wave{wave.depth}-child{i}",
                engagement_code=args.engagement_code,
                workstream_identifier=args.workstream,
                workstream_title="Parallel agent orchestrator",
                api_base=args.api_base,
            )
            path = out_dir / f"kickoff-wave{wave.depth}-child{i}.md"
            path.write_text(text, encoding="utf-8")
            rendered += 1
    print(f"\n[dry-run] rendered {rendered} child kickoff(s) into {out_dir}")
    print("[dry-run] no identifiers reserved, no items claimed, no agents spawned.")
    return 0


def _execute(args: argparse.Namespace) -> int:
    # Live dispatch is the WS-012 acceptance test and is intended to be
    # human-driven. It reserves identifiers (PI-078), claims items
    # (PI-077), spawns Claude Code subagents, polls the wave, then records
    # the orchestrates edges and the orchestrator's own close-out. The
    # Claude Code invocation is environment-specific; wire it to the local
    # setup before the first real run.
    raise NotImplementedError(
        "live --execute dispatch is the human-driven WS-012 acceptance test; "
        "run --dry-run first to inspect the plan, then wire the child-spawn "
        "invocation (subprocess to the local `claude` CLI) for your setup. "
        "See this module's docstring and the PI-081 description."
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Parallel-agent orchestrator (PI-081)")
    p.add_argument("--api-base", default="http://127.0.0.1:8765")
    p.add_argument("--engagement-code", default="CRMBUILDER")
    p.add_argument("--workstream", default="WS-012")
    p.add_argument("--max-depth", type=int, default=None)
    p.add_argument("--area", action="append", default=None, help="filter to area(s)")
    p.add_argument(
        "--out-dir",
        default="/tmp/crmbuilder-orchestrator",
        help="where dry-run writes rendered child kickoffs",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        help="actually dispatch (default is a safe dry-run)",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.execute:
        return _dry_run(args)
    with orchestrator_lock():
        return _execute(args)


if __name__ == "__main__":
    raise SystemExit(main())
