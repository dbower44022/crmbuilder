"""Instances panel / dialog tests — PI-186 (PRJ-027).

Covers the "Instances" sidebar registration (Governance group + entity-type
label map + build_panel wiring), the master-pane columns, the create/edit
dialog round-trips through a real API, and the detail pane never exposing a
secret value — only whether one is configured (REQ-157).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2 import secrets
from crmbuilder_v2.access.vocab import ENTITY_TYPES
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.instance_crud import (
    InstanceCreateDialog,
    InstanceDeleteDialog,
    InstanceEditDialog,
)
from crmbuilder_v2.ui.main_window import (
    ENTITY_TYPE_TO_SIDEBAR_LABEL,
    build_panel,
)
from crmbuilder_v2.ui.panels.instances import InstancesPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QLineEdit


@pytest.fixture(autouse=True)
def _keyring_in_memory(monkeypatch):
    monkeypatch.setenv(secrets.DISABLE_ENV_VAR, "1")
    secrets._reset_in_memory_store_for_tests()
    yield
    secrets._reset_in_memory_store_for_tests()


@pytest.fixture
def instance_client(v2_env) -> StorageClient:
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    sc.set_active_engagement("ENG-001")
    return sc


def _seed(client: StorageClient, name: str, **overrides) -> dict:
    body = {"instance_name": name, "instance_url": "https://crm.example.org"}
    body.update(overrides)
    return client.create_instance(body)


def test_entity_type_registered():
    assert "instance" in ENTITY_TYPES
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["instance"] == "Instances"


def test_sidebar_has_instances_in_governance():
    governance = dict(SIDEBAR_GROUPS)["Governance"]
    assert "Instances" in governance


def test_build_panel_returns_instances_panel(qtbot, instance_client):
    panel = build_panel("Instances", instance_client)
    qtbot.addWidget(panel)
    assert isinstance(panel, InstancesPanel)


def test_master_columns(qtbot, instance_client):
    panel = InstancesPanel(instance_client)
    qtbot.addWidget(panel)
    fields = [c.field for c in panel.list_columns()]
    assert "instance_identifier" in fields
    assert "instance_name" in fields
    assert "instance_role" in fields


def test_fetch_records_returns_seeded(qtbot, instance_client):
    _seed(instance_client, "CBM sandbox")
    _seed(instance_client, "CBM prod", instance_role="target")
    panel = InstancesPanel(instance_client)
    qtbot.addWidget(panel)
    names = {r["instance_name"] for r in panel.fetch_records()}
    assert names == {"CBM sandbox", "CBM prod"}


def test_create_dialog_round_trip(qtbot, instance_client):
    dialog = InstanceCreateDialog(instance_client)
    qtbot.addWidget(dialog)
    assert "instance_identifier" not in dialog._widgets  # server-assigned
    dialog._widgets["instance_name"].setText("Via dialog")
    dialog._widgets["instance_url"].setText("https://dlg.example.org")
    dialog._widgets["secret"].setText("dialog-secret")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert dialog.created_identifier() == "INST-001"
    row = instance_client.get_instance("INST-001")
    assert row["instance_secret_ref"].startswith("crmbuilder:")
    assert secrets.get_secret(row["instance_secret_ref"]) == "dialog-secret"


def test_detail_pane_hides_secret_value(qtbot, instance_client):
    row = _seed(instance_client, "Secret holder", secret="top-secret")
    panel = InstancesPanel(instance_client)
    qtbot.addWidget(panel)
    fresh = instance_client.get_instance(row["instance_identifier"])
    extras = {"references": {"as_source": [], "as_target": []}}
    detail = panel.render_detail(fresh, extras)
    line_texts = [w.text() for w in detail.findChildren(QLineEdit)]
    assert "configured" in line_texts
    assert "top-secret" not in line_texts
    assert all(not t.startswith("crmbuilder:") for t in line_texts)


def test_delete_dialog_requires_typed_identifier(qtbot, instance_client):
    row = _seed(instance_client, "Deletable")
    ident = row["instance_identifier"]
    dialog = InstanceDeleteDialog(instance_client, ident, "Deletable")
    qtbot.addWidget(dialog)
    assert not dialog._delete_btn.isEnabled()
    dialog._confirm_edit.setText(ident)
    assert dialog._delete_btn.isEnabled()


def test_edit_dialog_blank_secret_preserves(qtbot, instance_client):
    row = _seed(instance_client, "Keeps secret", secret="orig")
    ident = row["instance_identifier"]
    ref = instance_client.get_instance(ident)["instance_secret_ref"]
    dialog = InstanceEditDialog(instance_client, instance_client.get_instance(ident))
    qtbot.addWidget(dialog)
    dialog._widgets["instance_name"].setText("Renamed")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    after = instance_client.get_instance(ident)
    assert after["instance_name"] == "Renamed"
    assert after["instance_secret_ref"] == ref
    assert secrets.get_secret(ref) == "orig"
