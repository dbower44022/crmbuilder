"""Tests for the extension install SSH orchestration."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from automation.core.deployment.deploy_config_repo import InstanceDeployConfig
from automation.core.deployment.extension_ssh import (
    ExtensionManifest,
    InstallResult,
    _safe_filename,
    install_extension,
    parse_extension_manifest,
    phase_install,
    phase_pre_check,
    phase_verify,
)


# ── Helpers ────────────────────────────────────────────────────────────


def _make_zip(
    tmp_path: Path,
    name: str = "Test Extension",
    version: str = "1.0.0",
    *,
    omit_manifest: bool = False,
    bad_json: bool = False,
    leading_slash: bool = False,
) -> Path:
    """Build a minimal EspoCRM-style extension zip for tests."""
    path = tmp_path / "test-ext.zip"
    with zipfile.ZipFile(path, "w") as zf:
        if omit_manifest:
            zf.writestr("README.txt", "no manifest here")
            return path
        body = (
            "not json {"
            if bad_json
            else json.dumps({
                "name": name,
                "version": version,
                "acceptableVersions": ["8.4.0"],
                "author": "Test",
            })
        )
        entry = "/manifest.json" if leading_slash else "manifest.json"
        zf.writestr(entry, body)
    return path


def _make_config() -> InstanceDeployConfig:
    """A bare InstanceDeployConfig sufficient for the SSH phases under test."""
    return InstanceDeployConfig(
        instance_id=1,
        scenario="self_hosted",
        ssh_host="example.com",
        ssh_port=22,
        ssh_username="root",
        ssh_auth_type="password",
        ssh_credential="x",
        domain="crm.example.com",
        letsencrypt_email="a@b.com",
        db_root_password="dbroot",
    )


# ── parse_extension_manifest ──────────────────────────────────────────


class TestParseManifest:
    def test_basic(self, tmp_path):
        p = _make_zip(tmp_path)
        m = parse_extension_manifest(p)
        assert m.name == "Test Extension"
        assert m.version == "1.0.0"
        assert m.acceptable_versions == ["8.4.0"]

    def test_leading_slash_entry(self, tmp_path):
        """EspoCRM packs ship manifest.json as '/manifest.json'."""
        p = _make_zip(tmp_path, leading_slash=True)
        m = parse_extension_manifest(p)
        assert m.name == "Test Extension"

    def test_missing_manifest(self, tmp_path):
        p = _make_zip(tmp_path, omit_manifest=True)
        with pytest.raises(ValueError, match="no manifest.json"):
            parse_extension_manifest(p)

    def test_bad_json(self, tmp_path):
        p = _make_zip(tmp_path, bad_json=True)
        with pytest.raises(ValueError, match="not valid JSON"):
            parse_extension_manifest(p)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_extension_manifest(tmp_path / "nope.zip")

    def test_real_cbm_zips(self):
        """Smoke test against the actual CBM-purchased extension zips."""
        cbm = Path(
            "/home/doug/Dropbox/Projects/ClevelandBusinessMentors/"
            "ExtensionFiles"
        )
        if not cbm.exists():
            pytest.skip("CBM ExtensionFiles directory not present")

        ap = parse_extension_manifest(cbm / "advanced-pack-3.12.1.zip")
        assert ap.name == "Advanced Pack"
        assert ap.version == "3.12.1"

        gi = parse_extension_manifest(cbm / "google-integration-1.8.4.zip")
        assert gi.name == "Google Integration"
        assert gi.version == "1.8.4"


# ── _safe_filename ────────────────────────────────────────────────────


class TestSafeFilename:
    def test_normal(self):
        assert _safe_filename("advanced-pack-3.12.1.zip") == (
            "advanced-pack-3.12.1.zip"
        )

    def test_strips_shell_metacharacters(self):
        assert _safe_filename("evil`name`;rm.zip") == "evil_name_rm.zip"

    def test_strips_spaces(self):
        assert _safe_filename("My Extension.zip") == "My_Extension.zip"


# ── Phase functions with mocked SSH ───────────────────────────────────


def _fake_run_remote_factory(responses: dict[str, tuple[int, str]]):
    """Build a fake run_remote that returns canned output per command substring.

    The first matching substring wins. Unknown commands return (0, "").
    Records the actual command strings passed for assertion.
    """
    called: list[str] = []

    def fake(ssh, command, log=None, *, get_pty=False):
        called.append(command)
        for needle, response in responses.items():
            if needle in command:
                return response
        return (0, "")

    fake.called = called  # type: ignore[attr-defined]
    return fake


class TestPhasePreCheck:
    def test_happy_path(self):
        manifest = ExtensionManifest(name="X", version="1.0")
        config = _make_config()
        fake = _fake_run_remote_factory({
            "docker compose": (0, "espocrm   Up 5 minutes"),
        })
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            ok, err = phase_pre_check(
                MagicMock(), config, manifest, lambda m, l: None,
            )
        assert ok is True
        assert err == ""

    def test_container_not_running(self):
        manifest = ExtensionManifest(name="X", version="1.0")
        config = _make_config()
        fake = _fake_run_remote_factory({
            "docker compose": (0, "(nothing)"),
        })
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            ok, err = phase_pre_check(
                MagicMock(), config, manifest, lambda m, l: None,
            )
        assert ok is False
        assert "not running" in err

    def test_docker_compose_missing(self):
        manifest = ExtensionManifest(name="X", version="1.0")
        config = _make_config()
        fake = _fake_run_remote_factory({
            "docker compose": (1, "command not found"),
        })
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            ok, err = phase_pre_check(
                MagicMock(), config, manifest, lambda m, l: None,
            )
        assert ok is False
        assert "compose" in err.lower()


class TestPhaseInstall:
    def test_happy_path(self, tmp_path):
        zip_path = _make_zip(tmp_path)
        manifest = parse_extension_manifest(zip_path)
        config = _make_config()

        fake = _fake_run_remote_factory({
            "docker compose": (0, ""),
            "php command.php extension": (0, "Installed."),
            "php command.php clear-cache": (0, "Cache cleared."),
        })

        mock_sftp = MagicMock()
        mock_ssh = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp

        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            ok, err = phase_install(
                mock_ssh, config, manifest, zip_path, lambda m, l: None,
            )

        assert ok is True
        assert err == ""

        # SFTP put called once with the right local + remote path
        mock_sftp.put.assert_called_once()
        local_arg, remote_arg = mock_sftp.put.call_args[0]
        assert local_arg == str(zip_path)
        assert remote_arg.startswith("/tmp/") and remote_arg.endswith(".zip")

        # docker compose cp, extension install, clear-cache, and the two
        # cleanup commands ran
        joined = "\n".join(fake.called)
        assert "docker compose -f" in joined
        assert "cp /tmp/" in joined
        assert "php command.php extension --file=/tmp/" in joined
        assert "php command.php clear-cache" in joined
        assert "rm -f /tmp/" in joined

    def test_sftp_failure_aborts(self, tmp_path):
        zip_path = _make_zip(tmp_path)
        manifest = parse_extension_manifest(zip_path)
        config = _make_config()

        mock_sftp = MagicMock()
        mock_sftp.put.side_effect = OSError("disk full")
        mock_ssh = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp

        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
        ) as mock_run:
            ok, err = phase_install(
                mock_ssh, config, manifest, zip_path, lambda m, l: None,
            )
            mock_run.assert_not_called()

        assert ok is False
        assert "SFTP upload failed" in err

    def test_incompatible_extension_explained(self, tmp_path):
        zip_path = _make_zip(tmp_path)
        manifest = parse_extension_manifest(zip_path)
        config = _make_config()

        fake = _fake_run_remote_factory({
            "docker compose -f /var/www/espocrm/docker-compose.yml cp": (0, ""),
            "php command.php extension": (
                1,
                "Error: extension is not compatible with this EspoCRM version",
            ),
        })

        mock_ssh = MagicMock()
        mock_ssh.open_sftp.return_value = MagicMock()
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            ok, err = phase_install(
                mock_ssh, config, manifest, zip_path, lambda m, l: None,
            )

        assert ok is False
        assert "not compatible" in err

    def test_cleanup_runs_even_on_failure(self, tmp_path):
        zip_path = _make_zip(tmp_path)
        manifest = parse_extension_manifest(zip_path)
        config = _make_config()

        fake = _fake_run_remote_factory({
            "docker compose -f /var/www/espocrm/docker-compose.yml cp": (0, ""),
            "php command.php extension": (1, "boom"),
        })

        mock_ssh = MagicMock()
        mock_ssh.open_sftp.return_value = MagicMock()
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            ok, _ = phase_install(
                mock_ssh, config, manifest, zip_path, lambda m, l: None,
            )

        assert ok is False
        joined = "\n".join(fake.called)
        assert "rm -f /tmp/" in joined

    def test_missing_zip(self, tmp_path):
        manifest = ExtensionManifest(name="X", version="1.0")
        config = _make_config()
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
        ) as mock_run:
            ok, err = phase_install(
                MagicMock(), config, manifest,
                tmp_path / "nope.zip", lambda m, l: None,
            )
            mock_run.assert_not_called()
        assert ok is False
        assert "not found" in err.lower()


class TestPhaseVerify:
    def test_happy_path(self):
        config = _make_config()
        manifest = ExtensionManifest(name="X", version="1.0")
        fake = _fake_run_remote_factory({
            "curl -sI": (0, "HTTP/2 200"),
            "docker compose": (0, "espocrm   Up 5 minutes"),
        })
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            ok, err = phase_verify(
                MagicMock(), config, manifest, lambda m, l: None,
            )
        assert ok is True

    def test_https_not_200(self):
        config = _make_config()
        manifest = ExtensionManifest(name="X", version="1.0")
        fake = _fake_run_remote_factory({
            "curl -sI": (0, "HTTP/2 500"),
        })
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            ok, err = phase_verify(
                MagicMock(), config, manifest, lambda m, l: None,
            )
        assert ok is False
        assert "smoke check failed" in err


# ── Orchestrator branching ─────────────────────────────────────────────


class TestInstallExtension:
    def test_invalid_zip_returns_phase0(self, tmp_path):
        bad = _make_zip(tmp_path, omit_manifest=True)
        result = install_extension(
            MagicMock(), _make_config(), bad, lambda m, l: None,
        )
        assert result.success is False
        assert result.failed_phase == 0
        assert "no manifest.json" in result.error

    def test_skip_backup_omits_phase2(self, tmp_path):
        zip_path = _make_zip(tmp_path)
        config = _make_config()
        fake = _fake_run_remote_factory({
            "docker compose -f /var/www/espocrm/docker-compose.yml ps": (
                0, "espocrm   Up",
            ),
            "docker compose -f /var/www/espocrm/docker-compose.yml cp": (0, ""),
            "php command.php extension": (0, "ok"),
            "php command.php clear-cache": (0, ""),
            "curl -sI": (0, "HTTP/2 200"),
        })
        mock_ssh = MagicMock()
        mock_ssh.open_sftp.return_value = MagicMock()
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            with patch(
                "automation.core.deployment.extension_ssh.phase_backup",
            ) as backup:
                result = install_extension(
                    mock_ssh, config, zip_path, lambda m, l: None,
                    skip_backup=True,
                )
                backup.assert_not_called()

        assert result.success is True
        assert result.manifest is not None
        assert result.manifest.name == "Test Extension"

    def test_phase3_failure_returns_phase3(self, tmp_path):
        zip_path = _make_zip(tmp_path)
        config = _make_config()
        fake = _fake_run_remote_factory({
            "docker compose -f /var/www/espocrm/docker-compose.yml ps": (
                0, "espocrm   Up",
            ),
            "docker compose -f /var/www/espocrm/docker-compose.yml cp": (
                1, "permission denied",
            ),
        })
        mock_ssh = MagicMock()
        mock_ssh.open_sftp.return_value = MagicMock()
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            with patch(
                "automation.core.deployment.extension_ssh.phase_backup",
                return_value=(True, ""),
            ):
                result = install_extension(
                    mock_ssh, config, zip_path, lambda m, l: None,
                )

        assert result.success is False
        assert result.failed_phase == 3
        assert "docker compose cp" in result.error

    def test_phase1_failure_short_circuits(self, tmp_path):
        zip_path = _make_zip(tmp_path)
        config = _make_config()
        fake = _fake_run_remote_factory({
            "docker compose -f /var/www/espocrm/docker-compose.yml ps": (
                0, "(nothing)",
            ),
        })
        with patch(
            "automation.core.deployment.extension_ssh.run_remote",
            side_effect=fake,
        ):
            with patch(
                "automation.core.deployment.extension_ssh.phase_backup",
            ) as backup:
                result = install_extension(
                    MagicMock(), config, zip_path, lambda m, l: None,
                )
                backup.assert_not_called()

        assert result.success is False
        assert result.failed_phase == 1
