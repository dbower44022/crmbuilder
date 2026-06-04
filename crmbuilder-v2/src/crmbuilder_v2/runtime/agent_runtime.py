"""ADO agent runtime — resolve a registry contract + a Work Task into the system
prompt for a spawned agent (the missing piece that makes agents actually run).

The registry (PI-122) *holds and resolves* an agent's contract; this runtime
*injects* it: it pulls the resolved contract (system prompt + tool-skills +
ruleset) for an ``agent_profile`` from the API, fetches the assigned Work Task,
and fills the per-invocation placeholders (``{AREA}`` / ``{WORK_TASK}`` /
``{API_BASE}``) — producing the exact prompt an Area-Specialist agent boots from.
The orchestrator then spawns a real agent session with that prompt (in a git
worktree from current ``main`` HEAD, per the proven Area-Specialist's runtime
requirement) and drives the Work Task lifecycle.

This is deliberately small and inspectable: ``build_agent_prompt`` is pure
string assembly over live API reads, so a human (or the orchestrator) can see
exactly what an agent will be told before it runs.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass


def _get(api_base: str, path: str, engagement: str) -> dict:
    url = f"{api_base.rstrip('/')}{path}"
    req = urllib.request.Request(url, headers={"X-Engagement": engagement})
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if payload.get("errors"):
        raise RuntimeError(f"API error for {path}: {payload['errors']}")
    return payload["data"]


@dataclass
class AgentInvocation:
    """A resolved, ready-to-spawn agent assignment."""

    profile_id: str
    work_task_id: str
    area: str
    system_prompt: str  # the full prompt to spawn the agent with
    contract: dict
    work_task: dict


def _fill(text: str, *, area: str, work_task_id: str, api_base: str) -> str:
    return (
        text.replace("{AREA}", area)
        .replace("{WORK_TASK}", work_task_id)
        .replace("{WORKSTREAM_ID}", "")
        .replace("{API_BASE}", api_base)
        .replace("{PI}", "")
    )


def build_agent_prompt(
    api_base: str,
    engagement: str,
    profile_id: str,
    work_task_id: str,
) -> AgentInvocation:
    """Resolve the contract + Work Task into the agent's full system prompt."""
    contract = _get(
        api_base,
        f"/agent-profiles/{profile_id}/contract?engagement={urllib.parse.quote(engagement)}",
        engagement,
    )
    work_task = _get(api_base, f"/work-tasks/{work_task_id}", engagement)
    area = work_task["work_task_area"]

    base_prompt = _fill(
        contract["system_prompt"], area=area, work_task_id=work_task_id, api_base=api_base
    )

    # Advisory rules are already composed into the resolved system_prompt by the
    # resolver; only the enforced gates + learnings need explicit surfacing.
    enforced = "\n".join(
        f"- (ENFORCED) {r['body']}" for r in contract.get("enforced_ruleset", [])
    )
    learnings = "\n".join(
        f"- ({lr['category']}) {lr['content']}" for lr in contract.get("active_learnings", [])
    )

    parts = [base_prompt]
    if enforced:
        parts.append(
            "### Hard gates (ENFORCED — you may not mark the Work Task Complete "
            "until these pass)\n" + enforced
        )
    if learnings:
        parts.append("### What past agents in your area learned\n" + learnings)
    parts.append(
        "### Your assigned Work Task\n"
        f"- identifier: {work_task_id}\n"
        f"- area: {area}\n"
        f"- title: {work_task['work_task_title']}\n"
        f"- description: {work_task['work_task_description']}"
    )
    return AgentInvocation(
        profile_id=profile_id,
        work_task_id=work_task_id,
        area=area,
        system_prompt="\n\n".join(parts),
        contract=contract,
        work_task=work_task,
    )


def main(argv: list[str] | None = None) -> int:
    """``python -m crmbuilder_v2.runtime.agent_runtime <profile> <work_task> [api_base] [engagement]``

    Prints the composed agent prompt — the contract the orchestrator injects when
    it spawns the agent.
    """
    import sys

    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print(
            "usage: agent_runtime <profile_id> <work_task_id> "
            "[api_base=http://127.0.0.1:8765] [engagement=CRMBUILDER]",
            file=sys.stderr,
        )
        return 2
    profile_id, work_task_id = args[0], args[1]
    api_base = args[2] if len(args) > 2 else "http://127.0.0.1:8765"
    engagement = args[3] if len(args) > 3 else "CRMBUILDER"
    inv = build_agent_prompt(api_base, engagement, profile_id, work_task_id)
    print(inv.system_prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
