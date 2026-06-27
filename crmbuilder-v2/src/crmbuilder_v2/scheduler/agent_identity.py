"""Per-agent service-agent principal minting at spawn (REQ-381 / PI-340).

When principal authentication is enabled, each spawned ADO agent gets its own
``service_agent`` principal + bearer token so it calls the API as a distinct
identity and claims its Work Task as *itself*; the token is revoked when the run
ends. Minting goes **directly** through ``session_scope`` (the
``event_capture`` / ``cost_capture`` pattern) rather than the HTTP ``/admin/agents``
endpoint, so the orchestrator needs no bootstrap admin token.

Gated on ``Settings.principal_auth_enabled`` (default ``False``): when auth is
off, :func:`mint_for_spawn` returns ``None`` and the spawn path is unchanged —
a minted token would never be validated anyway. The companion gap (making the
scheduler's *own* API calls auth-aware) is a separate, deferred follow-on.
"""

from __future__ import annotations

import contextlib
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class AgentIdentity:
    """A spawned agent's minted identity: its principal + one-time token."""

    principal_id: str
    token: str  # the plaintext bearer token (shown once) — injected into the agent
    token_id: str  # the token's id, used to revoke it after the run


def _engagement_ctx(engagement: str | None):
    if engagement is None:
        return contextlib.nullcontext()
    from crmbuilder_v2.access.engagement_scope import active_engagement

    return active_engagement(engagement)


def mint_for_spawn(
    engagement: str, *, area: str | None, tier: str | None, work_task_id: str
) -> AgentIdentity | None:
    """Mint a service-agent principal + token for a spawn, or ``None`` when auth is off.

    Returns ``None`` (no identity, behaviour unchanged) when
    ``principal_auth_enabled`` is off. When auth is on, mints and **raises on
    failure** — an agent that cannot authenticate would only 401, so a mint
    failure must surface rather than silently spawn a broken agent.
    """
    from crmbuilder_v2.config import get_settings

    if not get_settings().principal_auth_enabled:
        return None
    from crmbuilder_v2.access.db import session_scope
    from crmbuilder_v2.access.principal import mint_agent_principal

    with _engagement_ctx(engagement), session_scope() as s:
        principal, minted = mint_agent_principal(
            s,
            engagement_id=engagement,
            role="area_specialist",
            agent_tier=tier,
            agent_area=area,
            display_name=f"agent {work_task_id} on {engagement}",
            label=f"work-task {work_task_id}",
        )
        return AgentIdentity(
            principal_id=principal.principal_id,
            token=minted.plaintext,
            token_id=minted.token_id,
        )


def revoke(engagement: str, token_id: str | None) -> None:
    """Revoke a spawned agent's token after its run (best-effort — never raises)."""
    if not token_id:
        return
    try:
        from crmbuilder_v2.access.db import session_scope
        from crmbuilder_v2.access.principal import revoke_token

        with _engagement_ctx(engagement), session_scope() as s:
            revoke_token(s, token_id)
    except Exception as exc:  # noqa: BLE001 — revocation failure must not break the run
        log.warning("agent token revoke skipped for %s: %s", token_id, exc)
