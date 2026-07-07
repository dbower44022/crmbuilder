"""Agent-profile binding repository (REQ-472 / PI-396).

Registry-native bindings with nullable ``engagement_id`` scope: a NULL row is
a **system-baseline** binding every engagement inherits when a contract is
resolved; an engagement row is that engagement's overlay. An engagement-scoped
``mode='disable'`` row masks the system-baseline binding of the same
``(target_type, target_id)`` for that engagement — replace = a disable row
plus an engagement ``bind`` row, mirroring the governance-rule
``disable:<target>`` overlay.

Per-engagement ``agent_profile_has_skill`` / ``agent_profile_governed_by_rule``
reference edges continue to work unchanged (``refs.engagement_id`` is NOT
NULL, so system bindings cannot live there); the resolver unions both sources.
No change_log emission: bindings are not an ``ENTITY_TYPES`` member and are
not referenceable from ``refs``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from crmbuilder_v2.access._helpers import to_dict
from crmbuilder_v2.access.exceptions import (
    ConflictError,
    FieldError,
    NotFoundError,
    UnprocessableError,
)
from crmbuilder_v2.access.models import AgentProfileBindingRow
from crmbuilder_v2.access.repositories import agent_profiles, governance_rules, skills
from crmbuilder_v2.access.repositories._registry import resolve_scope, with_scope
from crmbuilder_v2.access.vocab import BINDING_MODES, BINDING_TARGET_TYPES


def _enrich(row: AgentProfileBindingRow) -> dict:
    return with_scope(to_dict(row), row.engagement_id)


def _require_vocab(field: str, value: str, allowed) -> str:
    if value not in allowed:
        raise UnprocessableError(
            [FieldError(field, "invalid", f"{field} must be one of {sorted(allowed)}")]
        )
    return value


def _require_target_exists(session: Session, target_type: str, target_id: str) -> None:
    if target_type == "skill":
        skills.get(session, target_id)
    else:
        governance_rules.get(session, target_id)


def list_for_profile(
    session: Session,
    profile_id: str,
    *,
    engagement_id: str | None = None,
) -> list[dict]:
    """All binding rows visible when resolving ``profile_id`` for
    ``engagement_id``: the system baseline plus that engagement's overlay
    (system rows only when ``engagement_id`` is None)."""
    stmt = (
        select(AgentProfileBindingRow)
        .where(AgentProfileBindingRow.profile_id == profile_id)
        .order_by(AgentProfileBindingRow.id)
    )
    rows = session.scalars(stmt).all()
    return [
        _enrich(r)
        for r in rows
        if r.engagement_id is None or r.engagement_id == engagement_id
    ]


def create(
    session: Session,
    *,
    profile_id: str,
    target_type: str,
    target_id: str,
    mode: str = "bind",
    scope: str | None = None,
) -> dict:
    """Create a binding row. ``scope`` follows the registry convention:
    ``None`` / ``"system"`` = system baseline, else an engagement identifier.
    A ``disable`` row must be engagement-scoped — disabling the baseline at
    system scope is just deleting the baseline row."""
    _require_vocab("target_type", target_type, BINDING_TARGET_TYPES)
    _require_vocab("mode", mode, BINDING_MODES)
    agent_profiles.get(session, profile_id)
    _require_target_exists(session, target_type, target_id)
    engagement_id = resolve_scope(session, scope)
    if mode == "disable" and engagement_id is None:
        raise UnprocessableError(
            [
                FieldError(
                    "mode",
                    "invalid_scope",
                    "a disable binding must be engagement-scoped; delete the "
                    "system-baseline row to remove a baseline binding",
                )
            ]
        )
    duplicate = session.scalar(
        select(AgentProfileBindingRow).where(
            AgentProfileBindingRow.profile_id == profile_id,
            AgentProfileBindingRow.target_type == target_type,
            AgentProfileBindingRow.target_id == target_id,
            AgentProfileBindingRow.mode == mode,
            AgentProfileBindingRow.engagement_id == engagement_id
            if engagement_id is not None
            else AgentProfileBindingRow.engagement_id.is_(None),
        )
    )
    if duplicate is not None:
        raise ConflictError(
            f"binding already exists (id {duplicate.id}): {profile_id} "
            f"-{mode}-> {target_type}:{target_id} at scope "
            f"{engagement_id or 'system'}"
        )
    row = AgentProfileBindingRow(
        engagement_id=engagement_id,
        profile_id=profile_id,
        target_type=target_type,
        target_id=target_id,
        mode=mode,
    )
    session.add(row)
    session.flush()
    return _enrich(row)


def delete(session: Session, binding_id: int) -> None:
    row = session.get(AgentProfileBindingRow, binding_id)
    if row is None:
        raise NotFoundError("agent_profile_binding", str(binding_id))
    session.delete(row)
    session.flush()


def effective_targets(
    session: Session,
    profile_id: str,
    *,
    engagement_id: str | None = None,
) -> dict[str, list[str]]:
    """The merged binding targets for a contract resolution.

    System-baseline ``bind`` rows, minus targets the engagement disables,
    plus the engagement's own ``bind`` rows. Order: baseline rows first,
    then engagement rows, each in insertion order; duplicates collapse to
    the first occurrence.
    """
    visible = list_for_profile(session, profile_id, engagement_id=engagement_id)
    disabled = {
        (b["target_type"], b["target_id"])
        for b in visible
        if b["mode"] == "disable" and b["engagement_id"] is not None
    }
    out: dict[str, list[str]] = {t: [] for t in BINDING_TARGET_TYPES}
    for baseline_pass in (True, False):
        for b in visible:
            if b["mode"] != "bind":
                continue
            if (b["engagement_id"] is None) != baseline_pass:
                continue
            if baseline_pass and (b["target_type"], b["target_id"]) in disabled:
                continue
            if b["target_id"] not in out[b["target_type"]]:
                out[b["target_type"]].append(b["target_id"])
    return out
