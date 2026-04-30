"""Tests for the upgrade manager module."""

from unittest.mock import MagicMock, patch

import pytest

from espo_impl.core.models import DeployConfig
from espo_impl.core.upgrade_manager import (
    BACKUP_RETENTION,
    is_major_upgrade,
    is_upgrade_available,
    parse_version,
    phase1_pre_upgrade_checks,
    phase2_backup,
    phase3_run_upgrade,
    phase4_verify_upgrade,
    prune_old_backups,
)


def _make_config(**overrides) -> DeployConfig:
    defaults = {
        "droplet_ip": "10.0.0.1",
        "ssh_key_path": "/tmp/key",
        "ssh_user": "root",
        "base_domain": "example.com",
        "subdomain": "crm",
        "letsencrypt_email": "admin@example.com",
        "db_password": "dbpass",
        "db_root_password": "rootpass",
        "admin_username": "admin",
        "admin_password": "adminpass",
        "admin_email": "admin@example.com",
    }
    defaults.update(overrides)
    return DeployConfig(**defaults)


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


# ── Phase 1: Pre-upgrade checks ──────────────────────────────────────


def test_phase1_fails_when_compose_unavailable():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "espo_impl.core.upgrade_manager.run_remote",
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
        "espo_impl.core.upgrade_manager.run_remote",
        return_value=(0, "no services here"),
    ):
        ok, error = phase1_pre_upgrade_checks(ssh, config, log)
    assert ok is False
    assert "EspoCRM container" in error


def test_phase1_fails_when_version_unreadable():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    # First call: compose ps (success, espocrm in output)
    # Second call: get_current_version (fails)
    with patch(
        "espo_impl.core.upgrade_manager.run_remote",
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
        "espo_impl.core.upgrade_manager.run_remote",
        side_effect=[
            (0, "espocrm Up\n"),  # compose ps
            (0, "8.4.0\n"),        # version grep
            (0, "5000\n"),         # df free MB
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
        "espo_impl.core.upgrade_manager.run_remote",
        side_effect=[
            (0, "espocrm Up\n"),  # compose ps
            (0, "8.4.0\n"),        # version
            (0, "500\n"),          # only 500 MB free
        ],
    ):
        ok, error = phase1_pre_upgrade_checks(ssh, config, log)
    assert ok is False
    assert "Free disk space" in error or "free on /" in error


# ── Phase 2: Backup retention ─────────────────────────────────────────


def test_prune_old_backups_keeps_last_n():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    listing = "\n".join(
        f"/var/backups/espocrm/2026010{i}_000000/" for i in range(1, 8)
    )
    with patch(
        "espo_impl.core.upgrade_manager.run_remote",
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
        "espo_impl.core.upgrade_manager.run_remote",
        return_value=(0, listing),
    ):
        remaining = prune_old_backups(ssh, config, log)
    assert remaining == ["/var/backups/espocrm/20260101_000000"]


def test_phase2_backup_records_path():
    ssh = MagicMock()
    config = _make_config()
    log = MagicMock()
    with patch(
        "espo_impl.core.upgrade_manager.run_remote",
        side_effect=[
            (0, ""),  # mkdir
            (0, ""),  # mysqldump
            (0, ""),  # tar
            (0, ""),  # ls (prune scan, empty result triggers fallback)
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
        "espo_impl.core.upgrade_manager.run_remote",
        side_effect=[
            (0, ""),  # mkdir
            (1, "dump error"),  # mysqldump fails
        ],
    ):
        ok, error = phase2_backup(ssh, config, log)
    assert ok is False
    assert "Database backup" in error


# ── Phase 3: Run upgrade ──────────────────────────────────────────────


def test_phase3_succeeds_and_updates_version():
    ssh = MagicMock()
    config = _make_config(current_espocrm_version="8.4.0")
    log = MagicMock()
    with patch(
        "espo_impl.core.upgrade_manager.run_remote",
        side_effect=[
            (0, "Upgrade complete"),  # upgrade command
            (0, "Cache cleared"),      # clear-cache
            (0, "8.5.1\n"),            # get_current_version
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
        "espo_impl.core.upgrade_manager.run_remote",
        return_value=(1, "EspoCRM is up to date"),
    ):
        ok, error = phase3_run_upgrade(ssh, config, log)
    assert ok is False
    assert "no upgrade" in error.lower()


# ── Phase 4: Verification ─────────────────────────────────────────────


def test_phase4_all_checks_pass():
    ssh = MagicMock()
    config = _make_config(current_espocrm_version="8.5.1")
    log = MagicMock()
    with patch(
        "espo_impl.core.upgrade_manager.run_remote",
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
