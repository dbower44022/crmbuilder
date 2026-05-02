"""CRUD for the InstanceDeployConfig table.

Reads and writes deploy config rows from the per-client SQLite
database, round-tripping secret values through the OS keyring so
plaintext secrets never live in the DB.

See PRDs/product/features/feat-server-management.md §5.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import sqlite3
from collections.abc import Iterable

from automation.core import secrets

logger = logging.getLogger(__name__)


SCENARIO_SELF_HOSTED = "self_hosted"
SSH_AUTH_KEY = "key"
SSH_AUTH_PASSWORD = "password"


@dataclasses.dataclass
class InstanceDeployConfig:
    """Hydrated deploy config for an instance.

    Secret values are resolved at load time. ``ssh_credential`` holds
    the key file path when ``ssh_auth_type == 'key'`` and the password
    when ``'password'``. ``db_root_password`` is always resolved.

    The internal ``_*_ref`` fields preserve the keyring reference IDs
    so updates can replace specific secrets without rewriting all of
    them.
    """

    instance_id: int
    scenario: str
    ssh_host: str
    ssh_port: int
    ssh_username: str
    ssh_auth_type: str
    ssh_credential: str
    domain: str
    letsencrypt_email: str
    db_root_password: str
    admin_email: str | None = None
    current_espocrm_version: str | None = None
    latest_espocrm_version: str | None = None
    last_upgrade_at: str | None = None
    last_backup_paths: list[str] = dataclasses.field(default_factory=list)
    cert_expiry_date: str | None = None
    domain_registrar: str | None = None
    dns_provider: str | None = None
    droplet_id: str | None = None
    backups_enabled: bool | None = None
    proton_pass_admin_entry: str | None = None
    proton_pass_db_root_entry: str | None = None
    proton_pass_hosting_entry: str | None = None
    last_record_version: str | None = None
    id: int | None = None
    _ssh_credential_ref: str | None = None
    _db_root_password_ref: str | None = None


def _row_to_config(row: sqlite3.Row | tuple) -> InstanceDeployConfig:
    """Build an InstanceDeployConfig from a SELECT * row."""
    (
        id_,
        instance_id,
        scenario,
        ssh_host,
        ssh_port,
        ssh_username,
        ssh_auth_type,
        ssh_credential_ref,
        domain,
        letsencrypt_email,
        db_root_password_ref,
        admin_email,
        current_version,
        latest_version,
        last_upgrade_at,
        last_backup_paths,
        cert_expiry_date,
        domain_registrar,
        dns_provider,
        droplet_id,
        backups_enabled,
        proton_pass_admin_entry,
        proton_pass_db_root_entry,
        proton_pass_hosting_entry,
        last_record_version,
        _created_at,
        _updated_at,
    ) = row

    if ssh_auth_type == SSH_AUTH_KEY:
        ssh_credential = ssh_credential_ref
    else:
        ssh_credential = secrets.get_secret(ssh_credential_ref)
    db_root_password = secrets.get_secret(db_root_password_ref)

    paths: list[str] = []
    if last_backup_paths:
        try:
            decoded = json.loads(last_backup_paths)
            if isinstance(decoded, list):
                paths = [str(p) for p in decoded]
        except json.JSONDecodeError:
            logger.warning(
                "Could not decode last_backup_paths for instance %s",
                instance_id,
            )

    return InstanceDeployConfig(
        id=id_,
        instance_id=instance_id,
        scenario=scenario,
        ssh_host=ssh_host,
        ssh_port=ssh_port,
        ssh_username=ssh_username,
        ssh_auth_type=ssh_auth_type,
        ssh_credential=ssh_credential,
        domain=domain,
        letsencrypt_email=letsencrypt_email,
        db_root_password=db_root_password,
        admin_email=admin_email,
        current_espocrm_version=current_version,
        latest_espocrm_version=latest_version,
        last_upgrade_at=last_upgrade_at,
        last_backup_paths=paths,
        cert_expiry_date=cert_expiry_date,
        domain_registrar=domain_registrar,
        dns_provider=dns_provider,
        droplet_id=droplet_id,
        backups_enabled=(
            None if backups_enabled is None else bool(backups_enabled)
        ),
        proton_pass_admin_entry=proton_pass_admin_entry,
        proton_pass_db_root_entry=proton_pass_db_root_entry,
        proton_pass_hosting_entry=proton_pass_hosting_entry,
        last_record_version=last_record_version,
        _ssh_credential_ref=ssh_credential_ref,
        _db_root_password_ref=db_root_password_ref,
    )


def load_deploy_config(
    conn: sqlite3.Connection, instance_id: int
) -> InstanceDeployConfig | None:
    """Load a deploy config for the given instance, or None if absent.

    :param conn: Per-client database connection.
    :param instance_id: Instance.id to look up.
    :returns: InstanceDeployConfig with secrets resolved, or None.
    """
    row = conn.execute(
        "SELECT id, instance_id, scenario, ssh_host, ssh_port, "
        "ssh_username, ssh_auth_type, ssh_credential_ref, domain, "
        "letsencrypt_email, db_root_password_ref, admin_email, "
        "current_espocrm_version, latest_espocrm_version, "
        "last_upgrade_at, last_backup_paths, cert_expiry_date, "
        "domain_registrar, dns_provider, droplet_id, backups_enabled, "
        "proton_pass_admin_entry, proton_pass_db_root_entry, "
        "proton_pass_hosting_entry, last_record_version, "
        "created_at, updated_at "
        "FROM InstanceDeployConfig WHERE instance_id = ?",
        (instance_id,),
    ).fetchone()
    if row is None:
        return None
    return _row_to_config(row)


def save_deploy_config(
    conn: sqlite3.Connection, config: InstanceDeployConfig
) -> InstanceDeployConfig:
    """Insert or update a deploy config, persisting secrets to keyring.

    Replaces existing keyring entries for this instance so old values
    do not linger. Runs in a single transaction with the keyring writes
    completed *before* the DB commit so a DB rollback does not leave
    orphan secrets — only an unused secret in the keyring, which is
    safe.

    :param conn: Per-client database connection.
    :param config: Config to save. Mutated in place to record the
        keyring reference IDs and (on insert) the new row id.
    :returns: The same config, with refs and id populated.
    """
    if config.scenario != SCENARIO_SELF_HOSTED:
        raise ValueError(
            f"Unsupported scenario {config.scenario!r}; v1 supports "
            "'self_hosted' only."
        )
    if config.ssh_auth_type not in {SSH_AUTH_KEY, SSH_AUTH_PASSWORD}:
        raise ValueError(
            f"Unsupported ssh_auth_type {config.ssh_auth_type!r}"
        )

    existing = load_deploy_config(conn, config.instance_id)
    old_refs_to_delete: list[str] = []
    if existing is not None:
        if existing._ssh_credential_ref and existing.ssh_auth_type != SSH_AUTH_KEY:
            old_refs_to_delete.append(existing._ssh_credential_ref)
        if existing._db_root_password_ref:
            old_refs_to_delete.append(existing._db_root_password_ref)

    if config.ssh_auth_type == SSH_AUTH_KEY:
        ssh_credential_ref = config.ssh_credential
    else:
        ssh_credential_ref = secrets.put_secret(config.ssh_credential)
    db_root_password_ref = secrets.put_secret(config.db_root_password)

    config._ssh_credential_ref = ssh_credential_ref
    config._db_root_password_ref = db_root_password_ref

    last_backup_paths_json = json.dumps(config.last_backup_paths or [])

    backups_enabled_int = (
        None if config.backups_enabled is None else int(config.backups_enabled)
    )
    if existing is None:
        cursor = conn.execute(
            "INSERT INTO InstanceDeployConfig ("
            "    instance_id, scenario, ssh_host, ssh_port, "
            "    ssh_username, ssh_auth_type, ssh_credential_ref, "
            "    domain, letsencrypt_email, db_root_password_ref, "
            "    admin_email, current_espocrm_version, "
            "    latest_espocrm_version, last_upgrade_at, "
            "    last_backup_paths, cert_expiry_date, "
            "    domain_registrar, dns_provider, droplet_id, "
            "    backups_enabled, proton_pass_admin_entry, "
            "    proton_pass_db_root_entry, proton_pass_hosting_entry, "
            "    last_record_version"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, "
            "?, ?, ?, ?, ?, ?, ?, ?)",
            (
                config.instance_id,
                config.scenario,
                config.ssh_host,
                config.ssh_port,
                config.ssh_username,
                config.ssh_auth_type,
                ssh_credential_ref,
                config.domain,
                config.letsencrypt_email,
                db_root_password_ref,
                config.admin_email,
                config.current_espocrm_version,
                config.latest_espocrm_version,
                config.last_upgrade_at,
                last_backup_paths_json,
                config.cert_expiry_date,
                config.domain_registrar,
                config.dns_provider,
                config.droplet_id,
                backups_enabled_int,
                config.proton_pass_admin_entry,
                config.proton_pass_db_root_entry,
                config.proton_pass_hosting_entry,
                config.last_record_version,
            ),
        )
        config.id = cursor.lastrowid
    else:
        conn.execute(
            "UPDATE InstanceDeployConfig SET "
            "    scenario = ?, ssh_host = ?, ssh_port = ?, "
            "    ssh_username = ?, ssh_auth_type = ?, "
            "    ssh_credential_ref = ?, domain = ?, "
            "    letsencrypt_email = ?, db_root_password_ref = ?, "
            "    admin_email = ?, current_espocrm_version = ?, "
            "    latest_espocrm_version = ?, last_upgrade_at = ?, "
            "    last_backup_paths = ?, cert_expiry_date = ?, "
            "    domain_registrar = ?, dns_provider = ?, "
            "    droplet_id = ?, backups_enabled = ?, "
            "    proton_pass_admin_entry = ?, "
            "    proton_pass_db_root_entry = ?, "
            "    proton_pass_hosting_entry = ?, "
            "    last_record_version = ?, "
            "    updated_at = CURRENT_TIMESTAMP "
            "WHERE instance_id = ?",
            (
                config.scenario,
                config.ssh_host,
                config.ssh_port,
                config.ssh_username,
                config.ssh_auth_type,
                ssh_credential_ref,
                config.domain,
                config.letsencrypt_email,
                db_root_password_ref,
                config.admin_email,
                config.current_espocrm_version,
                config.latest_espocrm_version,
                config.last_upgrade_at,
                last_backup_paths_json,
                config.cert_expiry_date,
                config.domain_registrar,
                config.dns_provider,
                config.droplet_id,
                backups_enabled_int,
                config.proton_pass_admin_entry,
                config.proton_pass_db_root_entry,
                config.proton_pass_hosting_entry,
                config.last_record_version,
                config.instance_id,
            ),
        )
        config.id = existing.id
    conn.commit()

    for ref in old_refs_to_delete:
        secrets.delete_secret(ref)

    return config


def delete_deploy_config(
    conn: sqlite3.Connection, instance_id: int
) -> bool:
    """Remove a deploy config and its keyring secrets.

    :param conn: Per-client database connection.
    :param instance_id: Instance.id whose config should be removed.
    :returns: True if a row was deleted, False if no config existed.
    """
    existing = load_deploy_config(conn, instance_id)
    if existing is None:
        return False

    conn.execute(
        "DELETE FROM InstanceDeployConfig WHERE instance_id = ?",
        (instance_id,),
    )
    conn.commit()

    if (
        existing._ssh_credential_ref
        and existing.ssh_auth_type != SSH_AUTH_KEY
    ):
        secrets.delete_secret(existing._ssh_credential_ref)
    if existing._db_root_password_ref:
        secrets.delete_secret(existing._db_root_password_ref)
    return True


def update_version_state(
    conn: sqlite3.Connection,
    instance_id: int,
    *,
    current_version: str | None = None,
    latest_version: str | None = None,
) -> None:
    """Update only the version-tracking columns. No-op if no config exists.

    Used by VersionCheckWorker to persist results without rewriting
    secret references.
    """
    sets: list[str] = []
    values: list = []
    if current_version is not None:
        sets.append("current_espocrm_version = ?")
        values.append(current_version)
    if latest_version is not None:
        sets.append("latest_espocrm_version = ?")
        values.append(latest_version)
    if not sets:
        return
    sets.append("updated_at = CURRENT_TIMESTAMP")
    values.append(instance_id)
    conn.execute(
        f"UPDATE InstanceDeployConfig SET {', '.join(sets)} "
        "WHERE instance_id = ?",
        values,
    )
    conn.commit()


def update_after_upgrade(
    conn: sqlite3.Connection,
    instance_id: int,
    *,
    current_version: str,
    last_upgrade_at: str,
    last_backup_paths: Iterable[str],
) -> None:
    """Record post-upgrade state. No-op if no config exists."""
    conn.execute(
        "UPDATE InstanceDeployConfig SET "
        "    current_espocrm_version = ?, "
        "    last_upgrade_at = ?, "
        "    last_backup_paths = ?, "
        "    updated_at = CURRENT_TIMESTAMP "
        "WHERE instance_id = ?",
        (
            current_version,
            last_upgrade_at,
            json.dumps(list(last_backup_paths)),
            instance_id,
        ),
    )
    conn.commit()
