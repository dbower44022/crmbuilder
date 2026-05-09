"""Tests for ReferenceCreateDialog — v0.3 slice C (DEC-033).

Covers the cascading-filter behavior: source-type changes filter the
relationship combo; (source_type, kind) filter the target-type combo;
target_type changes drive the target-identifier picker. Save sends the
expected POST body.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
from crmbuilder_v2.ui.dialogs.reference_create import ReferenceCreateDialog
from crmbuilder_v2.ui.widgets.entity_identifier_picker import (
    EntityIdentifierPicker,
)

from .conftest import build_client, envelope_ok

_DEFAULT_DECISIONS = [
    {"identifier": "DEC-001", "title": "First decision"},
    {"identifier": "DEC-002", "title": "Second decision"},
]
_DEFAULT_SESSIONS = [
    {"identifier": "SES-001", "title": "First session"},
    {"identifier": "SES-002", "title": "Second session"},
]
_DEFAULT_TOPICS = [
    {"identifier": "TOP-001", "title": "Topic one"},
]


def _refs_handler(captured: dict[str, Any] | None = None):
    """Handler that backs every list-* call the cascade may issue."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        method = request.method
        if method == "GET":
            if path == "/decisions":
                return httpx.Response(200, json=envelope_ok(_DEFAULT_DECISIONS))
            if path == "/sessions":
                return httpx.Response(200, json=envelope_ok(_DEFAULT_SESSIONS))
            if path == "/risks":
                return httpx.Response(200, json=envelope_ok([]))
            if path == "/planning-items":
                return httpx.Response(200, json=envelope_ok([]))
            if path == "/topics":
                return httpx.Response(200, json=envelope_ok(_DEFAULT_TOPICS))
            if path == "/charter/versions":
                return httpx.Response(200, json=envelope_ok([]))
            if path == "/status/versions":
                return httpx.Response(200, json=envelope_ok([]))
        if method == "POST" and path == "/references":
            body = json.loads(request.read())
            if captured is not None:
                captured["body"] = body
            return httpx.Response(
                201,
                json=envelope_ok({"id": 99, **body}),
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


def _make(qtbot, *, pre_populated_source=None):
    client = build_client(_refs_handler())
    dialog = ReferenceCreateDialog(
        client, pre_populated_source=pre_populated_source
    )
    qtbot.addWidget(dialog)
    return dialog


# ---------------------------------------------------------------------------
# Construction & cascade behavior
# ---------------------------------------------------------------------------


def test_dialog_renders_five_fields(qapp, qtbot):
    dialog = _make(qtbot)
    expected_keys = {
        "source_type",
        "source_id",
        "relationship",
        "target_type",
        "target_id",
    }
    assert expected_keys.issubset(set(dialog._field_widgets.keys()))


def test_dialog_opens_with_source_id_disabled_when_no_pre_population(qapp, qtbot):
    dialog = _make(qtbot)
    # source_type combo is enabled but unselected; source_id depends on it
    # so it starts disabled.
    assert dialog._field_widgets["source_id"].isEnabled() is False
    assert dialog._field_widgets["relationship"].isEnabled() is False


def test_dialog_pre_populated_source_fills_and_disables(qapp, qtbot):
    dialog = _make(qtbot, pre_populated_source=("decision", "DEC-001"))
    source_type = dialog._field_widgets["source_type"]
    source_id = dialog._field_widgets["source_id"]
    assert source_type.currentText() == "decision"
    assert source_type.isEnabled() is False
    assert source_id.isEnabled() is False
    assert dialog._current_value(dialog._fields_by_key["source_id"]) == "DEC-001"
    # The relationship combo is now enabled because the source chain
    # is complete.
    assert dialog._field_widgets["relationship"].isEnabled() is True


def test_kind_combo_filtered_by_source_type(qapp, qtbot):
    dialog = _make(qtbot)
    source_type = dialog._field_widgets["source_type"]
    rel = dialog._field_widgets["relationship"]
    source_type.setCurrentText("decision")
    items = sorted([rel.itemText(i) for i in range(rel.count())])
    # Decision as source: supersedes (same-type), is_about, references,
    # decided_in (target=session), but NOT covers/affects/blocks (those
    # require risk/charter/status/planning_item sources).
    assert "supersedes" in items
    assert "is_about" in items
    assert "references" in items
    assert "decided_in" in items
    assert "affects" not in items
    assert "covers" not in items


def test_kind_combo_for_risk_includes_affects_and_blocks(qapp, qtbot):
    dialog = _make(qtbot)
    source_type = dialog._field_widgets["source_type"]
    rel = dialog._field_widgets["relationship"]
    source_type.setCurrentText("risk")
    items = sorted([rel.itemText(i) for i in range(rel.count())])
    assert "affects" in items
    assert "blocks" in items


def test_target_type_combo_filtered_by_source_and_kind_decided_in(qapp, qtbot):
    dialog = _make(qtbot)
    dialog._field_widgets["source_type"].setCurrentText("decision")
    dialog._field_widgets["relationship"].setCurrentText("decided_in")
    target_type = dialog._field_widgets["target_type"]
    items = [target_type.itemText(i) for i in range(target_type.count())]
    # decided_in only points at sessions.
    assert items == ["session"]


def test_target_type_combo_supersedes_is_same_type_only(qapp, qtbot):
    dialog = _make(qtbot)
    dialog._field_widgets["source_type"].setCurrentText("decision")
    dialog._field_widgets["relationship"].setCurrentText("supersedes")
    target_type = dialog._field_widgets["target_type"]
    items = [target_type.itemText(i) for i in range(target_type.count())]
    assert items == ["decision"]


def test_target_identifier_picker_repopulates_on_target_type_change(
    qapp, qtbot
):
    dialog = _make(qtbot)
    dialog._field_widgets["source_type"].setCurrentText("decision")
    dialog._field_widgets["relationship"].setCurrentText("decided_in")
    dialog._field_widgets["target_type"].setCurrentText("session")
    target_id = dialog._field_widgets["target_id"]
    assert isinstance(target_id, EntityIdentifierPicker)
    items = [target_id.itemData(i) for i in range(target_id.count())]
    assert items == ["SES-001", "SES-002"]


def test_source_id_picker_populates_after_source_type_set(qapp, qtbot):
    dialog = _make(qtbot)
    dialog._field_widgets["source_type"].setCurrentText("decision")
    source_id = dialog._field_widgets["source_id"]
    assert isinstance(source_id, EntityIdentifierPicker)
    items = [source_id.itemData(i) for i in range(source_id.count())]
    assert items == ["DEC-001", "DEC-002"]


# ---------------------------------------------------------------------------
# Save flow
# ---------------------------------------------------------------------------


def test_save_posts_correct_payload(qapp, qtbot):
    captured: dict[str, Any] = {}
    client = build_client(_refs_handler(captured))
    dialog = ReferenceCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._field_widgets["source_type"].setCurrentText("decision")
    # Set via the dialog helper so it resolves the identifier through
    # the EntityIdentifierPicker's user-data lookup.
    dialog._set_widget_value(
        dialog._fields_by_key["source_id"], "DEC-001"
    )
    dialog._refresh_dependent_fields()
    dialog._field_widgets["relationship"].setCurrentText("decided_in")
    dialog._field_widgets["target_type"].setCurrentText("session")
    dialog._set_widget_value(
        dialog._fields_by_key["target_id"], "SES-001"
    )

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    assert captured["body"] == {
        "source_type": "decision",
        "source_id": "DEC-001",
        "target_type": "session",
        "target_id": "SES-001",
        "relationship": "decided_in",
    }


def test_save_with_missing_required_field_does_not_post(qapp, qtbot):
    captured: dict[str, Any] = {}
    client = build_client(_refs_handler(captured))
    dialog = ReferenceCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._field_widgets["source_type"].setCurrentText("decision")
    # Don't select source_id; click Save.
    dialog._on_save_clicked()
    # Required-field check fails inline; no POST happens.
    assert "body" not in captured


def test_save_rejects_blocked_combination(qapp, qtbot):
    """Cascading filters make invalid combinations unrepresentable.

    For source_type=risk + kind=covers (covers requires charter or status
    source), the kind combo never offers ``covers`` in the first place.
    This test asserts the cascade contract by enumerating the rendered
    options after a source_type change.
    """
    dialog = _make(qtbot)
    dialog._field_widgets["source_type"].setCurrentText("risk")
    rel = dialog._field_widgets["relationship"]
    items = [rel.itemText(i) for i in range(rel.count())]
    # ``covers`` requires charter/status as source — never offered for risk.
    assert "covers" not in items


def test_charter_status_target_lists_use_version_label(qapp, qtbot):
    """Charter/Status records have no identifier field; the picker
    should render version-labeled entries."""
    versioned_records = [
        {"version": 1, "is_current": False, "payload": {}},
        {"version": 2, "is_current": True, "payload": {}},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET" and request.url.path == "/charter/versions":
            return httpx.Response(200, json=envelope_ok(versioned_records))
        if request.method == "GET" and request.url.path == "/decisions":
            return httpx.Response(200, json=envelope_ok(_DEFAULT_DECISIONS))
        if request.method == "GET":
            return httpx.Response(200, json=envelope_ok([]))
        return httpx.Response(404, json={"data": None, "meta": {}, "errors": []})

    client = build_client(handler)
    dialog = ReferenceCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._field_widgets["source_type"].setCurrentText("charter")
    source_id = dialog._field_widgets["source_id"]
    items = [source_id.itemData(i) for i in range(source_id.count())]
    # The picker stores the synthetic identifier we built (e.g., "v1", "v2").
    assert items == ["v1", "v2"]
