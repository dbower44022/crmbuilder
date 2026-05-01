"""SSH command logic for the Recovery & Reset operations.

Two operations:

1. ``reset_admin_credentials`` — runs a SQL UPDATE inside the
   ``espocrm-db`` MariaDB container to set a new admin username and
   password. Used when the admin lost access but the deployment is
   otherwise healthy.

2. ``teardown`` and ``build_reinstall_config`` — primitives for the
   full database reset, which tears down all containers and volumes
   and re-runs the EspoCRM installer. Destructive.

Pure Python, no Qt. Takes the persistent ``InstanceDeployConfig``
rather than the ephemeral ``SelfHostedConfig``.

See PRDs/product/features/feat-server-management.md §6.4.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import paramiko

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.ssh_deploy import (
    SelfHostedConfig,
    run_remote,
)
from automation.core.deployment.upgrade_ssh import mask_secrets

logger = logging.getLogger(__name__)


COMPOSE_FILE = "/var/www/espocrm/docker-compose.yml"
COMPOSE_DIR = "/var/www/espocrm"

# Verified against deployed EspoCRM containers:
# - Database engine is MariaDB; CLI is 'mariadb'
# - User table is named 'user' (singular)
# - Admin users have type='admin'; no separate is_admin column
DB_CLI = "mariadb"
USER_TABLE = "user"

LogCallback = Callable[[str, str], None]


# ── Admin credential reset ────────────────────────────────────────────


def reset_admin_credentials(
    ssh: paramiko.SSHClient,
    config: InstanceDeployConfig,
    new_username: str,
    new_password: str,
    log: LogCallback,
) -> tuple[bool, str]:
    """Reset the EspoCRM admin user's username and password.

    Runs a single SQL UPDATE inside the ``espocrm-db`` container. The
    plaintext password is hashed with MD5 (EspoCRM's stored format).

    :param ssh: Connected SSH client.
    :param config: Hydrated deploy config; ``db_root_password`` is used.
    :param new_username: New admin username.
    :param new_password: New admin password (plaintext; hashed in SQL).
    :param log: ``(message, level)`` callback for streaming output.
    :returns: (success, error_message).
    """
    if not new_username or not new_password:
        return False, "Username and password are both required."

    sql = (
        f"UPDATE {USER_TABLE} "
        f"SET user_name = '{new_username}', "
        f"password = MD5('{new_password}') "
        f"WHERE type = 'admin' AND deleted = 0 LIMIT 1;"
    )
    cmd = (
        f"docker compose -f {COMPOSE_FILE} exec -T espocrm-db "
        f"{DB_CLI} -u root -p'{config.db_root_password}' "
        f'espocrm -e "{sql}"'
    )
    safe_cmd = mask_secrets(cmd, [config.db_root_password, new_password])
    log(f"$ {safe_cmd}", "info")

    exit_code, output = run_remote(ssh, cmd)
    if exit_code != 0:
        safe_output = mask_secrets(
            output, [config.db_root_password, new_password]
        )
        return False, f"Credential reset failed: {safe_output}"

    log("Admin credentials reset successfully.", "info")
    return True, ""


# ── Full reset primitives ─────────────────────────────────────────────


def teardown(
    ssh: paramiko.SSHClient,
    log: LogCallback,
) -> tuple[bool, str]:
    """Stop and remove all EspoCRM Docker containers and volumes.

    Followed by removing ``/var/www/espocrm`` so the installer can
    start from a completely clean slate.

    :returns: (success, error_message).
    """
    teardown_cmd = f"docker compose -f {COMPOSE_FILE} down --volumes"
    log(f"$ {teardown_cmd}", "info")
    exit_code, output = run_remote(ssh, teardown_cmd, log)
    if exit_code != 0:
        return False, f"Teardown failed: {output[:200]}"

    rm_cmd = f"rm -rf {COMPOSE_DIR}"
    log(f"$ {rm_cmd}", "info")
    exit_code, output = run_remote(ssh, rm_cmd, log)
    if exit_code != 0:
        return False, f"Failed to remove install directory: {output[:200]}"

    return True, ""


def build_reinstall_config(
    config: InstanceDeployConfig,
    *,
    admin_username: str,
    admin_password: str,
    db_password: str,
) -> SelfHostedConfig:
    """Build a ``SelfHostedConfig`` for a fresh install during full reset.

    The persisted ``InstanceDeployConfig`` carries the SSH and server
    credentials that survive across operations (SSH host, db root
    password, domain, Let's Encrypt email). The user-facing admin
    credentials and the application-level DB password are supplied
    fresh by the caller — for a reset we never reuse the previous
    values.

    :param config: Persisted server-connection details.
    :param admin_username: New EspoCRM admin username.
    :param admin_password: New EspoCRM admin password (plaintext).
    :param db_password: New application-level DB password.
    :returns: SelfHostedConfig ready to pass to phase_install_espocrm.
    """
    return SelfHostedConfig(
        ssh_host=config.ssh_host,
        ssh_port=config.ssh_port,
        ssh_username=config.ssh_username,
        ssh_credential=config.ssh_credential,
        ssh_auth_type=config.ssh_auth_type,
        domain=config.domain,
        letsencrypt_email=config.letsencrypt_email,
        db_password=db_password,
        db_root_password=config.db_root_password,
        admin_username=admin_username,
        admin_password=admin_password,
        admin_email=config.admin_email or "",
    )
