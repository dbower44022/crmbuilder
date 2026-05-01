"""Tests for automation.core.deployment.recovery_ssh.

Covers admin credential reset SQL generation, teardown command order,
and the build_reinstall_config helper that constructs a fresh
SelfHostedConfig from the durable InstanceDeployConfig.

No real SSH — run_remote is mocked.
"""

from unittest.mock import MagicMock, patch

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.recovery_ssh import (
    build_reinstall_config,
    reset_admin_credentials,
    teardown,
)


def _make_config(**overrides) -> InstanceDeployConfig:
    defaults = {
        "instance_id": 1,
        "scenario": "self_hosted",
        "ssh_host": "1.2.3.4",
        "ssh_port": 22,
        "ssh_username": "root",
        "ssh_auth_type": "key",
        "ssh_credential": "/tmp/key",
        "domain": "crm.example.com",
        "letsencrypt_email": "ops@example.com",
        "db_root_password": "rootpass",
        "admin_email": "admin@example.com",
    }
    defaults.update(overrides)
    return InstanceDeployConfig(**defaults)


# ── Admin credential reset ────────────────────────────────────────────


def test_reset_admin_credentials_runs_update_inside_db_container():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.recovery_ssh.run_remote",
        return_value=(0, ""),
    ) as mock_run:
        ok, error = reset_admin_credentials(
            ssh, config, "admin", "newpass", log,
        )
    assert ok is True
    assert error == ""
    cmd = mock_run.call_args[0][1]
    assert "docker compose" in cmd
    assert "espocrm-db" in cmd
    assert "mariadb" in cmd
    assert "UPDATE user" in cmd
    assert "type = 'admin'" in cmd
    assert "MD5('newpass')" in cmd
    assert "rootpass" in cmd  # in actual command (not log)


def test_reset_admin_credentials_masks_secrets_in_log():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.recovery_ssh.run_remote",
        return_value=(0, ""),
    ):
        reset_admin_credentials(
            ssh, config, "admin", "secretpass", log,
        )
    log_messages = [call.args[0] for call in log.call_args_list]
    log_text = " ".join(log_messages)
    assert "rootpass" not in log_text
    assert "secretpass" not in log_text


def test_reset_admin_credentials_fails_on_sql_error():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.recovery_ssh.run_remote",
        return_value=(1, "ERROR: cannot connect to database"),
    ):
        ok, error = reset_admin_credentials(
            ssh, config, "admin", "newpass", log,
        )
    assert ok is False
    assert "Credential reset failed" in error


def test_reset_admin_credentials_masks_error_output():
    """Even error output must not leak the root password back to caller."""
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.recovery_ssh.run_remote",
        return_value=(1, "Authentication failed for user 'root' with password 'rootpass'"),
    ):
        ok, error = reset_admin_credentials(
            ssh, config, "admin", "newpass", log,
        )
    assert ok is False
    assert "rootpass" not in error


def test_reset_admin_credentials_rejects_empty_username():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    ok, error = reset_admin_credentials(ssh, config, "", "newpass", log)
    assert ok is False
    assert "required" in error.lower()


def test_reset_admin_credentials_rejects_empty_password():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    ok, error = reset_admin_credentials(ssh, config, "admin", "", log)
    assert ok is False
    assert "required" in error.lower()


# ── Teardown ──────────────────────────────────────────────────────────


def test_teardown_runs_compose_down_then_rm():
    ssh = MagicMock()
    log = MagicMock()
    with patch(
        "automation.core.deployment.recovery_ssh.run_remote",
        side_effect=[(0, ""), (0, "")],
    ) as mock_run:
        ok, error = teardown(ssh, log)
    assert ok is True
    assert error == ""
    assert mock_run.call_count == 2
    first_cmd = mock_run.call_args_list[0][0][1]
    second_cmd = mock_run.call_args_list[1][0][1]
    assert "docker compose" in first_cmd
    assert "down --volumes" in first_cmd
    assert second_cmd.startswith("rm -rf /var/www/espocrm")


def test_teardown_fails_on_compose_down_failure():
    ssh = MagicMock()
    log = MagicMock()
    with patch(
        "automation.core.deployment.recovery_ssh.run_remote",
        return_value=(1, "containers not found"),
    ):
        ok, error = teardown(ssh, log)
    assert ok is False
    assert "Teardown" in error


def test_teardown_fails_on_rm_failure():
    ssh = MagicMock()
    log = MagicMock()
    with patch(
        "automation.core.deployment.recovery_ssh.run_remote",
        side_effect=[(0, ""), (1, "permission denied")],
    ):
        ok, error = teardown(ssh, log)
    assert ok is False
    assert "install directory" in error


# ── build_reinstall_config ────────────────────────────────────────────


def test_build_reinstall_config_carries_durable_fields():
    config = _make_config()
    install = build_reinstall_config(
        config,
        admin_username="admin",
        admin_password="admin-secret",
        db_password="db-app-secret",
    )
    assert install.ssh_host == "1.2.3.4"
    assert install.ssh_port == 22
    assert install.ssh_username == "root"
    assert install.ssh_auth_type == "key"
    assert install.ssh_credential == "/tmp/key"
    assert install.domain == "crm.example.com"
    assert install.letsencrypt_email == "ops@example.com"
    assert install.db_root_password == "rootpass"
    assert install.admin_email == "admin@example.com"


def test_build_reinstall_config_uses_supplied_admin_creds():
    config = _make_config()
    install = build_reinstall_config(
        config,
        admin_username="newadmin",
        admin_password="newpass",
        db_password="newdb",
    )
    assert install.admin_username == "newadmin"
    assert install.admin_password == "newpass"
    assert install.db_password == "newdb"


def test_build_reinstall_config_handles_missing_admin_email():
    config = _make_config(admin_email=None)
    install = build_reinstall_config(
        config,
        admin_username="admin",
        admin_password="p",
        db_password="d",
    )
    assert install.admin_email == ""
