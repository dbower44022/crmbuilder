"""Tests for the AboutDialog (slice H)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

from PySide6.QtWidgets import QFormLayout, QLabel

from crmbuilder_v2.ui import about_dialog as about_module
from crmbuilder_v2.ui.about_dialog import AboutDialog


def _form_rows(dialog: AboutDialog) -> dict[str, str]:
    """Read the dialog's form layout as a {label: value} mapping."""
    form: QFormLayout | None = None
    layout = dialog.layout()
    for i in range(layout.count()):
        item = layout.itemAt(i)
        candidate = item.layout()
        if isinstance(candidate, QFormLayout):
            form = candidate
            break
    assert form is not None, "AboutDialog must contain a QFormLayout"

    rows: dict[str, str] = {}
    for r in range(form.rowCount()):
        label_item = form.itemAt(r, QFormLayout.ItemRole.LabelRole)
        field_item = form.itemAt(r, QFormLayout.ItemRole.FieldRole)
        assert label_item is not None and field_item is not None
        label_widget = label_item.widget()
        field_widget = field_item.widget()
        assert isinstance(label_widget, QLabel)
        assert isinstance(field_widget, QLabel)
        # Labels are wrapped in <b>...</b>; strip the tags for a stable key.
        key = label_widget.text().replace("<b>", "").replace("</b>", "")
        rows[key] = field_widget.text()
    return rows


def test_construct_shows_required_rows(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    assert "Application" in rows
    assert "Version" in rows
    assert "API base URL" in rows
    assert "Database path" in rows
    assert "Snapshot directory" in rows


def test_application_name_is_crmbuilder_v2(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    assert rows["Application"] == "CRMBuilder v2"


def test_version_falls_back_when_package_metadata_missing(qtbot, monkeypatch):
    def _raise(_name):
        raise PackageNotFoundError("not installed")

    monkeypatch.setattr(about_module, "version", _raise)
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    assert "unknown" in rows["Version"].lower()


def test_paths_are_strings_from_settings(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    # Both paths should be non-empty stringified values.
    assert rows["Database path"]
    assert rows["Snapshot directory"]
    assert rows["API base URL"].startswith("http")


def test_help_about_menu_opens_dialog(
    qapp, qtbot, monkeypatch, lifecycle_stub, client_stub
):
    """The Help → About menu action constructs and exec()s an AboutDialog."""
    from crmbuilder_v2.ui import main_window as mw_module
    from crmbuilder_v2.ui.main_window import MainWindow

    captured: dict = {}

    class _StubAbout:
        def __init__(self, parent=None):
            captured["constructed"] = True
            captured["parent"] = parent

        def exec(self):
            captured["execed"] = True
            return 0

    monkeypatch.setattr(mw_module, "AboutDialog", _StubAbout)

    window = MainWindow(lifecycle=lifecycle_stub, client=client_stub)
    qtbot.addWidget(window)
    window._about_action.trigger()

    assert captured.get("constructed") is True
    assert captured.get("execed") is True
    assert captured.get("parent") is window
