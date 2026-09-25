"""Deployments panel tests — PI-580 (PRJ-128; the record is PI-576 / PI-577).

The panel replaces the Instances panel in the registry: it lists the active
application's deployments with their client, hosting provider and purpose,
its detail shows the CRM connection, deploy configuration and hosting
credentials the deployment holds (with each credential's scope), Register
existing… creates a deployment with its connection through the real API,
and nothing people read on the panel says "engagement" or "instance".
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.segments.client_management.repositories import (
    client as client_repo,
)
from crmbuilder_v2.segments.operate.ui import ENTITY_TYPE_TO_LABEL, PANELS
from crmbuilder_v2.segments.operate.ui.dialogs.deployment_register_dialog import (
    DeploymentRegisterDialog,
)
from crmbuilder_v2.segments.operate.ui.panels.deployments import DeploymentsPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL, build_panel
from crmbuilder_v2.ui.panel_registry import PANEL_REGISTRY
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QCheckBox, QGroupBox, QLabel, QLineEdit, QPushButton

FORBIDDEN_WORDS = ("engagement", "instance")


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def ui_client(v2_env) -> StorageClient:
    """ENG-001 (active) is an application defined by CLI-001; CLI-002 is another
    client that may not deploy the private application."""
    with session_scope() as s:
        client_repo.create_client(s, name="Cleveland Business Mentors")
        client_repo.create_client(s, name="Rochester Business Mentors")
        client_repo.set_engagement_clients(
            s, "ENG-001", clients=["CLI-001"], primary="CLI-001"
        )
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _seed_deployment(
    client: StorageClient, name: str = "Chapter CRM", **overrides
) -> dict:
    body = {
        "deployment_client": "CLI-001",
        "deployment_purpose": "client_own",
        "deployment_name": name,
        "instance": {
            "instance_name": name,
            "instance_url": "https://crm.example.org",
            "secret": "top-secret",
        },
    }
    body.update(overrides)
    return client.create_deployment(body)


def _visible_texts(widget) -> list[str]:
    """Every label, button, tick box and group title plus their tooltips."""
    texts: list[str] = []
    for cls in (QLabel, QPushButton, QCheckBox, QGroupBox):
        for w in widget.findChildren(cls):
            text = w.title() if isinstance(w, QGroupBox) else w.text()
            texts.extend(t for t in (text, w.toolTip()) if t)
    return texts


def test_registry_replaces_instances_with_deployments():
    assert "Deployments" in PANELS and "Instances" not in PANELS
    assert ENTITY_TYPE_TO_LABEL["instance"] == "Deployments"
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["instance"] == "Deployments"
    assert "Deployments" in PANEL_REGISTRY and "Instances" not in PANEL_REGISTRY


def test_build_panel_returns_deployments_panel(qtbot, ui_client):
    panel = build_panel("Deployments", ui_client)
    qtbot.addWidget(panel)
    assert isinstance(panel, DeploymentsPanel)
    assert panel.view_entity_type == "instance"


def test_columns(qtbot, ui_client):
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    assert titles == [
        "Identifier",
        "Name",
        "Client",
        "Application",
        "Hosting provider",
        "Purpose",
        "Status",
        "Created",
    ]


def test_rows_come_from_the_api_with_the_client_name(qtbot, ui_client):
    _seed_deployment(ui_client, "Chapter CRM")
    _seed_deployment(
        ui_client,
        "Sandbox",
        instance={
            "instance_name": "Sandbox",
            "instance_url": "https://sandbox.example.org",
        },
    )
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    records = panel.fetch_records()
    assert [r["deployment_identifier"] for r in records] == ["DPL-001", "DPL-002"]
    first = records[0]
    assert first["client_display"] == "Cleveland Business Mentors"
    assert first["deployment_application"] == "ENG-001"
    assert first["hosting_provider_display"] == "DigitalOcean"
    assert first["purpose_display"] == "Client's own"
    assert first["deployment_status"] == "active"
    assert first["created_at_display"]


def test_retired_and_removed_hidden_unless_asked(qtbot, ui_client):
    _seed_deployment(ui_client, "Live")
    _seed_deployment(
        ui_client,
        "Old",
        instance={
            "instance_name": "Old",
            "instance_url": "https://old.example.org",
        },
    )
    ui_client.patch_deployment("DPL-002", {"deployment_status": "retired"})
    _seed_deployment(
        ui_client,
        "Gone",
        instance={
            "instance_name": "Gone",
            "instance_url": "https://gone.example.org",
        },
    )
    ui_client.delete_deployment("DPL-003")
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    assert [r["deployment_identifier"] for r in panel.fetch_records()] == ["DPL-001"]
    panel._show_retired_check.setChecked(True)
    assert [r["deployment_identifier"] for r in panel.fetch_records()] == [
        "DPL-001",
        "DPL-002",
        "DPL-003",
    ]


def test_detail_shows_connection_config_and_credential_scope(qtbot, ui_client):
    _seed_deployment(ui_client, "Chapter CRM")
    ui_client.put_provider_credential("digitalocean", "do-token", "CRMBuilder DO")
    ui_client.put_deployment_provider_credential("DPL-001", "cloudflare", "cf-token")
    ui_client.put_deploy_config(
        "INST-001",
        {
            "scenario": "self_hosted",
            "ssh_host": "203.0.113.7",
            "ssh_username": "root",
            "domain": "crm.example.org",
            "droplet_ip": "203.0.113.7",
        },
    )
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    record = panel.fetch_records()[0]
    extras = panel.fetch_detail_extras(record)
    assert extras["deployment"]["deployment_identifier"] == "DPL-001"
    detail = panel.render_detail(record, extras)
    qtbot.addWidget(detail)

    lines = {
        w.objectName(): w.text()
        for w in detail.findChildren(QLineEdit)
        if w.objectName()
    }
    assert lines["deployment_name_value"] == "Chapter CRM"
    assert lines["deployment_client_value"] == "Cleveland Business Mentors"
    assert lines["deployment_application_value"] == "ENG-001"
    assert lines["deployment_purpose_value"] == "Client's own"
    assert lines["instance_url_value"] == "https://crm.example.org"
    assert lines["instance_vendor_value"] == "espocrm"
    assert lines["instance_role_value"] == "both"
    assert lines["instance_auth_method_value"] == "api_key"
    assert lines["instance_status_value"] == "active"
    assert lines["instance_feature_selection_value"] == "full design (no selection)"
    # Secret presence only — never the value or the opaque ref (REQ-157).
    assert lines["instance_secret_state_value"] == "configured"
    assert "top-secret" not in lines.values()
    assert all(not t.startswith("crmbuilder:") for t in lines.values())

    labels = {
        w.objectName(): w.text() for w in detail.findChildren(QLabel) if w.objectName()
    }
    assert labels["credential_digitalocean"] == (
        "DigitalOcean: configured (application default) — CRMBuilder DO"
    )
    assert labels["credential_cloudflare"] == "Cloudflare: configured (this deployment)"
    assert labels["deployment_open_items"] == "Nothing outstanding from the deploy."

    buttons = {b.objectName() for b in detail.findChildren(QPushButton)}
    assert {
        "audit_instance_button",
        "publish_instance_button",
        "feature_selection_button",
        "run_history_button",
        "check_dns_button",
        "deployment_credentials_button",
        "edit_connection_button",
        "remove_deployment_button",
    } <= buttons


def test_check_dns_now_acts_on_the_held_connection(qtbot, ui_client, monkeypatch):
    from crmbuilder_v2.segments.operate.ui.panels import deployments as panel_module

    _seed_deployment(ui_client, "Deployed")
    ui_client.put_deploy_config(
        "INST-001",
        {
            "scenario": "self_hosted",
            "ssh_host": "203.0.113.7",
            "ssh_username": "root",
            "domain": "crm.example.org",
            "droplet_ip": "203.0.113.7",
        },
    )
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    record = panel.fetch_records()[0]
    detail = panel.render_detail(record, panel.fetch_detail_extras(record))
    qtbot.addWidget(detail)
    calls: list[str] = []
    monkeypatch.setattr(
        ui_client,
        "check_instance_dns",
        lambda i: (
            calls.append(i) or {"dns": {"state": "correct", "title": "DNS is correct"}}
        ),
    )
    shown: list[str] = []
    monkeypatch.setattr(
        panel_module.CopyableMessageBox, "exec", lambda self: shown.append(self.text())
    )
    detail.findChild(QPushButton, "check_dns_button").click()
    qtbot.waitUntil(lambda: bool(shown), timeout=5000)
    assert calls == ["INST-001"] and shown[0].startswith("DNS is correct")


def test_detail_without_connection_says_so(qtbot, ui_client):
    ui_client.create_deployment(
        {
            "deployment_client": "CLI-001",
            "deployment_purpose": "client_own",
            "deployment_name": "Planned",
        }
    )
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    record = panel.fetch_records()[0]
    detail = panel.render_detail(record, panel.fetch_detail_extras(record))
    qtbot.addWidget(detail)
    assert detail.findChild(QLabel, "connection_empty") is not None
    assert detail.findChild(QLabel, "deploy_config_empty") is not None
    buttons = {b.objectName() for b in detail.findChildren(QPushButton)}
    assert "audit_instance_button" not in buttons and "run_history_button" in buttons


def test_no_label_says_engagement_or_instance(qtbot, ui_client):
    _seed_deployment(ui_client, "Chapter CRM")
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    record = panel.fetch_records()[0]
    detail = panel.render_detail(record, panel.fetch_detail_extras(record))
    qtbot.addWidget(detail)
    texts = _visible_texts(panel) + _visible_texts(detail)
    assert texts  # the check has something to look at
    offenders = [t for t in texts if any(w in t.lower() for w in FORBIDDEN_WORDS)]
    assert offenders == []
    assert panel.entity_title() == "Deployments"


def test_selects_by_deployment_or_by_held_connection(qtbot, ui_client):
    _seed_deployment(ui_client, "Chapter CRM")
    panel = DeploymentsPanel(ui_client)
    qtbot.addWidget(panel)
    panel._records = panel.fetch_records()
    panel._model.set_records(panel._records)
    assert panel._select_by_identifier("INST-001")
    assert panel._currently_selected_identifier() == "DPL-001"
    assert panel._select_by_identifier("DPL-001")
    assert not panel._select_by_identifier("DPL-999")


def test_register_existing_creates_deployment_with_connection(qtbot, ui_client):
    dialog = DeploymentRegisterDialog(ui_client)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(
        lambda: dialog.client_combo.currentData() == "CLI-001", timeout=5000
    )
    assert dialog.client_combo.currentText() == "Cleveland Business Mentors"
    # Nothing is disabled: Register explains what is missing.
    dialog._save_btn.click()
    assert "name" in dialog._notice.text()
    dialog.deployment_name.setText("Existing CRM")
    dialog._save_btn.click()
    assert "URL" in dialog._notice.text()
    dialog.instance_url.setText("https://old.example.org")
    dialog.instance_auth_method.setCurrentIndex(
        dialog.instance_auth_method.findData("basic")
    )
    dialog.secret.setText("admin")
    dialog.secret_key.setText("pw-123")
    dialog.hosting_provider.setCurrentIndex(dialog.hosting_provider.findData("other"))
    dialog._save_btn.click()
    # ``waitUntil`` rather than ``waitSignal(accepted)``: the nested loop the
    # latter opens tears the dialog's worker down mid-delivery under offscreen Qt.
    qtbot.waitUntil(lambda: dialog.created_identifier() == "DPL-001", timeout=5000)
    assert dialog.result() == dialog.DialogCode.Accepted
    record = ui_client.get_deployment("DPL-001")
    assert record["deployment_client"] == "CLI-001"
    assert record["deployment_hosting_provider"] == "other"
    assert record["deployment_purpose"] == "client_own"
    instance = record["instance"]
    assert (
        instance["instance_name"] == "Existing CRM"
    )  # defaults to the deployment name
    assert instance["instance_url"] == "https://old.example.org"
    assert instance["instance_auth_method"] == "basic"
    assert secrets.get_secret(instance["instance_secret_ref"]) == "admin"
    assert secrets.get_secret(instance["instance_secret_key_ref"]) == "pw-123"


def test_register_existing_shows_the_apis_refusal_inline(qtbot, ui_client):
    dialog = DeploymentRegisterDialog(ui_client)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.client_combo.count() == 2, timeout=5000)
    dialog.client_combo.setCurrentIndex(dialog.client_combo.findData("CLI-002"))
    dialog.deployment_name.setText("Not allowed")
    dialog.instance_url.setText("https://x.example.org")
    dialog._save_btn.click()
    qtbot.waitUntil(
        lambda: dialog._notice.text().startswith("Not registered"), timeout=5000
    )
    assert dialog.created_identifier() is None
    assert ui_client.list_deployments() == []
    assert dialog._save_btn.isEnabled()
