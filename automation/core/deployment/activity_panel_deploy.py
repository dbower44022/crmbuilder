"""Deploy coordinator for entity activity panels (PI-338 / REQ-379).

Ties together the two paths (REST layout enable + SSH parent-list registration)
into a single idempotent operation that gives a set of entities their
Activities / History / Tasks panels — and, where requested, enables ``Stream`` —
against one EspoCRM instance, then verifies the result.

Sequence (per ``entity-activity-panel-enablement-design.md``):

1. **Scaffold** (SSH) every target entity's own activity metadata — the
   ``meetings``/``calls``/``tasks``/``emails`` links and the ``activities``/
   ``history`` ``clientDefs`` panels a fresh ``BasePlus`` entity has but an
   audit-deployed one lacks. Without this the panels stay empty even when
   registered, because the entity has no relationships for them to read.
2. **Register** (SSH, Path 2) every target entity not already an activity parent
   of Meeting/Call/Task — one batched metadata write per holder.
3. **Stream** (REST) — enable ``stream`` on the entities that ask for it.
4. **Panels** (REST, Path 1) — deploy each entity's ``bottomPanelsDetail`` layout
   so the panels render.
5. **Rebuild** once (SSH) to apply the metadata + layout changes.
6. **Verify** — poll each entity's registration (the cache can briefly lag after
   rebuild), read back its panel layout, and confirm its activity links.

The op is safe to re-run: scaffolding overwrites to the canonical shape,
registration skips entities already present, layout deploys are idempotent, and
enabling ``stream`` twice is a no-op.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from automation.core.deployment import activity_metadata_ssh as ams
from automation.core.deployment.ssh_deploy import connect_ssh
from espo_impl.core.activity_panel_manager import (
    PANEL_HOLDERS,
    ActivityPanelManager,
)

LogFn = Callable[[str, str], None]


@dataclass
class EntityPanelResult:
    """Per-entity outcome of an activity-panel deploy."""

    entity: str
    registered: bool = False
    panels_enabled: bool = False
    links_ok: bool = False
    stream_set: bool | None = None  # None when stream was not requested

    @property
    def ok(self) -> bool:
        """True when the entity ended registered, with its activity links and
        panels in place (and, if stream was requested, with stream set)."""
        return (
            self.registered
            and self.panels_enabled
            and self.links_ok
            and (self.stream_set is not False)
        )


@dataclass
class ActivityPanelDeployResult:
    """Aggregate result of an activity-panel deploy across entities."""

    entities: dict[str, EntityPanelResult] = field(default_factory=dict)
    registered_via_ssh: list[str] = field(default_factory=list)

    @property
    def all_ok(self) -> bool:
        return bool(self.entities) and all(r.ok for r in self.entities.values())


def deploy_activity_panels(
    client: Any,
    ssh_config: Any,
    entities: list[str],
    *,
    stream_entities: tuple[str, ...] = (),
    drop_links: dict[str, tuple[str, ...]] | None = None,
    holders: tuple[str, ...] = PANEL_HOLDERS,
    timestamp: str,
    log: LogFn | None = None,
    verify_timeout: float = 20.0,
) -> ActivityPanelDeployResult:
    """Give ``entities`` their activity panels on one instance, then verify.

    :param client: An :class:`EspoAdminClient` for the target instance.
    :param ssh_config: An object with ``ssh_host``/``ssh_port``/``ssh_username``/
        ``ssh_auth_type``/``ssh_credential`` (e.g. ``InstanceDeployConfig`` or
        ``SelfHostedConfig``) — passed to :func:`connect_ssh`.
    :param entities: EspoCRM entity names (C-prefixed) to enable panels on.
    :param stream_entities: Subset of entities to additionally enable Stream on.
    :param drop_links: Optional ``{entity: (link, …)}`` of mis-wired links to
        remove before scaffolding (e.g. a ``cParent``-based ``meetings`` link).
    :param holders: Activity-parent holders (Meeting/Call/Task by default).
    :param timestamp: Backup-folder discriminator for the SSH metadata writes.
    :param log: Optional ``(message, color)`` logger.
    :param verify_timeout: Seconds to poll registration after rebuild.
    :returns: An :class:`ActivityPanelDeployResult`.
    """
    emit = log or (lambda *_: None)
    mgr = ActivityPanelManager(client, output_fn=emit)
    result = ActivityPanelDeployResult(
        entities={e: EntityPanelResult(entity=e) for e in entities}
    )

    ssh = connect_ssh(ssh_config)
    try:
        # 1. Scaffold each entity's own activity links + clientDefs panels — the
        #    piece an audit-deployed entity lacks (a fresh BasePlus has it).
        emit(f"[DEPLOY]  scaffolding activity metadata on {len(entities)} entit(y/ies)...", "white")
        ams.scaffold_entity_activity_metadata(
            ssh, entities, timestamp, drop_links=drop_links, log=log
        )

        # 2. Register any entity not already an activity parent (batched).
        to_register = [e for e in entities if not mgr.is_registered(e, holders)]
        result.registered_via_ssh = to_register
        if to_register:
            emit(f"[DEPLOY]  registering {len(to_register)} entit(y/ies) via SSH...", "white")
            ams.register_activity_parents(
                ssh, client, to_register, timestamp, holders, log
            )
        else:
            emit("[DEPLOY]  all entities already registered as activity parents", "gray")

        # 3. Stream (REST) — enable where requested.
        for entity in stream_entities:
            emit(f"[DEPLOY]  enabling Stream on {entity}...", "white")
            status, _body = client.update_entity({"name": entity, "stream": True})
            result.entities[entity].stream_set = status == 200

        # 4. Panels (REST) — deploy each layout.
        for entity in entities:
            result.entities[entity].panels_enabled = mgr.enable_panels_layout(entity)

        # 5. Rebuild once to apply metadata + layouts.
        ams.rebuild_in_container(ssh, log)

        # 6. Verify — poll registration (cache can lag), confirm panels + links.
        for entity in entities:
            res = result.entities[entity]
            res.registered = mgr.wait_until_registered(
                entity, holders, timeout=verify_timeout
            )
            res.panels_enabled = mgr.panels_enabled(entity)
            res.links_ok = mgr.has_activity_links(entity)
            colour = "green" if res.ok else "red"
            emit(
                f"[DEPLOY]  {entity}: registered={res.registered} "
                f"panels={res.panels_enabled} links={res.links_ok} "
                f"stream={res.stream_set}",
                colour,
            )
    finally:
        ssh.close()

    return result
