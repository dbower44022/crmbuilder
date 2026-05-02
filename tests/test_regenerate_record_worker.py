"""Tests for the manual Deployment Record regeneration worker.

Patches the SSH layer and the generator so the worker's signal flow
can be exercised without a real Droplet or python-docx round trip.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import keyring
import pytest
from keyring.backend import KeyringBackend

from automation.core import secrets
from automation.core.deployment.deploy_config_repo import (
    InstanceDeployConfig,
    save_deploy_config,
)
from automation.core.deployment.record_generator import (
    AdministratorInputs,
    DeploymentRecordValues,
)
from automation.core.deployment.wizard_logic import create_wizard_instance
from automation.db.migrations import run_client_migrations
from automation.ui.deployment.deployment_logic import InstanceDetail

pytestmark = pytest.mark.skipif(
    os.environ.get("DISPLAY", "") == ""
    and os.environ.get("QT_QPA_PLATFORM", "") != "offscreen",
    reason="Worker uses Qt signals; needs offscreen Qt",
)


@pytest.fixture(scope="module", autouse=True)
def _qapplication():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


class _MemoryBackend(KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        self._store: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self._store[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self._store.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        if (service, username) not in self._store:
            from keyring.errors import PasswordDeleteError
            raise PasswordDeleteError(username)
        del self._store[(service, username)]


@pytest.fixture(autouse=True)
def _memory_keyring(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(secrets.DISABLE_ENV_VAR, raising=False)
    backend = _MemoryBackend()
    original = keyring.get_keyring()
    keyring.set_keyring(backend)
    try:
        yield backend
    finally:
        keyring.set_keyring(original)


@pytest.fixture()
def db_path(tmp_path: Path) -> str:
    path = tmp_path / "client.db"
    conn = run_client_migrations(str(path))
    conn.close()
    return str(path)


def _make_setup(db_path: str) -> tuple[InstanceDetail, InstanceDeployConfig]:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        instance_id = create_wizard_instance(
            conn, name="CBM Test", code="CBMTEST", environment="test",
        )
        cfg = InstanceDeployConfig(
            instance_id=instance_id,
            scenario="self_hosted",
            ssh_host="1.2.3.4",
            ssh_port=22,
            ssh_username="root",
            ssh_auth_type="password",
            ssh_credential="ssh-secret",
            domain="crm-test.example.com",
            letsencrypt_email="ops@example.com",
            db_root_password="db-root-secret",
            admin_email="admin@example.com",
        )
        cfg = save_deploy_config(conn, cfg)
    finally:
        conn.close()

    detail = InstanceDetail(
        id=cfg.instance_id,
        name="CBM Test",
        code="CBMTEST",
        environment="test",
        url="https://crm-test.example.com/",
        username="admin",
        password="adminpw",
        description=None,
        is_default=False,
        created_at="2026-04-01T00:00:00+00:00",
        updated_at="2026-04-01T00:00:00+00:00",
    )
    return detail, cfg


def _make_admin_inputs() -> AdministratorInputs:
    return AdministratorInputs(
        domain_registrar="Porkbun",
        dns_provider="Porkbun",
        primary_domain="example.com",
        instance_subdomain="crm-test",
        droplet_id="123456789",
        backups_enabled=True,
        proton_pass_admin_entry="CBMTEST-ESPOCRM-Test Instance Admin",
        proton_pass_db_root_entry="CBMTEST-ESPOCRM-Test DB Root",
        proton_pass_hosting_entry="CBMTEST-ESPOCRM-Test DigitalOcean Account",
    )


class _FakeSSH:
    def close(self) -> None:
        pass


def _make_values_stub() -> DeploymentRecordValues:
    """Build a minimum-viable values bag for tests."""
    return DeploymentRecordValues(
        document_version="1.0",
        document_last_updated="01-01-26 00:00",
        document_status="Active",
        client_name="CBM",
        instance_name="CBM Test",
        instance_code="CBMTEST",
        environment="test",
        application_url="https://crm-test.example.com/",
        admin_username="admin",
        instance_created_at_utc="2026-04-01T00:00:00+00:00",
        hosting_provider="DigitalOcean",
        droplet_id="123456789",
        droplet_detail_url="https://example.com/droplets/123",
        droplet_console_url="https://example.com/droplets/123/console",
        region="NYC3",
        hostname="cbm-test-NYC3",
        public_ipv4="1.2.3.4",
        droplet_size_summary="2 vCPU / 4GiB / 80GB",
        os_release="Ubuntu 22.04",
        kernel="5.15.0",
        cpu_count=2,
        memory_summary="4Gi",
        disk_summary="80GB on /dev/vda1",
        swap_summary="2GB",
        ufw_summary="active; allows 22 / 80 / 443",
        backups_enabled=True,
        primary_domain="example.com",
        domain_registrar="Porkbun",
        dns_provider="Porkbun",
        instance_subdomain="crm-test",
        tls_issuer="Let's Encrypt",
        tls_subject="crm-test.example.com",
        tls_issued_utc="2026-04-01 00:00:00 UTC",
        tls_expires_utc="2026-07-01 00:00:00 UTC",
        tls_sha256_fingerprint="AA:BB",
        espocrm_version="9.2.0",
        espocrm_install_completed_utc="2026-04-01 00:00:00",
        espocrm_install_path="/var/www/espocrm",
        mariadb_version="10.11",
        nginx_version="1.27",
        docker_version="27.0",
        docker_compose_version="v2.30",
        ssh_authorized_user="root",
        ssh_key_algorithm="ED25519",
        ssh_key_comment="doug@laptop",
        ssh_key_fingerprint="SHA256:abc",
        proton_pass_admin_entry="CBMTEST-ESPOCRM-Test Instance Admin",
        proton_pass_db_root_entry="CBMTEST-ESPOCRM-Test DB Root",
        proton_pass_hosting_entry="CBMTEST-ESPOCRM-Test DigitalOcean Account",
        deployment_history=[],
        open_items=[],
        revision_history=[{"version": "1.0", "date": "01-01-26", "notes": "x"}],
        change_log=[{"version": "1.0", "date": "01-01-26", "changes": "x"}],
    )


def _collect_signals(worker) -> dict[str, list[Any]]:
    """Collect all log/completed/failed signal payloads synchronously."""
    captured: dict[str, list[Any]] = {
        "log": [], "completed": [], "failed": [],
    }
    worker.log_line.connect(
        lambda msg, lvl: captured["log"].append((msg, lvl))
    )
    worker.completed.connect(lambda p: captured["completed"].append(p))
    worker.failed.connect(lambda e: captured["failed"].append(e))
    return captured


def test_worker_emits_completed_on_success(
    db_path, monkeypatch, tmp_path,
):
    from automation.ui.deployment import regenerate_record_worker as mod

    detail, cfg = _make_setup(db_path)

    monkeypatch.setattr(mod, "connect_ssh", lambda _config: _FakeSSH())
    monkeypatch.setattr(
        mod, "inspect_server_for_record_values",
        lambda *_args, **_kwargs: _make_values_stub(),
    )

    written: list[Path] = []

    def _fake_generate(values, output_path):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_bytes(b"PK\x03\x04 fake docx")
        written.append(Path(output_path))
        return output_path

    monkeypatch.setattr(mod, "generate_deployment_record", _fake_generate)

    output_path = tmp_path / "out" / "CBMTEST-Record.docx"
    worker = mod.RegenerateRecordWorker(
        instance=detail,
        deploy_config=cfg,
        administrator_inputs=_make_admin_inputs(),
        output_path=output_path,
        db_path=db_path,
    )
    captured = _collect_signals(worker)

    worker.run()

    assert captured["completed"] == [str(output_path)]
    assert captured["failed"] == []
    assert written == [output_path]


def test_worker_emits_failed_on_inspection_error(
    db_path, monkeypatch, tmp_path,
):
    from automation.ui.deployment import regenerate_record_worker as mod

    detail, cfg = _make_setup(db_path)
    monkeypatch.setattr(mod, "connect_ssh", lambda _config: _FakeSSH())

    def _boom(*_args, **_kwargs):
        raise RuntimeError("server unreachable")

    monkeypatch.setattr(mod, "inspect_server_for_record_values", _boom)
    monkeypatch.setattr(
        mod, "generate_deployment_record",
        lambda *_a, **_k: pytest.fail("generator should not be called"),
    )

    worker = mod.RegenerateRecordWorker(
        instance=detail,
        deploy_config=cfg,
        administrator_inputs=_make_admin_inputs(),
        output_path=tmp_path / "out.docx",
        db_path=db_path,
    )
    captured = _collect_signals(worker)

    worker.run()

    assert captured["completed"] == []
    assert captured["failed"] == ["server unreachable"]


def test_worker_emits_failed_on_generation_error(
    db_path, monkeypatch, tmp_path,
):
    from automation.ui.deployment import regenerate_record_worker as mod

    detail, cfg = _make_setup(db_path)
    monkeypatch.setattr(mod, "connect_ssh", lambda _config: _FakeSSH())
    monkeypatch.setattr(
        mod, "inspect_server_for_record_values",
        lambda *_a, **_k: _make_values_stub(),
    )

    def _explode(_values, _output):
        raise OSError("disk full")

    monkeypatch.setattr(mod, "generate_deployment_record", _explode)

    worker = mod.RegenerateRecordWorker(
        instance=detail,
        deploy_config=cfg,
        administrator_inputs=_make_admin_inputs(),
        output_path=tmp_path / "out.docx",
        db_path=db_path,
    )
    captured = _collect_signals(worker)

    worker.run()

    assert captured["completed"] == []
    assert captured["failed"] == ["disk full"]


def test_worker_persists_changed_administrator_inputs(
    db_path, monkeypatch, tmp_path,
):
    """Updated administrator inputs are written back to InstanceDeployConfig."""
    from automation.core.deployment.deploy_config_repo import (
        load_deploy_config,
    )
    from automation.ui.deployment import regenerate_record_worker as mod

    detail, cfg = _make_setup(db_path)
    monkeypatch.setattr(mod, "connect_ssh", lambda _config: _FakeSSH())
    monkeypatch.setattr(
        mod, "inspect_server_for_record_values",
        lambda *_a, **_k: _make_values_stub(),
    )
    monkeypatch.setattr(
        mod, "generate_deployment_record",
        lambda v, p: Path(p).write_bytes(b"x") or p,
    )

    inputs = _make_admin_inputs()
    inputs.domain_registrar = "Cloudflare"
    inputs.droplet_id = "999999"

    worker = mod.RegenerateRecordWorker(
        instance=detail,
        deploy_config=cfg,
        administrator_inputs=inputs,
        output_path=tmp_path / "out.docx",
        db_path=db_path,
    )

    worker.run()

    conn = sqlite3.connect(db_path)
    try:
        reloaded = load_deploy_config(conn, detail.id)
    finally:
        conn.close()
    assert reloaded is not None
    assert reloaded.domain_registrar == "Cloudflare"
    assert reloaded.droplet_id == "999999"
