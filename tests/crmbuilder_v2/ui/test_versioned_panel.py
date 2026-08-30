"""Tests for the VersionedPanel base class.

Exercises the slice-E machinery shared by the Charter and Status
panels: synthetic ``_current_marker`` field, payload-as-form rendering,
and auto-select of the current version on first load.
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.base.versioned_panel import VersionedPanel
from PySide6.QtWidgets import QFormLayout, QLabel, QPlainTextEdit


class _FakeVersionedPanel(VersionedPanel):
    """Minimal subclass driven by an injected fetch impl (no client calls)."""

    def __init__(self, fetch_impl, parent=None):
        self._fetch_impl = fetch_impl
        super().__init__(client=None, parent=parent)

    def entity_title(self) -> str:
        return "Versioned"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._fetch_impl()


def _records():
    return [
        {
            "version": 2,
            "is_current": True,
            "created_at": "2026-05-01T12:00:00",
            "payload": {"scope": "v2 scope"},
        },
        {
            "version": 1,
            "is_current": False,
            "created_at": "2026-04-01T12:00:00",
            "payload": {"scope": "v1 scope"},
        },
    ]


def test_current_marker_is_set_correctly(qapp, qtbot):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=2000)

    assert panel._records[0]["_current_marker"] == "✓"
    assert panel._records[1]["_current_marker"] == ""


def test_render_detail_renders_payload_as_form(qapp, qtbot):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    qtbot.addWidget(panel)

    payload = {
        "name": "short",
        "long_text": "x" * 200,
        "items": [1, 2, 3],
        "config": {"a": 1},
    }
    rendered = panel._render_payload(payload)
    forms = rendered.findChildren(QFormLayout)
    assert len(forms) == 1
    form = forms[0]
    assert form.rowCount() == 4

    # Long string and structured values render as QPlainTextEdit;
    # short string renders as QLabel (the row's field widget).
    long_widgets = rendered.findChildren(QPlainTextEdit)
    # 3 long widgets: long_text, items, config.
    assert len(long_widgets) == 3

    # Assert the short string field is a QLabel containing the value.
    name_field = form.itemAt(0, QFormLayout.ItemRole.FieldRole).widget()
    assert isinstance(name_field, QLabel)
    assert "short" in name_field.text()


def test_default_selection_on_first_load_is_current_version(qapp, qtbot):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(
        lambda: panel._table.currentIndex().isValid()
        and panel._table.currentIndex().row() == 0,
        timeout=2000,
    )

    selected_record = panel._records[panel._table.currentIndex().row()]
    assert selected_record.get("is_current") is True
    assert panel._initial_select_done is True


def test_empty_payload_renders_placeholder(qapp, qtbot):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    qtbot.addWidget(panel)

    rendered = panel._render_payload({})
    labels = rendered.findChildren(QLabel)
    assert any("(empty payload)" in label.text() for label in labels)


# ----------------------------------------------------------------------
# Engagement row (PI-431 / REQ-525)
# ----------------------------------------------------------------------


class _FakeClient:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[str] = []

    def get_engagement(self, identifier: str) -> dict[str, Any]:
        self.calls.append(identifier)
        if self.fail:
            raise RuntimeError("boom")
        return {
            "engagement_identifier": identifier,
            "engagement_name": "CRMBuilder v2",
        }


def _engagement_text(widget) -> str:
    labels = [
        w for w in widget.findChildren(QLabel)
        if w.objectName() == "engagement_value_label"
    ]
    assert len(labels) == 1
    return labels[0].text()


def test_fetch_engagement_extra_resolves_name(qapp):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    client = _FakeClient()
    panel._client = client
    extras = panel.fetch_engagement_extra({"engagement_id": "ENG-001"})
    assert client.calls == ["ENG-001"]
    assert extras["engagement"]["engagement_name"] == "CRMBuilder v2"


def test_fetch_engagement_extra_swallows_lookup_failure(qapp):
    panel = _FakeVersionedPanel(fetch_impl=_records)
    panel._client = _FakeClient(fail=True)
    assert panel.fetch_engagement_extra({"engagement_id": "ENG-001"}) == {
        "engagement": None
    }


def test_engagement_section_shows_identifier_and_name(qapp, qtbot):
    record = {"version": 1, "engagement_id": "ENG-001"}
    extras = {"engagement": {"engagement_name": "CRMBuilder v2"}}
    widget = VersionedPanel.engagement_section(record, extras)
    qtbot.addWidget(widget)
    assert _engagement_text(widget) == "ENG-001 — CRMBuilder v2"


def test_engagement_section_falls_back_to_identifier(qapp, qtbot):
    widget = VersionedPanel.engagement_section(
        {"version": 1, "engagement_id": "ENG-001"}, {"engagement": None}
    )
    qtbot.addWidget(widget)
    assert _engagement_text(widget) == "ENG-001"


def test_charter_and_status_detail_render_engagement_row(qapp, qtbot):
    from crmbuilder_v2.ui.panels.charter import CharterPanel
    from crmbuilder_v2.ui.panels.status import StatusPanel

    record = {
        "version": 3,
        "is_current": True,
        "created_at": "2026-06-12T23:08:58",
        "payload": {"title": "CRMBuilder Charter"},
        "engagement_id": "ENG-001",
    }
    extras = {
        "references": {},
        "engagement": {"engagement_name": "CRMBuilder v2"},
    }
    for cls in (CharterPanel, StatusPanel):
        panel = cls(client=_FakeClient())
        qtbot.addWidget(panel)
        detail = panel.render_detail(record, extras)
        qtbot.addWidget(detail)
        assert _engagement_text(detail) == "ENG-001 — CRMBuilder v2"
