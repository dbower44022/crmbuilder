"""Redesigned reconcile surface — models + grid panel tests — PI-333 (REL-027)."""

from __future__ import annotations

import httpx
from crmbuilder_v2.ui.panels.reconcile_grid import ReconcileGridPanel
from crmbuilder_v2.ui.panels.reconcile_models import (
    RECORD_ROLE,
    STATE_ROLE,
    EntityDetailModel,
    ExistenceGridModel,
    fmt_value,
)
from PySide6.QtCore import QModelIndex, Qt

from .conftest import build_client, envelope_ok

_INSTANCES = [
    {"instance_identifier": "INST-001", "instance_name": "Alpha"},
    {"instance_identifier": "INST-002", "instance_name": "Beta"},
]
_EXISTENCE = [
    {"entity_identifier": "ENT-001", "entity": "Account", "entity_label": "Org",
     "design": "present", "instance_a": "present", "instance_b": "absent"},
    {"entity_identifier": "ENT-002", "entity": "Contact", "entity_label": None,
     "design": "present", "instance_a": "present", "instance_b": "present"},
]
_GROUPS = [
    {
        "entity": "Account", "entity_identifier": "ENT-001", "entity_label": "Org",
        "rows": [
            {"member_type": "field", "member_identifier": "FLD-001",
             "member_name": "phone", "kind": "attribute", "attribute": "field_max_length",
             "design": 255, "instance_a": 100, "instance_b": "absent",
             "differs": True, "actionable": True},
        ],
        "object_groups": [
            {"object_type": "fields", "differing_count": 1, "rows": [
                {"member_type": "field", "member_identifier": "FLD-001",
                 "member_name": "phone", "kind": "attribute", "attribute": "field_max_length",
                 "design": 255, "instance_a": 100, "instance_b": "absent",
                 "differs": True, "actionable": True},
            ]},
        ],
    }
]
_COMPARE = {
    "instance_a": "INST-001", "instance_b": "INST-002", "scope": "all",
    "existence": _EXISTENCE, "groups": _GROUPS, "row_count": 1,
}


def _handler(req: httpx.Request) -> httpx.Response:
    p = req.url.path
    if req.method == "GET" and p == "/instances":
        return httpx.Response(200, json=envelope_ok(_INSTANCES))
    if req.method == "GET" and p == "/reconcile/compare":
        return httpx.Response(200, json=envelope_ok(_COMPARE))
    return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})


# --- models -----------------------------------------------------------------


def test_fmt_value_operator_language():
    assert fmt_value("present") == "In"
    assert fmt_value("absent") == "Missing"
    assert fmt_value("unknown") == "n/a"
    assert fmt_value(None) == "—"
    assert fmt_value(True) == "Yes"
    assert fmt_value(["a", "b"]) == "a, b"


def test_existence_grid_model_shape(qapp):
    m = ExistenceGridModel(_EXISTENCE, instance_a_label="Alpha", instance_b_label="Beta")
    assert m.rowCount() == 2
    assert m.columnCount() == 4
    assert m.headerData(2, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "Alpha"
    # entity cell shows name + label
    assert "Account" in m.data(m.index(0, 0), Qt.ItemDataRole.DisplayRole)
    # location cell uses operator language + carries the raw state token
    assert m.data(m.index(0, 3), Qt.ItemDataRole.DisplayRole) == "Missing"
    assert m.data(m.index(0, 3), STATE_ROLE) == "absent"
    # the record is reachable for drill
    assert m.data(m.index(0, 0), RECORD_ROLE)["entity_identifier"] == "ENT-001"


def test_entity_detail_model_tree(qapp):
    m = EntityDetailModel(_GROUPS[0]["object_groups"])
    # one group node
    assert m.rowCount() == 1
    grp_idx = m.index(0, 0, QModelIndex())
    assert "Fields" in m.data(grp_idx, Qt.ItemDataRole.DisplayRole)
    assert "1 differ" in m.data(grp_idx, Qt.ItemDataRole.DisplayRole)
    # one child diff row under it
    assert m.rowCount(grp_idx) == 1
    child = m.index(0, 0, grp_idx)
    assert m.parent(child) == grp_idx
    assert "phone" in m.data(child, Qt.ItemDataRole.DisplayRole)
    # value cells humanized; the record is reachable for apply
    assert m.data(m.index(0, 1, grp_idx), Qt.ItemDataRole.DisplayRole) == "255"
    assert m.data(m.index(0, 3, grp_idx), Qt.ItemDataRole.DisplayRole) == "Missing"
    assert m.data(child, RECORD_ROLE)["member_identifier"] == "FLD-001"


# --- panel ------------------------------------------------------------------


def test_panel_loads_instances(qtbot):
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    assert panel._combo_a.count() == 2


def test_compare_populates_existence_grid(qtbot):
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    assert panel._grid_model.rowCount() == 2
    # differing-entity set drives the attention filter
    assert "ENT-001" in panel._grid_proxy._differing


def test_attention_filter_hides_in_sync_entities(qtbot):
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    panel._attention.setChecked(True)
    # ENT-002 is fully in sync → filtered out; ENT-001 (missing on B) remains
    assert panel._grid_proxy.rowCount() == 1


def test_drill_into_entity_shows_detail_tree(qtbot):
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    panel._drill(_EXISTENCE[0])
    assert panel._stack.currentIndex() == 1
    assert panel._detail_model.rowCount() == 1  # one object group (Fields)
    assert "Account" in panel._detail_title.text()


def test_drill_into_in_sync_entity_shows_no_differences(qtbot):
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    panel._drill(_EXISTENCE[1])  # Contact: no group
    assert panel._detail_model.rowCount() == 0
    assert "no differences" in panel._detail_title.text()
