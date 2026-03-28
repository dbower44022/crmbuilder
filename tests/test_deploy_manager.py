"""Tests for the deploy manager module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from espo_impl.core.deploy_manager import (
    cert_days_remaining,
    check_dns,
    load_deploy_config,
    mask_credentials,
    save_deploy_config,
)
from espo_impl.core.models import DeployConfig


def _make_config(**overrides) -> DeployConfig:
    """Create a DeployConfig with sensible defaults."""
    defaults = {
        "droplet_ip": "165.232.150.42",
        "ssh_key_path": "/root/.ssh/id_ed25519",
        "ssh_user": "root",
        "base_domain": "mycompany.com",
        "subdomain": "crm",
        "letsencrypt_email": "admin@mycompany.com",
        "db_password": "secret_db_pass",
        "db_root_password": "secret_root_pass",
        "admin_username": "admin",
        "admin_password": "secret_admin_pass",
        "admin_email": "admin@mycompany.com",
    }
    defaults.update(overrides)
    return DeployConfig(**defaults)


# ── 9a: DeployConfig model ────────────────────────────────────────────


def test_full_domain_property():
    config = _make_config(subdomain="crm", base_domain="mycompany.com")
    assert config.full_domain == "crm.mycompany.com"


def test_full_domain_production():
    config = _make_config(subdomain="crm", base_domain="clevelandbusinessmentors.org")
    assert config.full_domain == "crm.clevelandbusinessmentors.org"


def test_full_domain_test_env():
    config = _make_config(subdomain="crm-test", base_domain="mycompany.com")
    assert config.full_domain == "crm-test.mycompany.com"


# ── 9b: Config file read/write ────────────────────────────────────────


def test_save_and_load_deploy_config(tmp_path):
    config = _make_config()
    save_deploy_config(tmp_path, "test_instance", config)
    loaded = load_deploy_config(tmp_path, "test_instance")
    assert loaded is not None
    assert loaded.droplet_ip == config.droplet_ip
    assert loaded.full_domain == config.full_domain
    assert loaded.db_password == config.db_password
    assert loaded.admin_email == config.admin_email


def test_load_deploy_config_missing_returns_none(tmp_path):
    result = load_deploy_config(tmp_path, "nonexistent")
    assert result is None


def test_save_deploy_config_creates_file(tmp_path):
    config = _make_config()
    save_deploy_config(tmp_path, "test_instance", config)
    path = tmp_path / "test_instance_deploy.json"
    assert path.exists()


def test_save_deploy_config_filename_uses_slug(tmp_path):
    config = _make_config()
    save_deploy_config(tmp_path, "cbm_production", config)
    assert (tmp_path / "cbm_production_deploy.json").exists()
    assert not (tmp_path / "test_instance_deploy.json").exists()


# ── 9c: DNS validation ────────────────────────────────────────────────


@patch("espo_impl.core.deploy_manager.dns.resolver.resolve")
def test_check_dns_match(mock_resolve):
    mock_rdata = MagicMock()
    mock_rdata.address = "165.232.150.42"
    mock_resolve.return_value = [mock_rdata]
    ok, msg = check_dns("crm.mycompany.com", "165.232.150.42")
    assert ok is True
    assert msg == ""


@patch("espo_impl.core.deploy_manager.dns.resolver.resolve")
def test_check_dns_mismatch(mock_resolve):
    mock_rdata = MagicMock()
    mock_rdata.address = "10.0.0.1"
    mock_resolve.return_value = [mock_rdata]
    ok, msg = check_dns("crm.mycompany.com", "165.232.150.42")
    assert ok is False
    assert "165.232.150.42" in msg
    assert "10.0.0.1" in msg


@patch("espo_impl.core.deploy_manager.dns.resolver.resolve")
def test_check_dns_no_result(mock_resolve):
    import dns.resolver
    mock_resolve.side_effect = dns.resolver.NXDOMAIN()
    ok, msg = check_dns("crm.mycompany.com", "165.232.150.42")
    assert ok is False
    assert msg != ""


@patch("espo_impl.core.deploy_manager.dns.resolver.resolve")
def test_check_dns_message_includes_domain(mock_resolve):
    import dns.resolver
    mock_resolve.side_effect = dns.resolver.NXDOMAIN()
    ok, msg = check_dns("crm.mycompany.com", "165.232.150.42")
    assert "crm.mycompany.com" in msg


@patch("espo_impl.core.deploy_manager.dns.resolver.resolve")
def test_check_dns_message_includes_ips(mock_resolve):
    mock_rdata = MagicMock()
    mock_rdata.address = "10.0.0.1"
    mock_resolve.return_value = [mock_rdata]
    ok, msg = check_dns("crm.mycompany.com", "165.232.150.42")
    assert "10.0.0.1" in msg
    assert "165.232.150.42" in msg


# ── 9d: Password masking ──────────────────────────────────────────────


def test_mask_credentials_replaces_db_password():
    config = _make_config(db_password="myDbPass123")
    cmd = "install --db-password=myDbPass123"
    safe = mask_credentials(cmd, config)
    assert "myDbPass123" not in safe
    assert "[db_password]" in safe


def test_mask_credentials_replaces_admin_password():
    config = _make_config(admin_password="adminSecret!")
    cmd = "install --admin-password=adminSecret!"
    safe = mask_credentials(cmd, config)
    assert "adminSecret!" not in safe
    assert "[admin_password]" in safe


def test_mask_credentials_replaces_root_password():
    config = _make_config(db_root_password="rootSecret!")
    cmd = "install --db-root-password=rootSecret!"
    safe = mask_credentials(cmd, config)
    assert "rootSecret!" not in safe
    assert "[db_root_password]" in safe


def test_mask_credentials_leaves_non_credential_text_unchanged():
    config = _make_config()
    cmd = "apt-get update && apt-get upgrade -y"
    safe = mask_credentials(cmd, config)
    assert safe == cmd


def test_mask_credentials_handles_empty_password():
    config = _make_config(db_password="", db_root_password="", admin_password="")
    cmd = "install --domain=crm.example.com"
    safe = mask_credentials(cmd, config)
    assert safe == cmd


# ── 9e: Certificate expiry helpers ────────────────────────────────────


def test_cert_days_remaining_future_date():
    future = (datetime.now(UTC) + timedelta(days=60)).strftime("%Y-%m-%d")
    result = cert_days_remaining(future)
    assert result is not None
    assert result >= 59  # allow for time-of-day rounding


def test_cert_days_remaining_past_date():
    past = (datetime.now(UTC) - timedelta(days=10)).strftime("%Y-%m-%d")
    result = cert_days_remaining(past)
    assert result is not None
    assert result < 0


def test_cert_days_remaining_none_input():
    assert cert_days_remaining(None) is None


def test_cert_days_remaining_correct_calculation():
    target = (datetime.now(UTC) + timedelta(days=30)).strftime("%Y-%m-%d")
    result = cert_days_remaining(target)
    assert result is not None
    assert 29 <= result <= 30
