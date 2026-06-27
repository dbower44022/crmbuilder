"""SSH metadata patch that registers an entity as an EspoCRM activity parent.

The Activities / History / Tasks panels appear on an entity's detail view only
when the entity is listed in ``entityDefs.{Meeting,Call,Task}.fields.parent.entityList``.
``createEntity(BasePlus)`` registers a *new* entity there, but an entity that is
already ``BasePlus`` yet absent from those lists cannot be repaired over REST —
``updateEntity`` no-ops on the template, and there is no REST write path to a
foreign entity's ``parent.entityList`` metadata (the dead-``put_metadata``
constraint).

This module performs that registration the only way available: by patching the
EspoCRM container's custom metadata over SSH (the server-management layer already
owns SSH via ``InstanceDeployConfig``), then rebuilding the cache. The pure JSON
transform lives in :mod:`espo_impl.core.activity_panel_manager`
(``merge_parent_entity_list`` / ``union_parent_list``); this module is the I/O
and orchestration around it.

Mechanism (per ``PRDs/product/crmbuilder-automation-PRD/entity-activity-panel-enablement-design.md``):

* EspoCRM *replaces* (does not append) the ``parent.entityList`` array on
  metadata merge, so the custom override must carry the **complete** list. The
  live merged list is read over REST and unioned with the entities to add.
* Files are written by shipping base64 into the container (no in-container
  ``sed``; no shell-escaping of JSON), after backing up any existing file.
* The EspoCRM source tree is root-owned (Docker COPY caveat), so writes run as
  root and the touched files are ``chown``ed back to ``www-data`` before rebuild.
"""

from __future__ import annotations

import base64
import json
import shlex
from collections.abc import Callable
from typing import Any

import paramiko

from automation.core.deployment.ssh_deploy import run_remote
from espo_impl.core.activity_panel_manager import (
    PANEL_HOLDERS,
    union_parent_list,
)

COMPOSE_FILE = "/var/www/espocrm/docker-compose.yml"
SERVICE = "espocrm"
ESPO_ROOT = "/var/www/html"
CUSTOM_ENTITYDEFS_DIR = (
    f"{ESPO_ROOT}/custom/Espo/Custom/Resources/metadata/entityDefs"
)
BACKUP_ROOT = "/var/backups/espocrm/metadata"

LogFn = Callable[[str, str], None]


def _exec_in_container(
    ssh: paramiko.SSHClient, inner: str, *, as_root: bool = False
) -> tuple[int, str]:
    """Run ``inner`` inside the EspoCRM container via ``docker compose exec``.

    :param ssh: Connected SSH client (to the droplet host).
    :param inner: Shell command to run inside the container.
    :param as_root: Run as ``root`` (for writes to the root-owned source tree);
        otherwise run as ``www-data``.
    :returns: ``(exit_code, output)``.
    """
    user = "root" if as_root else "www-data"
    cmd = (
        f"docker compose -f {COMPOSE_FILE} exec -T -u {user} {SERVICE} "
        f"sh -c {shlex.quote(inner)}"
    )
    return run_remote(ssh, cmd)


def read_custom_holder_def(
    ssh: paramiko.SSHClient, holder: str
) -> dict[str, Any]:
    """Read a holder's custom ``entityDefs`` override file from the container.

    :param ssh: Connected SSH client.
    :param holder: Holder entity (``Meeting`` / ``Call`` / ``Task``).
    :returns: The parsed override dict, or ``{}`` if the file is absent/empty.
    """
    path = f"{CUSTOM_ENTITYDEFS_DIR}/{holder}.json"
    # base64 the file so newlines/encoding survive the SSH text channel; a
    # missing file yields empty output.
    exit_code, output = _exec_in_container(
        ssh, f"cat {path} 2>/dev/null | base64 | tr -d '\\n'"
    )
    blob = output.strip()
    if exit_code != 0 or not blob:
        return {}
    try:
        raw = base64.b64decode(blob).decode("utf-8").strip()
        return json.loads(raw) if raw else {}
    except (ValueError, json.JSONDecodeError):
        return {}


def write_custom_holder_def(
    ssh: paramiko.SSHClient,
    holder: str,
    data: dict[str, Any],
    timestamp: str,
    log: LogFn | None = None,
) -> bool:
    """Back up and write a holder's custom ``entityDefs`` override file.

    :param ssh: Connected SSH client.
    :param holder: Holder entity.
    :param data: The complete override dict to persist.
    :param timestamp: Backup-folder discriminator (caller supplies — no clock
        here so the function stays deterministic/testable in isolation).
    :param log: Optional ``(message, color)`` logger.
    :returns: True on success.
    """
    path = f"{CUSTOM_ENTITYDEFS_DIR}/{holder}.json"
    backup_dir = f"{BACKUP_ROOT}/{timestamp}"
    payload = json.dumps(data, indent=4, sort_keys=True)
    blob = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    # Backup any existing file, ensure the dir exists, write via base64, then
    # restore www-data ownership so PHP-FPM can read it.
    inner = (
        f"mkdir -p {backup_dir} {CUSTOM_ENTITYDEFS_DIR} && "
        f"if [ -f {path} ]; then cp {path} {backup_dir}/{holder}.json; fi && "
        f"echo {blob} | base64 -d > {path} && "
        f"chown www-data:www-data {path}"
    )
    exit_code, output = _exec_in_container(ssh, inner, as_root=True)
    if exit_code != 0:
        if log:
            log(f"[SSH] write {holder}.json failed (exit {exit_code}): {output}", "error")
        return False
    if log:
        log(f"[SSH] wrote {holder}.json (backup in {backup_dir})", "info")
    return True


def rebuild_in_container(
    ssh: paramiko.SSHClient, log: LogFn | None = None
) -> bool:
    """Run ``php command.php rebuild`` inside the container as www-data.

    :param ssh: Connected SSH client.
    :param log: Optional logger.
    :returns: True on success.
    """
    if log:
        log("[SSH] rebuilding EspoCRM cache...", "info")
    exit_code, output = _exec_in_container(
        ssh, f"cd {ESPO_ROOT} && php command.php rebuild"
    )
    if exit_code != 0:
        if log:
            log(f"[SSH] rebuild failed (exit {exit_code}): {output}", "error")
        return False
    return True


def register_activity_parents(
    ssh: paramiko.SSHClient,
    client: Any,
    entities: list[str],
    timestamp: str,
    holders: tuple[str, ...] = PANEL_HOLDERS,
    log: LogFn | None = None,
) -> dict[str, bool]:
    """Register ``entities`` as activity parents of each holder, via SSH patch.

    For each holder, reads the live merged ``parent.entityList`` over REST,
    unions in the target entities, merges that complete list into the holder's
    custom override file, and writes it back. The caller is responsible for the
    subsequent :func:`rebuild_in_container` (batched once after all holders).

    :param ssh: Connected SSH client.
    :param client: An :class:`EspoAdminClient` (for reading the merged list).
    :param entities: EspoCRM entity names to register (C-prefixed).
    :param timestamp: Backup-folder discriminator.
    :param holders: Holders to register against (Meeting/Call/Task by default).
    :param log: Optional logger.
    :returns: ``{holder: changed}`` — whether each holder's file was rewritten.
    """
    results: dict[str, bool] = {}
    for holder in holders:
        status, merged = client.get_metadata(
            f"entityDefs.{holder}.fields.parent.entityList"
        )
        current = merged if (status == 200 and isinstance(merged, list)) else []
        desired = union_parent_list(current, entities)
        if desired == current:
            if log:
                log(f"[SSH] {holder}: already registered, no change", "info")
            results[holder] = False
            continue

        custom = read_custom_holder_def(ssh, holder)
        custom.setdefault("fields", {}).setdefault("parent", {})
        custom["fields"]["parent"]["entityList"] = desired
        # Keep entityTypeList in sync only when the platform already uses it.
        type_status, type_list = client.get_metadata(
            f"entityDefs.{holder}.fields.parent.entityTypeList"
        )
        if type_status == 200 and isinstance(type_list, list):
            custom["fields"]["parent"]["entityTypeList"] = union_parent_list(
                type_list, entities
            )

        ok = write_custom_holder_def(ssh, holder, custom, timestamp, log)
        results[holder] = ok
    return results
