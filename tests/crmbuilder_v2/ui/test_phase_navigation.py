"""Phase-tab navigation (REQ-526 / PI-432, DEC-953).

Covers the acceptance summary of REQ-526: the default phase tab and its
three-group sidebar; per-tab state surviving a switch away and back; open
tabs remembered per engagement across a window restart; quick open by
identifier prefix and by panel name; Operate CRMBuilder appearing only when
opened; step markers being advisory (nothing disabled).
"""

from __future__ import annotations

import json

import httpx
import pytest
from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.navigation import (
    ALL_PANELS_GROUP_TITLE,
    DEFAULT_PHASE_STEPS,
    EVERY_SESSION_STEPS,
    OPERATE_KEY,
    PHASES,
    PhaseMap,
    split_identifier_prefix,
)
from crmbuilder_v2.ui.panel_registry import ALL_PANEL_LABELS, PANEL_REGISTRY
from crmbuilder_v2.ui.phase_page import PhasePage
from crmbuilder_v2.ui.quick_open import QuickOpenDialog
from crmbuilder_v2.ui.sidebar import Sidebar

from .conftest import build_client

_DECISIONS = [
    {
        "identifier": "DEC-001",
        "title": "Adopt phase tabs",
        "decision_date": "2026-08-30",
        "status": "Active",
        "superseded_by": None,
    },
    {
        "identifier": "DEC-002",
        "title": "Open on demand",
        "decision_date": "2026-08-30",
        "status": "Active",
        "superseded_by": None,
    },
]


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path.startswith("/decisions"):
        return httpx.Response(200, json={"data": _DECISIONS, "meta": {}, "errors": []})
    if request.url.path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    return httpx.Response(200, json={"data": [], "meta": {}, "errors": []})


@pytest.fixture
def client(qapp):
    return build_client(_handler)


@pytest.fixture
def window(qapp, qtbot, lifecycle_stub, client, tmp_path):
    w = MainWindow(
        lifecycle=lifecycle_stub,
        client=client,
        tab_state_path=tmp_path / "tabs.json",
    )
    qtbot.addWidget(w)
    return w


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


def test_phase_map_steps_are_registered_panels():
    for key, steps in DEFAULT_PHASE_STEPS.items():
        assert steps, key
        for label in steps:
            assert label in PANEL_REGISTRY, (key, label)
    for label in EVERY_SESSION_STEPS:
        assert label in PANEL_REGISTRY


def test_phases_are_in_prd_order_with_operate_last():
    numbers = [p.number for p in PHASES if p.number]
    assert numbers == ["1", "1.5", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13"]
    assert PHASES[-1].key == OPERATE_KEY


def test_sidebar_groups_for_a_phase():
    groups = PhaseMap().sidebar_groups("13", ALL_PANEL_LABELS)
    assert groups[0][0] == "Every session"
    assert groups[1] == ("Phase 13 steps", DEFAULT_PHASE_STEPS["13"])
    assert groups[2][0] == ALL_PANELS_GROUP_TITLE
    assert groups[2][1] == tuple(sorted(ALL_PANEL_LABELS))


def test_all_panels_index_is_alphabetical_and_complete():
    assert list(ALL_PANEL_LABELS) == sorted(ALL_PANEL_LABELS)
    assert set(ALL_PANEL_LABELS) == set(PANEL_REGISTRY)


def test_split_identifier_prefix():
    assert split_identifier_prefix("req-52") == ("REQ", "REQ-52")
    assert split_identifier_prefix("REQ-") == ("REQ", "REQ-")
    assert split_identifier_prefix("deploy") is None
    assert split_identifier_prefix("REQ-5x") is None


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def test_sidebar_numbers_steps_and_collapses_all_panels(qtbot):
    groups = PhaseMap().sidebar_groups("1", ALL_PANEL_LABELS)
    sidebar = Sidebar(
        groups,
        numbered_groups=("Phase 1 steps",),
        collapsed_groups=(ALL_PANELS_GROUP_TITLE,),
    )
    qtbot.addWidget(sidebar)
    assert sidebar.step_labels() == DEFAULT_PHASE_STEPS["1"]
    assert sidebar.is_group_collapsed(ALL_PANELS_GROUP_TITLE)
    # Collapsed group's entries are hidden; the step entries are visible
    # (a step that is also in the index has a visible step row first).
    assert sidebar._entry_for_label("Cost").isHidden()
    assert not sidebar._entry_for_label("Charter").isHidden()
    # Selecting a hidden All-panels entry expands the group.
    sidebar.select_entry("Cost")
    assert sidebar.current_text() == "Cost"
    assert not sidebar.is_group_collapsed(ALL_PANELS_GROUP_TITLE)


def test_sidebar_step_markers_round_trip(qtbot):
    groups = PhaseMap().sidebar_groups("1", ALL_PANEL_LABELS)
    sidebar = Sidebar(groups, numbered_groups=("Phase 1 steps",))
    qtbot.addWidget(sidebar)
    sidebar.set_step_marker("Charter", "done")
    sidebar.set_step_marker("Personas", "next")
    assert sidebar.step_marker("Charter") == "done"
    assert sidebar.step_marker("Personas") == "next"
    assert sidebar.step_marker("Domains") is None


# ---------------------------------------------------------------------------
# Window: tabs
# ---------------------------------------------------------------------------


def test_window_opens_on_default_phase_with_chat_pinned(window):
    assert window._tabs.tabText(0) == "Chat"
    assert window.open_phase_keys() == ["1"]
    assert window.current_phase_key() == "1"
    assert window._sidebar.current_text() == "Charter"
    # Operate CRMBuilder is not on screen until opened.
    assert OPERATE_KEY not in window.open_phase_keys()


def test_open_phase_inserts_in_prd_order_and_persists(window, tmp_path):
    window.open_phase("13")
    window.open_phase("3")
    assert window.open_phase_keys() == ["1", "3", "13"]
    assert window.current_phase_key() == "3"
    saved = json.loads((tmp_path / "tabs.json").read_text())
    assert saved["_no_engagement"] == {"open": ["1", "3", "13"], "current": "3"}


def test_tab_keeps_its_place_across_a_switch(window, qtbot):
    page1 = window.page_for_phase("1")
    window._lifecycle_ready = True
    window._go_to("Decisions", "DEC-002")
    decisions = page1.panel_for("Decisions")
    qtbot.waitUntil(lambda: decisions._currently_selected_identifier() == "DEC-002")
    assert page1.current_entry() == "Decisions"

    window.open_phase("13")
    assert window.current_phase_key() == "13"
    assert window._sidebar.current_text() == "Reconcile"

    window._tabs.setCurrentWidget(page1)
    assert window.current_phase_key() == "1"
    assert window._sidebar.current_text() == "Decisions"
    assert page1.panel_for("Decisions")._currently_selected_identifier() == "DEC-002"


def test_last_phase_tab_cannot_be_closed(window):
    assert window.close_phase("1") is False
    window.open_phase("2")
    assert window.close_phase("1") is True
    assert window.open_phase_keys() == ["2"]


def test_remembered_tabs_restore_on_a_new_window(qapp, qtbot, lifecycle_stub, client, tmp_path):
    first = MainWindow(lifecycle=lifecycle_stub, client=client, tab_state_path=tmp_path / "t.json")
    qtbot.addWidget(first)
    first.open_phase("11")
    first.open_phase(OPERATE_KEY)
    first._tabs.setCurrentWidget(first.page_for_phase("11"))

    second = MainWindow(lifecycle=lifecycle_stub, client=client, tab_state_path=tmp_path / "t.json")
    qtbot.addWidget(second)
    assert second.open_phase_keys() == ["1", "11", OPERATE_KEY]
    assert second.current_phase_key() == "11"


def test_chat_entry_switches_to_pinned_chat_tab(window):
    window._sidebar.select_entry("Chat")
    assert window._tabs.currentIndex() == 0
    # The compatibility accessors still address the last phase page.
    assert isinstance(window._current_phase_page(), PhasePage)


def test_step_markers_derive_from_record_counts(window, qtbot):
    page = window.open_phase("4")  # steps start with Requirements (empty stub)
    window._lifecycle_ready = True
    window._load_step_counts(page)
    qtbot.waitUntil(lambda: "Requirements" in page.record_counts())
    assert page.sidebar.step_marker("Requirements") == "next"
    # A panel whose fetch fails (or is not a list panel) simply carries no
    # marker — it never blocks the checklist.
    assert page.sidebar.step_marker("Processes") in (None, "done", "next")
    # Advisory only — every step entry stays selectable and enabled.
    from PySide6.QtCore import Qt  # noqa: PLC0415

    for r in range(page.sidebar.count()):
        assert bool(page.sidebar.item(r).flags() & Qt.ItemFlag.ItemIsEnabled)


# ---------------------------------------------------------------------------
# Quick open
# ---------------------------------------------------------------------------


def test_quick_open_matches_panels_by_name(window, qtbot):
    from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL

    dialog = QuickOpenDialog(
        entity_type_to_label=ENTITY_TYPE_TO_SIDEBAR_LABEL,
        panel_provider=lambda label: None,
        parent=window,
    )
    qtbot.addWidget(dialog)
    dialog.set_query("dep")
    dialog._run_query()
    labels = [label for kind, label, _ in dialog.results() if kind == "panel"]
    assert "Deploy History" in labels
    assert "Deposit Events" in labels
    assert "Charter" not in labels


def test_quick_open_finds_records_by_identifier_prefix(window, qtbot):
    from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL

    page = window._current_phase_page()
    dialog = QuickOpenDialog(
        entity_type_to_label=ENTITY_TYPE_TO_SIDEBAR_LABEL,
        panel_provider=lambda label: page.ensure_panel(label),
        parent=window,
    )
    qtbot.addWidget(dialog)
    dialog.set_query("DEC-00")
    dialog._run_query()
    qtbot.waitUntil(
        lambda: any(kind == "record" for kind, _l, _i in dialog.results())
    )
    records = [(label, ident) for kind, label, ident in dialog.results() if kind == "record"]
    assert ("Decisions", "DEC-001") in records
    assert ("Decisions", "DEC-002") in records

    opened = []
    dialog.open_requested.connect(lambda label, ident: opened.append((label, ident)))
    dialog._results.setCurrentRow(len(dialog.results()) - 1)
    dialog._open_current()
    assert opened == [("Decisions", "DEC-002")]


def test_quick_open_result_navigates_current_tab(window, qtbot):
    window._lifecycle_ready = True
    window._on_quick_open_requested("Decisions", "DEC-001")
    assert window._sidebar.current_text() == "Decisions"
    panel = window._current_phase_page().panel_for("Decisions")
    qtbot.waitUntil(lambda: panel._currently_selected_identifier() == "DEC-001")
