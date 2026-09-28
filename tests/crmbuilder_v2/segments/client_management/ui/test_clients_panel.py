"""Clients panel tests (PI-512 / REQ-589): the sidebar entry, the master
columns, the detail pane with its Engagements section, and the create and
delete dialogs, end to end against a real per-test store."""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.segments.client_management.ui.dialogs.client_crud import (
    ClientCreateDialog,
)
from crmbuilder_v2.segments.client_management.ui.panels.clients import ClientsPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.navigation import OPERATE_PANELS
from crmbuilder_v2.ui.panel_registry import PANEL_REGISTRY
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QComboBox, QLabel, QPushButton


@pytest.fixture
def store_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _wait_rows(qtbot, panel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


def test_clients_registered_in_sidebar_and_registry():
    assert "Clients" in OPERATE_PANELS
    assert "Clients" in PANEL_REGISTRY
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["client"] == "Clients"


def test_columns_and_rows(qtbot, store_client):
    store_client.create_client({"client_name": "Cleveland Business Mentors"})
    panel = ClientsPanel(store_client)
    qtbot.addWidget(panel)
    assert [c.title for c in panel.list_columns()] == [
        "Identifier",
        "Name",
        "Status",
        "Applications",
        "Deployments",
        "Created",
    ]
    _wait_rows(qtbot, panel, 1)
    assert panel._records[0]["client_identifier"] == "CLI-001"
    assert panel._records[0]["engagement_count"] == 0


def test_detail_engagements_section_add_and_remove(qtbot, store_client):
    created = store_client.create_client({"client_name": "A"})
    ident = created["client_identifier"]
    panel = ClientsPanel(store_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    panel.select_record_by_identifier(ident)
    qtbot.waitUntil(
        lambda: panel.findChild(QLabel, "client_engagements_empty") is not None,
        timeout=3000,
    )
    combo = panel.findChild(QComboBox, "add_engagement_combo")
    assert combo is not None and combo.count() == 1  # ENG-001 is the only engagement
    assert combo.currentData() == "ENG-001"
    panel._on_add_engagement(ident, "ENG-001")
    qtbot.waitUntil(
        lambda: panel.findChild(QLabel, "client_engagement_ENG-001") is not None,
        timeout=3000,
    )
    assert "defined by" not in panel.findChild(QLabel, "client_engagement_ENG-001").text()
    assert store_client.get_engagement_clients("ENG-001")["primary"] == ident
    remove = panel.findChild(QPushButton, "remove_engagement_ENG-001")
    assert remove is not None
    panel.select_record_by_identifier(ident)
    panel._on_remove_engagement("ENG-001")
    qtbot.waitUntil(
        lambda: panel.findChild(QLabel, "client_engagements_empty") is not None,
        timeout=3000,
    )
    assert store_client.get_engagement_clients("ENG-001")["primary"] is None


def test_create_dialog_creates_a_client(qtbot, store_client):
    dialog = ClientCreateDialog(store_client)
    qtbot.addWidget(dialog)
    assert "client_identifier" not in dialog._widgets
    dialog._widgets["client_name"].setText("New Org")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert store_client.get_client(dialog.created_identifier())["client_name"] == "New Org"


def test_delete_refused_while_holding_engagements(store_client):
    from crmbuilder_v2.ui.exceptions import StorageClientError

    ident = store_client.create_client({"client_name": "Held"})["client_identifier"]
    store_client.set_engagement_clients("ENG-001", [ident])
    with pytest.raises(StorageClientError):
        store_client.delete_client(ident)
    store_client.set_engagement_clients("ENG-001", [])
    assert store_client.delete_client(ident)["client_deleted_at"] is not None


def _two_clients_on_eng_001(store_client) -> tuple[str, str]:
    """ENG-001 defined by Cleveland; Rochester holds nothing yet."""
    a = store_client.create_client({"client_name": "Cleveland"})["client_identifier"]
    b = store_client.create_client({"client_name": "Rochester"})["client_identifier"]
    store_client.set_engagement_clients("ENG-001", [a], primary=a)
    return a, b


def test_adding_an_application_with_a_defining_client_adds_a_deployment_grant(
    qtbot, store_client
):
    """PI-588 / REQ-664: the added client gets a deployment grant and the
    defining client does not move."""
    a, b = _two_clients_on_eng_001(store_client)
    panel = ClientsPanel(store_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 2)
    panel.select_record_by_identifier(b)
    qtbot.waitUntil(
        lambda: panel.findChild(QLabel, "client_grants_empty") is not None, timeout=3000
    )
    combo = panel.findChild(QComboBox, "add_engagement_combo")
    assert "adds a deployment grant" in combo.itemText(combo.findData("ENG-001"))
    panel._on_add_engagement(b, "ENG-001")
    qtbot.waitUntil(
        lambda: panel.findChild(QLabel, "client_engagement_ENG-001") is not None,
        timeout=3000,
    )
    assert f"defined by {a}" in panel.findChild(QLabel, "client_engagement_ENG-001").text()
    assert panel.findChild(QLabel, "client_engagements_empty") is not None
    assert store_client.get_engagement_clients("ENG-001")["primary"] == a
    grants = store_client.list_deployment_grants("ENG-001")["deployment_grants"]
    assert [g["client_identifier"] for g in grants] == [b]

    # Removing it withdraws the deployment grant only.
    panel.select_record_by_identifier(b)
    panel._on_remove_engagement("ENG-001")
    qtbot.waitUntil(
        lambda: panel.findChild(QLabel, "client_grants_empty") is not None, timeout=3000
    )
    assert store_client.list_deployment_grants("ENG-001")["deployment_grants"] == []
    assert store_client.get_engagement_clients("ENG-001")["primary"] == a


def test_removing_the_defining_client_is_refused_while_grants_exist(
    qtbot, store_client, monkeypatch
):
    """PI-588: removing the defining client never makes a deployment-grant
    holder the defining client; the panel says why instead."""
    a, b = _two_clients_on_eng_001(store_client)
    store_client.add_deployment_grant("ENG-001", b)
    panel = ClientsPanel(store_client)
    qtbot.addWidget(panel)
    explained: list[str] = []
    monkeypatch.setattr(panel, "_explain_refusal", lambda title, text: explained.append(text))
    _wait_rows(qtbot, panel, 2)
    panel.select_record_by_identifier(a)
    qtbot.waitUntil(
        lambda: panel.findChild(QPushButton, "remove_engagement_ENG-001") is not None,
        timeout=3000,
    )
    panel._on_remove_engagement("ENG-001")
    assert explained and "deployment grant" in explained[0]
    holding = store_client.get_engagement_clients("ENG-001")
    assert holding["primary"] == a
    assert {c["client_identifier"] for c in holding["clients"]} == {a, b}
