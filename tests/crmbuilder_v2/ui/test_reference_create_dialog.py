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
# Methodology rows carry type-prefixed keys, not bare identifier/title
# (REQ-562 / PI-463): the picker must read them.
_DEFAULT_PROCESSES = [
    {
        "process_identifier": "PROC-001",
        "process_name": "Mentor matching",
        "process_domain_identifier": "DOM-001",
    },
    {
        "process_identifier": "PROC-002",
        "process_name": "Session logging",
        "process_domain_identifier": "DOM-001",
    },
]
_DEFAULT_ENTITIES = [
    {"entity_identifier": "ENT-001", "entity_name": "Contact"},
    {"entity_identifier": "ENT-002", "entity_name": "Account"},
]
_DEFAULT_PERSONAS = [
    {"persona_identifier": "PER-001", "persona_name": "Mentor coordinator"},
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
            if path == "/processes":
                return httpx.Response(200, json=envelope_ok(_DEFAULT_PROCESSES))
            if path == "/entities":
                return httpx.Response(200, json=envelope_ok(_DEFAULT_ENTITIES))
            if path == "/personas":
                return httpx.Response(200, json=envelope_ok(_DEFAULT_PERSONAS))
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
    dialog = ReferenceCreateDialog(client, pre_populated_source=pre_populated_source)
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


def test_kind_combo_for_risk_includes_affects(qapp, qtbot):
    """v0.8: risk no longer emits ``blocks`` (the kind is retired); ``affects``
    remains. The directed ``blocked_by`` replacement is sourced from
    ``planning_item``, not ``risk`` — see vocab.py and methodology §3.4.
    """
    dialog = _make(qtbot)
    source_type = dialog._field_widgets["source_type"]
    rel = dialog._field_widgets["relationship"]
    source_type.setCurrentText("risk")
    items = sorted([rel.itemText(i) for i in range(rel.count())])
    assert "affects" in items
    assert "blocks" not in items
    assert "blocked_by" not in items


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


def test_target_identifier_picker_repopulates_on_target_type_change(qapp, qtbot):
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


def test_source_id_picker_lists_processes_by_identifier_and_name(qapp, qtbot):
    """REQ-562: a process source lists the engagement's processes, read
    from the type-prefixed row keys, so the operator picks instead of
    typing the identifier."""
    dialog = _make(qtbot)
    dialog._field_widgets["source_type"].setCurrentText("process")
    source_id = dialog._field_widgets["source_id"]
    assert isinstance(source_id, EntityIdentifierPicker)
    items = [source_id.itemData(i) for i in range(source_id.count())]
    assert items == ["PROC-001", "PROC-002"]
    labels = [source_id.itemText(i) for i in range(source_id.count())]
    assert any("Mentor matching" in label for label in labels)


def test_target_id_picker_lists_entities_for_process_touches_entity(qapp, qtbot):
    """REQ-562: choosing process -> process_touches_entity -> entity fills
    the target picker with the engagement's entities."""
    dialog = _make(qtbot)
    dialog._field_widgets["source_type"].setCurrentText("process")
    dialog._field_widgets["relationship"].setCurrentText("process_touches_entity")
    dialog._field_widgets["target_type"].setCurrentText("entity")
    target_id = dialog._field_widgets["target_id"]
    assert isinstance(target_id, EntityIdentifierPicker)
    items = [target_id.itemData(i) for i in range(target_id.count())]
    assert items == ["ENT-001", "ENT-002"]


def test_target_id_picker_lists_personas_for_performed_by(qapp, qtbot):
    dialog = _make(qtbot)
    dialog._field_widgets["source_type"].setCurrentText("process")
    dialog._field_widgets["relationship"].setCurrentText("process_performed_by_persona")
    dialog._field_widgets["target_type"].setCurrentText("persona")
    target_id = dialog._field_widgets["target_id"]
    items = [target_id.itemData(i) for i in range(target_id.count())]
    assert items == ["PER-001"]


def test_every_listed_type_maps_to_a_real_client_method(qapp, qtbot):
    """The fetch map names only StorageClient methods that exist and take
    no required arguments, so no picker can fail on a signature."""
    import inspect

    from crmbuilder_v2.access.vocab import ENTITY_TYPES
    from crmbuilder_v2.ui.client import StorageClient
    from crmbuilder_v2.ui.dialogs.reference_create import _LIST_METHOD_NAMES

    for entity_type, method_name in _LIST_METHOD_NAMES.items():
        assert entity_type in ENTITY_TYPES
        method = getattr(StorageClient, method_name)
        params = list(inspect.signature(method).parameters.values())[1:]
        required = [
            p.name
            for p in params
            if p.default is inspect.Parameter.empty
            and p.kind
            in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            )
        ]
        assert required == [], (entity_type, method_name, required)


def test_identifier_and_title_reads_prefixed_bare_and_versioned_rows():
    from crmbuilder_v2.ui.dialogs.reference_create import _identifier_and_title

    assert _identifier_and_title(
        {
            "field_identifier": "FLD-1",
            "field_name": "Email",
            "field_previous_parent_entity_identifier": "ENT-9",
        },
        "field",
    ) == ("FLD-1", "Email")
    assert _identifier_and_title(
        {"identifier": "DEC-1", "title": "A ruling"}, "decision"
    ) == ("DEC-1", "A ruling")
    assert _identifier_and_title({"version": 3}, "charter") == ("v3", "")
    assert _identifier_and_title(
        {"reference_book_identifier": "RBK-1", "reference_book_title": "Book"},
        "reference_book",
    ) == ("RBK-1", "Book")


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
    dialog._set_widget_value(dialog._fields_by_key["source_id"], "DEC-001")
    dialog._refresh_dependent_fields()
    dialog._field_widgets["relationship"].setCurrentText("decided_in")
    dialog._field_widgets["target_type"].setCurrentText("session")
    dialog._set_widget_value(dialog._fields_by_key["target_id"], "SES-001")

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
