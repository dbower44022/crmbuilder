"""Tests for automation.core.deployment.upgrade_ssh.

Ports tests/test_upgrade_manager.py against the new module signatures
(InstanceDeployConfig, two-arg log callback). Uses unittest.mock to
patch run_remote — no real SSH.
"""

from unittest.mock import MagicMock, patch

import pytest

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.upgrade_ssh import (
    BACKUP_RETENTION,
    is_major_upgrade,
    is_upgrade_available,
    mask_secrets,
    parse_version,
    phase1_pre_upgrade_checks,
    phase2_backup,
    phase3_run_upgrade,
    phase4_verify_upgrade,
    prune_old_backups,
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
    }
    defaults.update(overrides)
    return InstanceDeployConfig(**defaults)


# ── Version parsing ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        ("8.4.0", (8, 4, 0)),
        ("v8.4.1", (8, 4, 1)),
        ("EspoCRM 7.5.12 (community)", (7, 5, 12)),
        ("8.4", None),
        ("", None),
        ("garbage", None),
    ],
)
def test_parse_version(value, expected):
    assert parse_version(value) == expected


def test_is_upgrade_available_true():
    assert is_upgrade_available("8.4.0", "8.5.1") is True


def test_is_upgrade_available_false_when_equal():
    assert is_upgrade_available("8.4.0", "8.4.0") is False


def test_is_upgrade_available_false_when_current_newer():
    assert is_upgrade_available("8.5.0", "8.4.0") is False


def test_is_upgrade_available_false_on_unparseable():
    assert is_upgrade_available(None, "8.4.0") is False
    assert is_upgrade_available("8.4.0", None) is False
    assert is_upgrade_available("", "") is False


def test_is_major_upgrade_detects_major_jump():
    assert is_major_upgrade("7.5.12", "8.0.0") is True


def test_is_major_upgrade_minor_only():
    assert is_major_upgrade("8.4.0", "8.5.0") is False


# ── Secret masking ───────────────────────────────────────────────────


def test_mask_secrets_replaces_values():
    cmd = "mariadb-dump -u root -p superpass espocrm"
    assert "superpass" not in mask_secrets(cmd, ["superpass"])


def test_mask_secrets_handles_empty_list():
    cmd = "echo hello"
    assert mask_secrets(cmd, []) == cmd


def test_mask_secrets_orders_longest_first():
    """A short secret that's a substring of a longer one must not corrupt
    the longer secret's masking."""
    masked = mask_secrets("AAA AAABBB", ["AAA", "AAABBB"])
    # The longer "AAABBB" should be replaced first, leaving the standalone
    # "AAA" to also be replaced.
    assert "AAABBB" not in masked


# ── Phase 1: Pre-upgrade checks ──────────────────────────────────────


def test_phase1_fails_when_compose_unavailable():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        return_value=(1, "compose: not found"),
    ):
        ok, error = phase1_pre_upgrade_checks(ssh, config, log)
    assert ok is False
    assert "Docker compose" in error


def test_phase1_fails_when_container_not_running():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        return_value=(0, "no services here"),
    ):
        ok, error = phase1_pre_upgrade_checks(ssh, config, log)
    assert ok is False
    assert "EspoCRM container" in error


def test_phase1_fails_when_version_unreadable():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        side_effect=[(0, "espocrm Up\n"), (1, "")],
    ):
        ok, error = phase1_pre_upgrade_checks(ssh, config, log)
    assert ok is False
    assert "current EspoCRM version" in error


def test_phase1_succeeds_and_records_version():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        side_effect=[
            (0, "espocrm Up\n"),
            (0, "8.4.0\n"),
            (0, "5000\n"),
        ],
    ):
        ok, error = phase1_pre_upgrade_checks(ssh, config, log)
    assert ok is True
    assert error == ""
    assert config.current_espocrm_version == "8.4.0"


def test_phase1_fails_on_low_disk_space():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        side_effect=[
            (0, "espocrm Up\n"),
            (0, "8.4.0\n"),
            (0, "500\n"),
        ],
    ):
        ok, error = phase1_pre_upgrade_checks(ssh, config, log)
    assert ok is False
    assert "free on /" in error or "Free disk space" in error


# ── Phase 2: Backup retention ────────────────────────────────────────


def test_prune_old_backups_keeps_last_n():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    listing = "\n".join(
        f"/var/backups/espocrm/2026010{i}_000000/" for i in range(1, 8)
    )
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        side_effect=[
            (0, listing),
            *[(0, "") for _ in range(7 - BACKUP_RETENTION)],
        ],
    ):
        remaining = prune_old_backups(ssh, config, log)
    assert len(remaining) == BACKUP_RETENTION
    assert remaining[-1].endswith("20260107_000000")


def test_prune_old_backups_no_op_when_under_limit():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    listing = "/var/backups/espocrm/20260101_000000/\n"
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        return_value=(0, listing),
    ):
        remaining = prune_old_backups(ssh, config, log)
    assert remaining == ["/var/backups/espocrm/20260101_000000"]


def test_phase2_backup_records_path():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        side_effect=[
            (0, ""),  # mkdir
            (0, ""),  # mariadb-dump
            (0, ""),  # tar
            (0, ""),  # ls (prune empty)
        ],
    ):
        ok, error = phase2_backup(ssh, config, log)
    assert ok is True
    assert error == ""
    assert len(config.last_backup_paths) >= 1
    assert config.last_backup_paths[-1].startswith(
        "/var/backups/espocrm/"
    )


def test_phase2_backup_fails_on_dump_failure():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        side_effect=[
            (0, ""),
            (1, "dump error"),
        ],
    ):
        ok, error = phase2_backup(ssh, config, log)
    assert ok is False
    assert "Database backup" in error


# ── Phase 3: Run upgrade ─────────────────────────────────────────────


def test_phase3_succeeds_and_updates_version():
    ssh = MagicMock()
    config = _make_config(current_espocrm_version="8.4.0")
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        side_effect=[
            (0, "Upgrade complete"),
            (0, "Cache cleared"),
            (0, "8.5.1\n"),
        ],
    ):
        ok, error = phase3_run_upgrade(ssh, config, log)
    assert ok is True
    assert error == ""
    assert config.current_espocrm_version == "8.5.1"
    assert config.last_upgrade_at is not None


def test_phase3_fails_on_no_upgrade_available():
    ssh = MagicMock()
    config = _make_config(current_espocrm_version="8.4.0")
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        return_value=(1, "EspoCRM is up to date"),
    ):
        ok, error = phase3_run_upgrade(ssh, config, log)
    assert ok is False
    assert "no upgrade" in error.lower()


# ── Phase 4: Verification ────────────────────────────────────────────


def test_phase4_all_checks_pass():
    ssh = MagicMock()
    config = _make_config(current_espocrm_version="8.5.1")
    log = MagicMock()
    with patch(
        "automation.core.deployment.upgrade_ssh.run_remote",
        side_effect=[
            (0, "espocrm Up"),
            (0, "HTTP/2 200"),
            (0, "<html>EspoCRM</html>"),
            (0, "'version' => '8.5.1'"),
        ],
    ):
        overall, results = phase4_verify_upgrade(ssh, config, log)
    assert overall is True
    assert all(r["passed"] for r in results)
    assert len(results) == 4
