"""Per-panel parity tests for the v0.3 ``ListDetailPanel`` factory refactor.

DEC-035 introduced two factory methods on ``ListDetailPanel``:
``_create_master_widget`` (default ``QTableView``) and
``_build_context_menu`` (default empty ``QMenu``). These tests assert,
for every panel class, the master-widget type matches expectations and
the context-menu factory returns a ``QMenu``. They catch the dominant
regression class — silently using the wrong widget type — without
re-checking behavior that v0.2's 458-test net already covers.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.ui.panels.charter import CharterPanel
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.panels.status import StatusPanel
from crmbuilder_v2.ui.panels.topics import TopicsPanel
from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QMenu, QTableView, QTreeView

# Every panel except TopicsPanel uses QTableView. TopicsPanel uses
# QTreeView for its hierarchy. ReferencesPanel is list-only
# (``_has_detail_pane = False``) but still uses QTableView.
_TABLE_PANELS = [
    CharterPanel,
    DecisionsPanel,
    PlanningItemsPanel,
    ReferencesPanel,
    RisksPanel,
    SessionsPanel,
    StatusPanel,
]


@pytest.mark.parametrize("panel_cls", _TABLE_PANELS)
def test_table_panel_master_widget_is_qtableview(qtbot, client_stub, panel_cls):
    panel = panel_cls(client=client_stub)
    qtbot.addWidget(panel)
    assert isinstance(panel._master_view, QTableView)
    # The backwards-compat alias is preserved for subclasses and tests
    # that reference ``self._table`` directly.
    assert panel._table is panel._master_view


def test_topics_panel_master_widget_is_qtreeview(qtbot, client_stub):
    panel = TopicsPanel(client=client_stub)
    qtbot.addWidget(panel)
    assert isinstance(panel._master_view, QTreeView)
    assert panel._table is panel._master_view


_ALL_PANELS = _TABLE_PANELS + [TopicsPanel]


@pytest.mark.parametrize("panel_cls", _ALL_PANELS)
def test_panel_context_menu_factory_returns_qmenu(qtbot, client_stub, panel_cls):
    panel = panel_cls(client=client_stub)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu(QModelIndex())
    assert isinstance(menu, QMenu)
    # The default empty menu has no actions; slice B will populate per
    # panel. The factory contract is the empty-menu return.
    assert menu.actions() == []
