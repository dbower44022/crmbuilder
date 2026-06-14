"""UI slice tests — intrinsic field/entity attributes + field_options editor.

PRJ-025 PI-182 UI slice. Exercises the genuine
dialog → StorageClient → REST → access → DB path via a ``StorageClient``
bound to a real FastAPI ``TestClient`` (mirroring ``test_field_panel`` /
``test_entities_panel``). Covers:

* the new field-dialog intrinsic inputs appear and populate from a record;
* the field create dialog forwards the §7 scalars + ``field_options``;
* the field edit dialog round-trips edited intrinsics + options;
* the ``FieldOptionsEditor`` widget round-trips (add / remove / reorder →
  correct list emitted), and its buttons are never disabled;
* the entity dialog forwards the §6 intrinsics, and its combos restrict
  to vocab;
* the detail panes render the new attributes read-only.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.vocab import (
    ENTITY_SORT_DIRECTIONS,
    FIELD_FORMATS,
    FIELD_NUMERIC_SCALES,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.entity_crud import (
    EntityCreateDialog,
    EntityEditDialog,
)
from crmbuilder_v2.ui.dialogs.field_crud import FieldCreateDialog, FieldEditDialog
from crmbuilder_v2.ui.panels.entities import EntitiesPanel
from crmbuilder_v2.ui.panels.field import FieldsPanel
from crmbuilder_v2.ui.widgets.field_options_editor import FieldOptionsEditor
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QCheckBox


@pytest.fixture
def client(v2_env) -> StorageClient:
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    sc.set_active_engagement("ENG-001")
    return sc


def _seed_entity(c: StorageClient, name: str = "Contact") -> str:
    return c.create_entity(
        {"entity_name": name, "entity_description": "seed"}
    )["entity_identifier"]


# ---------------------------------------------------------------------------
# FieldOptionsEditor widget
# ---------------------------------------------------------------------------


def test_options_editor_set_and_get_round_trips(qtbot):
    editor = FieldOptionsEditor()
    qtbot.addWidget(editor)
    editor.set_options(
        [
            {"option_value": "b", "option_label": "Bee", "option_order": 1},
            {"option_value": "a", "option_label": "Ay", "option_order": 0},
        ]
    )
    # Sorted by option_order on load, re-emitted with 0-based positions.
    assert editor.options() == [
        {"option_value": "a", "option_label": "Ay", "option_order": 0},
        {"option_value": "b", "option_label": "Bee", "option_order": 1},
    ]


def test_options_editor_add_remove_reorder(qtbot):
    editor = FieldOptionsEditor()
    qtbot.addWidget(editor)
    editor.set_options(
        [
            {"option_value": "a", "option_label": None, "option_order": 0},
            {"option_value": "b", "option_label": None, "option_order": 1},
            {"option_value": "c", "option_label": None, "option_order": 2},
        ]
    )
    # Remove the middle row.
    editor._table.setCurrentCell(1, 0)
    editor._on_remove_clicked()
    assert [o["option_value"] for o in editor.options()] == ["a", "c"]

    # Move "c" up above "a".
    editor._table.setCurrentCell(1, 0)
    editor._on_move_up_clicked()
    opts = editor.options()
    assert [o["option_value"] for o in opts] == ["c", "a"]
    assert [o["option_order"] for o in opts] == [0, 1]


def test_options_editor_drops_blank_value_rows(qtbot):
    editor = FieldOptionsEditor()
    qtbot.addWidget(editor)
    editor._on_add_clicked()  # adds a blank row
    assert editor.options() == []


def test_options_editor_buttons_never_disabled(qtbot):
    editor = FieldOptionsEditor()
    qtbot.addWidget(editor)
    # No selection: the action buttons must stay enabled (project rule).
    for btn in (
        editor._remove_btn,
        editor._up_btn,
        editor._down_btn,
        editor._add_btn,
    ):
        assert btn.isEnabled()
    # Clicking with no selection shows an explanatory message rather than
    # greying out; stub the widget's _inform so the offscreen modal can't
    # block (PySide6's QMessageBox.information cannot be monkeypatched).
    messages: list[str] = []
    editor._inform = messages.append  # type: ignore[method-assign]
    editor._on_remove_clicked()
    editor._on_move_up_clicked()
    assert len(messages) == 2
    assert editor.options() == []


# ---------------------------------------------------------------------------
# Field create dialog forwards the intrinsics + options
# ---------------------------------------------------------------------------


def test_field_create_dialog_has_intrinsic_inputs(qtbot, client):
    _seed_entity(client)
    dialog = FieldCreateDialog(client)
    qtbot.addWidget(dialog)
    for key in (
        "field_tooltip",
        "field_usage_summary",
        "field_default_value",
        "field_format",
        "field_numeric_scale",
        "field_max_length",
        "field_min",
        "field_max",
        "field_read_only",
        "field_unique",
        "field_externally_populated",
    ):
        assert key in dialog._intrinsic_widgets
    assert dialog._options_editor is not None
    # Format combo restricts to the vocab (plus the blank "unset" entry).
    fmt = dialog._intrinsic_widgets["field_format"]
    items = {fmt.itemText(i) for i in range(fmt.count())}
    assert items == {""} | set(FIELD_FORMATS)
    scale = dialog._intrinsic_widgets["field_numeric_scale"]
    scale_items = {scale.itemText(i) for i in range(scale.count())}
    assert scale_items == {""} | set(FIELD_NUMERIC_SCALES)


def test_field_create_dialog_forwards_intrinsics_and_options(qtbot, client):
    ent = _seed_entity(client)
    dialog = FieldCreateDialog(client)
    qtbot.addWidget(dialog)
    dialog._widgets["field_belongs_to_entity_identifier"].setCurrentText(ent)
    dialog._widgets["field_name"].setText("status")
    dialog._widgets["field_description"].setPlainText("d")
    dialog._widgets["field_type"].setCurrentText("enum")

    iw = dialog._intrinsic_widgets
    iw["field_tooltip"].setPlainText("pick one")
    iw["field_default_value"].setText("open")
    iw["field_format"].setCurrentText("email")
    iw["field_max_length"].setText("64")
    iw["field_read_only"].setChecked(True)
    iw["field_unique"].setChecked(True)
    dialog._options_editor.set_options(
        [
            {"option_value": "open", "option_label": "Open", "option_order": 0},
            {"option_value": "closed", "option_label": None, "option_order": 1},
        ]
    )

    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()

    fid = dialog.created_identifier()
    stored = client.get_field(fid)
    assert stored["field_tooltip"] == "pick one"
    assert stored["field_default_value"] == "open"
    assert stored["field_format"] == "email"
    assert stored["field_max_length"] == 64
    assert stored["field_read_only"] is True
    assert stored["field_unique"] is True
    assert stored["field_externally_populated"] is False
    opts = stored["field_options"]
    assert [o["option_value"] for o in opts] == ["open", "closed"]
    assert opts[0]["option_label"] == "Open"
    assert opts[1]["option_label"] is None


def test_field_edit_dialog_populates_and_round_trips(qtbot, client):
    ent = _seed_entity(client)
    created = client.create_field(
        {
            "field_name": "status",
            "field_description": "d",
            "field_type": "enum",
            "field_belongs_to_entity_identifier": ent,
            "field_tooltip": "old tip",
            "field_read_only": True,
            "field_options": [
                {"option_value": "a", "option_label": "Ay", "option_order": 0},
            ],
        }
    )
    record = client.get_field(created["field_identifier"])

    dialog = FieldEditDialog(client, record)
    qtbot.addWidget(dialog)
    # Populated from the record.
    assert dialog._intrinsic_widgets["field_tooltip"].toPlainText() == "old tip"
    assert dialog._intrinsic_widgets["field_read_only"].isChecked() is True
    assert [o["option_value"] for o in dialog._options_editor.options()] == ["a"]

    # Edit an intrinsic + append an option, then save (PATCH diff).
    dialog._intrinsic_widgets["field_tooltip"].setPlainText("new tip")
    dialog._options_editor.set_options(
        [
            {"option_value": "a", "option_label": "Ay", "option_order": 0},
            {"option_value": "b", "option_label": "Bee", "option_order": 1},
        ]
    )
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()

    stored = client.get_field(created["field_identifier"])
    assert stored["field_tooltip"] == "new tip"
    assert stored["field_read_only"] is True  # unchanged
    assert [o["option_value"] for o in stored["field_options"]] == ["a", "b"]


def test_field_edit_dialog_untouched_intrinsics_not_in_diff(qtbot, client):
    ent = _seed_entity(client)
    created = client.create_field(
        {
            "field_name": "status",
            "field_description": "d",
            "field_type": "enum",
            "field_belongs_to_entity_identifier": ent,
        }
    )
    record = client.get_field(created["field_identifier"])
    dialog = FieldEditDialog(client, record)
    qtbot.addWidget(dialog)
    # Nothing touched → no intrinsic / options keys in the diff.
    diff = dialog._build_edit_diff()
    assert "field_options" not in diff
    assert "field_tooltip" not in diff
    assert "field_read_only" not in diff


# ---------------------------------------------------------------------------
# Entity dialog forwards the §6 intrinsics
# ---------------------------------------------------------------------------


def test_entity_create_dialog_has_intrinsic_inputs_with_vocab(qtbot, client):
    dialog = EntityCreateDialog(client)
    qtbot.addWidget(dialog)
    for key in (
        "entity_default_sort_field",
        "entity_default_sort_direction",
        "entity_track_activity",
    ):
        assert key in dialog._widgets
    direction = dialog._widgets["entity_default_sort_direction"]
    items = {direction.itemText(i) for i in range(direction.count())}
    assert items == {""} | set(ENTITY_SORT_DIRECTIONS)


def test_entity_create_dialog_forwards_intrinsics(qtbot, client):
    dialog = EntityCreateDialog(client)
    qtbot.addWidget(dialog)
    dialog._widgets["entity_name"].setText("Engagement")
    dialog._widgets["entity_description"].setPlainText("d")
    dialog._widgets["entity_default_sort_field"].setText("createdAt")
    dialog._widgets["entity_default_sort_direction"].setCurrentText("desc")
    dialog._widgets["entity_track_activity"].setCurrentText("true")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()

    stored = client.get_entity(dialog.created_identifier())
    assert stored["entity_default_sort_field"] == "createdAt"
    assert stored["entity_default_sort_direction"] == "desc"
    assert stored["entity_track_activity"] is True


def test_entity_edit_dialog_populates_track_activity(qtbot, client):
    created = client.create_entity(
        {
            "entity_name": "Engagement",
            "entity_description": "d",
            "entity_track_activity": True,
        }
    )
    record = client.get_entity(created["entity_identifier"])
    dialog = EntityEditDialog(client, record)
    qtbot.addWidget(dialog)
    assert dialog._widgets["entity_track_activity"].currentText() == "true"
    # Toggle off and save.
    dialog._widgets["entity_track_activity"].setCurrentText("false")
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()
    assert client.get_entity(created["entity_identifier"])[
        "entity_track_activity"
    ] is False


# ---------------------------------------------------------------------------
# Detail panes render the new attributes read-only
# ---------------------------------------------------------------------------


def test_field_detail_renders_intrinsics_and_options(qtbot, client):
    ent = _seed_entity(client)
    created = client.create_field(
        {
            "field_name": "status",
            "field_description": "d",
            "field_type": "enum",
            "field_belongs_to_entity_identifier": ent,
            "field_tooltip": "pick one",
            "field_read_only": True,
            "field_options": [
                {"option_value": "open", "option_label": "Open", "option_order": 0},
            ],
        }
    )
    record = client.get_field(created["field_identifier"])
    panel = FieldsPanel(client)
    qtbot.addWidget(panel)
    extras = panel.fetch_detail_extras(record)
    detail = panel.render_detail(record, extras)
    qtbot.addWidget(detail)
    tooltip = detail.findChild(object, "field_tooltip_value")
    assert tooltip is not None and tooltip.text() == "pick one"
    read_only = detail.findChild(QCheckBox, "field_read_only_value")
    assert read_only is not None and read_only.isChecked()
    assert not read_only.isEnabled()
    option_row = detail.findChild(object, "field_option_row")
    assert option_row is not None and "open" in option_row.text()


def test_entity_detail_renders_intrinsics(qtbot, client):
    created = client.create_entity(
        {
            "entity_name": "Engagement",
            "entity_description": "d",
            "entity_default_sort_field": "createdAt",
            "entity_default_sort_direction": "asc",
            "entity_track_activity": True,
        }
    )
    record = client.get_entity(created["entity_identifier"])
    panel = EntitiesPanel(client)
    qtbot.addWidget(panel)
    extras = panel.fetch_detail_extras(record)
    detail = panel.render_detail(record, extras)
    qtbot.addWidget(detail)
    sort_field = detail.findChild(object, "entity_default_sort_field_value")
    assert sort_field is not None and sort_field.text() == "createdAt"
    track = detail.findChild(QCheckBox, "entity_track_activity_value")
    assert track is not None and track.isChecked()
    assert not track.isEnabled()
