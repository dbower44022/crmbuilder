"""ADO dispatcher — auto-pull the next eligible Work Task and prepare its agent.

The "wrapper" above :mod:`agent_prompt`: instead of an operator hand-picking a
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
import logging
import urllib.parse
import urllib.request
from dataclasses import dataclass

from crmbuilder_v2.scheduler.agent_prompt import AgentInvocation, build_agent_prompt

log = logging.getLogger(__name__)

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
    profiles: list[dict],
    area: str,
    tier: str = _DEFAULT_TIER,
    technology: str | None = None,
) -> str | None:
    """Pick the system agent profile for ``(area, technology, tier)``.

    Matches the task's **area** strictly: a task is never run under a profile
    from a different area (REQ-273) — a mis-scoped run like a ui task under the
    storage profile is the WTK-176 wrong-area-contract failure. When no
    matching-area system profile of the tier exists, returns ``None`` (the caller
    then refuses / falls back to the area-parameterized minimal contract, never a
    sibling area's profile).

    Within the area, technology selects the variant (REQ-281): when the task
    names a ``technology`` (e.g. ``qt-desktop`` vs ``web`` for the ui area), an
    exact-technology profile wins; otherwise a technology-agnostic profile
    (``technology`` null/empty) serves, and a task naming a technology is never
    forced through another technology's profile. Returns ``None`` if only a
    different technology's profile exists for the area.
    """
    in_area = [
        p
        for p in profiles
        if p.get("scope") == "system"
        and p.get("tier") == tier
        and p.get("area") == area
    ]
    if not in_area:
        return None  # REQ-273: refuse rather than fall back to another area
    agnostic = [p for p in in_area if not p.get("technology")]
    if technology is not None:
        exact = [p for p in in_area if p.get("technology") == technology]
        chosen = exact or agnostic  # an agnostic profile may serve; a wrong-tech one never
    else:
        chosen = agnostic or in_area
    return chosen[0]["identifier"] if chosen else None


def select_stamped_profile_id(
    profiles: list[dict], stamp: str, area: str, tier: str
) -> str | None:
    """Re-validate a Work Task's ``work_task_resolved_agent_profile`` stamp (PI-302).

    The architect's chosen specialist is authoritative *only while it still holds*:
    the stamped profile must exist among ``profiles``, be ``active``, share the
    task's ``area`` (the hard backstop, REQ-273), and match the ``tier`` the
    dispatcher resolved. Returns the stamp when all four hold, else ``None`` so the
    caller falls back to generalist ``(area, tier)`` selection. Pure — no I/O.
    """
    for profile in profiles:
        if profile.get("identifier") != stamp:
            continue
        if profile.get("status") != "active":
            return None
        if profile.get("area") != area:
            return None
        if profile.get("tier") != tier:
            return None
        return stamp
    return None  # stamp names no known profile


def resolve_profile_for_task(
    profiles: list[dict],
    *,
    area: str,
    tier: str = _DEFAULT_TIER,
    technology: str | None = None,
    stamp: str | None = None,
) -> tuple[str | None, str | None]:
    """Decide the agent profile for a task, honouring an authoritative stamp first.

    A non-empty ``stamp`` (the Work Task's ``work_task_resolved_agent_profile``) is
    re-validated via :func:`select_stamped_profile_id`; when it holds, that profile
    wins outright. When the stamp is absent the task routes through the existing
    generalist :func:`select_profile_id`; when the stamp is *present but fails
    re-validation* (inactive / wrong area / wrong tier / unknown) the task still
    falls back to generalist selection, and a non-``None`` warning message is
    returned so the caller can surface it (a warning, never an error). Pure — no I/O.

    :returns: ``(profile_id, warning)`` — ``profile_id`` may be ``None`` when no
        generalist profile exists either; ``warning`` is ``None`` unless a present
        stamp failed re-validation.
    """
    if stamp:
        stamped = select_stamped_profile_id(profiles, stamp, area, tier)
        if stamped is not None:
            return stamped, None
        fallback = select_profile_id(profiles, area, tier, technology=technology)
        warning = (
            f"resolved_agent_profile {stamp!r} failed re-validation for area "
            f"{area!r} / tier {tier!r}; falling back to generalist (area, tier) "
            f"selection ({fallback!r})"
        )
        return fallback, warning
    return select_profile_id(profiles, area, tier, technology=technology), None


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
    profile_id, warning = resolve_profile_for_task(
        profiles,
        area=area,
        tier=tier,
        technology=wt.get("work_task_technology"),
        stamp=wt.get("work_task_resolved_agent_profile"),
    )
    if warning:
        log.warning("work_task %s: %s", wt["work_task_identifier"], warning)
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
    """``python -m crmbuilder_v2.scheduler.dispatcher [api_base] [engagement]``

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
