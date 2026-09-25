"""Hosting credentials dialog + client tests — PI-419 (REQ-522); per
deployment PI-580 (PRJ-128).

Drives the dialog against a real in-process API: status loads as "Not set",
saving a token flips it to configured without the token ever reaching the
dialog again, and Remove clears it. Opened for a deployment, the dialog shows
whether each token is the deployment's own or the application default, writes
the deployment's own token, and refuses to remove the application default
from there. Worker threads are drained with qtbot.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.segments.client_management.repositories import (
    client as client_repo,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.provider_credentials_dialog import (
    ProviderCredentialsDialog,
)
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _secrets_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def ui_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def test_client_round_trip_never_returns_token(ui_client):
    assert ui_client.list_provider_credentials() == []
    rec = ui_client.put_provider_credential("cloudflare", "cf-secret", "CRMBuilder CF")
    assert rec["provider"] == "cloudflare" and rec["configured"] is True
    assert "cf-secret" not in str(rec)
    assert [r["provider"] for r in ui_client.list_provider_credentials()] == ["cloudflare"]
    ui_client.delete_provider_credential("cloudflare")
    assert ui_client.list_provider_credentials() == []


def test_dialog_status_save_and_remove(qtbot, ui_client):
    dialog = ProviderCredentialsDialog(ui_client)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: dialog.status_for("digitalocean").startswith("Not set"), timeout=5000)
    assert dialog.status_for("cloudflare").startswith("Not set")

    row = dialog._rows["digitalocean"]
    # Saving with no token is a no-op with an explanation, never an error.
    row.save_btn.click()
    assert "Paste a token" in dialog.status_for("digitalocean")

    row.token.setText("dop_v1_abc")
    row.label.setText("CRMBuilder DO")
    changed = []
    dialog.changed.connect(lambda: changed.append(True))
    row.save_btn.click()
    qtbot.waitUntil(lambda: dialog.status_for("digitalocean").startswith("✓ Configured"), timeout=5000)
    assert "CRMBuilder DO" in dialog.status_for("digitalocean")
    assert row.token.text() == ""  # the token is not kept in the widget
    assert changed

    stored = ui_client.list_provider_credentials()
    assert [(r["provider"], r["configured"]) for r in stored] == [("digitalocean", True)]

    row.remove_btn.click()
    qtbot.waitUntil(lambda: dialog.status_for("digitalocean").startswith("Not set"), timeout=5000)
    assert ui_client.list_provider_credentials() == []


def _seed_deployment(ui_client) -> str:
    with session_scope() as s:
        client_repo.create_client(s, name="Cleveland Business Mentors")
        client_repo.set_engagement_clients(
            s, "ENG-001", clients=["CLI-001"], primary="CLI-001"
        )
    return ui_client.create_deployment({
        "deployment_client": "CLI-001", "deployment_purpose": "client_own",
        "deployment_name": "Chapter CRM",
    })["deployment_identifier"]


def test_dialog_title_and_application_scope(qtbot, ui_client):
    dialog = ProviderCredentialsDialog(ui_client)
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Hosting credentials"
    assert dialog.deployment_identifier is None
    # Let the first load finish: a dialog torn down mid-load aborts the process.
    qtbot.waitUntil(lambda: dialog.status_for("digitalocean").startswith("Not set"), timeout=5000)


def test_dialog_for_a_deployment_shows_scope_and_writes_its_own_token(qtbot, ui_client):
    ident = _seed_deployment(ui_client)
    ui_client.put_provider_credential("digitalocean", "dop_v1_app", "CRMBuilder DO")
    dialog = ProviderCredentialsDialog(ui_client, deployment_identifier=ident)
    qtbot.addWidget(dialog)
    assert dialog.deployment_identifier == ident
    qtbot.waitUntil(lambda: dialog.status_for("digitalocean").startswith("✓ Configured"), timeout=5000)
    assert "(application default)" in dialog.status_for("digitalocean")
    assert dialog.status_for("cloudflare").startswith("Not set")

    # The application default cannot be removed from the deployment's dialog.
    row = dialog._rows["digitalocean"]
    row.remove_btn.click()
    assert "application default applies" in dialog.status_for("digitalocean")
    assert ui_client.list_provider_credentials()[0]["configured"] is True

    row.token.setText("dop_v1_own")
    row.label.setText("Client DO")
    row.save_btn.click()
    qtbot.waitUntil(lambda: "(this deployment)" in dialog.status_for("digitalocean"), timeout=5000)
    assert "Client DO" in dialog.status_for("digitalocean")
    assert row.token.text() == ""
    effective = {r["provider"]: r for r in ui_client.list_deployment_provider_credentials(ident)}
    assert effective["digitalocean"]["scope"] == "deployment"
    assert "dop_v1_own" not in str(effective)
    # The application's own record is untouched.
    assert ui_client.list_provider_credentials()[0]["label"] == "CRMBuilder DO"

    # Removing the deployment's token lets the application default apply again.
    row.remove_btn.click()
    qtbot.waitUntil(lambda: "(application default)" in dialog.status_for("digitalocean"), timeout=5000)
    effective = {r["provider"]: r for r in ui_client.list_deployment_provider_credentials(ident)}
    assert effective["digitalocean"]["scope"] == "application"
