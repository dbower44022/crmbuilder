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
from PySide6.QtWidgets import QLabel

from .conftest import build_client


def _make_handler():
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
            "identifier": "SES-004",
            "title": "Storage v0.1 build",
            "session_date": "2026-05-07",
            "status": "Closed",
            "topics_covered": "everything",
            "summary": "summary",
            "artifacts_produced": "artifacts",
            "in_flight_at_end": "none",
            "conversation_reference": "conv-ref",
        }
    ]
    references_payload = {
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
                json={"data": references_payload, "meta": {}, "errors": None},
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
        lambda: decisions_panel._model.rowCount() == 1, timeout=2000
    )

    decisions_panel._select_row(0)
    qtbot.waitUntil(
        lambda: decisions_panel._detail_stack.currentWidget()
        is not decisions_panel._loading_detail
        and decisions_panel._detail_stack.currentWidget()
        is not decisions_panel._empty_detail,
        timeout=2000,
    )

    # Find the "Decided in" link in the rendered detail.
    detail_widget = decisions_panel._detail_stack.currentWidget()
    link_label = None
    for label in detail_widget.findChildren(QLabel):
        text = label.text() or ""
        if "Decided in" in text and "SES-004" in text:
            link_label = label
            break
    assert link_label is not None, "expected a Decided-in link to SES-004"

    # Simulate the click via the linkActivated signal (offscreen Qt
    # platform doesn't render or hit-test, so we drive the signal
    # directly).
    link_label.linkActivated.emit("session:SES-004")

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
