"""Deploy wizard + progress dialog tests — PI-419 (REQ-522).

The wizard is driven page by page against a real in-process API with the
provider catalogs faked at the router; Next explains what is missing instead
of being disabled; Deploy queues a run and emits its identifier. The progress
dialog renders snapshots (queued → running → terminal), only appends new log
lines, shows Retry on failure, and emits the registered instance.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import deploy_runs
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.api.routers import provider_credentials as pc_router
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.deploy_progress_dialog import (
    DeployProgressDialog,
    describe_run,
    phase_index,
)
from crmbuilder_v2.ui.dialogs.deploy_wizard_dialog import (
    PAGE_ACCOUNTS,
    PAGE_DOMAIN,
    PAGE_PROVIDERS,
    PAGE_REVIEW,
    PAGE_SERVER,
    DeployWizardDialog,
)
from crmbuilder_v2.ui.panels.instances import InstancesPanel
from fastapi.testclient import TestClient
from PySide6.QtCore import Qt


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def ui_client(v2_env, monkeypatch) -> StorageClient:
    class FakeDO:
        def __init__(self, token, **_):
            pass

        def list_regions(self):
            return [{"slug": "nyc3", "name": "New York 3"}, {"slug": "sfo3", "name": "San Francisco 3"}]

        def list_sizes(self):
            return [
                {"slug": "s-2vcpu-4gb", "vcpus": 2, "memory": 4096, "price_monthly": 24.0, "regions": ["nyc3", "sfo3"]},
                {"slug": "s-1vcpu-1gb", "vcpus": 1, "memory": 1024, "price_monthly": 6.0, "regions": ["sfo3"]},
            ]

        def list_images(self):
            return [{"slug": "ubuntu-24-04-x64", "name": "Ubuntu 24.04 LTS"}]

        def list_ssh_keys(self):
            return [{"id": 11, "name": "laptop", "fingerprint": "aa:bb"}]

    class FakeCF:
        def __init__(self, token, **_):
            pass

        def list_zones(self):
            return [{"id": "z1", "name": "example.org"}]

    monkeypatch.setattr(pc_router, "DigitalOceanClient", FakeDO)
    monkeypatch.setattr(pc_router, "CloudflareClient", FakeCF)
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def test_wizard_blocks_until_credentials_then_queues_a_run(qtbot, ui_client):
    wizard = DeployWizardDialog(ui_client)
    qtbot.addWidget(wizard)
    qtbot.waitUntil(lambda: wizard._do_status.text() == "Not set", timeout=5000)
    assert wizard.page == PAGE_PROVIDERS
    wizard._next_btn.click()
    assert wizard.page == PAGE_PROVIDERS  # never disabled — explains instead
    assert "DigitalOcean and Cloudflare" in wizard._notice.text()

    ui_client.put_provider_credential("digitalocean", "do")
    ui_client.put_provider_credential("cloudflare", "cf")
    wizard._load_providers()
    qtbot.waitUntil(lambda: wizard.region.count() == 2 and wizard.zone.count() == 1, timeout=5000)
    wizard._next_btn.click()
    assert wizard.page == PAGE_SERVER

    wizard._next_btn.click()
    assert wizard.page == PAGE_SERVER and "name" in wizard._notice.text()
    wizard.instance_name.setText("Chapter CRM")
    wizard.region.setCurrentIndex(0)  # nyc3 → only the 2vcpu size applies
    assert [wizard.size.itemData(i) for i in range(wizard.size.count())] == ["s-2vcpu-4gb"]
    wizard.region.setCurrentIndex(1)
    assert wizard.size.count() == 2
    wizard.region.setCurrentIndex(0)
    wizard.ssh_keys.item(0).setCheckState(Qt.CheckState.Checked)
    wizard._next_btn.click()
    assert wizard.page == PAGE_DOMAIN

    wizard.subdomain.setText("CRM")
    assert wizard.fqdn.text() == "crm.example.org"
    wizard._next_btn.click()
    assert "Let's Encrypt" in wizard._notice.text()
    wizard.letsencrypt_email.setText("ops@example.org")
    wizard._next_btn.click()
    assert wizard.page == PAGE_ACCOUNTS

    wizard.admin_email.setText("admin@example.org")
    wizard._next_btn.click()
    assert "password" in wizard._notice.text()
    wizard.findChild(type(wizard._next_btn), "wizard_generate_password").click()
    assert len(wizard.admin_password.text()) >= 16
    wizard._next_btn.click()
    assert wizard.page == PAGE_REVIEW
    assert wizard._next_btn.text() == "Deploy"
    review = wizard.review.toPlainText()
    assert "https://crm.example.org" in review and "s-2vcpu-4gb in nyc3" in review
    body = wizard.build_body()
    assert body["ssh_key_ids"] == [11] and "db_password" not in body

    queued: list[str] = []
    wizard.run_queued.connect(queued.append)
    wizard._next_btn.click()
    qtbot.waitUntil(lambda: bool(queued), timeout=5000)
    assert queued == ["DEP-001"]
    run = ui_client.get_deploy_run("DEP-001")
    assert run["deploy_run_status"] == "queued"
    assert run["deploy_run_spec"]["domain"] == "crm.example.org"


def test_wizard_surfaces_server_rejection_inline(qtbot, ui_client):
    ui_client.put_provider_credential("digitalocean", "do")
    ui_client.put_provider_credential("cloudflare", "cf")
    wizard = DeployWizardDialog(ui_client)
    qtbot.addWidget(wizard)
    qtbot.waitUntil(lambda: wizard.zone.count() == 1 and wizard.region.count() == 2, timeout=5000)
    wizard.instance_name.setText("x")
    wizard.subdomain.setText("api")
    wizard.zone.clear()
    wizard.zone.addItem("crmbuilder.ai", "zprod")
    wizard.letsencrypt_email.setText("a@b.co")
    wizard.admin_email.setText("a@b.co")
    wizard.admin_password.setText("longenoughpassword")
    wizard._show_page(PAGE_REVIEW)
    wizard._next_btn.click()
    qtbot.waitUntil(lambda: "Not queued" in wizard._notice.text(), timeout=5000)
    assert "production host" in wizard._notice.text()
    assert wizard.page == PAGE_REVIEW


def _snapshot(status, *, phases_done=(), log=(), log_length=None, instance=None, phase=None, state=None):
    st = {"phases": {p: {"status": "done"} for p in phases_done}}
    st.update(state or {})
    return {
        "deploy_run_identifier": "DEP-001",
        "deploy_run_status": status,
        "deploy_run_phase": phase,
        "deploy_run_state": st,
        "deploy_run_log": [["t", lvl, msg] for lvl, msg in log],
        "log_length": log_length if log_length is not None else len(log),
        "instance_identifier": instance,
    }


def test_progress_dialog_renders_snapshots_and_emits_instance(qtbot, ui_client):
    dialog = DeployProgressDialog(ui_client, "DEP-001", poll_ms=60_000)
    qtbot.addWidget(dialog)
    dialog._timer.stop()
    # The constructor's first poll finds no such run (404) — let it settle so no
    # worker is in flight while we feed snapshots directly.
    qtbot.waitUntil(lambda: "✗" in dialog._log.toPlainText(), timeout=5000)
    dialog._log.clear()
    created: list[str] = []
    dialog.instance_created.connect(created.append)

    dialog.apply(_snapshot("queued"))
    assert "Queued" in dialog._status.text()
    assert not dialog._cancel_btn.isHidden()
    dialog.apply(_snapshot("running", phases_done=("validate", "create_droplet"), phase="wait_droplet",
                           log=(("info", "one"), ("success", "two")), log_length=2))
    assert dialog._progress.value() == 2
    assert "Waiting for server" in dialog._status.text()
    assert dialog._log_seen == 2
    assert "one" in dialog._log.toPlainText() and "two" in dialog._log.toPlainText()
    # A later poll only carries the new lines (log_after); nothing is repeated.
    dialog.apply(_snapshot("running", phases_done=("validate", "create_droplet", "wait_droplet"),
                           phase="create_dns", log=(("info", "three"),), log_length=3))
    assert dialog._log.toPlainText().count("one") == 1 and "three" in dialog._log.toPlainText()

    dialog.apply(_snapshot("succeeded", phases_done=("validate",), instance="INST-007"))
    assert created == ["INST-007"]
    assert not dialog._timer.isActive()
    assert dialog._retry_btn.isHidden()


def test_progress_dialog_failed_shows_kept_server_and_retry(qtbot, ui_client):
    with session_scope() as s:
        deploy_runs.create_deploy_run(s, spec={"domain": "crm.example.org"})
        deploy_runs.claim_next_run(s, worker_id="w")
        deploy_runs.set_phase(s, "DEP-001", "create_droplet", state={"droplet_id": "4242", "droplet_ip": "203.0.113.7"}, phase_status="done")
        deploy_runs.set_phase(s, "DEP-001", "create_dns", phase_status="failed", error="403")
        deploy_runs.finish(s, "DEP-001", status="failed", error="create_dns: 403")
    dialog = DeployProgressDialog(ui_client, "DEP-001", poll_ms=60_000)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.last_run.get("deploy_run_status") == "failed", timeout=5000)
    assert "Server 4242 (203.0.113.7) still exists" in dialog._status.text()
    assert not dialog._retry_btn.isHidden()
    dialog._retry_btn.click()
    qtbot.waitUntil(lambda: dialog.last_run.get("deploy_run_status") == "queued", timeout=5000)
    assert dialog._timer.isActive()


def test_describe_and_phase_index_helpers():
    assert describe_run({"deploy_run_status": "queued"}).startswith("Queued")
    assert "Installing CRM" in describe_run({"deploy_run_status": "running", "deploy_run_phase": "install_espocrm"})
    assert phase_index({"deploy_run_state": {"phases": {"validate": {"status": "done"}, "create_droplet": {"status": "failed"}}}}) == 1


def test_instances_panel_has_deploy_button(qtbot, ui_client):
    panel = InstancesPanel(ui_client)
    qtbot.addWidget(panel)
    assert panel.findChild(type(panel._deploy_button), "deploy_new_instance_button") is not None
