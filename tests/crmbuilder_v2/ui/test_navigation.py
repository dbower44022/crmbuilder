"""End-to-end cross-panel navigation tests for slice D.

A click on a "Decided in: SES-X" link in the Decisions detail pane
should switch the sidebar to Sessions and select the SES-X row in the
SessionsPanel.
"""

from __future__ import annotations

import httpx
import pytest
from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.sessions import SessionsPanel

from .conftest import build_client


def _navigate_via_refs_grid(detail_widget, target_id: str) -> None:
    """Double-click the references-grid row whose Identifier == target_id.

    PRJ-015: ReferencesSection renders a grid; navigation is via row
    double-click (wired to ``navigate_requested``) rather than a QLabel
    link. The Identifier column is index 2.
    """
    from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

    section = detail_widget.findChild(ReferencesSection)
    assert section is not None, "expected a ReferencesSection in the detail pane"
    proxy = section._proxy
    for row in range(proxy.rowCount()):
        if proxy.data(proxy.index(row, 2)) == target_id:
            section._table.doubleClicked.emit(proxy.index(row, 0))
            return
    raise AssertionError(f"no references-grid row for {target_id}")


def _make_handler():
    # Three decisions so DEC-018 is NOT at row 0; this is what makes a
    # post-refresh "Qt auto-selects row 0" or "selection cleared" path
    # observable as a regression. With one decision the bug is masked
    # because row 0 happens to be the right answer either way.
    decisions_payload = [
        {
            "identifier": "DEC-001",
            "title": "First decision",
            "decision_date": "2026-05-07",
            "status": "Active",
            "context": "ctx",
            "decision": "dec",
            "rationale": "rat",
            "alternatives_considered": "alt",
            "consequences": "cons",
            "supersedes_identifier": None,
            "superseded_by_identifier": None,
        },
        {
            "identifier": "DEC-002",
            "title": "Second decision",
            "decision_date": "2026-05-07",
            "status": "Active",
            "context": "ctx",
            "decision": "dec",
            "rationale": "rat",
            "alternatives_considered": "alt",
            "consequences": "cons",
            "supersedes_identifier": None,
            "superseded_by_identifier": None,
        },
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
        },
    ]
    sessions_payload = [
        {
            "session_identifier": "SES-004",
            "session_title": "Storage v0.1 build",
            "session_description": "Storage v0.1 build session",
            "session_medium": "chat",
            "session_executive_summary": (
                "This session built storage v0.1: the structured database, "
                "access layer, and governance entities that make the project "
                "queryable; it is captured here purely so the cross-panel "
                "navigation regression net exercises a realistically shaped "
                "session record under the PI-073 medium-agnostic data model."
            ),
            "session_status": "complete",
            "session_notes": "notes",
            "session_participants": [],
            "session_medium_metadata": {},
            "session_deleted_at": None,
        }
    ]
    refs_for_decision = {
        "as_source": [],
        "as_target": [
            {
                "source_type": "session",
                "source_id": "SES-004",
                "target_type": "decision",
                "target_id": "DEC-018",
                "relationship": "decided_in",
            }
        ],
    }
    refs_for_session = {
        "as_source": [
            {
                "source_type": "session",
                "source_id": "SES-004",
                "target_type": "decision",
                "target_id": "DEC-018",
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
                200,
                json={"data": decisions_payload, "meta": {}, "errors": None},
            )
        if method == "GET" and path == "/sessions":
            return httpx.Response(
                200,
                json={"data": sessions_payload, "meta": {}, "errors": None},
            )
        if method == "GET" and path == "/risks":
            return httpx.Response(
                200, json={"data": [], "meta": {}, "errors": None}
            )
        if (
            method == "GET"
            and path == "/references/touching/decision/DEC-018"
        ):
            return httpx.Response(
                200,
                json={"data": refs_for_decision, "meta": {}, "errors": None},
            )
        if (
            method == "GET"
            and path == "/references/touching/session/SES-004"
        ):
            return httpx.Response(
                200,
                json={"data": refs_for_session, "meta": {}, "errors": None},
            )
        if method == "GET" and path.startswith("/references/touching/"):
            return httpx.Response(
                200,
                json={
                    "data": {"as_source": [], "as_target": []},
                    "meta": {},
                    "errors": None,
                },
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
def navigation_window(qapp, qtbot, lifecycle_stub):
    client = build_client(_make_handler())
    window = MainWindow(lifecycle=lifecycle_stub, client=client)
    qtbot.addWidget(window)
    return window


def test_decision_to_session_link_navigates(qapp, qtbot, navigation_window):
    decisions_panel: DecisionsPanel = navigation_window._stack.widget(
        navigation_window._pages_by_entry["Decisions"]
    )
    sessions_panel: SessionsPanel = navigation_window._stack.widget(
        navigation_window._pages_by_entry["Sessions"]
    )

    # Trigger initial load on the visible Decisions panel.
    decisions_panel.refresh()
    qtbot.waitUntil(
        lambda: decisions_panel._model.rowCount() == 3, timeout=2000
    )

    # DEC-018 (the one with references) is at row 2 in this fixture.
    decisions_panel.select_record_by_identifier("DEC-018")
    qtbot.waitUntil(
        lambda: decisions_panel._detail_stack.currentWidget()
        is not decisions_panel._loading_detail
        and decisions_panel._detail_stack.currentWidget()
        is not decisions_panel._empty_detail,
        timeout=2000,
    )

    # Find the SES-004 link in the rendered detail. The v0.2
    # ReferencesSection widget renders each reference as its own QLabel
    # with an `<a href="session:SES-004">` anchor; locate it by the href
    # rather than by free-text co-occurrence with the relationship name
    # (which is rendered in a separate group-header label).
    detail_widget = decisions_panel._detail_stack.currentWidget()
    # Drive navigation by double-clicking the SES-004 row in the grid
    # (offscreen Qt doesn't hit-test, so we emit the view signal directly).
    _navigate_via_refs_grid(detail_widget, "SES-004")

    qtbot.waitUntil(
        lambda: navigation_window._sidebar.currentItem()
        and navigation_window._sidebar.currentItem().text() == "Sessions",
        timeout=2000,
    )
    qtbot.waitUntil(
        lambda: sessions_panel._model.rowCount() == 1
        and sessions_panel._table.currentIndex().isValid()
        and sessions_panel._table.currentIndex().row() == 0,
        timeout=2000,
    )
    # Drain the detail-extras worker on the sessions panel before teardown.
    qtbot.waitUntil(
        lambda: sessions_panel._detail_stack.currentWidget()
        is not sessions_panel._loading_detail,
        timeout=2000,
    )


def test_session_to_decision_link_navigates_when_decisions_visited_first(
    qapp, qtbot, navigation_window
):
    """Cross-panel navigation must survive the post-refresh path.

    Bug surfaced during slice E acceptance walk: when the target panel
    has been visited before (its records are cached), clicking a link
    elsewhere triggers two refreshes — one from the sidebar selection,
    one from select_record_by_identifier's pending-or-refresh fallback —
    and the second refresh's _on_fetch_success would call set_records
    + _show_empty_detail and blow away the synchronously-selected row.
    The fix: _on_fetch_success preserves the prior selection (or honors
    pending) instead of unconditionally clearing the detail pane.
    """
    decisions_panel: DecisionsPanel = navigation_window._stack.widget(
        navigation_window._pages_by_entry["Decisions"]
    )
    sessions_panel: SessionsPanel = navigation_window._stack.widget(
        navigation_window._pages_by_entry["Sessions"]
    )

    # Mark the lifecycle ready so _on_sidebar_selected actually calls
    # page.refresh() during cross-panel navigation. Without this, the
    # sidebar-driven refresh is gated off and the bug doesn't reproduce
    # in tests (the live app always has _lifecycle_ready=True after
    # the API probe completes).
    navigation_window._lifecycle_ready = True

    # Visit Decisions first so its records are cached, but DO NOT
    # select any row. The bug surfaces specifically when the cached
    # records let select_record_by_identifier select synchronously
    # while the sidebar's refresh is concurrently in flight; the
    # synchronous selection then races with the post-refresh model
    # reset. Selecting DEC-018 here would mask the bug because Qt
    # auto-preserves the prior current-index across model resets.
    decisions_panel.refresh()
    qtbot.waitUntil(
        lambda: decisions_panel._model.rowCount() == 3, timeout=2000
    )
    # Briefly select-then-deselect a different row so the model has a
    # concrete prior-current of row 0 (DEC-001), which Qt will try to
    # restore across the post-refresh model reset. This is what makes
    # the regression bite — pre-fix the panel ends on DEC-001 rather
    # than the synchronously-targeted DEC-018.
    decisions_panel._select_row(0)
    qtbot.waitUntil(
        lambda: decisions_panel._detail_stack.currentWidget()
        is not decisions_panel._loading_detail
        and decisions_panel._detail_stack.currentWidget()
        is not decisions_panel._empty_detail,
        timeout=2000,
    )

    # Move to Sessions and open SES-004.
    sessions_panel.refresh()
    qtbot.waitUntil(
        lambda: sessions_panel._model.rowCount() == 1, timeout=2000
    )
    sessions_panel._select_row(0)
    qtbot.waitUntil(
        lambda: sessions_panel._detail_stack.currentWidget()
        is not sessions_panel._loading_detail
        and sessions_panel._detail_stack.currentWidget()
        is not sessions_panel._empty_detail,
        timeout=2000,
    )

    # Locate the decided_in DEC-018 link in the rendered detail.
    detail_widget = sessions_panel._detail_stack.currentWidget()
    _navigate_via_refs_grid(detail_widget, "DEC-018")

    qtbot.waitUntil(
        lambda: navigation_window._sidebar.currentItem()
        and navigation_window._sidebar.currentItem().text() == "Decisions",
        timeout=2000,
    )

    # Wait for the navigation-triggered refresh to FULLY complete — the
    # status label leaves "Loading…" only after _on_fetch_success has
    # run set_records + post-refresh selection logic. This ensures we
    # observe the post-refresh state, not the transient pre-completion
    # state where the synchronously-set selection still appears valid.
    qtbot.waitUntil(
        lambda: decisions_panel._status_label.text() == "3 records",
        timeout=2000,
    )
    # Drain a couple more event loop turns so any queued signals from
    # the model-reset propagate before we check state.
    qtbot.wait(50)

    # Critical: the selected row must be DEC-018 (row 2), not a
    # different row that Qt auto-selected after the model reset.
    # Pre-fix, _on_fetch_success would call set_records + _show_empty_detail
    # which on Qt 6 leaves the QTableView's currentIndex pinned to row 0
    # (the first decision), or invalid — never the synchronously-selected
    # DEC-018 at row 2. The fix re-applies the prior selection if the
    # identifier still exists in the new dataset.
    current = decisions_panel._table.currentIndex()
    assert current.isValid(), (
        "decision row was deselected by the post-refresh path"
    )
    selected_record = decisions_panel._records[current.row()]
    assert selected_record["identifier"] == "DEC-018", (
        f"expected DEC-018 selected, got "
        f"{selected_record['identifier']} at row {current.row()}"
    )
    assert (
        decisions_panel._detail_stack.currentWidget()
        is not decisions_panel._empty_detail
    ), "detail pane was reset to empty by the post-refresh path"

    # Drain the detail-extras worker before teardown.
    qtbot.waitUntil(
        lambda: decisions_panel._detail_stack.currentWidget()
        is not decisions_panel._loading_detail,
        timeout=2000,
    )
