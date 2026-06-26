"""Reconcile panel tests — PI-319 (REL-024)."""

from __future__ import annotations

import httpx
from crmbuilder_v2.ui.panels.reconcile import ReconcilePanel
from PySide6.QtCore import Qt

from .conftest import build_client, envelope_ok

_INSTANCES = [
    {"instance_identifier": "INST-001", "instance_name": "Alpha"},
    {"instance_identifier": "INST-002", "instance_name": "Beta"},
]
_COMPARE = {
    "instance_a": "INST-001",
    "instance_b": "INST-002",
    "scope": "all",
    "row_count": 2,
    "groups": [
        {
            "entity": "Account",
            "entity_identifier": "ENT-001",
            "rows": [
                {
                    "member_type": "field", "member_identifier": "FLD-001",
                    "member_name": "phone", "kind": "attribute",
                    "attribute": "field_max_length", "design": 255,
                    "instance_a": 100, "instance_b": 255, "differs": True,
                },
                {
                    "member_type": "field", "member_identifier": "FLD-002",
                    "member_name": "region", "kind": "presence",
                    "attribute": None, "design": "present",
                    "instance_a": "present", "instance_b": "absent", "differs": True,
                },
            ],
        }
    ],
}
_TXNS = [
    {
        "id": 2, "direction": "capture", "member_identifier": "FLD-001",
        "attribute": "field_max_length", "before_value": 255, "after_value": 100,
        "status": "applied", "actor": "desktop",
    }
]


def _handler(req: httpx.Request) -> httpx.Response:
    p = req.url.path
    if req.method == "GET" and p == "/instances":
        return httpx.Response(200, json=envelope_ok(_INSTANCES))
    if req.method == "GET" and p == "/reconcile/compare":
        return httpx.Response(200, json=envelope_ok(_COMPARE))
    if req.method == "GET" and p == "/reconcile/transactions":
        return httpx.Response(200, json=envelope_ok(_TXNS))
    return httpx.Response(
        404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]}
    )


def test_instances_load_into_pickers(qtbot):
    panel = ReconcilePanel(build_client(_handler))
    qtbot.addWidget(panel)
    assert panel._combo_a.count() == 2
    assert panel._combo_a.itemData(0) == "INST-001"


def test_compare_populates_grouped_tree(qtbot):
    panel = ReconcilePanel(build_client(_handler))
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    assert panel._tree.topLevelItemCount() == 1
    group = panel._tree.topLevelItem(0)
    assert group.text(0) == "Account"
    assert group.childCount() == 2
    # the attribute row carries its difference dict for capture
    leaf = group.child(0)
    row = leaf.data(0, Qt.ItemDataRole.UserRole)
    assert row["member_identifier"] == "FLD-001"
    assert row["attribute"] == "field_max_length"


def test_transaction_log_loads(qtbot):
    panel = ReconcilePanel(build_client(_handler))
    qtbot.addWidget(panel)
    panel._load_transactions()
    assert panel._log_tree.topLevelItemCount() == 1
    assert panel._log_tree.topLevelItem(0).text(1) == "capture"
