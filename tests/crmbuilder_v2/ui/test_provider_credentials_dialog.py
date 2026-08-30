"""Provider credentials dialog + client tests — PI-419 (REQ-522).

Drives the dialog against a real in-process API: status loads as "Not set",
saving a token flips it to configured without the token ever reaching the
dialog again, and Remove clears it. Worker threads are drained with qtbot.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.api.main import create_app
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
