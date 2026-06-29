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


def test_detail_renders_inventory_section(qtbot, instance_client):
    from PySide6.QtWidgets import QLabel
    row = _seed(instance_client, "Audited")
    panel = InstancesPanel(instance_client)
    qtbot.addWidget(panel)
    fresh = instance_client.get_instance(row["instance_identifier"])
    extras = {
        "references": {"as_source": [], "as_target": []},
        "membership_summary": {"entity": {"present": 3, "drifted": 1, "absent": 0}},
        "publish_plan": {"item_count": 4},
    }
    detail = panel.render_detail(fresh, extras)
    labels = {w.objectName(): w.text() for w in detail.findChildren(QLabel)
              if w.objectName()}
    assert "membership_summary_entity" in labels
    assert "3 present" in labels["membership_summary_entity"]
    assert "4 object" in labels["publish_plan_count"]


def test_audit_button_visible_for_source_hidden_for_target(qtbot, instance_client):
    from PySide6.QtWidgets import QPushButton
    src = instance_client.get_instance(
        _seed(instance_client, "src", instance_role="source")["instance_identifier"]
    )
    tgt = instance_client.get_instance(
        _seed(instance_client, "tgt", instance_url="https://t", instance_role="target")[
            "instance_identifier"
        ]
    )
    panel = InstancesPanel(instance_client)
    qtbot.addWidget(panel)
    extras = {"references": {"as_source": [], "as_target": []}}
    src_detail = panel.render_detail(src, extras)
    tgt_detail = panel.render_detail(tgt, extras)
    src_btns = [b.objectName() for b in src_detail.findChildren(QPushButton)]
    tgt_btns = [b.objectName() for b in tgt_detail.findChildren(QPushButton)]
    assert "audit_instance_button" in src_btns
    assert "audit_instance_button" not in tgt_btns


# ---------------------------------------------------------------------------
# both role surfaced in the UI (WTK-259) — the both value is settable through
# the dialogs, viewable in the detail, and a both-role instance gets the full
# surface (audit + publish) plus full-inventory audit results across every area.
# ---------------------------------------------------------------------------


def test_create_dialog_offers_both_role_by_default(qtbot, instance_client):
    """The role combo offers ``both`` and pre-selects it on Create."""
    dialog = InstanceCreateDialog(instance_client)
    qtbot.addWidget(dialog)
    combo = dialog._widgets["instance_role"]
    items = {combo.itemText(i) for i in range(combo.count())}
    assert {"source", "target", "both"} <= items
    assert combo.currentText() == "both"


def test_edit_dialog_sets_both_role(qtbot, instance_client):
    """Editing an instance to the ``both`` role round-trips through the API."""
    ident = _seed(instance_client, "Re-roled", instance_role="target")[
        "instance_identifier"
    ]
    dialog = InstanceEditDialog(instance_client, instance_client.get_instance(ident))
    qtbot.addWidget(dialog)
    dialog._widgets["instance_role"].setCurrentText("both")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert instance_client.get_instance(ident)["instance_role"] == "both"


def test_both_role_detail_displays_role_and_full_surface(qtbot, instance_client):
    """A both-role detail shows the role and both audit + publish actions."""
    from PySide6.QtWidgets import QLineEdit, QPushButton
    both = instance_client.get_instance(
        _seed(instance_client, "dual", instance_role="both")["instance_identifier"]
    )
    panel = InstancesPanel(instance_client)
    qtbot.addWidget(panel)
    extras = {"references": {"as_source": [], "as_target": []}}
    detail = panel.render_detail(both, extras)
    role_value = detail.findChild(QLineEdit, "instance_role_value")
    assert role_value is not None
    assert role_value.text() == "both"
    btns = {b.objectName() for b in detail.findChildren(QPushButton)}
    # The both role is simultaneously a source (audit) and a target (publish).
    assert "audit_instance_button" in btns
    assert "publish_instance_button" in btns


def test_detail_reflects_full_inventory_audit_for_both(qtbot, instance_client):
    """Every area of a both-role full-inventory audit renders its own row."""
    from PySide6.QtWidgets import QLabel
    both = instance_client.get_instance(
        _seed(instance_client, "audited-both", instance_role="both")[
            "instance_identifier"
        ]
    )
    panel = InstancesPanel(instance_client)
    qtbot.addWidget(panel)
    # A both-role audit classifies every area as present/drifted/absent
    # (WTK-256) — the detail must surface one row per area, none dropped.
    areas = {
        "entity": {"present": 12, "drifted": 2, "absent": 1},
        "field": {"present": 205, "drifted": 4, "absent": 0},
        "relationship": {"present": 44, "drifted": 0, "absent": 0},
        "layout": {"present": 12, "drifted": 1, "absent": 0},
        "role": {"present": 10, "drifted": 0, "absent": 0},
        "team": {"present": 7, "drifted": 0, "absent": 0},
    }
    extras = {
        "references": {"as_source": [], "as_target": []},
        "membership_summary": areas,
        "publish_plan": {"item_count": 5},
    }
    detail = panel.render_detail(both, extras)
    labels = {w.objectName(): w.text() for w in detail.findChildren(QLabel)
              if w.objectName()}
    for area, counts in areas.items():
        key = f"membership_summary_{area}"
        assert key in labels, f"missing row for area {area}"
        assert f"{counts['present']} present" in labels[key]
        assert f"{counts['drifted']} drifted" in labels[key]
        assert f"{counts['absent']} absent" in labels[key]
