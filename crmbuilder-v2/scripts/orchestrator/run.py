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
from dataclasses import dataclass, field
from datetime import datetime
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
_WORKTREE_ROOT = _LOCK_DIR / "worktrees"
_TEMPLATE = (
    _REPO_ROOT
    / "PRDs"
    / "product"
    / "crmbuilder-v2"
    / "orchestrator"
    / "child-agent-kickoff-template.md"
)
_APPLY_SCRIPT = _REPO_ROOT / "crmbuilder-v2" / "scripts" / "apply_close_out.py"
_CLOSEOUT_DIR = (
    _REPO_ROOT / "PRDs" / "product" / "crmbuilder-v2" / "close-out-payloads"
)
_PROMPTS_DIR = _REPO_ROOT / "PRDs" / "product" / "crmbuilder-v2" / "prompts"
_LOG_ROOT = _REPO_ROOT / "crmbuilder-v2" / "data" / "logs" / "orchestrator"


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
# Live dispatch (--execute) glue
# --------------------------------------------------------------------------
#
# Everything below is the I/O layer the WS-012 acceptance run exercises:
# API calls, git worktrees, subprocess spawns. The pure decisions
# (branch naming, the child-success predicate) are factored into small
# helpers so they unit-test without touching the network or disk. The
# I/O seams (``_api``, ``_git``, ``_create_worktree``, ``_spawn_child``,
# ``_run_apply``) are module-level functions so a test can monkeypatch
# them and drive ``_execute`` with no real API, repo, or agents.


class DispatchError(RuntimeError):
    """A dispatch step (reserve / claim / worktree / spawn) failed."""


@dataclass
class ChildHandle:
    """Live state for one dispatched child agent."""

    depth: int
    index: int
    cluster: object  # planning.Cluster
    branch: str
    worktree: Path
    kickoff_path: Path
    log_path: Path
    session_id: str
    conversation_id: str
    proc: object = None  # subprocess.Popen (or a test double)
    log_handle: object = None
    exit_code: int | None = None
    verify: dict = field(default_factory=dict)

    @property
    def label(self) -> str:
        return f"wave{self.depth}-child{self.index}"


def child_branch_name(depth: int, index: int) -> str:
    """Deterministic per-child branch name (pure)."""
    return f"orch-wave{depth}-child{index}"


def child_succeeded(exit_code: int | None, session_exists: bool) -> bool:
    """The child-success predicate (pure).

    A child succeeded iff its subprocess exited 0 *and* it applied its
    close-out — proven by its reserved session identifier now resolving
    to a real record (the close-out's session block lands via apply).
    """
    return exit_code == 0 and bool(session_exists)


def _api(
    method: str,
    api_base: str,
    path: str,
    *,
    json_body: dict | None = None,
    params: dict | None = None,
) -> tuple[int, dict]:
    """One HTTP call to the v2 API. Returns ``(status_code, body)``.

    Never raises on a 4xx/5xx — the caller decides what a non-2xx means
    (a 200 GET that 404s is meaningful to verification, a 409 POST is
    benign). Connection failure surfaces as status 0.
    """
    import requests

    url = f"{api_base.rstrip('/')}{path}"
    try:
        resp = requests.request(
            method, url, json=json_body, params=params, timeout=120
        )
    except requests.RequestException as exc:
        return 0, {"error": "connection_failed", "detail": str(exc)}
    try:
        body = resp.json()
    except ValueError:
        body = {}
    return resp.status_code, body


def _api_ok(
    method: str,
    api_base: str,
    path: str,
    *,
    json_body: dict | None = None,
    what: str = "",
) -> dict:
    """``_api`` wrapper that raises ``DispatchError`` on any non-2xx.

    Returns the unwrapped ``.data`` payload. Use for the writes that must
    succeed for a dispatch to be safe (reserve, claim, create, edge).
    """
    status, body = _api(method, api_base, path, json_body=json_body)
    if status not in (200, 201):
        errors = body.get("errors") if isinstance(body, dict) else body
        raise DispatchError(
            f"{what or method + ' ' + path} failed (HTTP {status}): {errors}"
        )
    return body.get("data") if isinstance(body, dict) else body


def _reserve_identifier(api_base: str, entity_type: str, reserved_by: str | None) -> str:
    """Reserve exactly one identifier of ``entity_type`` and return it."""
    data = _api_ok(
        "POST",
        api_base,
        "/identifiers/reserve",
        json_body={
            "entity_type": entity_type,
            "count": 1,
            "reserved_by": reserved_by,
        },
        what=f"reserve {entity_type}",
    )
    reserved = data.get("reserved") or []
    if not reserved:
        raise DispatchError(f"reserve {entity_type} returned no identifiers")
    return reserved[0]


def _claim_item(api_base: str, pi_identifier: str, claimant: str) -> None:
    """Claim a planning item for ``claimant`` (the child conversation id)."""
    _api_ok(
        "POST",
        api_base,
        f"/planning-items/{pi_identifier}/claim",
        json_body={"claimant": claimant},
        what=f"claim {pi_identifier}",
    )


def _post_reference(api_base: str, edge: dict) -> None:
    """POST one references edge; HTTP 409 (already present) is benign."""
    status, body = _api("POST", api_base, "/references", json_body=edge)
    if status not in (200, 201, 409):
        errors = body.get("errors") if isinstance(body, dict) else body
        raise DispatchError(
            f"reference {edge.get('source_id')} {edge.get('relationship')} "
            f"{edge.get('target_id')} failed (HTTP {status}): {errors}"
        )


def _patch_status(api_base: str, collection: str, identifier: str, status: str) -> None:
    """PATCH a governance record's status (e.g. in_flight → complete)."""
    key = "session_status" if collection == "sessions" else "conversation_status"
    _api_ok(
        "PATCH",
        api_base,
        f"/{collection}/{identifier}",
        json_body={key: status},
        what=f"patch {identifier} -> {status}",
    )


def _create_orchestrator_pair(
    api_base: str, *, workstream_identifier: str, run_id: str
) -> tuple[str, str, str]:
    """Create the orchestrator's supervising session + conversation in_flight.

    Returns ``(session_id, conversation_id, executive_summary)``. The
    session carries the mandatory ``session_belongs_to_workstream`` edge;
    the conversation carries ``conversation_belongs_to_session`` (mandatory)
    and ``conversation_belongs_to_workstream`` (per the WS-012 design).
    Identifiers are reserved first so they are known for the inline edges.
    """
    ses_id = _reserve_identifier(api_base, "session", "orchestrator")
    conv_id = _reserve_identifier(api_base, "conversation", "orchestrator")

    exec_summary = (
        f"Parallel-agent orchestrator supervising run {run_id} against the "
        f"open {workstream_identifier} planning-item backlog. This session "
        "dispatches one Claude Code child agent per area-disjoint work "
        "cluster, joins each dependency-depth wave before dispatching the "
        "next, and records the parent-child orchestration edge to every "
        "child conversation on success. It halts the run on any child "
        "failure and leaves claims in place for forensic review."
    )
    _api_ok(
        "POST",
        api_base,
        "/sessions",
        json_body={
            "session_identifier": ses_id,
            "session_title": f"Orchestrator supervising run {run_id}",
            "session_description": (
                "Supervising session for a parallel-agent orchestrator run "
                f"({run_id}). Dispatches child agents across the open "
                f"{workstream_identifier} backlog under static-wave scheduling."
            ),
            "session_medium": "other",
            "session_status": "in_flight",
            "session_executive_summary": exec_summary,
            "references": [
                {
                    "source_type": "session",
                    "source_id": ses_id,
                    "target_type": "workstream",
                    "target_id": workstream_identifier,
                    "relationship": "session_belongs_to_workstream",
                }
            ],
        },
        what="create orchestrator session",
    )
    _api_ok(
        "POST",
        api_base,
        "/conversations",
        json_body={
            "conversation_identifier": conv_id,
            "conversation_title": f"Orchestrator run {run_id} supervision",
            "conversation_purpose": (
                "Supervise a parallel-agent orchestrator run and record the "
                "orchestration edge to each dispatched child conversation."
            ),
            "conversation_description": (
                f"Orchestrator supervision conversation for run {run_id}. "
                "Owns the conversation_orchestrates_conversation edges to "
                "every child agent dispatched in this run."
            ),
            "conversation_status": "in_flight",
            "references": [
                {
                    "source_type": "conversation",
                    "source_id": conv_id,
                    "target_type": "session",
                    "target_id": ses_id,
                    "relationship": "conversation_belongs_to_session",
                },
                {
                    "source_type": "conversation",
                    "source_id": conv_id,
                    "target_type": "workstream",
                    "target_id": workstream_identifier,
                    "relationship": "conversation_belongs_to_workstream",
                },
            ],
        },
        what="create orchestrator conversation",
    )
    return ses_id, conv_id, exec_summary


def _git_fetch() -> None:
    _git("fetch", "origin")


def _create_worktree(branch: str, path: Path, *, base: str = "origin/main") -> None:
    """Create a fresh git worktree on a new ``branch`` cut from ``base``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "worktree", "add", "-b", branch, str(path), base],
        check=True,
        capture_output=True,
        text=True,
    )


def _spawn_child(kickoff_path: Path, cwd: Path, log_path: Path):
    """Spawn one non-interactive Claude Code child agent.

    Runs unattended (``--dangerously-skip-permissions``) in the child's
    own worktree, reading the rendered kickoff and stopping when done.
    stdout+stderr stream to ``log_path``. Returns the Popen handle and
    its open log file handle (closed by the caller after join).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handle = log_path.open("w", encoding="utf-8")
    prompt = (
        f"Read and execute the kickoff at {kickoff_path}, then stop. "
        "Carry out everything it instructs — implement its planning items, "
        "run the tests, commit on your branch, and apply your own close-out "
        "payload. Do not switch branches or touch files outside your claimed "
        "areas."
    )
    proc = subprocess.Popen(
        [
            "claude",
            "-p",
            prompt,
            "--dangerously-skip-permissions",
            "--max-turns",
            "300",
        ],
        cwd=str(cwd),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return proc, handle


def _run_apply(payload_path: Path, *, skip_validation: bool = False) -> int:
    """Run ``apply_close_out.py`` against ``payload_path`` in the main repo."""
    cmd = ["uv", "run", "python", str(_APPLY_SCRIPT), str(payload_path)]
    if skip_validation:
        cmd.append("--skip-validation")
    return subprocess.run(
        cmd, cwd=str(_REPO_ROOT / "crmbuilder-v2")
    ).returncode


def _dispatch_child(
    api_base: str,
    *,
    cluster,
    depth: int,
    index: int,
    orchestrator_conversation: str,
    run_id: str,
    template_body: str,
    engagement_code: str,
    workstream_identifier: str,
    workstream_title: str,
) -> ChildHandle:
    """Reserve → claim → worktree → render → spawn one child (in that order).

    Returns the live ``ChildHandle`` once the subprocess is running. The
    subprocess is non-blocking (``Popen`` returns immediately), so the
    caller dispatches every cluster in a wave before joining any — that
    is what makes the children run concurrently.
    """
    # (a) Reserve the child's identifiers — never compute next-available
    #     for a child (concurrent writers race on it).
    ses_id = _reserve_identifier(api_base, "session", orchestrator_conversation)
    conv_id = _reserve_identifier(
        api_base, "conversation", orchestrator_conversation
    )

    # (b) Claim every planning item in the cluster for the child conversation.
    for pi_identifier in cluster.identifiers:
        _claim_item(api_base, pi_identifier, conv_id)

    # (c) Cut the child's own worktree off origin/main.
    branch = child_branch_name(depth, index)
    worktree = _WORKTREE_ROOT / run_id / branch
    _create_worktree(branch, worktree)

    # (d) Render the kickoff into the child's worktree as its sole input.
    text = render_child_kickoff(
        template_body,
        cluster=cluster,
        session_identifier=ses_id,
        conversation_identifier=conv_id,
        orchestrator_conversation=orchestrator_conversation,
        branch_name=branch,
        engagement_code=engagement_code,
        workstream_identifier=workstream_identifier,
        workstream_title=workstream_title,
        api_base=api_base,
    )
    kickoff_path = worktree / "ORCHESTRATOR-CHILD-KICKOFF.md"
    kickoff_path.write_text(text, encoding="utf-8")

    # (e) Spawn the child agent (non-blocking).
    log_path = _LOG_ROOT / run_id / f"child-{branch}.log"
    proc, log_handle = _spawn_child(kickoff_path, worktree, log_path)

    return ChildHandle(
        depth=depth,
        index=index,
        cluster=cluster,
        branch=branch,
        worktree=worktree,
        kickoff_path=kickoff_path,
        log_path=log_path,
        session_id=ses_id,
        conversation_id=conv_id,
        proc=proc,
        log_handle=log_handle,
    )


def _join_child(handle: ChildHandle) -> None:
    """Block until the child exits; record its exit code and close the log."""
    handle.exit_code = handle.proc.wait()
    if handle.log_handle is not None:
        try:
            handle.log_handle.flush()
            handle.log_handle.close()
        except (OSError, ValueError):
            pass


def _verify_child(api_base: str, handle: ChildHandle) -> dict:
    """Confirm a joined child applied its close-out and moved its items.

    Success = exit 0 AND the child's reserved session now resolves to a
    real record. Planning-item statuses are captured for the watched
    run's log but are not part of the predicate (a child may legitimately
    *address* rather than *resolve* an item, which leaves it Open).
    """
    status, body = _api("GET", api_base, f"/sessions/{handle.session_id}")
    session_exists = status == 200 and isinstance(
        (body or {}).get("data"), dict
    )
    pi_status: dict[str, str | None] = {}
    for pi_identifier in handle.cluster.identifiers:
        st, b = _api("GET", api_base, f"/planning-items/{pi_identifier}")
        if st == 200 and isinstance((b or {}).get("data"), dict):
            pi_status[pi_identifier] = b["data"].get("status")
        else:
            pi_status[pi_identifier] = None
    verify = {
        "ok": child_succeeded(handle.exit_code, session_exists),
        "session_exists": session_exists,
        "exit_code": handle.exit_code,
        "pi_status": pi_status,
    }
    handle.verify = verify
    return verify


def _record_orchestrates_edge(
    api_base: str, orchestrator_conversation: str, handle: ChildHandle
) -> None:
    """Record the orchestrator → child ``conversation_orchestrates_conversation`` edge."""
    _post_reference(
        api_base,
        {
            "source_type": "conversation",
            "source_id": orchestrator_conversation,
            "target_type": "conversation",
            "target_id": handle.conversation_id,
            "relationship": "conversation_orchestrates_conversation",
        },
    )


def _build_orchestrator_closeout(
    *,
    session_id: str,
    conversation_id: str,
    executive_summary: str,
    workstream_identifier: str,
    run_id: str,
    children: list[ChildHandle],
) -> dict:
    """Assemble the orchestrator's own nine-section close-out payload.

    The records already exist in the live DB (created directly during the
    run); this payload is the durable documentation snapshot and the
    vehicle for the deposit_event + close_out_payload governance
    bookkeeping. Empty sections are present as empty arrays.
    """
    child_lines = "; ".join(
        f"{c.conversation_id} (session {c.session_id}, items "
        f"{', '.join(c.cluster.identifiers)})"
        for c in children
    )
    return {
        "label": f"orchestrator-run-{run_id}",
        "session": {
            "session_identifier": session_id,
            "session_title": f"Orchestrator supervising run {run_id}",
            "session_description": (
                f"Supervising session for orchestrator run {run_id}. "
                f"Dispatched {len(children)} child agent(s): {child_lines}."
            ),
            "session_medium": "other",
            "session_status": "complete",
            "session_executive_summary": executive_summary,
        },
        "conversation": {
            "conversation_identifier": conversation_id,
            "conversation_title": f"Orchestrator run {run_id} supervision",
            "conversation_purpose": (
                "Supervise a parallel-agent orchestrator run and record the "
                "orchestration edge to each dispatched child conversation."
            ),
            "conversation_description": (
                f"Supervised {len(children)} concurrent child agent(s) in "
                f"run {run_id}: {child_lines}."
            ),
            "conversation_summary": (
                f"Dispatched and joined {len(children)} child agent(s); all "
                "succeeded and were linked via "
                "conversation_orchestrates_conversation."
            ),
            "conversation_status": "complete",
        },
        "work_tickets": [],
        "planning_items": [],
        "commits": [],
        "decisions": [],
        "references": [
            {
                "source_type": "conversation",
                "source_id": conversation_id,
                "target_type": "conversation",
                "target_id": c.conversation_id,
                "relationship": "conversation_orchestrates_conversation",
            }
            for c in children
        ],
        "resolves_planning_items": [],
        "addresses_planning_items": [],
    }


def _finalize_orchestrator(
    api_base: str,
    *,
    session_id: str,
    conversation_id: str,
    executive_summary: str,
    workstream_identifier: str,
    run_id: str,
    children: list[ChildHandle],
) -> None:
    """Complete the orchestrator's session+conversation and apply its close-out."""
    # in_flight → complete (conversation first: the session's complete-rule
    # needs the inbound conversation_belongs_to_session edge already present,
    # which it is — created at run start).
    _patch_status(api_base, "conversations", conversation_id, "complete")
    _patch_status(api_base, "sessions", session_id, "complete")

    payload = _build_orchestrator_closeout(
        session_id=session_id,
        conversation_id=conversation_id,
        executive_summary=executive_summary,
        workstream_identifier=workstream_identifier,
        run_id=run_id,
        children=children,
    )
    num = session_id.split("-")[-1]
    payload_path = _CLOSEOUT_DIR / f"ses_{num}.json"
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    payload_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\n[execute] wrote orchestrator close-out payload {payload_path}")

    # The records were authored directly during the run, so this apply is a
    # documentation snapshot (session/conversation/edges 409 as already
    # present); --skip-validation bypasses the create-shape validator, which
    # targets first-creation payloads, while still landing the
    # deposit_event + close_out_payload bookkeeping.
    rc = _run_apply(payload_path, skip_validation=True)
    if rc != 0:
        print(
            f"[execute] WARNING: orchestrator close-out apply returned {rc}; "
            "the supervising records and edges are already in the DB.",
            file=sys.stderr,
        )


def _halt(
    api_base: str,
    *,
    session_id: str,
    conversation_id: str,
    failures: list[ChildHandle],
) -> int:
    """Halt the run on child failure: surface, mark non-complete-terminal, exit non-zero."""
    print("\n" + "=" * 60, file=sys.stderr)
    print("ORCHESTRATOR HALTED — child agent failure(s)", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    for h in failures:
        unresolved = [
            pi
            for pi, st in (h.verify.get("pi_status") or {}).items()
            if st != "Resolved"
        ]
        print(
            f"  ✗ {h.label}: exit={h.exit_code} "
            f"session_applied={h.verify.get('session_exists')}\n"
            f"      conversation={h.conversation_id} session={h.session_id}\n"
            f"      log: {h.log_path}\n"
            f"      claimed items left in place: {h.cluster.identifiers}\n"
            f"      unresolved items: {unresolved}",
            file=sys.stderr,
        )
    print(
        "\nNo further waves dispatched. Child claims are LEFT IN PLACE for "
        "forensic review (design §4 — no retry, no requeue).",
        file=sys.stderr,
    )
    # Transition the orchestrator to a non-complete terminal state.
    try:
        _patch_status(api_base, "conversations", conversation_id, "cancelled")
        _patch_status(api_base, "sessions", session_id, "cancelled")
    except DispatchError as exc:  # pragma: no cover - best-effort on halt
        print(f"  (could not cancel orchestrator records: {exc})", file=sys.stderr)
    return 1


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
    """Live dispatch — the human-driven WS-012 acceptance path.

    Creates the orchestrator's supervising session+conversation, plans the
    waves, then for each wave dispatches one child per area-disjoint
    cluster (reserve → claim → worktree → render → spawn), joins the whole
    wave, verifies each child, halts on any failure, and on success records
    the orchestrates edge to each child. After all waves succeed it
    completes and applies the orchestrator's own close-out. Runs inside
    ``orchestrator_lock`` (see ``main``).
    """
    preflight(args.api_base, require_clean_git=True)
    run_id = datetime.now().strftime("%Y%m%dT%H%M%S")
    print(f"[execute] orchestrator run {run_id} against {args.api_base}")

    # (per run, once) the supervising conversation + session, created
    # in_flight. Children reference the conversation id as their dispatcher.
    orch_ses, orch_conv, orch_exec = _create_orchestrator_pair(
        args.api_base, workstream_identifier=args.workstream, run_id=run_id
    )
    print(
        f"[execute] orchestrator session={orch_ses} conversation={orch_conv} "
        "(in_flight)"
    )

    ready = fetch_ready_batches(
        args.api_base, max_depth=args.max_depth, areas=args.area
    )
    waves = plan_waves(ready)
    print(summarize_plan(ready, waves))

    # Make sure origin/main is current so every worktree is cut from the
    # same fresh base.
    _git_fetch()

    template_body = _load_template()
    workstream_title = "Parallel agent orchestrator"
    dispatched: list[ChildHandle] = []

    for wave in waves:
        if not wave.clusters:
            print(f"\n[execute] wave depth {wave.depth}: no clusters — skipping")
            continue
        print(
            f"\n[execute] wave depth {wave.depth}: dispatching "
            f"{len(wave.clusters)} child agent(s) concurrently"
        )
        # Dispatch every cluster (non-blocking Popen) before joining any —
        # this is what runs the children in parallel.
        wave_children: list[ChildHandle] = []
        try:
            for i, cluster in enumerate(wave.clusters, 1):
                handle = _dispatch_child(
                    args.api_base,
                    cluster=cluster,
                    depth=wave.depth,
                    index=i,
                    orchestrator_conversation=orch_conv,
                    run_id=run_id,
                    template_body=template_body,
                    engagement_code=args.engagement_code,
                    workstream_identifier=args.workstream,
                    workstream_title=workstream_title,
                )
                wave_children.append(handle)
                dispatched.append(handle)
                print(
                    f"  → {handle.label}: items={cluster.identifiers} "
                    f"areas={sorted(cluster.areas)} session={handle.session_id} "
                    f"conversation={handle.conversation_id} branch={handle.branch}"
                )
        except DispatchError as exc:
            # A dispatch-time failure (reserve/claim/worktree) before all
            # children are running — join whatever started, then halt.
            print(f"\n[execute] dispatch error: {exc}", file=sys.stderr)
            for h in wave_children:
                if h.exit_code is None and h.proc is not None:
                    _join_child(h)
            return _halt(
                args.api_base,
                session_id=orch_ses,
                conversation_id=orch_conv,
                failures=wave_children,
            )

        # (join) wait for the whole wave before going further.
        print(f"[execute] waiting for {len(wave_children)} child agent(s)…")
        for handle in wave_children:
            _join_child(handle)
            print(f"  · {handle.label} exited {handle.exit_code}")

        # (verify) confirm each child applied its close-out.
        failures: list[ChildHandle] = []
        for handle in wave_children:
            verify = _verify_child(args.api_base, handle)
            mark = "✓" if verify["ok"] else "✗"
            print(
                f"  {mark} {handle.label}: exit={verify['exit_code']} "
                f"close_out_applied={verify['session_exists']} "
                f"items={verify['pi_status']}"
            )
            if not verify["ok"]:
                failures.append(handle)

        if failures:
            return _halt(
                args.api_base,
                session_id=orch_ses,
                conversation_id=orch_conv,
                failures=failures,
            )

        # (on wave success) record the orchestrates edge to each child.
        for handle in wave_children:
            _record_orchestrates_edge(args.api_base, orch_conv, handle)
            print(
                f"  + edge: {orch_conv} orchestrates {handle.conversation_id}"
            )

    # All waves succeeded — complete + apply the supervising close-out.
    _finalize_orchestrator(
        args.api_base,
        session_id=orch_ses,
        conversation_id=orch_conv,
        executive_summary=orch_exec,
        workstream_identifier=args.workstream,
        run_id=run_id,
        children=dispatched,
    )
    print(
        f"\n[execute] run {run_id} complete: {len(dispatched)} child agent(s), "
        f"orchestrator session={orch_ses} conversation={orch_conv}."
    )
    return 0


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
