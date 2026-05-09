"""Tests for the Topic create/edit/delete dialogs (v0.2 slice D)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.dialogs.topic_create import TopicCreateDialog
from crmbuilder_v2.ui.dialogs.topic_delete import TopicDeleteDialog
from crmbuilder_v2.ui.dialogs.topic_edit import TopicEditDialog
from crmbuilder_v2.ui.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from crmbuilder_v2.ui.widgets.hierarchical_picker import HierarchicalEntityPicker
from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QPushButton


def _stub_client(topics: list[dict[str, Any]] | None = None) -> MagicMock:
    client = MagicMock()
    client.list_topics.return_value = list(topics or [])
    return client


def _topic(
    identifier: str, name: str = "", parent: str | None = None
) -> dict[str, Any]:
    return {
        "identifier": identifier,
        "name": name or identifier,
        "description": "",
        "parent_topic_identifier": parent,
    }


def _record() -> dict[str, Any]:
    return {
        "identifier": "TOP-001",
        "name": "Storage system",
        "description": "the v2 store",
        "parent_topic_identifier": "TOP-000",
    }


def _fill_required(dialog: TopicCreateDialog) -> None:
    dialog._widgets.identifier.setText("TOP-001")
    dialog._widgets.name.setText("Storage system")


# ---------------------------------------------------------------------------
# TopicCreateDialog
# ---------------------------------------------------------------------------


def test_construct_has_all_four_fields(qtbot):
    dialog = TopicCreateDialog(_stub_client())
    qtbot.addWidget(dialog)

    assert isinstance(dialog._widgets.identifier, QLineEdit)
    assert isinstance(dialog._widgets.name, QLineEdit)
    assert isinstance(dialog._widgets.description, QPlainTextEdit)
    # parent_topic is a tree-picker, rendered as a QPushButton.
    assert isinstance(dialog._widgets.parent_topic, QPushButton)
    assert dialog._widgets.parent_topic.text() == "(no selection)"
    assert dialog._save_btn is not None
    assert dialog._cancel_btn is not None


def test_required_fields_block_submission(qtbot):
    client = _stub_client()
    dialog = TopicCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._on_save_clicked()

    client.create_topic.assert_not_called()
    for field in ("identifier", "name"):
        label = dialog._widgets.error_labels[field]
        assert label.text() == "This field is required."


def test_invalid_identifier_format_blocks_submission(qtbot):
    client = _stub_client()
    dialog = TopicCreateDialog(client)
    qtbot.addWidget(dialog)

    dialog._widgets.identifier.setText("abc")
    dialog._widgets.name.setText("name")

    dialog._on_save_clicked()

    assert client.create_topic.call_count == 0
    err = dialog._widgets.error_labels["identifier"].text()
    assert "TOP-NNN" in err


def test_successful_create_without_parent_omits_field(qtbot):
    client = _stub_client()
    client.create_topic.return_value = {
        "identifier": "TOP-001",
        "name": "Storage system",
    }
    dialog = TopicCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    assert dialog.created_identifier() == "TOP-001"
    args, _kwargs = client.create_topic.call_args
    body = args[0]
    assert body["identifier"] == "TOP-001"
    assert body["name"] == "Storage system"
    # parent_topic omitted when empty in create.
    assert "parent_topic" not in body


def test_successful_create_with_parent_sends_parent_topic(qtbot, monkeypatch):
    """Selecting a parent in the tree picker populates the parent_topic field."""
    parents = [_topic("TOP-000", "Existing parent")]
    client = _stub_client(parents)
    client.create_topic.return_value = {"identifier": "TOP-001"}
    dialog = TopicCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    captured: dict[str, Any] = {}

    class _AcceptingPicker:
        def __init__(self, nodes, *, selectable=None, title="", current_id=None, parent=None):
            captured["nodes"] = nodes
            captured["selectable"] = selectable
            captured["current_id"] = current_id

        def exec(self):  # noqa: A003
            from PySide6.QtWidgets import QDialog
            return QDialog.DialogCode.Accepted

        def selected_id(self):
            return "TOP-000"

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.HierarchicalEntityPicker",
        _AcceptingPicker,
    )

    # Open the picker.
    dialog._on_tree_picker_clicked("parent_topic")
    assert dialog._widgets.parent_topic.text() == "TOP-000"

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    args, _kwargs = client.create_topic.call_args
    body = args[0]
    assert body["parent_topic"] == "TOP-000"


def test_create_picker_data_is_built_from_list_topics(qtbot, monkeypatch):
    """The picker receives nodes built from list_topics()."""
    topics = [
        _topic("TOP-000", "Root"),
        _topic("TOP-001", "Child", parent="TOP-000"),
    ]
    client = _stub_client(topics)
    dialog = TopicCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    captured: dict[str, Any] = {}

    class _CapturePicker:
        def __init__(self, nodes, *, selectable=None, title="", current_id=None, parent=None):
            captured["nodes"] = nodes
            captured["selectable"] = selectable

        def exec(self):  # noqa: A003
            from PySide6.QtWidgets import QDialog
            return QDialog.DialogCode.Rejected

        def selected_id(self):
            return None

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.HierarchicalEntityPicker",
        _CapturePicker,
    )

    dialog._on_tree_picker_clicked("parent_topic")

    nodes = captured["nodes"]
    ids = [n.id for n in nodes]
    assert "TOP-000" in ids
    assert "TOP-001" in ids
    # Create-mode: every node selectable.
    selectable = captured["selectable"]
    if selectable is not None:
        for n in nodes:
            assert selectable(n) is True


def test_validation_error_shows_inline(qtbot):
    client = _stub_client()
    client.create_topic.side_effect = ValidationError(
        errors=[
            {
                "code": "validation_error",
                "field": "name",
                "message": "Name must be set",
            }
        ],
        message="Validation failed",
    )
    dialog = TopicCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["name"].text() != "",
        timeout=2000,
    )
    assert dialog._widgets.error_labels["name"].text() == "Name must be set"


def test_conflict_error_shows_inline_on_identifier(qtbot):
    client = _stub_client()
    client.create_topic.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "exists"}],
        message="exists",
    )
    dialog = TopicCreateDialog(client)
    qtbot.addWidget(dialog)
    _fill_required(dialog)

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._widgets.error_labels["identifier"].text() != "",
        timeout=2000,
    )
    assert (
        dialog._widgets.error_labels["identifier"].text()
        == "An identifier with this value already exists."
    )


# ---------------------------------------------------------------------------
# TopicEditDialog
# ---------------------------------------------------------------------------


def test_edit_construct_pre_populates_from_record(qtbot):
    client = _stub_client()
    dialog = TopicEditDialog(client, _record())
    qtbot.addWidget(dialog)

    assert dialog._widgets.identifier.text() == "TOP-001"
    assert dialog._widgets.name.text() == "Storage system"
    assert dialog._widgets.description.toPlainText() == "the v2 store"
    # Parent picker shows the current parent identifier.
    assert dialog._widgets.parent_topic.text() == "TOP-000"


def test_edit_identifier_is_read_only(qtbot):
    dialog = TopicEditDialog(_stub_client(), _record())
    qtbot.addWidget(dialog)
    assert dialog._widgets.identifier.isReadOnly() is True


def test_edit_no_changes_skips_api_and_accepts(qtbot):
    client = _stub_client()
    dialog = TopicEditDialog(client, _record())
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    client.update_topic.assert_not_called()


def test_edit_single_field_change_sends_one_field_patch(qtbot):
    client = _stub_client()
    client.update_topic.return_value = {"identifier": "TOP-001", "name": "new"}
    dialog = TopicEditDialog(client, _record())
    qtbot.addWidget(dialog)

    dialog._widgets.name.setText("new name")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    args, _kwargs = client.update_topic.call_args
    assert args[0] == "TOP-001"
    body = args[1]
    assert body == {"name": "new name"}


def test_edit_reparent_sends_parent_topic(qtbot, monkeypatch):
    topics = [
        _topic("TOP-000"),
        _topic("TOP-002", "New parent"),
        _topic("TOP-001", "Child", parent="TOP-000"),
    ]
    client = _stub_client(topics)
    client.update_topic.return_value = {"identifier": "TOP-001"}
    record = {
        "identifier": "TOP-001",
        "name": "Child",
        "description": "",
        "parent_topic_identifier": "TOP-000",
    }
    dialog = TopicEditDialog(client, record)
    qtbot.addWidget(dialog)

    class _AcceptPicker:
        def __init__(self, *args, **kwargs):
            pass

        def exec(self):  # noqa: A003
            from PySide6.QtWidgets import QDialog
            return QDialog.DialogCode.Accepted

        def selected_id(self):
            return "TOP-002"

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.HierarchicalEntityPicker",
        _AcceptPicker,
    )
    dialog._on_tree_picker_clicked("parent_topic")
    assert dialog._widgets.parent_topic.text() == "TOP-002"

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    args, _kwargs = client.update_topic.call_args
    assert args[0] == "TOP-001"
    body = args[1]
    assert body == {"parent_topic": "TOP-002"}


def test_edit_cycle_filter_excludes_self_and_descendants(qtbot, monkeypatch):
    """Editing TOP-1 — TOP-1 itself and its descendants are non-selectable."""
    topics = [
        _topic("TOP-1", "Root"),
        _topic("TOP-2", "Mid", parent="TOP-1"),
        _topic("TOP-3", "Leaf", parent="TOP-2"),
        _topic("TOP-9", "Sibling"),
    ]
    client = _stub_client(topics)
    record = topics[0]
    dialog = TopicEditDialog(client, record)
    qtbot.addWidget(dialog)

    captured: dict[str, Any] = {}

    class _CapturePicker:
        def __init__(self, nodes, *, selectable=None, title="", current_id=None, parent=None):
            captured["nodes"] = nodes
            captured["selectable"] = selectable

        def exec(self):  # noqa: A003
            from PySide6.QtWidgets import QDialog
            return QDialog.DialogCode.Rejected

        def selected_id(self):
            return None

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.HierarchicalEntityPicker",
        _CapturePicker,
    )
    dialog._on_tree_picker_clicked("parent_topic")

    selectable = captured["selectable"]
    assert selectable is not None
    by_id = {n.id: n for n in captured["nodes"]}
    assert selectable(by_id["TOP-1"]) is False
    assert selectable(by_id["TOP-2"]) is False
    assert selectable(by_id["TOP-3"]) is False
    assert selectable(by_id["TOP-9"]) is True


def test_edit_not_found_shows_dialog_and_accepts(qtbot, monkeypatch):
    captured: dict[str, Any] = {}

    class _Recorder(ErrorDialog):
        def exec(self):  # noqa: A003
            captured["exec_called"] = True
            return 1

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.ErrorDialog", _Recorder
    )

    client = _stub_client()
    client.update_topic.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = TopicEditDialog(client, _record())
    qtbot.addWidget(dialog)
    dialog._widgets.name.setText("changed")

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_save_clicked()

    assert captured.get("exec_called") is True


# ---------------------------------------------------------------------------
# TopicDeleteDialog
# ---------------------------------------------------------------------------


def test_delete_construct_shows_identifier_and_title(qtbot):
    dialog = TopicDeleteDialog(_stub_client(), "TOP-001", "Storage system")
    qtbot.addWidget(dialog)
    text = dialog._body_label.text()
    assert "TOP-001" in text
    assert "Storage system" in text
    assert "cannot be undone" in text


def test_delete_successful_accepts(qtbot):
    client = _stub_client()
    client.delete_topic.return_value = {"identifier": "TOP-001"}
    dialog = TopicDeleteDialog(client, "TOP-001", "Storage system")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()

    client.delete_topic.assert_called_once_with("TOP-001")


def test_delete_conflict_routes_to_error_dialog(qtbot, monkeypatch):
    """If a topic has children or is referenced, the access layer raises 409."""
    client = _stub_client()
    client.delete_topic.side_effect = ConflictError(
        errors=[{"code": "conflict", "message": "has children"}],
        message="has children",
    )

    captured: dict[str, Any] = {}

    class _StubErrorDialog:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def exec(self):
            return 0

    monkeypatch.setattr(
        "crmbuilder_v2.ui.base.crud_dialog.ErrorDialog", _StubErrorDialog
    )

    dialog = TopicDeleteDialog(client, "TOP-001", "Storage system")
    qtbot.addWidget(dialog)
    dialog._on_delete_clicked()
    qtbot.waitUntil(lambda: "title" in captured, timeout=2000)

    assert captured["title"] == "Could not delete topic"
    assert dialog._delete_btn.isEnabled() is True


def test_delete_not_found_treated_as_success(qtbot):
    client = _stub_client()
    client.delete_topic.side_effect = NotFoundError(
        errors=[{"code": "not_found", "message": "missing"}],
        message="missing",
    )
    dialog = TopicDeleteDialog(client, "TOP-001", "Storage system")
    qtbot.addWidget(dialog)

    with qtbot.waitSignal(dialog.accepted, timeout=2000):
        dialog._on_delete_clicked()


# ---------------------------------------------------------------------------
# Schema-level checks (pure, no dialog construction)
# ---------------------------------------------------------------------------


def test_create_schema_parent_topic_omitted_when_empty():
    """The parent_topic field on Create has omit_when_empty_in_create=True."""
    from crmbuilder_v2.ui.dialogs._topic_schema import topic_fields_create

    fields = topic_fields_create()
    parent = next(f for f in fields if f.key == "parent_topic")
    assert parent.omit_when_empty_in_create is True
    assert parent.widget == "tree_picker"


def test_picker_node_label_format():
    """The picker labels nodes 'IDENT — Name' for readability."""
    from crmbuilder_v2.ui.dialogs._topic_schema import _fetch_topic_nodes

    client = _stub_client(
        [_topic("TOP-1", "Storage system")]
    )
    nodes = _fetch_topic_nodes(client)
    assert len(nodes) == 1
    node = nodes[0]
    assert isinstance(node, HierarchicalEntityPicker.Node)
    assert node.id == "TOP-1"
    assert "Storage system" in node.label
