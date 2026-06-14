"""PRJ-015 UI usability batch — tests.

Covers the eight enhancements REQ-131..138 / PI-172..179. Each section is
labelled with its requirement/PI. Built incrementally as the items land.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.panels import _governance_helpers as gh
from crmbuilder_v2.ui.panels.projects import ProjectsPanel
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit


@pytest.fixture
def api_client(v2_env) -> StorageClient:
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    sc.set_active_engagement("ENG-001")
    return sc


# ----------------------------------------------------------------------
# D — REQ-134 / PI-175: short read-only fields reveal full content on
# hover; project purpose wraps rather than truncating.
# ----------------------------------------------------------------------


def test_read_only_line_sets_full_value_tooltip(qapp):
    long = "x" * 300
    w = gh.read_only_line(long)
    assert w.toolTip() == long


def test_read_only_line_no_tooltip_when_empty(qapp):
    assert gh.read_only_line("").toolTip() == ""


def test_read_only_text_wraps_and_tooltips(qapp):
    long = "y" * 300
    w = gh.read_only_text(long)
    assert w.lineWrapMode() == QPlainTextEdit.LineWrapMode.WidgetWidth
    assert w.toolTip() == long


def _find(widget, cls):
    return widget.findChildren(cls)


def test_project_purpose_renders_as_wrapping_widget(qtbot, client_stub):
    panel = ProjectsPanel(client_stub)
    qtbot.addWidget(panel)
    purpose = "A purpose sentence that is quite a lot longer than one line " * 3
    record = {
        "project_identifier": "PRJ-999",
        "project_name": "Test",
        "project_status": "planned",
        "project_purpose": purpose,
        "project_description": "desc",
    }
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )
    qtbot.addWidget(detail)
    # The purpose value must live in a wrapping QPlainTextEdit (not a
    # single-line QLineEdit that would truncate it).
    plain_texts = [
        w.toPlainText() for w in _find(detail, QPlainTextEdit)
    ]
    assert purpose in plain_texts
    line_texts = [w.text() for w in _find(detail, QLineEdit)]
    assert purpose not in line_texts
