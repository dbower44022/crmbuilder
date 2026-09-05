"""The access effect of a whole-design publish — PI-466 (REQ-521, DEC-982).

The whole-design publish (``/instances/{id}/publish`` and its preview) renders
the security program and deploys it (LSN-071), so it changes who can reach
what exactly as a role publish from the reconcile grid does — and until PI-466
it did so with no statement of effect and no removal fence. This module gives
that route the same statement in the same words: for every role and team the
scoped programs declare, what the *live* target currently grants, what the
design would set, and which of those settings would take access away.

Two things are deliberately not done here. The judgement of what counts as a
removal is not restated — each role goes through
:func:`crmbuilder_v2.access.reconcile_access.assess_member_access`, the core
of the reconcile route's gate — and nothing is applied: this module only
reads the target and reports. When the target's roles cannot be read the
effect is reported as *unknown*, never guessed, because a guess in either
direction is exactly what lets a real removal past the fence.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.access import reconcile_access
from espo_impl.core.models import ProgramFile

#: The words the section uses for how the target holds a member right now.
LIVE_PRESENT = "present"
LIVE_ABSENT = "absent"
LIVE_UNKNOWN = "unknown"


def _rows_of(body: Any) -> list[dict]:
    """The records of an EspoCRM list response, or nothing."""
    if isinstance(body, dict):
        rows = body.get("list")
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    return []


def _read_by_name(
    reader, what: str
) -> tuple[dict[str, dict] | None, str | None]:
    """Index a live list by ``name``; ``(None, reason)`` when it cannot be read.

    Read-only. A non-200 or an unreadable body is reported as a reason and the
    caller says *unknown*; it is never treated as "the target holds none".
    """
    status, body = reader()
    if status != 200 or not isinstance(body, dict):
        return None, f"could not read the target's {what} (HTTP {status})"
    by_name: dict[str, dict] = {}
    for row in _rows_of(body):
        name = row.get("name")
        if isinstance(name, str) and name:
            by_name[name] = row
    return by_name, None


def gather_live_roles(client) -> tuple[dict[str, dict] | None, str | None]:
    """The target's roles by name — the same ``GET /Role`` the audit reads."""
    return _read_by_name(client.get_roles, "roles")


def gather_live_teams(client) -> tuple[dict[str, dict] | None, str | None]:
    """The target's teams by name — the same ``GET /Team`` the audit reads."""
    return _read_by_name(client.get_teams, "teams")


def _live_role_sides(live: dict | None) -> tuple[dict | None, dict | None]:
    """A live Role record's scope matrix and system permissions, shaped as the
    design stores them (the audit copies ``data`` and the ``*Permission``
    columns straight in, so the two sides compare directly)."""
    if live is None:
        return None, None
    scope = live.get("data") if isinstance(live.get("data"), dict) else None
    perms = {k: v for k, v in live.items() if "Permission" in k} or None
    return scope, perms


def assess_publish_access(
    programs: list[tuple[str, ProgramFile]],
    design_client,
    client,
    *,
    target_identifier: str,
) -> dict[str, Any]:
    """What publishing these programs would do to access on the target.

    Every role and team the scoped programs declare is assessed against the
    live target. The section is always returned, so a preview always states
    the effect, even when that effect is "nothing here touches access".

    :param programs: the scoped, parsed programs a publish would deploy.
    :param design_client: the design source, read for each role's stored
        definition (the same record the reconcile route assesses).
    :param client: the connected target admin client (``get_roles``,
        ``get_teams``). Only read.
    :returns: ``{target, assessed, known, reason, roles, teams, changes,
        removals, removes_access, requires_confirmation, summary}``. Each
        entry of ``roles`` is an :func:`assess_member_access` result plus
        ``live_state``; each change carries ``member_name`` so a refusal can
        name the role it belongs to.
    """
    role_names = sorted({r.name for _, p in programs for r in p.roles})
    team_names = sorted({t.name for _, p in programs for t in p.teams})
    section: dict[str, Any] = {
        "target": target_identifier,
        "assessed": bool(role_names or team_names),
        "known": True,
        "reason": None,
        "roles": [],
        "teams": [],
        "changes": [],
        "removals": [],
        "removes_access": False,
        "requires_confirmation": bool(role_names or team_names),
        "summary": "",
    }
    if not section["assessed"]:
        section["summary"] = (
            "The published programs declare no role or team; access on "
            f"{target_identifier} is left as it is."
        )
        return section

    reasons: list[str] = []
    live_roles: dict[str, dict] | None = {}
    if role_names:
        live_roles, err = gather_live_roles(client)
        if err:
            reasons.append(err)
    live_teams: dict[str, dict] | None = {}
    if team_names:
        live_teams, err = gather_live_teams(client)
        if err:
            reasons.append(err)

    design_roles = {
        r.get("role_name"): r for r in design_client.list_roles()
    }
    for name in role_names:
        record = design_roles.get(name) or {}
        live = (live_roles or {}).get(name)
        if live_roles is None:
            state = LIVE_UNKNOWN
        elif live is None:
            state = LIVE_ABSENT
        else:
            state = LIVE_PRESENT
        inst_scope, inst_perms = _live_role_sides(live)
        entry = reconcile_access.assess_member_access(
            instance=target_identifier,
            member_type="role",
            member_identifier=record.get("role_identifier") or name,
            member_name=name,
            design_scope_access=record.get("role_scope_access"),
            design_system_permissions=record.get("role_system_permissions"),
            instance_scope_access=inst_scope,
            instance_system_permissions=inst_perms,
        )
        entry["live_state"] = state
        if state == LIVE_UNKNOWN:
            # Not "no changes": the target could not be read, so nothing is
            # claimed either way.
            entry["changes"] = []
            entry["removals"] = []
            entry["removes_access"] = False
            entry["summary"] = (
                f"Publishing role {name} to {target_identifier} has an "
                "effect on access that could not be determined: "
                + "; ".join(reasons)
            )
        for change in entry["changes"]:
            change["member_name"] = name
        section["roles"].append(entry)
        section["changes"].extend(entry["changes"])
        section["removals"].extend(entry["removals"])

    for name in team_names:
        if live_teams is None:
            state = LIVE_UNKNOWN
        elif name in live_teams:
            state = LIVE_PRESENT
        else:
            state = LIVE_ABSENT
        entry = reconcile_access.assess_member_access(
            instance=target_identifier,
            member_type="team",
            member_identifier=name,
            member_name=name,
        )
        entry["live_state"] = state
        if state == LIVE_ABSENT:
            entry["summary"] += " The target holds no such team; it is created."
        section["teams"].append(entry)

    section["known"] = not reasons
    section["reason"] = "; ".join(reasons) or None
    section["removes_access"] = bool(section["removals"])

    if reasons:
        section["summary"] = (
            f"The effect of this publish on access at {target_identifier} "
            "could not be determined: " + "; ".join(reasons)
        )
    else:
        parts = [
            f"Publishing the security program to {target_identifier} "
            f"changes {len(section['changes'])} access setting(s) across "
            f"{len(role_names)} role(s), {len(section['removals'])} of "
            "which take access away."
        ]
        if team_names:
            parts.append(
                f"{len(team_names)} team(s) change who is grouped for "
                "sharing on that instance."
            )
        section["summary"] = " ".join(parts)
    return section


def describe_removals(section: dict[str, Any]) -> str:
    """The removals, one per clause, in the reconcile route's words."""
    return "; ".join(c["description"] for c in section.get("removals", []))
