"""ADO dispatcher — auto-pull the next eligible Work Task and prepare its agent.

The "wrapper" above :mod:`agent_runtime`: instead of an operator hand-picking a
Work Task, the dispatcher pulls the **next eligible** one from the API, selects
the agent profile for its area/tier, and resolves the ready-to-spawn assignment
(contract + prompt + a worktree branch name). The orchestrator then spawns the
agent, verifies, integrates, and marks the task Complete — and calls the
dispatcher again. That repetition is the continuous loop.

Eligibility (Area-Specialist pull): a Work Task is dispatchable when it is
``Ready``, unclaimed, and every Work Task it is ``blocked_by`` is ``Complete``.
Profile selection: the system profile for the task's exact ``(area, tier)`` if
one exists, else any system profile of that tier (the proven Area-Specialist
prompt is area-parameterized via ``{AREA}``, so one developer profile serves any
area). The pure decision helpers are separated from the HTTP I/O so they are
unit-testable without a server.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

from crmbuilder_v2.runtime.agent_runtime import AgentInvocation, build_agent_prompt

_CLAIMABLE_STATUS = "Ready"
_COMPLETE_STATUS = "Complete"
_DEFAULT_TIER = "developer"


# --------------------------------------------------------------------------
# Pure decision helpers (no I/O — unit-tested directly)
# --------------------------------------------------------------------------
def is_work_task_eligible(work_task: dict, blocker_statuses: list[str]) -> bool:
    """True if a Work Task can be dispatched to an agent now.

    Eligible = ``Ready`` + unclaimed + every ``blocked_by`` predecessor Complete.
    """
    if work_task.get("work_task_status") != _CLAIMABLE_STATUS:
        return False
    if work_task.get("work_task_claimed_by"):
        return False
    return all(s == _COMPLETE_STATUS for s in blocker_statuses)


def select_profile_id(
    profiles: list[dict], area: str, tier: str = _DEFAULT_TIER
) -> str | None:
    """Pick the system agent profile for ``(area, tier)``.

    Prefers an exact ``(area, tier)`` system profile; falls back to any
    system profile of that ``tier`` (the area-parameterized proven prompt).
    Returns ``None`` when no system profile of the tier exists.
    """
    system = [p for p in profiles if p.get("scope") == "system" and p.get("tier") == tier]
    exact = [p for p in system if p.get("area") == area]
    chosen = exact or system
    return chosen[0]["identifier"] if chosen else None


# --------------------------------------------------------------------------
# HTTP I/O
# --------------------------------------------------------------------------
def _get(api_base: str, path: str, engagement: str) -> object:
    url = f"{api_base.rstrip('/')}{path}"
    req = urllib.request.Request(url, headers={"X-Engagement": engagement})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"API error for {path}: {payload['errors']}")
    return payload["data"]


def _post(api_base: str, path: str, engagement: str, body: dict) -> object:
    url = f"{api_base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"X-Engagement": engagement, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"API error for POST {path}: {payload['errors']}")
    return payload["data"]


def _patch(api_base: str, path: str, engagement: str, body: dict) -> object:
    url = f"{api_base.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="PATCH",
        headers={"X-Engagement": engagement, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"API error for PATCH {path}: {payload['errors']}")
    return payload["data"]


def _blocker_statuses(api_base: str, engagement: str, work_task_id: str) -> list[str]:
    edges = _get(
        api_base,
        f"/references?source_id={urllib.parse.quote(work_task_id)}&relationship=blocked_by",
        engagement,
    )
    statuses: list[str] = []
    for e in edges:
        if e.get("target_type") != "work_task":
            continue
        target = _get(api_base, f"/work-tasks/{e['target_id']}", engagement)
        statuses.append(target.get("work_task_status"))
    return statuses


def eligible_work_tasks(api_base: str, engagement: str) -> list[dict]:
    """Return the dispatchable Work Tasks, in identifier order."""
    ready = _get(api_base, "/work-tasks?status=Ready", engagement)
    out = []
    for wt in ready:
        blockers = _blocker_statuses(api_base, engagement, wt["work_task_identifier"])
        if is_work_task_eligible(wt, blockers):
            out.append(wt)
    return sorted(out, key=lambda w: w["work_task_identifier"])


@dataclass
class Assignment:
    """A dispatched assignment, ready for the orchestrator to spawn."""

    work_task_id: str
    area: str
    profile_id: str
    invocation: AgentInvocation
    worktree_branch: str


def next_assignment(
    api_base: str, engagement: str, *, tier: str = _DEFAULT_TIER
) -> Assignment | None:
    """Pull the next eligible Work Task and resolve its agent assignment.

    Returns ``None`` when there is no eligible work (the loop is drained) or no
    system profile of ``tier`` exists.
    """
    eligible = eligible_work_tasks(api_base, engagement)
    if not eligible:
        return None
    wt = eligible[0]
    area = wt["work_task_area"]
    profiles = _get(api_base, "/agent-profiles", engagement)
    profile_id = select_profile_id(profiles, area, tier)
    if profile_id is None:
        return None
    invocation = build_agent_prompt(
        api_base, engagement, profile_id, wt["work_task_identifier"]
    )
    branch = f"ado/{wt['work_task_identifier'].lower()}"
    return Assignment(
        work_task_id=wt["work_task_identifier"],
        area=area,
        profile_id=profile_id,
        invocation=invocation,
        worktree_branch=branch,
    )


def claim_and_start(api_base: str, engagement: str, assignment: Assignment) -> dict:
    """Transition the assignment's Work Task Ready → Claimed → In Progress.

    The governance side of dispatch (the agent's claim/lifecycle). Returns the
    Work Task record after the transitions.
    """
    wt = assignment.work_task_id
    _patch(api_base, f"/work-tasks/{wt}", engagement, {"work_task_status": "Claimed"})
    _post(api_base, f"/work-tasks/{wt}/claim", engagement, {"claimed_by": assignment.profile_id})
    return _patch(
        api_base, f"/work-tasks/{wt}", engagement, {"work_task_status": "In Progress"}
    )


def complete(api_base: str, engagement: str, work_task_id: str) -> dict:
    """Mark a Work Task Complete (called after verify + integrate)."""
    return _patch(
        api_base, f"/work-tasks/{work_task_id}", engagement,
        {"work_task_status": "Complete"},
    )


def main(argv: list[str] | None = None) -> int:
    """``python -m crmbuilder_v2.runtime.dispatcher [api_base] [engagement]``

    Prints the next eligible assignment as JSON (metadata + the agent prompt), or
    a "no eligible work" notice. The orchestrator consumes this to spawn the agent.
    """
    import sys

    args = argv if argv is not None else sys.argv[1:]
    api_base = args[0] if args else "http://127.0.0.1:8765"
    engagement = args[1] if len(args) > 1 else "CRMBUILDER"
    assignment = next_assignment(api_base, engagement)
    if assignment is None:
        print(json.dumps({"status": "no_eligible_work"}))
        return 0
    print(json.dumps({
        "status": "dispatched",
        "work_task_id": assignment.work_task_id,
        "area": assignment.area,
        "profile_id": assignment.profile_id,
        "worktree_branch": assignment.worktree_branch,
        "system_prompt": assignment.invocation.system_prompt,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
