"""Deploy wizard + progress dialog tests — PI-419 (REQ-522), redesigned by
PI-571 (REQ-648, REQ-650, REQ-652).

The wizard is driven page by page against a real in-process API with the
provider catalogs and the DNS lookup faked; Next explains what is missing
instead of being disabled; the address is looked up before the DNS choice,
which offers Cloudflare only when CRMBuilder can edit the zone the internet
uses; Deploy creates the deployment record (PI-580) and then queues a run
against it, emitting both identifiers. The progress dialog shows every step
in words, a message when something needs action, Try again with a corrected
address, and the handover sheet.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import deploy_runs
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.api.routers import provider_credentials as pc_router
from crmbuilder_v2.deploy import dns_check
from crmbuilder_v2.segments.client_management.repositories import (
    client as client_repo,
)
from crmbuilder_v2.segments.operate.ui.handover import render_handover_html
from crmbuilder_v2.segments.operate.ui.panels.deployments import DeploymentsPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.deploy_progress_dialog import (
    DeployProgressDialog,
    describe_run,
    phase_index,
)
from crmbuilder_v2.ui.dialogs.deploy_wizard_dialog import (
    PAGE_ACCOUNTS,
    PAGE_ADDRESS,
    PAGE_DNS,
    PAGE_REVIEW,
    PAGE_SERVER,
    PAGE_START,
    DeployWizardDialog,
    describe_size,
)
from fastapi.testclient import TestClient
from PySide6.QtCore import Qt

from tests.crmbuilder_v2.deploy.fakes import FakeDnsLookup


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

    class Lookups:
        """example.org is served by Cloudflare; bbmentors.org by GoDaddy."""

        def __init__(self):
            self.cf = FakeDnsLookup(zone="example.org")
            self.gd = FakeDnsLookup(zone="bbmentors.org", name_servers=("ns51.domaincontrol.com",),
                                    records={("old.bbmentors.org", "A"): ["198.51.100.9"]})

        def _pick(self, name):
            return self.gd if name.endswith("bbmentors.org") else self.cf

        def zone_and_name_servers(self, domain):
            return self._pick(domain).zone_and_name_servers(domain)

        def authoritative(self, ns, name, rdtype):
            return self._pick(name).authoritative(ns, name, rdtype)

        def public(self, name, rdtype="A"):
            return self._pick(name).public(name, rdtype)

        def negative_ttl(self, ns, zone):
            return 300

    monkeypatch.setattr(dns_check, "PublicDnsLookup", Lookups)
    # PI-580: the wizard creates a deployment, so ENG-001 must be an application
    # defined by a client; CLI-002 may not deploy the private application.
    with session_scope() as s:
        client_repo.create_client(s, name="Cleveland Business Mentors")
        client_repo.create_client(s, name="Rochester Business Mentors")
        client_repo.set_engagement_clients(
            s, "ENG-001", clients=["CLI-001"], primary="CLI-001"
        )
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _clients_loaded(qtbot, wizard):
    qtbot.waitUntil(lambda: wizard.deployment_client.currentData() == "CLI-001", timeout=5000)


def _to_address_page(qtbot, wizard):
    qtbot.waitUntil(lambda: wizard.region.count() == 2, timeout=5000)
    wizard._next_btn.click()
    assert wizard.page == PAGE_ADDRESS


def _through_server_and_accounts(qtbot, wizard):
    assert wizard.page == PAGE_SERVER
    wizard._next_btn.click()
    assert wizard.page == PAGE_SERVER and "name" in wizard._notice.text()
    wizard.instance_name.setText("Chapter CRM")
    wizard._next_btn.click()
    assert wizard.page == PAGE_ACCOUNTS
    wizard.admin_email.setText("admin@example.org")
    wizard._next_btn.click()
    assert "password" in wizard._notice.text()
    wizard.findChild(type(wizard._next_btn), "wizard_generate_password").click()
    assert len(wizard.admin_password.text()) >= 16
    wizard._next_btn.click()
    assert wizard.page == PAGE_REVIEW and wizard._next_btn.text() == "Deploy"


def test_wizard_needs_only_digitalocean_then_queues_a_cloudflare_run(qtbot, ui_client):
    wizard = DeployWizardDialog(ui_client)
    qtbot.addWidget(wizard)
    qtbot.waitUntil(lambda: wizard._do_status.text() == "Not set", timeout=5000)
    assert wizard.page == PAGE_START
    wizard._next_btn.click()
    assert wizard.page == PAGE_START  # never disabled — explains instead
    assert "DigitalOcean" in wizard._notice.text() and "Cloudflare" not in wizard._notice.text()

    ui_client.put_provider_credential("digitalocean", "do")
    ui_client.put_provider_credential("cloudflare", "cf")
    wizard._load_providers()
    qtbot.waitUntil(lambda: wizard.region.count() == 2 and bool(wizard._zones), timeout=5000)
    # The application's defining client is pre-selected (PI-580).
    _clients_loaded(qtbot, wizard)
    assert wizard.deployment_client.currentText() == "Cleveland Business Mentors"
    assert wizard.deployment_purpose.currentData() == "client_own"
    wizard._next_btn.click()
    assert wizard.page == PAGE_ADDRESS

    wizard._next_btn.click()
    assert "full web address" in wizard._notice.text()
    wizard.full_address.setText("CRM.example.org")
    wizard._next_btn.click()  # looks the address up, then moves on by itself
    qtbot.waitUntil(lambda: wizard.page == PAGE_DNS, timeout=5000)
    assert "hosted by <b>Cloudflare</b>" in wizard.address_result.text()
    assert wizard.dns_cloudflare.isEnabled() and wizard.dns_cloudflare.isChecked()
    assert "Available" in wizard._cloudflare_note.text()
    wizard._next_btn.click()

    # Plain-language sizes, the recommended one pre-selected, one supported image.
    assert wizard.size.currentData() == "s-2vcpu-4gb"
    assert wizard.size.currentText() == "2 processors, 4 GB memory — $24 a month  (recommended)"
    assert wizard.image.currentData() == "ubuntu-24-04-x64"
    wizard.region.setCurrentIndex(wizard.region.findData("sfo3"))
    wizard.all_sizes.setChecked(True)
    assert wizard.size.count() == 2
    wizard.region.setCurrentIndex(wizard.region.findData("nyc3"))
    assert [wizard.size.itemData(i) for i in range(wizard.size.count())] == ["s-2vcpu-4gb"]
    wizard.ssh_keys.item(0).setCheckState(Qt.CheckState.Checked)
    _through_server_and_accounts(qtbot, wizard)

    review = wizard.review.toPlainText()
    assert "https://crm.example.org" in review and "CRMBuilder creates the record in Cloudflare" in review
    assert "Cleveland Business Mentors" in review and "Client's own" in review
    assert "instance" not in review.lower()
    body = wizard.build_body()
    assert body["dns_mode"] == "cloudflare"
    assert (body["zone_id"], body["zone_name"], body["subdomain"]) == ("z1", "example.org", "crm")
    assert body["ssh_key_ids"] == [11] and "db_password" not in body
    assert body["letsencrypt_email"] == "admin@example.org"  # defaults to the administrator's

    queued: list[str] = []
    created: list[str] = []
    wizard.run_queued.connect(queued.append)
    wizard.deployment_created.connect(created.append)
    wizard._next_btn.click()
    qtbot.waitUntil(lambda: bool(queued), timeout=5000)
    # Deploy created the deployment first, then queued the run against it.
    assert created == ["DPL-001"]
    run = ui_client.get_deploy_run(queued[0])
    assert run["deploy_run_status"] == "queued"
    assert run["deploy_run_spec"]["domain"] == "crm.example.org"
    assert run["deployment_identifier"] == "DPL-001"
    deployment = ui_client.get_deployment("DPL-001")
    assert deployment["deployment_client"] == "CLI-001"
    assert deployment["deployment_purpose"] == "client_own"
    assert deployment["deployment_name"] == "Chapter CRM"
    assert deployment["deployment_hosting_provider"] == "digitalocean"
    assert deployment["deployment_instance_identifier"] is None  # the run registers it


def test_wizard_offers_only_manual_dns_when_another_host_serves_the_domain(qtbot, ui_client):
    ui_client.put_provider_credential("digitalocean", "do")
    ui_client.put_provider_credential("cloudflare", "cf")
    wizard = DeployWizardDialog(ui_client)
    qtbot.addWidget(wizard)
    _to_address_page(qtbot, wizard)
    wizard.full_address.setText("old.bbmentors.org")
    wizard._next_btn.click()
    qtbot.waitUntil(lambda: wizard.page == PAGE_DNS, timeout=5000)
    result = wizard.address_result.text()
    assert "hosted by <b>GoDaddy</b>" in result
    assert "already in use" in result and "198.51.100.9" in result
    assert not wizard.dns_cloudflare.isEnabled() and wizard.dns_manual.isChecked()
    assert "hosted by GoDaddy, not Cloudflare" in wizard._cloudflare_note.text()
    wizard._next_btn.click()
    _through_server_and_accounts(qtbot, wizard)
    body = wizard.build_body()
    assert body["dns_mode"] == "manual" and body["domain"] == "old.bbmentors.org"
    assert "zone_id" not in body


def test_wizard_keeps_the_operators_dns_choice(qtbot, ui_client):
    ui_client.put_provider_credential("digitalocean", "do")
    ui_client.put_provider_credential("cloudflare", "cf")
    wizard = DeployWizardDialog(ui_client)
    qtbot.addWidget(wizard)
    qtbot.waitUntil(lambda: bool(wizard._zones), timeout=5000)
    _to_address_page(qtbot, wizard)
    wizard.full_address.setText("crm.example.org")
    wizard._next_btn.click()
    qtbot.waitUntil(lambda: wizard.page == PAGE_DNS, timeout=5000)
    wizard.dns_manual.click()
    wizard._back_btn.click()
    wizard._next_btn.click()
    assert wizard.page == PAGE_DNS and wizard.dns_manual.isChecked()


def test_wizard_help_panel_follows_the_field_in_use(qtbot, ui_client):
    ui_client.put_provider_credential("digitalocean", "do")
    wizard = DeployWizardDialog(ui_client)
    qtbot.addWidget(wizard)
    wizard.show()
    _to_address_page(qtbot, wizard)
    assert "Choosing the address" in wizard._help_view.toPlainText()
    wizard.full_address.setFocus()
    qtbot.waitUntil(lambda: "Web address" in wizard._help_view.toPlainText(), timeout=2000)
    assert "crm.clevelandbusinessmentors.org" in wizard._help_view.toPlainText()


def test_wizard_surfaces_server_rejection_inline(qtbot, ui_client):
    ui_client.put_provider_credential("digitalocean", "do")
    wizard = DeployWizardDialog(ui_client)
    qtbot.addWidget(wizard)
    qtbot.waitUntil(lambda: wizard.region.count() == 2, timeout=5000)
    _clients_loaded(qtbot, wizard)
    wizard.instance_name.setText("x")
    wizard.full_address.setText("api.crmbuilder.ai")
    wizard.admin_email.setText("a@b.co")
    wizard.admin_password.setText("longenoughpassword")
    wizard._show_page(PAGE_REVIEW)
    wizard._next_btn.click()
    qtbot.waitUntil(lambda: "Not queued" in wizard._notice.text(), timeout=5000)
    assert "production host" in wizard._notice.text()
    assert wizard.page == PAGE_REVIEW
    # The deployment was created before the run was refused; a second Deploy
    # reuses it instead of creating another (PI-580).
    assert [d["deployment_identifier"] for d in ui_client.list_deployments()] == ["DPL-001"]
    wizard._notice.setText("")
    wizard._next_btn.click()
    qtbot.waitUntil(lambda: "Not queued" in wizard._notice.text(), timeout=5000)
    assert [d["deployment_identifier"] for d in ui_client.list_deployments()] == ["DPL-001"]


def test_wizard_surfaces_a_refused_deployment_inline(qtbot, ui_client):
    """A 422 from POST /deployments (PI-577: demo/test is only for the defining
    client) is shown under the page, and no run is queued."""
    ui_client.put_provider_credential("digitalocean", "do")
    wizard = DeployWizardDialog(ui_client)
    qtbot.addWidget(wizard)
    qtbot.waitUntil(lambda: wizard.region.count() == 2, timeout=5000)
    _clients_loaded(qtbot, wizard)
    wizard.deployment_client.setCurrentIndex(wizard.deployment_client.findData("CLI-002"))
    wizard.deployment_purpose.setCurrentIndex(wizard.deployment_purpose.findData("demo_test"))
    wizard.instance_name.setText("Demo")
    wizard.full_address.setText("demo.example.org")
    wizard.admin_email.setText("a@b.co")
    wizard.admin_password.setText("longenoughpassword")
    wizard._show_page(PAGE_REVIEW)
    wizard._next_btn.click()
    qtbot.waitUntil(lambda: "Not queued" in wizard._notice.text(), timeout=5000)
    assert ui_client.list_deployments() == [] and ui_client.list_deploy_runs() == []
    assert wizard._next_btn.isEnabled()


def test_describe_size_in_plain_words():
    assert describe_size({"slug": "s-1vcpu-2gb", "vcpus": 1, "memory": 2048, "price_monthly": 12.0}) == (
        "1 processor, 2 GB memory — $12 a month")


def _snapshot(status, *, phases_done=(), log=(), log_length=None, instance=None, phase=None, state=None,
              spec=None):
    st = {"phases": {p: {"status": "done"} for p in phases_done}}
    st.update(state or {})
    return {
        "deploy_run_identifier": "DEP-001",
        "deploy_run_status": status,
        "deploy_run_phase": phase,
        "deploy_run_spec": spec or {},
        "deploy_run_state": st,
        "deploy_run_log": [["t", lvl, msg] for lvl, msg in log],
        "log_length": log_length if log_length is not None else len(log),
        "instance_identifier": instance,
    }


def _settled_dialog(qtbot, ui_client):
    dialog = DeployProgressDialog(ui_client, "DEP-001", poll_ms=60_000, admin_password="S3cret-pw")
    qtbot.addWidget(dialog)
    dialog._timer.stop()
    # The constructor's first poll finds no such run (404) — let it settle so no
    # worker is in flight while we feed snapshots directly.
    qtbot.waitUntil(lambda: "✗" in dialog._log.toPlainText(), timeout=5000)
    dialog._log.clear()
    return dialog


def _steps(dialog):
    return [dialog._steps.item(i).text() for i in range(dialog._steps.count())]


def test_progress_dialog_renders_snapshots_and_emits_instance(qtbot, ui_client):
    dialog = _settled_dialog(qtbot, ui_client)
    created: list[str] = []
    dialog.instance_created.connect(created.append)

    dialog.apply(_snapshot("queued"))
    assert "Queued" in dialog._status.text()
    assert not dialog._cancel_btn.isHidden()
    dialog.apply(_snapshot("running", phases_done=("validate", "create_droplet"), phase="wait_droplet",
                           log=(("info", "one"), ("success", "two")), log_length=2,
                           spec={"domain": "crm.example.org"}))
    assert dialog._progress.value() == 2
    assert "Waiting for server" in dialog._status.text()
    assert dialog._title.text() == "Deploying crm.example.org"
    steps = _steps(dialog)
    assert steps[0] == "✓  Checking the provider accounts — a few seconds   (done)"
    assert steps[2].startswith("▸  Waiting for the server to start") and steps[2].endswith("(working)")
    assert steps[5] == "○  Installing the CRM — about 6 minutes   (not started)"
    assert dialog._log_seen == 2
    assert "one" in dialog._log.toPlainText() and "two" in dialog._log.toPlainText()
    # A later poll only carries the new lines (log_after); nothing is repeated.
    dialog.apply(_snapshot("running", phases_done=("validate", "create_droplet", "wait_droplet"),
                           phase="create_dns", log=(("info", "three"),), log_length=3))
    assert dialog._log.toPlainText().count("one") == 1 and "three" in dialog._log.toPlainText()

    dialog.apply(_snapshot("succeeded", phases_done=("validate",), instance="INST-007"))
    assert created == ["INST-007"]
    assert not dialog._timer.isActive()
    assert dialog._retry_btn.isHidden() and not dialog._handover_btn.isHidden()
    assert dialog._banner.isHidden()


def test_progress_dialog_needs_action_shows_what_to_do_and_offers_try_again(qtbot, ui_client):
    dialog = _settled_dialog(qtbot, ui_client)
    item = {"key": "dns", "state": "needs_action", "title": "The DNS record has not been created yet",
            "found": "GoDaddy has no address record for crm.bbmentors.org.", "meaning": "",
            "action": "At GoDaddy, create a DNS record: type A, name crm, value 203.0.113.7.",
            "who": "client", "verify": "run nslookup"}
    wait = {"key": "certificate", "state": "waiting", "title": "The certificate is waiting for DNS",
            "who": "nobody"}
    snap = _snapshot("needs_action", phases_done=("validate", "create_droplet"), instance="INST-007",
                     spec={"domain": "crm.bbmentors.org", "dns_mode": "manual"},
                     state={"open_items": {"dns": item, "certificate": wait},
                            "phases": {"check_dns": {"status": "needs_action"},
                                       "certificate": {"status": "waiting"}}})
    dialog.apply(snap)
    assert "something needs attention" in dialog._status.text()
    banner = dialog._banner.text()
    assert not dialog._banner.isHidden()
    assert banner.index("Needs action") < banner.index("Waiting")  # the person's item first
    assert "At GoDaddy, create a DNS record" in banner and "The client" in banner
    steps = _steps(dialog)
    assert steps[7].startswith("⚑  Checking DNS") and steps[7].endswith("(needs action)")
    assert steps[8].endswith("(waiting on another step)")
    assert not dialog._retry_btn.isHidden() and not dialog._address_btn.isHidden()
    assert dialog._retry_btn.text() == "Try again"

    assert dialog.corrections_for("CRM.bbmentor.org") == {"domain": "crm.bbmentor.org"}
    assert "full web address" in dialog.corrections_for("crm")
    dialog.apply({**snap, "deploy_run_spec": {"domain": "crm.example.org", "zone_name": "example.org"}})
    assert dialog.corrections_for("members.example.org") == {"subdomain": "members"}
    assert "must end in .example.org" in dialog.corrections_for("crm.other.org")

    sheet = dialog.open_handover()
    qtbot.addWidget(sheet)
    assert "S3cret-pw" in sheet.html and not sheet.copy_btn.isHidden()


def test_progress_dialog_failed_shows_kept_server_and_try_again(qtbot, ui_client):
    with session_scope() as s:
        deploy_runs.create_deploy_run(s, spec={"domain": "crm.example.org"})
        deploy_runs.claim_next_run(s, worker_id="w")
        deploy_runs.set_phase(s, "DEP-001", "create_droplet", state={"droplet_id": "4242", "droplet_ip": "203.0.113.7"}, phase_status="done")
        deploy_runs.set_phase(s, "DEP-001", "server_prep", phase_status="failed", error="apt lock")
        deploy_runs.finish(s, "DEP-001", status="failed", error="server_prep: apt lock")
    dialog = DeployProgressDialog(ui_client, "DEP-001", poll_ms=60_000)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.last_run.get("deploy_run_status") == "failed", timeout=5000)
    assert "Server 4242 (203.0.113.7) still exists" in dialog._status.text()
    assert "The deploy stopped" in dialog._banner.text() and "apt lock" in dialog._banner.text()
    assert "(failed) — apt lock" in _steps(dialog)[4]
    assert not dialog._retry_btn.isHidden()
    dialog._retry_btn.click()
    qtbot.waitUntil(lambda: dialog.last_run.get("deploy_run_status") == "queued", timeout=5000)
    assert dialog._timer.isActive()


def test_describe_and_phase_index_helpers():
    assert describe_run({"deploy_run_status": "queued"}).startswith("Queued")
    assert "Installing CRM" in describe_run({"deploy_run_status": "running", "deploy_run_phase": "install_espocrm"})
    assert phase_index({"deploy_run_state": {"phases": {"validate": {"status": "done"}, "create_droplet": {"status": "failed"}}}}) == 1
    assert phase_index({"deploy_run_state": {"phases": {"check_dns": {"status": "needs_action"}}}}) == 1


def test_describe_run_shows_the_manual_dns_record_while_it_is_being_created():
    state = {"manual_dns_record": {"type": "A", "name": "crm.bbmentors.org", "value": "203.0.113.7",
                                   "host_name": "crm", "dns_host": "GoDaddy"}}
    showing = {"deploy_run_status": "running", "deploy_run_phase": "create_dns", "deploy_run_state": state}
    text = describe_run(showing)
    assert "Add this DNS record at GoDaddy: type A, name crm, value 203.0.113.7" in text
    later = {**showing, "deploy_run_phase": "install_espocrm"}
    assert "Add this DNS record" not in describe_run(later)


def test_deployments_panel_has_new_deployment_button(qtbot, ui_client):
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    assert panel.findChild(type(panel._new_button), "new_deployment_button") is not None
    assert panel.findChild(type(panel._new_button), "register_deployment_button") is not None


def test_handover_sheet_gives_the_record_the_checks_and_the_troubleshooting():
    run = _snapshot(
        "needs_action", instance="INST-007",
        spec={"domain": "crm.bbmentors.org", "dns_mode": "manual", "instance_name": "BB Mentors CRM",
              "admin_username": "admin", "admin_email": "a@bbmentors.org"},
        state={"droplet_ip": "203.0.113.7",
               "dns": {"dns_host": "GoDaddy", "record_name": "crm", "zone": "bbmentors.org"},
               "open_items": {"dns": {"key": "dns", "state": "needs_action", "title": "missing",
                                      "found": "GoDaddy has no record.", "action": "Create it."}}},
    )
    page = render_handover_html(run, admin_password="pw-123")
    assert "Almost ready." in page and "Do not log in until the address shows a padlock" in page
    assert "sign in to GoDaddy and open the DNS settings for <b>bbmentors.org</b>" in page
    assert "type <b>A</b>, name <b>crm</b>, value <b>203.0.113.7</b>" in page
    assert "nslookup crm.bbmentors.org 1.1.1.1" in page and "Address: 203.0.113.7" in page
    assert "<code>pw-123</code>" in page
    assert "orange cloud" in page  # the troubleshooting list
    ready = render_handover_html({**run, "deploy_run_spec": {**run["deploy_run_spec"], "dns_mode": "cloudflare"},
                                  "deploy_run_state": {"droplet_ip": "203.0.113.7"}})
    assert "<b>Ready.</b>" in ready and "Point the web address" not in ready
    assert "the password recorded when the deploy was started" in ready
