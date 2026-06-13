"""End-to-end "Open <item type>" integration tests (PI-121 / WTK-081).

The per-layer suites already cover the pieces in isolation:

* ``test_context_menus`` / ``test_references_section`` — the grid's per-row
  "Open <Pretty Type>" action sits alongside "Go to" and emits the distinct
  ``open_requested`` signal, labeled per row item type.
* ``test_detail_window_manager`` — the manager spawns a non-modal, persistent
  window per request and tracks any number of them, but over a *stub* panel
  factory.

What no existing test exercises is the **whole chain wired through a real**
:class:`MainWindow` **and the real** ``build_panel`` **factory**: a grid's
"Open Session" → ``ReferencesSection.open_requested`` → (bubbled by
``ListDetailPanel._wire_link_section``) ``panel.open_requested`` →
``MainWindow._on_open_requested`` → ``DetailWindowManager.open`` → a live
:class:`StandaloneDetailWindow` hosting a factory-built, pre-selected
``SessionsPanel``. These tests close that gap, asserting the WTK-078 design
criteria against the integrated runtime:

* C2 — invoking the action spawns a separate, non-modal detail window that
  renders the related record's full view via the reused ``ListDetailPanel``.
* C3 — multiple such windows coexist independently, the originating view
  stays exactly where it was, and there is no artificial concurrency limit.
* C4 (regression) — "Open" pulls the record up beside the main window without
  swapping its current panel; it is *not* the in-place "Go to" navigation.
"""

from __future__ import annotations

import httpx
import pytest
from crmbuilder_v2.ui.detail_window_manager import StandaloneDetailWindow
from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

from .conftest import build_client


def _make_handler():
    """Serve one decision (DEC-018) that is ``decided_in`` SES-004.

    The decision's detail pane therefore renders a ``ReferencesSection`` with a
    single outbound row to the session — the row whose "Open Session" action
    drives the chain under test. ``/sessions`` is served so the spawned
    standalone ``SessionsPanel`` can load + pre-select SES-004.
    """
    decisions_payload = [
        {
            "identifier": "DEC-018",
            "title": "Test decision",
            "decision_date": "2026-05-07",
            "status": "Active",
            "context": "ctx",
            "decision": "dec",
            "rationale": "rat",
            "alternatives_considered": "alt",
            "consequences": "cons",
            "supersedes_identifier": None,
            "superseded_by_identifier": None,
        }
    ]
    sessions_payload = [
        {
            "session_identifier": "SES-004",
            "session_title": "Storage v0.1 build",
            "session_description": "Storage v0.1 build session",
            "session_medium": "chat",
            "session_executive_summary": (
                "A realistically shaped session record so the spawned "
                "standalone SessionsPanel has a row to pre-select and render."
            ),
            "session_status": "complete",
            "session_notes": "notes",
            "session_participants": [],
            "session_medium_metadata": {},
            "session_deleted_at": None,
        }
    ]
    refs_for_decision = {
        "as_source": [
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "session",
                "target_id": "SES-004",
                "relationship": "decided_in",
            }
        ],
        "as_target": [],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        method = request.method
        path = request.url.path
        if method == "GET" and path == "/decisions":
            return httpx.Response(
                200, json={"data": decisions_payload, "meta": {}, "errors": None}
            )
        if method == "GET" and path == "/sessions":
            return httpx.Response(
                200, json={"data": sessions_payload, "meta": {}, "errors": None}
            )
        if method == "GET" and path == "/risks":
            return httpx.Response(
                200, json={"data": [], "meta": {}, "errors": None}
            )
        if method == "GET" and path.startswith("/references/touching/"):
            payload = (
                refs_for_decision
                if path.endswith("/decision/DEC-018")
                else {"as_source": [], "as_target": []}
            )
            return httpx.Response(
                200, json={"data": payload, "meta": {}, "errors": None}
            )
        return httpx.Response(
            404,
            json={
                "data": None,
                "meta": {},
                "errors": [{"code": "not_found", "message": "no route"}],
            },
        )

    return handler


@pytest.fixture
def open_window(qapp, qtbot, lifecycle_stub):
    client = build_client(_make_handler())
    window = MainWindow(lifecycle=lifecycle_stub, client=client)
    qtbot.addWidget(window)
    return window


def _decisions_panel(window: MainWindow) -> DecisionsPanel:
    return window._stack.widget(window._pages_by_entry["Decisions"])


def _section_with_ses004(detail_widget) -> ReferencesSection:
    """The detail pane's ``ReferencesSection`` (the SES-004 reference grid)."""
    section = detail_widget.findChild(ReferencesSection)
    assert section is not None, "expected a ReferencesSection in the detail pane"
    return section


def _trigger_open_on_session_row(section: ReferencesSection) -> None:
    """Build the SES-004 row's right-click menu and trigger "Open Session".

    Mirrors the real interaction (build the per-row menu the grid would show,
    fire the additive "Open <Pretty Type>" entry) so the test drives the
    grid's wiring rather than reaching past it into the manager.
    """
    proxy = section._proxy
    row = None
    for r in range(proxy.rowCount()):
        candidate = section._row_at(proxy.index(r, 0))
        if candidate and candidate.get("other_id") == "SES-004":
            row = candidate
            break
    assert row is not None, "no references-grid row for SES-004"
    menu = section._build_row_menu(section._table, row)
    open_action = next(
        a for a in menu.actions() if a.text() == "Open Session"
    )
    open_action.trigger()


def _load_decision_detail(qtbot, panel: DecisionsPanel) -> object:
    """Refresh, select DEC-018, and return its fully-rendered detail widget."""
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=2000)
    panel.select_record_by_identifier("DEC-018")
    qtbot.waitUntil(
        lambda: panel._detail_stack.currentWidget()
        not in (panel._loading_detail, panel._empty_detail),
        timeout=2000,
    )
    return panel._detail_stack.currentWidget()


def _drain_and_close(qtbot, window: MainWindow) -> None:
    """Drain each spawned panel's detail worker, then close the windows.

    The standalone ``SessionsPanel`` fires a fetch + pre-select worker on
    spawn; close each window (its ``closeEvent`` drains the panel's workers)
    so teardown is free of the worker-thread GC hazard.
    """
    manager = window._detail_window_manager
    for spawned in list(manager.open_windows):
        qtbot.addWidget(spawned)
        spawned.close()
    qtbot.waitUntil(lambda: manager.open_windows == [], timeout=2000)


def test_open_action_spawns_real_detail_window_through_main_window(
    qapp, qtbot, open_window
):
    """C2: the grid's "Open Session" spawns a real non-modal SessionsPanel window.

    Exercises the full chain through a real ``MainWindow`` and the real
    ``build_panel`` factory — not a stub — so the window content is the
    reused ``ListDetailPanel`` (a ``SessionsPanel``) pre-selected to SES-004.
    """
    panel = _decisions_panel(open_window)
    section = _section_with_ses004(_load_decision_detail(qtbot, panel))

    manager = open_window._detail_window_manager
    assert manager.open_windows == []
    _trigger_open_on_session_row(section)
    qtbot.waitUntil(lambda: len(manager.open_windows) == 1, timeout=2000)

    spawned = manager.open_windows[0]
    assert isinstance(spawned, StandaloneDetailWindow)
    # Non-modal + the related record's full view via the reused panel.
    assert spawned.isVisible()
    assert spawned.isModal() is False
    assert isinstance(spawned.panel, SessionsPanel)
    assert spawned.windowTitle() == "Session SES-004"

    _drain_and_close(qtbot, open_window)


def test_open_leaves_originating_view_in_place(qapp, qtbot, open_window):
    """C3/C4: "Open" pulls the record up beside the main window, not over it.

    The main window's current page must stay on Decisions (the originating
    view) — "Open" is the standalone-window path, distinct from "Go to"'s
    in-place ``navigate_requested`` panel swap.
    """
    panel = _decisions_panel(open_window)
    open_window._sidebar.select_entry("Decisions")
    section = _section_with_ses004(_load_decision_detail(qtbot, panel))

    decisions_index = open_window._pages_by_entry["Decisions"]
    assert open_window._stack.currentIndex() == decisions_index

    _trigger_open_on_session_row(section)
    qtbot.waitUntil(
        lambda: len(open_window._detail_window_manager.open_windows) == 1,
        timeout=2000,
    )

    # The originating view is untouched: same page, still visible/selected.
    assert open_window._stack.currentIndex() == decisions_index
    assert open_window._sidebar.currentItem().text() == "Decisions"
    assert panel._detail_stack.currentWidget() not in (
        panel._loading_detail,
        panel._empty_detail,
    )

    _drain_and_close(qtbot, open_window)


def test_multiple_open_windows_coexist_with_no_cap(qapp, qtbot, open_window):
    """C3: many standalone windows coexist independently; there is no cap.

    Drives the real panel signal ``MainWindow`` listens to (``open_requested``,
    the same signal the grid bubbles) several times for distinct sessions; all
    windows stay live and tracked, well past any small fixed limit.
    """
    panel = _decisions_panel(open_window)
    manager = open_window._detail_window_manager

    spawn_count = 5
    for n in range(spawn_count):
        panel.open_requested.emit("session", f"SES-0{n:02d}")
        qtbot.waitUntil(
            lambda n=n: len(manager.open_windows) == n + 1, timeout=2000
        )

    assert len(manager.open_windows) == spawn_count
    assert all(w.isVisible() for w in manager.open_windows)
    # Independently positioned (cascade offset), not stacked on one spot.
    positions = {(w.pos().x(), w.pos().y()) for w in manager.open_windows}
    assert len(positions) == spawn_count

    _drain_and_close(qtbot, open_window)


def test_window_close_drains_panel_workers(qapp, qtbot):
    """Regression (PI-121 teardown SIGABRT): closing the top-level window must
    drain the hosted panel's worker threads. Qt does not deliver ``closeEvent``
    to a window's child widgets, so the window's ``closeEvent`` must call the
    panel's ``drain_workers`` explicitly — otherwise ``WA_DeleteOnClose`` deletes
    the panel while a worker QThread is live, aborting the process (the flaky
    crash that surfaced running the full suite in one process).
    """
    from PySide6.QtWidgets import QWidget

    class _DrainSpyPanel(QWidget):
        def __init__(self):
            super().__init__()
            self.drained = False

        def drain_workers(self):
            self.drained = True

    panel = _DrainSpyPanel()
    window = StandaloneDetailWindow(panel, "Spy")
    qtbot.addWidget(window)
    window.show()
    window.close()
    assert panel.drained is True
