"""Access-change assessment for a security publish — PI-417 (REQ-521).

Publishing a role or a team is not like publishing a field. A field publish
changes what a CRM can record; a role publish changes who can reach what, and
the operator finds out only when someone cannot do their job. So a publish that
touches access states its target and its effect before it runs, and the half of
that effect which *takes access away* is fenced separately: an operator who
agreed to "push the Mentor role" has not thereby agreed to revoke the delete
permission an instance currently grants.

This module answers both questions and applies neither. It reads the design
record and the instance's recorded deviation, then reports the change in the
vocabulary an operator reads — scope, action, from, to — and says plainly
whether any part of it is a removal.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from crmbuilder_v2.access.exceptions import ConflictError, NotFoundError
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import roles as roles_repo
from crmbuilder_v2.access.repositories import teams as teams_repo

#: Member types whose publish changes access and so passes through this gate.
ACCESS_MEMBER_TYPES = frozenset({"role", "team"})

#: EspoCRM's scope-access levels, weakest first. Ranking them is what lets the
#: gate tell a widening from a removal: ``team`` → ``all`` grants, ``all`` →
#: ``team`` takes away. ``account`` and ``contact`` are portal-side breadths
#: that both sit above ``own`` and below ``all``; they are not comparable with
#: each other, and a move between them is reported as a change, not a removal.
_LEVEL_RANK: dict[str, int] = {
    "no": 0,
    "own": 1,
    "account": 2,
    "contact": 2,
    "team": 3,
    "all": 4,
    # create/stream-style booleans share the ladder at its two ends
    "yes": 4,
}

#: System permissions use the same ladder plus EspoCRM's "inherit the default"
#: sentinel, which grants nothing of its own.
_NOT_SET = "not-set"


def _rank(level: Any) -> int | None:
    """The access weight of a level, or ``None`` when it is not on the ladder.

    An unranked value (a level this vocabulary has not met, or the ``not-set``
    sentinel) is deliberately not treated as zero: guessing that an unknown
    level means "no access" would let a real removal past the gate.
    """
    if not isinstance(level, str):
        return None
    return _LEVEL_RANK.get(level)


def _is_removal(before: Any, after: Any) -> bool:
    """Whether moving from ``before`` to ``after`` takes access away.

    Only a move down a ranked ladder counts. Anything else — a widening, a
    sideways move between portal breadths, a level either side of the ladder —
    is a change the operator still confirms, but not one the removal fence
    holds back.
    """
    b, a = _rank(before), _rank(after)
    if b is None or a is None:
        return False
    return a < b


def _scope_access_changes(
    instance_value: dict | None, design_value: dict | None
) -> list[dict[str, Any]]:
    """Per-(scope, action) changes between what an instance grants and what the
    design would set. A scope the design does not mention is not a change: the
    security program declares what it declares and leaves the rest alone."""
    inst = instance_value or {}
    design = design_value or {}
    out: list[dict[str, Any]] = []
    for scope in sorted(design):
        actions = design[scope]
        if not isinstance(actions, dict):
            continue
        inst_actions = inst.get(scope) if isinstance(inst.get(scope), dict) else {}
        for action in sorted(actions):
            after = actions[action]
            before = inst_actions.get(action)
            if before == after:
                continue
            out.append({
                "attribute": "role_scope_access",
                "scope": scope,
                "action": action,
                "before": before,
                "after": after,
                "removes_access": _is_removal(before, after),
            })
    return out


def _system_permission_changes(
    instance_value: dict | None, design_value: dict | None
) -> list[dict[str, Any]]:
    """Per-permission changes, same rules as the scope matrix. ``not-set`` on
    either side is off the ladder, so such a move is reported and confirmed but
    never claimed to be a removal we can prove."""
    inst = instance_value or {}
    design = design_value or {}
    out: list[dict[str, Any]] = []
    for key in sorted(design):
        after = design[key]
        before = inst.get(key)
        if before == after:
            continue
        out.append({
            "attribute": "role_system_permissions",
            "permission": key,
            "before": before,
            "after": after,
            "removes_access": (
                before != _NOT_SET and after != _NOT_SET
                and _is_removal(before, after)
            ),
        })
    return out


def _describe(change: dict[str, Any], member_name: str) -> str:
    """One operator-readable line for a change."""
    if "scope" in change:
        where = f"{change['scope']}.{change['action']}"
    else:
        where = change["permission"]
    before = change["before"] if change["before"] is not None else "unset"
    return f"{member_name}: {where} {before} → {change['after']}"


def assess_access_publish(
    session: Session,
    *,
    instance: str,
    member_type: str,
    member_identifier: str,
) -> dict[str, Any]:
    """What a role or team publish would do to access on ``instance`` (REQ-521).

    Compares the design record against the instance's recorded deviation and
    reports the effect. ``removes_access`` is true when any part of the change
    lowers a level the instance currently grants; the caller must not apply such
    a publish without a deliberate second confirmation.

    A team carries no access levels of its own — it is a container users are put
    into — so a team publish always requires confirmation and never reports a
    removal.

    :returns: ``{target, changes, removals, removes_access,
        requires_confirmation, summary}``.
    """
    if member_type not in ACCESS_MEMBER_TYPES:
        raise ConflictError(
            f"member type {member_type!r} does not change access; "
            "this assessment does not apply"
        )

    if member_type == "role":
        record = roles_repo.get_role(session, member_identifier)
        name_key = "role_name"
    else:
        record = teams_repo.get_team(session, member_identifier)
        name_key = "team_name"
    if record is None:
        raise NotFoundError(member_type, member_identifier)
    member_name = record.get(name_key) or member_identifier

    rows = membership_repo.list_memberships(
        session,
        instance_identifier=instance,
        member_type=member_type,
        member_identifier=member_identifier,
    )
    override = (rows[0] if rows else {}).get("override") or {}

    changes: list[dict[str, Any]] = []
    if member_type == "role":
        changes += _scope_access_changes(
            override.get("role_scope_access"), record.get("role_scope_access")
        )
        changes += _system_permission_changes(
            override.get("role_system_permissions"),
            record.get("role_system_permissions"),
        )

    removals = [c for c in changes if c["removes_access"]]
    for change in changes:
        change["description"] = _describe(change, member_name)

    if member_type == "team":
        summary = (
            f"Publishing team {member_name} to {instance} changes who is "
            "grouped for sharing on that instance."
        )
    elif not changes:
        summary = (
            f"Publishing role {member_name} to {instance} writes the design's "
            "access definition; the instance records no differing value."
        )
    else:
        summary = (
            f"Publishing role {member_name} to {instance} changes "
            f"{len(changes)} access setting(s), "
            f"{len(removals)} of which take access away."
        )

    return {
        "target": {
            "instance": instance,
            "member_type": member_type,
            "member_identifier": member_identifier,
            "member_name": member_name,
        },
        "changes": changes,
        "removals": removals,
        "removes_access": bool(removals),
        "requires_confirmation": True,
        "summary": summary,
    }
