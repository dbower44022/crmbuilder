"""Tests for EntityCrudDialog and EntityCrudDeleteDialog base classes."""

from __future__ import annotations

import re

import httpx
import pytest
from crmbuilder_v2.ui.base.crud_dialog import (
    EntityCrudDeleteDialog,
    EntityCrudDialog,
    FieldSchema,
)
from crmbuilder_v2.ui.dialogs.error import ErrorDialog as ErrorDialogClass
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    NotFoundError,
    StorageConnectionError,
    ValidationError,
)
from crmbuilder_v2.ui.widgets.date_field import DateField
from crmbuilder_v2.ui.widgets.hierarchical_picker import HierarchicalEntityPicker
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
)

from .conftest import build_client

_VOCAB = frozenset({"Active", "Done", "Blocked"})

_BASIC_SCHEMA: list[FieldSchema] = [
    FieldSchema(
        key="identifier",
        label="Identifier",
        widget="line",
        required=True,
        placeholder="X-NNN",
        regex=re.compile(r"^X-\d+$"),
        regex_hint="Identifier must be in the format X-N (e.g., X-1).",
        read_only_on_edit=True,
    ),
    FieldSchema(key="title", label="Title", widget="line", required=True),
    FieldSchema(
        key="status",
        label="Status",
        widget="combo",
        required=True,
        vocab=_VOCAB,
        default="Active",
    ),
    FieldSchema(key="notes", label="Notes", widget="text"),
    FieldSchema(key="event_date", label="Event Date", widget="date"),
]


def _success_handler(method: str, path: str, response_body: dict) -> callable:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == method and request.url.path == path:
            return httpx.Response(
                201, json={"data": response_body, "meta": {}, "errors": None}
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


# ---------------------------------------------------------------------------
# Construction & widget rendering
# ---------------------------------------------------------------------------


def test_create_mode_renders_fields_with_correct_widgets(qapp, qtbot):
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _BASIC_SCHEMA,
        mode="create",
        title="New Thing",
        create_method=lambda body: client._request("POST", "/things", json=body),
    )
    qtbot.addWidget(dialog)
    assert isinstance(dialog._widgets["identifier"], QLineEdit)
    assert isinstance(dialog._widgets["title"], QLineEdit)
    assert isinstance(dialog._widgets["status"], QComboBox)
    assert isinstance(dialog._widgets["notes"], QPlainTextEdit)
    assert isinstance(dialog._widgets["event_date"], DateField)
    # Combo populated with sorted vocab and default selection.
    combo: QComboBox = dialog._widgets["status"]
    assert combo.count() == 3
    assert [combo.itemText(i) for i in range(3)] == ["Active", "Blocked", "Done"]
    assert combo.currentText() == "Active"


def test_create_mode_construction_requires_create_method(qapp, qtbot):
    with pytest.raises(ValueError, match="create_method"):
        EntityCrudDialog(
            build_client(_success_handler("POST", "/things", {})),
            _BASIC_SCHEMA,
            mode="create",
            title="New Thing",
        )


def test_edit_mode_construction_requires_record(qapp, qtbot):
    with pytest.raises(ValueError, match="record"):
        EntityCrudDialog(
            build_client(_success_handler("PATCH", "/things/X-1", {})),
            _BASIC_SCHEMA,
            mode="edit",
            title="Edit",
            update_method=lambda i, b: {},
        )


# ---------------------------------------------------------------------------
# Required-field and format validation
# ---------------------------------------------------------------------------


def test_required_field_check_blocks_save(qapp, qtbot):
    captured: list[dict] = []

    def create(body):
        captured.append(body)
        return {"identifier": body.get("identifier", "")}

    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        _BASIC_SCHEMA,
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._on_save_clicked()
    assert captured == []  # no API call
    assert dialog._error_labels["identifier"].isHidden() is False
    assert dialog._error_labels["title"].isHidden() is False
    assert dialog._error_labels["status"].isHidden() is True  # has a default


def test_format_regex_blocks_save_when_pattern_does_not_match(qapp, qtbot):
    captured: list[dict] = []

    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        _BASIC_SCHEMA,
        mode="create",
        title="t",
        create_method=lambda b: captured.append(b) or {"identifier": "?"},
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("not-a-match")
    dialog._widgets["title"].setText("Title")
    dialog._on_save_clicked()
    assert captured == []
    err = dialog._error_labels["identifier"]
    assert err.isHidden() is False
    assert "X-N" in err.text()


def test_clear_error_on_edit(qapp, qtbot):
    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        _BASIC_SCHEMA,
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": "?"},
    )
    qtbot.addWidget(dialog)
    dialog._on_save_clicked()
    assert dialog._error_labels["identifier"].isHidden() is False
    dialog._widgets["identifier"].setText("X-1")
    assert dialog._error_labels["identifier"].isHidden() is True


# ---------------------------------------------------------------------------
# Successful save (create mode)
# ---------------------------------------------------------------------------


def test_successful_create_accepts_with_identifier(qapp, qtbot):
    captured: list[dict] = []

    def create(body):
        captured.append(body)
        return {"identifier": body["identifier"], "title": body["title"]}

    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        _BASIC_SCHEMA,
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-7")
    dialog._widgets["title"].setText("hello")
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured[0]["identifier"] == "X-7"
    assert captured[0]["title"] == "hello"
    assert captured[0]["status"] == "Active"
    assert dialog.saved_identifier() == "X-7"


# ---------------------------------------------------------------------------
# Edit mode
# ---------------------------------------------------------------------------


def test_edit_mode_pre_populates_from_record(qapp, qtbot):
    record = {
        "identifier": "X-3",
        "title": "Existing",
        "status": "Done",
        "notes": "some notes",
        "event_date": "01-15-26",
    }
    dialog = EntityCrudDialog(
        build_client(_success_handler("PATCH", "/x/X-3", {})),
        _BASIC_SCHEMA,
        mode="edit",
        title="Edit X-3",
        update_method=lambda i, b: {},
        record=record,
    )
    qtbot.addWidget(dialog)
    assert dialog._widgets["identifier"].text() == "X-3"
    assert dialog._widgets["identifier"].isReadOnly()
    assert dialog._widgets["title"].text() == "Existing"
    assert dialog._widgets["status"].currentText() == "Done"
    assert dialog._widgets["notes"].toPlainText() == "some notes"
    assert dialog._widgets["event_date"].date_text() == "01-15-26"


def test_edit_mode_no_changes_accepts_without_api_call(qapp, qtbot):
    record = {
        "identifier": "X-3",
        "title": "Existing",
        "status": "Done",
        "notes": "",
        "event_date": "01-15-26",
    }
    captured: list[dict] = []

    def update(identifier, body):
        captured.append((identifier, body))
        return {}

    dialog = EntityCrudDialog(
        build_client(_success_handler("PATCH", "/x/X-3", {})),
        _BASIC_SCHEMA,
        mode="edit",
        title="t",
        update_method=update,
        record=record,
    )
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured == []  # no API call


def test_edit_mode_single_field_change_sends_partial_diff(qapp, qtbot):
    record = {
        "identifier": "X-3",
        "title": "Existing",
        "status": "Done",
        "notes": "",
        "event_date": "01-15-26",
    }
    captured: list[tuple[str, dict]] = []

    def update(identifier, body):
        captured.append((identifier, body))
        return {}

    dialog = EntityCrudDialog(
        build_client(_success_handler("PATCH", "/x/X-3", {})),
        _BASIC_SCHEMA,
        mode="edit",
        title="t",
        update_method=update,
        record=record,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["title"].setText("Updated title")
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured == [("X-3", {"title": "Updated title"})]


# ---------------------------------------------------------------------------
# Error envelope handling
# ---------------------------------------------------------------------------


def test_validation_error_with_field_populates_inline(qapp, qtbot):
    def create(body):
        raise ValidationError(
            errors=[{"code": "validation_error", "field": "title", "message": "Too long"}],
            message="Validation failed",
        )

    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        _BASIC_SCHEMA,
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    dialog._widgets["title"].setText("hello")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["title"].text() != "",
        timeout=2000,
    )
    assert "Too long" in dialog._error_labels["title"].text()
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_conflict_error_populates_identifier_inline_on_create(qapp, qtbot):
    def create(body):
        raise ConflictError(
            errors=[{"code": "conflict_error", "message": "exists"}],
            message="conflict",
        )

    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        _BASIC_SCHEMA,
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    dialog._widgets["title"].setText("hello")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._error_labels["identifier"].text() != "",
        timeout=2000,
    )
    assert "already exists" in dialog._error_labels["identifier"].text()


def test_storage_connection_error_rejects_dialog(qapp, qtbot):
    def create(body):
        raise StorageConnectionError("connection lost")

    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        _BASIC_SCHEMA,
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    dialog._widgets["title"].setText("hello")
    with qtbot.waitSignal(dialog.rejected, timeout=2000):
        dialog._on_save_clicked()


def test_not_found_on_edit_accepts_with_message(qapp, qtbot, monkeypatch):
    def update(identifier, body):
        raise NotFoundError(
            errors=[{"code": "not_found", "message": "gone"}],
            message="not found",
        )

    captured: dict[str, bool] = {}

    class _Recorder(ErrorDialogClass):
        def exec(self):  # noqa: A003 — Qt's exec name
            captured["exec_called"] = True
            return 1

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.ErrorDialog", _Recorder
    )

    record = {
        "identifier": "X-3",
        "title": "Existing",
        "status": "Done",
        "notes": "",
        "event_date": "01-15-26",
    }
    dialog = EntityCrudDialog(
        build_client(_success_handler("PATCH", "/x/X-3", {})),
        _BASIC_SCHEMA,
        mode="edit",
        title="t",
        update_method=update,
        record=record,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["title"].setText("changed")
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured.get("exec_called") is True


# ---------------------------------------------------------------------------
# Optional field handling
# ---------------------------------------------------------------------------


def test_omit_when_empty_in_create_excludes_field(qapp, qtbot):
    schema = [
        FieldSchema(key="identifier", label="ID", widget="line", required=True),
        FieldSchema(
            key="parent_id",
            label="Parent",
            widget="line",
            omit_when_empty_in_create=True,
        ),
    ]
    captured: list[dict] = []

    def create(body):
        captured.append(body)
        return {"identifier": body["identifier"]}

    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        schema,
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    # parent_id left empty
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert "parent_id" not in captured[0]
    assert captured[0]["identifier"] == "X-1"


# ---------------------------------------------------------------------------
# Tree picker integration
# ---------------------------------------------------------------------------


def test_tree_picker_widget_constructs_with_label(qapp, qtbot):
    schema = [
        FieldSchema(key="identifier", label="ID", widget="line", required=True),
        FieldSchema(
            key="parent_id",
            label="Parent",
            widget="tree_picker",
            tree_picker_data=lambda c: [
                HierarchicalEntityPicker.Node(id="A", label="Alpha"),
            ],
        ),
    ]
    dialog = EntityCrudDialog(
        build_client(_success_handler("POST", "/x", {})),
        schema,
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": b["identifier"]},
    )
    qtbot.addWidget(dialog)
    button = dialog._widgets["parent_id"]
    assert isinstance(button, QPushButton)
    assert button.text() == "(no selection)"


# ---------------------------------------------------------------------------
# EntityCrudDeleteDialog
# ---------------------------------------------------------------------------


def test_delete_dialog_construction_shows_identifier_and_title(qapp, qtbot):
    dialog = EntityCrudDeleteDialog(
        build_client(_success_handler("DELETE", "/x/X-7", {})),
        "X-7",
        "Test thing",
        delete_method=lambda i: {"deleted": True},
    )
    qtbot.addWidget(dialog)
    assert "X-7" in dialog._body_label.text()
    assert "Test thing" in dialog._body_label.text()


def test_delete_dialog_successful_delete_accepts(qapp, qtbot):
    captured: list[str] = []

    def delete(identifier):
        captured.append(identifier)
        return {"deleted": True}

    dialog = EntityCrudDeleteDialog(
        build_client(_success_handler("DELETE", "/x/X-7", {})),
        "X-7",
        "Test thing",
        delete_method=delete,
    )
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()
    assert captured == ["X-7"]


def test_delete_dialog_not_found_accepts(qapp, qtbot):
    def delete(identifier):
        raise NotFoundError(
            errors=[{"code": "not_found", "message": "gone"}],
            message="not found",
        )

    dialog = EntityCrudDeleteDialog(
        build_client(_success_handler("DELETE", "/x/X-7", {})),
        "X-7",
        "Test thing",
        delete_method=delete,
    )
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()


def test_delete_dialog_connection_error_rejects(qapp, qtbot):
    def delete(identifier):
        raise StorageConnectionError("connection lost")

    dialog = EntityCrudDeleteDialog(
        build_client(_success_handler("DELETE", "/x/X-7", {})),
        "X-7",
        "Test thing",
        delete_method=delete,
    )
    qtbot.addWidget(dialog)
    with qtbot.waitSignal(dialog.rejected, timeout=2000):
        dialog._on_delete_clicked()


# ---------------------------------------------------------------------------
# Cascading dependencies (v0.3 slice C — DEC-033)
# ---------------------------------------------------------------------------


def _cascade_schema():
    """Two-field cascade: ``upstream`` (combo) and ``downstream`` (combo)."""

    def compute_downstream(state):
        upstream = state.get("upstream", "")
        if upstream == "alpha":
            return ["one", "two"]
        if upstream == "beta":
            return ["three", "four", "five"]
        return []

    return [
        FieldSchema(
            key="upstream",
            label="Upstream",
            widget="combo",
            required=True,
            vocab=frozenset({"alpha", "beta"}),
        ),
        FieldSchema(
            key="downstream",
            label="Downstream",
            widget="combo",
            required=True,
            depends_on=["upstream"],
            compute_options=compute_downstream,
        ),
    ]


def test_cascade_downstream_disabled_when_upstream_empty(qapp, qtbot):
    """Dependent field starts disabled when upstream value is empty."""
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _cascade_schema(),
        mode="create",
        title="Cascade",
        create_method=lambda body: client._post("/things", json=body)["data"],
    )
    qtbot.addWidget(dialog)
    # On open with no default on the upstream combo, downstream is disabled.
    upstream = dialog._field_widgets["upstream"]
    upstream.setCurrentIndex(-1)  # ensure empty
    upstream.setEditText("")
    dialog._refresh_dependent_fields()
    downstream = dialog._field_widgets["downstream"]
    assert downstream.isEnabled() is False
    assert downstream.count() == 0


def test_cascade_downstream_repopulates_when_upstream_changes(qapp, qtbot):
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _cascade_schema(),
        mode="create",
        title="Cascade",
        create_method=lambda body: client._post("/things", json=body)["data"],
    )
    qtbot.addWidget(dialog)
    upstream = dialog._field_widgets["upstream"]
    upstream.setCurrentText("alpha")
    downstream = dialog._field_widgets["downstream"]
    items = [downstream.itemText(i) for i in range(downstream.count())]
    assert items == ["one", "two"]
    assert downstream.isEnabled() is True

    upstream.setCurrentText("beta")
    items = [downstream.itemText(i) for i in range(downstream.count())]
    assert items == ["three", "four", "five"]


def test_identifier_picker_widget_constructed_for_identifier_picker_type(
    qapp, qtbot
):
    """A FieldSchema with widget='identifier_picker' produces an EntityIdentifierPicker."""
    from crmbuilder_v2.ui.widgets.entity_identifier_picker import (
        EntityIdentifierPicker,
    )

    schema = [
        FieldSchema(
            key="entity_id",
            label="Entity",
            widget="identifier_picker",
            required=True,
            compute_options=lambda _state: [("DEC-001", "First")],
        ),
    ]
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        schema,
        mode="create",
        title="Picker",
        create_method=lambda body: client._post("/things", json=body)["data"],
    )
    qtbot.addWidget(dialog)
    widget = dialog._field_widgets["entity_id"]
    assert isinstance(widget, EntityIdentifierPicker)


def test_identifier_picker_options_come_from_compute_options_at_open(
    qapp, qtbot
):
    """An identifier_picker with compute_options is populated at dialog open
    time (no upstream needed when depends_on is None)."""
    from crmbuilder_v2.ui.widgets.entity_identifier_picker import (
        EntityIdentifierPicker,
    )

    schema = [
        FieldSchema(
            key="entity_id",
            label="Entity",
            widget="identifier_picker",
            required=True,
            depends_on=[],  # no dependencies; populated at open
            compute_options=lambda _state: [
                ("DEC-001", "First"),
                ("DEC-002", "Second"),
            ],
        ),
    ]
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        schema,
        mode="create",
        title="Picker",
        create_method=lambda body: client._post("/things", json=body)["data"],
    )
    qtbot.addWidget(dialog)
    widget = dialog._field_widgets["entity_id"]
    assert isinstance(widget, EntityIdentifierPicker)
    assert widget.count() == 2


def test_set_field_enabled_disables_widget(qapp, qtbot):
    """The public set_field_enabled API toggles a field's widget."""
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _BASIC_SCHEMA,
        mode="create",
        title="X",
        create_method=lambda body: client._post("/things", json=body)["data"],
    )
    qtbot.addWidget(dialog)
    dialog.set_field_enabled("identifier", False)
    assert dialog._field_widgets["identifier"].isEnabled() is False
    dialog.set_field_enabled("identifier", True)
    assert dialog._field_widgets["identifier"].isEnabled() is True


# ---------------------------------------------------------------------------
# Length validation + live character counter (Phase 1 of v2-ui length series)
# ---------------------------------------------------------------------------


def _length_bounded_schema(
    min_length: int = 200, max_length: int = 800
) -> list[FieldSchema]:
    """Schema with a required identifier and an optional length-bounded summary."""
    return [
        FieldSchema(
            key="identifier",
            label="Identifier",
            widget="line",
            required=True,
        ),
        FieldSchema(
            key="summary",
            label="Summary",
            widget="text",
            min_length=min_length,
            max_length=max_length,
        ),
    ]


def test_length_bounded_text_field_builds_counter(qapp, qtbot):
    """A text widget with min_length/max_length renders a counter label."""
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _length_bounded_schema(),
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": b["identifier"]},
    )
    qtbot.addWidget(dialog)
    assert "summary" in dialog._length_counters
    counter = dialog._length_counters["summary"]
    # Empty initial state: shows 0 / 800 with neutral (empty) styling.
    assert counter.text() == "0 / 800"
    assert counter.styleSheet() == ""


def test_text_field_without_length_constraints_has_no_counter(qapp, qtbot):
    """A text widget without min/max length renders NO counter."""
    schema = [
        FieldSchema(key="identifier", label="ID", widget="line", required=True),
        FieldSchema(key="notes", label="Notes", widget="text"),
    ]
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        schema,
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": b["identifier"]},
    )
    qtbot.addWidget(dialog)
    assert "notes" not in dialog._length_counters


def test_counter_amber_when_below_minimum(qapp, qtbot):
    """Typing fewer than min_length characters renders the counter amber."""
    from crmbuilder_v2.ui.styling import t

    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _length_bounded_schema(),
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": b["identifier"]},
    )
    qtbot.addWidget(dialog)
    summary: QPlainTextEdit = dialog._widgets["summary"]
    summary.setPlainText("x" * 100)
    counter = dialog._length_counters["summary"]
    assert counter.text() == "100 / 800"
    expected = f"color: {t('color.warning.default')};"
    assert counter.styleSheet() == expected


def test_counter_neutral_when_in_range(qapp, qtbot):
    """Typing within range renders the counter with default (empty) style."""
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _length_bounded_schema(),
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": b["identifier"]},
    )
    qtbot.addWidget(dialog)
    summary: QPlainTextEdit = dialog._widgets["summary"]
    summary.setPlainText("y" * 500)
    counter = dialog._length_counters["summary"]
    assert counter.text() == "500 / 800"
    assert counter.styleSheet() == ""


def test_counter_red_when_above_maximum(qapp, qtbot):
    """Typing more than max_length characters renders the counter red."""
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _length_bounded_schema(),
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": b["identifier"]},
    )
    qtbot.addWidget(dialog)
    summary: QPlainTextEdit = dialog._widgets["summary"]
    summary.setPlainText("z" * 900)
    counter = dialog._length_counters["summary"]
    assert counter.text() == "900 / 800"
    assert "B22222" in counter.styleSheet()


def test_counter_with_only_min_length_renders_bare_count(qapp, qtbot):
    """When only min_length is set, the counter shows just the bare count."""
    schema = [
        FieldSchema(key="identifier", label="ID", widget="line", required=True),
        FieldSchema(
            key="summary",
            label="Summary",
            widget="text",
            min_length=50,
        ),
    ]
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        schema,
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": b["identifier"]},
    )
    qtbot.addWidget(dialog)
    summary: QPlainTextEdit = dialog._widgets["summary"]
    summary.setPlainText("a" * 25)
    counter = dialog._length_counters["summary"]
    assert counter.text() == "25"


def test_save_with_below_minimum_value_shows_inline_error(qapp, qtbot):
    """Save with a 100-char value (below min=200) shows the API-matching error."""
    captured: list[dict] = []

    def create(body):
        captured.append(body)
        return {"identifier": body["identifier"]}

    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _length_bounded_schema(),
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    summary: QPlainTextEdit = dialog._widgets["summary"]
    summary.setPlainText("x" * 100)
    dialog._on_save_clicked()
    # No API call — gate fired pre-submit.
    assert captured == []
    err = dialog._error_labels["summary"]
    assert err.isHidden() is False
    assert err.text() == "must be 200-800 characters (got 100)"


def test_save_with_above_maximum_value_shows_inline_error(qapp, qtbot):
    """Save with a 900-char value (above max=800) shows the API-matching error."""
    captured: list[dict] = []

    def create(body):
        captured.append(body)
        return {"identifier": body["identifier"]}

    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _length_bounded_schema(),
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    summary: QPlainTextEdit = dialog._widgets["summary"]
    summary.setPlainText("z" * 900)
    dialog._on_save_clicked()
    assert captured == []
    err = dialog._error_labels["summary"]
    assert err.isHidden() is False
    assert err.text() == "must be 200-800 characters (got 900)"


def test_save_with_empty_optional_length_field_omits_and_succeeds(qapp, qtbot):
    """Empty length-bounded text field is valid (optional) and triggers no error."""
    captured: list[dict] = []

    def create(body):
        captured.append(body)
        return {"identifier": body["identifier"]}

    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    schema = [
        FieldSchema(
            key="identifier",
            label="Identifier",
            widget="line",
            required=True,
        ),
        FieldSchema(
            key="summary",
            label="Summary",
            widget="text",
            min_length=200,
            max_length=800,
            # Mirror the access-layer contract: empty == omit on POST.
            omit_when_empty_in_create=True,
        ),
    ]
    dialog = EntityCrudDialog(
        client,
        schema,
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    # summary deliberately left empty
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert captured == [{"identifier": "X-1"}]
    err = dialog._error_labels["summary"]
    assert err.isHidden() is True


def test_save_with_in_range_value_succeeds(qapp, qtbot):
    """Save with a 500-char value (in [200, 800]) succeeds and dispatches."""
    captured: list[dict] = []

    def create(body):
        captured.append(body)
        return {"identifier": body["identifier"]}

    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _length_bounded_schema(),
        mode="create",
        title="t",
        create_method=create,
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    payload = "y" * 500
    dialog._widgets["summary"].setPlainText(payload)
    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()
    assert len(captured) == 1
    assert captured[0]["identifier"] == "X-1"
    assert captured[0]["summary"] == payload
    err = dialog._error_labels["summary"]
    assert err.isHidden() is True


def test_length_error_clears_when_user_edits(qapp, qtbot):
    """The standard clear-on-edit behavior covers the length-error case too."""
    client = build_client(_success_handler("POST", "/things", {"identifier": "X-1"}))
    dialog = EntityCrudDialog(
        client,
        _length_bounded_schema(),
        mode="create",
        title="t",
        create_method=lambda b: {"identifier": b["identifier"]},
    )
    qtbot.addWidget(dialog)
    dialog._widgets["identifier"].setText("X-1")
    summary: QPlainTextEdit = dialog._widgets["summary"]
    summary.setPlainText("x" * 100)
    dialog._on_save_clicked()
    assert dialog._error_labels["summary"].isHidden() is False
    # Edit clears the error label (existing wire_clear_on_change path).
    summary.setPlainText("x" * 300)
    assert dialog._error_labels["summary"].isHidden() is True
