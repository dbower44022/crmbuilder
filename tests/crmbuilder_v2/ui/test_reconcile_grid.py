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
    plan_apply,
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


_TXNS = [
    {"id": 7, "direction": "capture", "member_identifier": "FLD-001",
     "attribute": "field_max_length", "before_value": 255, "after_value": 100,
     "status": "applied", "actor": "desktop"},
]


def _handler(req: httpx.Request) -> httpx.Response:
    p = req.url.path
    if req.method == "GET" and p == "/instances":
        return httpx.Response(200, json=envelope_ok(_INSTANCES))
    if req.method == "GET" and p == "/reconcile/compare":
        return httpx.Response(200, json=envelope_ok(_COMPARE))
    if req.method == "GET" and p == "/reconcile/transactions":
        return httpx.Response(200, json=envelope_ok(_TXNS))
    return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})


# --- apply routing (pure) ---------------------------------------------------

def _row(design=255, a=100, b=255, actionable=True):
    return {"member_type": "field", "member_identifier": "FLD-1",
            "attribute": "field_max_length", "design": design,
            "instance_a": a, "instance_b": b, "actionable": actionable}


def test_plan_capture_instance_to_design():
    """Correct value on A, bring the design into line → one capture."""
    plan = plan_apply(_row(), "instance_a", ["design"])
    assert plan["ops"] == [{"kind": "capture", "location": "instance_a"}]


def test_plan_publish_design_to_instance():
    """Correct value in the design, push to A → one publish, no capture."""
    plan = plan_apply(_row(a=100), "design", ["instance_a"])
    assert plan["ops"] == [{"kind": "publish", "location": "instance_a"}]


def test_plan_instance_to_instance_routes_through_design():
    """A→B is mechanically capture A→design then publish design→B (hub)."""
    plan = plan_apply(_row(design=255, a=100, b=300), "instance_a", ["instance_b"])
    assert plan["ops"] == [
        {"kind": "capture", "location": "instance_a"},
        {"kind": "publish", "location": "instance_b"},
    ]


def test_plan_skips_already_matching_target():
    """B already holds the design value → publish to B is skipped, not attempted."""
    plan = plan_apply(_row(design=255, a=100, b=255), "design", ["instance_a", "instance_b"])
    assert plan["ops"] == [{"kind": "publish", "location": "instance_a"}]
    assert any("Instance B" in s for s in plan["skipped"])


def test_plan_non_actionable_is_skipped():
    plan = plan_apply(_row(actionable=False), "instance_a", ["design"])
    assert plan["ops"] == []
    assert plan["skipped"]


# --- models -----------------------------------------------------------------


def test_fmt_value_operator_language():
    assert fmt_value("present") == "In"
    assert fmt_value("absent") == "Missing"
    assert fmt_value("unknown") == "Not audited"  # REQ-390: not "n/a"
    assert fmt_value(None) == "—"
    assert fmt_value(True) == "Yes"
    assert fmt_value(["a", "b"]) == "a, b"


def test_unknown_presence_labelled_not_audited(qapp):
    """REQ-390: an entity not recorded in a location's last audit reads
    'Not audited', never the ambiguous 'n/a'."""
    from crmbuilder_v2.ui.panels.reconcile_models import STATE_LABELS
    assert STATE_LABELS["unknown"] == "Not audited"
    m = ExistenceGridModel(_EXISTENCE)
    # ENT-002 Contact is present on B; build a row that is unknown on B
    rows = [{"entity_identifier": "ENT-9", "entity": "Widget", "entity_label": None,
             "design": "present", "instance_a": "present", "instance_b": "unknown"}]
    m.set_rows(rows)
    assert m.data(m.index(0, 3), Qt.ItemDataRole.DisplayRole) == "Not audited"
    assert "n/a" not in {
        m.data(m.index(0, c), Qt.ItemDataRole.DisplayRole) for c in range(4)
    }


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


def test_entity_detail_model_handles_list_valued_cells(qapp):
    """A list/dict difference value (e.g. a layout/relationship payload) must not
    be probed against the string state maps — doing so raised ``TypeError:
    unhashable type: 'list'`` inside the Qt data() override and cascaded as
    index/parent errors. Every role must return cleanly here."""
    groups = [
        {"object_type": "layouts", "differing_count": 1, "rows": [
            {"member_type": "layout", "member_identifier": "LAY-001",
             "member_name": "detail", "kind": "structure", "attribute": "rows",
             "design": ["name", "phone"], "instance_a": ["name"],
             "instance_b": "absent", "differs": True, "actionable": False},
        ]},
    ]
    m = EntityDetailModel(groups)
    grp_idx = m.index(0, 0, QModelIndex())
    child = m.index(0, 1, grp_idx)  # the design column, holding a list
    # DisplayRole comma-joins; the state/colour roles return None without raising.
    assert m.data(child, Qt.ItemDataRole.DisplayRole) == "name, phone"
    assert m.data(child, STATE_ROLE) is None
    assert m.data(child, Qt.ItemDataRole.BackgroundRole) is None
    assert m.data(child, Qt.ItemDataRole.ForegroundRole) is None
    # the string "absent" cell still resolves to a state.
    absent = m.index(0, 3, grp_idx)
    assert m.data(absent, STATE_ROLE) == "absent"


# --- panel ------------------------------------------------------------------


def test_panel_loads_instances(qtbot):
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    assert panel._combo_a.count() == 2


def test_grid_columns_fill_width(qtbot):
    """REQ-391/429: both grids fill the available width. The existence grid's
    short location cells size to content; the detail grid's value cells STRETCH to
    share the viewport (REQ-429) so a long layout value cannot force horizontal
    scrolling. Neither auto-stretches its last section."""
    from PySide6.QtWidgets import QHeaderView
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    gh = panel._grid.horizontalHeader()
    assert gh.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert gh.sectionResizeMode(3) == QHeaderView.ResizeMode.ResizeToContents
    assert gh.stretchLastSection() is False
    th = panel._detail.header()
    # Every detail column stretches — the difference label and all three value
    # columns share the width, so the grid fits the window (REQ-429).
    assert th.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert th.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    assert th.sectionResizeMode(3) == QHeaderView.ResizeMode.Stretch
    assert th.stretchLastSection() is False
    # Overlong values elide rather than widen the column (REQ-429).
    assert panel._detail.textElideMode() == Qt.TextElideMode.ElideRight


def test_detail_model_tooltip_exposes_full_value(qapp):
    """REQ-429: an elided long value (and the row label) is recoverable on hover
    via the model's ToolTipRole, so nothing is lost when the column is narrow."""
    groups = [
        {"object_type": "layouts", "differing_count": 1, "rows": [
            {"member_type": "layout", "member_identifier": "LAY-002",
             "member_name": "detailLayout", "kind": "structure", "attribute": "rows",
             "design": ["name", "phone", "emailAddress", "billingAddress"],
             "instance_a": ["name"], "instance_b": "absent",
             "differs": True, "actionable": False},
        ]},
    ]
    m = EntityDetailModel(groups)
    grp_idx = m.index(0, 0, QModelIndex())
    val = m.index(0, 1, grp_idx)
    assert m.data(val, Qt.ItemDataRole.ToolTipRole) == "name, phone, emailAddress, billingAddress"
    label = m.index(0, 0, grp_idx)
    assert "detailLayout" in m.data(label, Qt.ItemDataRole.ToolTipRole)


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


def test_refresh_reloads_instances_after_engagement_active(qtbot):
    """REQ-431: the panel builds its combos at construction — before an engagement
    is active — so it can start empty. refresh() must reload the now-visible
    instances (and preserve any current selection), which is how the main window
    repopulates the selectors on engagement activation / navigation."""
    available: list[dict] = []  # no engagement active yet → no instances

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/instances":
            return httpx.Response(200, json=envelope_ok(available))
        return _handler(req)

    panel = ReconcileGridPanel(build_client(handler))
    qtbot.addWidget(panel)
    assert panel._combo_a.count() == 0  # empty at construction

    # Engagement becomes active → instances now visible; refresh() repopulates.
    available.extend(_INSTANCES)
    panel.refresh()
    assert panel._combo_a.count() == 2
    assert panel._combo_b.count() == 2

    # A selection survives a subsequent refresh when its instance persists.
    panel._combo_a.setCurrentIndex(1)
    keep = panel._combo_a.currentData()
    panel.refresh()
    assert panel._combo_a.currentData() == keep


def test_show_all_values_toggle_re_compares_and_lists_all_members(qtbot):
    """REQ-432: toggling 'Show all values' re-runs the comparison with
    include_unchanged and the detail drill then lists in-sync members too."""
    seen_flags: list[bool] = []
    # Differences-only payload: Account has one differing field; Contact in sync
    # (no group). All-values payload: Contact gains an in-sync presence row.
    diff_payload = _COMPARE
    all_payload = {
        **_COMPARE,
        "groups": _COMPARE["groups"] + [
            {"entity": "Contact", "entity_identifier": "ENT-002", "entity_label": None,
             "rows": [{"member_type": "field", "member_identifier": "FLD-9",
                       "member_name": "email", "kind": "presence", "attribute": None,
                       "design": "present", "instance_a": "present",
                       "instance_b": "present", "differs": False, "actionable": False}],
             "object_groups": [{"object_type": "fields", "differing_count": 0, "rows": [
                 {"member_type": "field", "member_identifier": "FLD-9",
                  "member_name": "email", "kind": "presence", "attribute": None,
                  "design": "present", "instance_a": "present",
                  "instance_b": "present", "differs": False, "actionable": False}]}]},
        ],
    }

    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/reconcile/compare":
            flag = req.url.params.get("include_unchanged") == "true"
            seen_flags.append(flag)
            return httpx.Response(200, json=envelope_ok(all_payload if flag else diff_payload))
        return _handler(req)

    panel = ReconcileGridPanel(build_client(handler))
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    assert seen_flags[-1] is False  # default differences-only

    # Drilling into the in-sync Contact in differences-only mode shows nothing.
    panel._drill(_EXISTENCE[1])
    assert panel._detail_model.rowCount() == 0

    # Toggle on → re-compares with include_unchanged → Contact now has a member.
    panel._show_all_check.setChecked(True)
    assert seen_flags[-1] is True
    panel._drill(_EXISTENCE[1])
    assert panel._detail_model.rowCount() == 1  # the in-sync fields group
    assert "all values" in panel._detail_title.text()


def test_reconcile_panel_is_recognized_as_refreshable(qtbot):
    """REQ-431: the main window drives refresh() on engagement switch/navigation
    only for pages it deems refreshable. The reconcile panel — a bare QWidget,
    not a ListDetailPanel — must qualify, while a plain widget must not."""
    from PySide6.QtWidgets import QWidget

    from crmbuilder_v2.ui.main_window import _is_refreshable

    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    assert _is_refreshable(panel) is True
    assert _is_refreshable(QWidget()) is False


# --- apply interaction ------------------------------------------------------


class _RecordingClient:
    """Wraps the mock client, recording reconcile capture/publish calls."""

    def __init__(self, inner):
        self._inner = inner
        self.captures: list[dict] = []
        self.publishes: list[dict] = []

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def reconcile_capture(self, **kw):
        self.captures.append(kw)
        return {"transaction": {"id": 1}}

    def reconcile_capture_setting(self, **kw):
        self.captures.append(kw)
        return {"transaction": {"id": 1}}

    def reconcile_publish(self, **kw):
        self.publishes.append(kw)
        return {"transaction": {"id": 2}}

    def audit_entity(self, identifier, entity_identifier):
        self.audits = getattr(self, "audits", [])
        self.audits.append((identifier, entity_identifier))
        return {"summary": {"entity": entity_identifier, "present": True}, "log": []}


def _apply_panel(qtbot):
    client = _RecordingClient(build_client(_handler))
    panel = ReconcileGridPanel(client)
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    panel._drill(_EXISTENCE[0])
    return panel, client


def test_apply_capture_from_instance_a_into_design(qtbot):
    panel, client = _apply_panel(qtbot)
    # select the single field difference row
    grp = panel._detail_model.index(0, 0)
    child = panel._detail_model.index(0, 0, grp)
    panel._detail.selectionModel().select(
        child, panel._detail.selectionModel().SelectionFlag.Select
    )
    # source = Instance A (index 1), target = Master design
    panel._source_combo.setCurrentIndex(1)
    panel._target_design.setChecked(True)
    panel._on_apply()
    assert len(client.captures) == 1
    assert client.captures[0]["field_identifier"] == "FLD-001"
    assert client.captures[0]["instance"] == "INST-001"


def test_apply_publish_design_to_instance_b(qtbot):
    panel, client = _apply_panel(qtbot)
    grp = panel._detail_model.index(0, 0)
    child = panel._detail_model.index(0, 0, grp)
    panel._detail.selectionModel().select(
        child, panel._detail.selectionModel().SelectionFlag.Select
    )
    # source = Master design (index 0); target = Instance B
    panel._source_combo.setCurrentIndex(0)
    panel._target_b.setChecked(True)
    panel._on_apply()
    assert len(client.publishes) == 1
    assert client.publishes[0]["instance"] == "INST-002"
    assert client.publishes[0]["member_type"] == "field"


_VIEW_ONLY_GROUPS = [
    {
        "entity": "Account", "entity_identifier": "ENT-001", "entity_label": None,
        "rows": [],
        "object_groups": [
            {"object_type": "other", "differing_count": 1, "rows": [
                {"member_type": "role", "member_identifier": "ROLE-1",
                 "member_name": "Sales Role", "kind": "attribute", "attribute": "role_scope",
                 "design": "x", "instance_a": "y", "instance_b": "x",
                 "differs": True, "actionable": False},
            ]},
        ],
    }
]


def test_view_only_item_explains_and_is_not_applied(qtbot, monkeypatch):
    """A non-actionable (view-only) difference: Apply stays available, but acting
    on it explains rather than writing anything (REQ-377)."""
    import crmbuilder_v2.ui.panels.reconcile_grid as mod
    seen: dict[str, str] = {}
    monkeypatch.setattr(
        mod.CopyableMessageBox, "information",
        classmethod(lambda cls, parent, title, text, *a, **k: seen.update(title=title, text=text)),
    )
    client = _RecordingClient(build_client(_handler))
    panel = ReconcileGridPanel(client)
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    # drill with a view-only group
    panel._groups_by_entity["ENT-001"] = _VIEW_ONLY_GROUPS[0]
    panel._drill(_EXISTENCE[0])
    grp = panel._detail_model.index(0, 0)
    child = panel._detail_model.index(0, 0, grp)
    panel._detail.selectionModel().select(
        child, panel._detail.selectionModel().SelectionFlag.Select
    )
    panel._source_combo.setCurrentIndex(1)
    panel._target_design.setChecked(True)
    panel._on_apply()
    assert client.captures == [] and client.publishes == []
    assert "Configure by hand" in seen.get("title", "")


def test_entity_audit_worker_audits_each_instance(qapp):
    """REQ-392: the worker re-audits the entity on each given instance."""
    from crmbuilder_v2.ui.panels.reconcile_grid import _EntityAuditWorker
    client = _RecordingClient(build_client(_handler))
    got = []
    w = _EntityAuditWorker(client, "ENT-001", ["INST-001", "INST-002"])
    w.done.connect(got.append)
    w.run()  # call synchronously (no thread) for a deterministic test
    assert client.audits == [("INST-001", "ENT-001"), ("INST-002", "ENT-001")]
    assert len(got) == 1 and len(got[0]) == 2


def test_reaudit_button_present(qtbot):
    from PySide6.QtWidgets import QPushButton
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    names = {b.objectName() for b in panel.findChildren(QPushButton)}
    assert "reconcile_reaudit_button" in names


def test_audit_done_and_failed_update_status(qtbot, monkeypatch):
    import crmbuilder_v2.ui.panels.reconcile_grid as mod
    monkeypatch.setattr(mod.CopyableMessageBox, "warning",
                        classmethod(lambda *a, **k: None))
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    panel._on_audit_done([{"instance": "INST-001", "result": {}}])
    assert "Re-audited" in panel._audit_status.text()
    panel._on_audit_failed("boom")
    assert "failed" in panel._audit_status.text().lower()


def test_history_tab_loads_transactions(qtbot):
    panel = ReconcileGridPanel(build_client(_handler))
    qtbot.addWidget(panel)
    # selecting the History tab loads the log
    panel._tabs.setCurrentIndex(1)
    assert panel._log_tree.topLevelItemCount() == 1
    assert panel._log_tree.topLevelItem(0).text(1) == "Pulled to design"


def test_promote_entity_publishes_to_checked_instances(qtbot):
    client = _RecordingClient(build_client(_handler))
    panel = ReconcileGridPanel(client)
    qtbot.addWidget(panel)
    panel._combo_a.setCurrentIndex(0)
    panel._combo_b.setCurrentIndex(1)
    panel._on_compare()
    # select a row and promote to Instance B; the handler must publish the
    # *selected* entity (independent of the grid's sort order)
    panel._grid.selectRow(0)
    proxy_idx = panel._grid.selectionModel().selectedRows()[0]
    src = panel._grid_proxy.mapToSource(proxy_idx)
    selected_eid = panel._grid_model.data(
        panel._grid_model.index(src.row(), 0), RECORD_ROLE
    )["entity_identifier"]
    panel._promote_b.setChecked(True)
    panel._on_promote_entity()
    assert len(client.publishes) == 1
    assert client.publishes[0]["member_type"] == "entity"
    assert client.publishes[0]["member_identifier"] == selected_eid
    assert client.publishes[0]["instance"] == "INST-002"
