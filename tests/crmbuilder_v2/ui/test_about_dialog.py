"""Tests for the AboutDialog (slice H; restructured in v0.6 slice A)."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError

from crmbuilder_v2.ui import about_dialog as about_module
from crmbuilder_v2.ui.about_dialog import AboutDialog
from PySide6.QtWidgets import QLabel, QVBoxLayout

# Per v0.6 slice A (design pass §2.8 / DEC-094) the metadata table
# renders as a vertical two-line-per-row list: each row is a nested
# QVBoxLayout containing a label QLabel (the field name) and a value
# QLabel. The wordmark + tagline header block is also a nested
# QVBoxLayout but is structurally the first sub-VBox in the outer
# layout, so it's skipped by position rather than content (the
# Application row also legitimately carries "CRMBuilder v2" as its
# value).


def _form_rows(dialog: AboutDialog) -> dict[str, str]:
    """Read the dialog's metadata rows as a {label: value} mapping.

    Walks the outer ``QVBoxLayout`` collecting every label+value pair
    nested in a sub-VBox of exactly two ``QLabel``s. The wordmark +
    tagline header block (the first sub-VBox in the outer layout) is
    skipped by position; the action row is skipped because it's a
    QHBoxLayout, not a QVBoxLayout.
    """
    layout = dialog.layout()
    assert isinstance(layout, QVBoxLayout)
    rows: dict[str, str] = {}
    header_skipped = False
    for i in range(layout.count()):
        item = layout.itemAt(i)
        sub = item.layout()
        if not isinstance(sub, QVBoxLayout):
            continue
        if not header_skipped:
            header_skipped = True
            continue
        labels = [
            sub.itemAt(j).widget()
            for j in range(sub.count())
            if isinstance(sub.itemAt(j).widget(), QLabel)
        ]
        if len(labels) == 2:
            rows[labels[0].text()] = labels[1].text()
    return rows


def test_construct_shows_required_rows(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    assert "Application" in rows
    assert "Version" in rows
    assert "API base url" in rows
    assert "Database path" in rows
    assert "Snapshot directory" in rows


def test_application_name_is_crmbuilder_v2(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    assert rows["Application"] == "CRMBuilder v2"


def test_version_falls_back_to_package_dunder(qtbot, monkeypatch):
    """When the standalone distribution metadata is absent (the bundled
    layout in this repo), AboutDialog falls back to ``crmbuilder_v2.__version__``.
    """
    import crmbuilder_v2

    def _raise(_name):
        raise PackageNotFoundError("not installed")

    monkeypatch.setattr(about_module, "version", _raise)
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    assert rows["Version"] == crmbuilder_v2.__version__


def test_version_falls_back_to_unknown_when_dunder_missing(
    qtbot, monkeypatch
):
    """If both the distribution metadata and the package dunder are missing,
    AboutDialog returns the 'unknown' sentinel."""
    import crmbuilder_v2

    def _raise(_name):
        raise PackageNotFoundError("not installed")

    monkeypatch.setattr(about_module, "version", _raise)
    monkeypatch.delattr(crmbuilder_v2, "__version__", raising=False)
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    assert "unknown" in rows["Version"].lower()


def test_version_displays_0_6_0(qtbot, monkeypatch):
    """v0.6 closeout: package version is 0.6.0."""
    def _raise(_name):
        raise PackageNotFoundError("not installed")

    monkeypatch.setattr(about_module, "version", _raise)
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    assert rows["Version"] == "0.6.0"


def test_paths_are_strings_from_settings(qtbot):
    dialog = AboutDialog()
    qtbot.addWidget(dialog)
    rows = _form_rows(dialog)
    # Both paths should be non-empty stringified values.
    assert rows["Database path"]
    assert rows["Snapshot directory"]
    assert rows["API base url"].startswith("http")


def test_snapshot_directory_renders_not_configured(qtbot, monkeypatch):
    """B3: the UNCONFIGURED sentinel renders as '(not configured)'."""
    from crmbuilder_v2.config import reset_settings_cache
    from crmbuilder_v2.runtime.engagement_routing import UNCONFIGURED_SENTINEL

    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", UNCONFIGURED_SENTINEL)
    reset_settings_cache()
    try:
        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        rows = _form_rows(dialog)
        assert rows["Snapshot directory"] == "(not configured)"
        # The raw sentinel is never shown to the operator.
        assert UNCONFIGURED_SENTINEL not in rows["Snapshot directory"]
    finally:
        reset_settings_cache()


def test_snapshot_directory_renders_missing_path(qtbot, monkeypatch, tmp_path):
    """B3: a configured path absent on disk renders as '(missing — <path>)'."""
    from crmbuilder_v2.config import reset_settings_cache

    missing = tmp_path / "does-not-exist"
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", str(missing))
    reset_settings_cache()
    try:
        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        rows = _form_rows(dialog)
        assert rows["Snapshot directory"] == f"(missing — {missing})"
    finally:
        reset_settings_cache()


def test_snapshot_directory_renders_raw_path_when_present(
    qtbot, monkeypatch, tmp_path
):
    """B3: an existing configured directory renders as its raw path."""
    from crmbuilder_v2.config import reset_settings_cache

    present = tmp_path / "export-here"
    present.mkdir()
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", str(present))
    reset_settings_cache()
    try:
        dialog = AboutDialog()
        qtbot.addWidget(dialog)
        rows = _form_rows(dialog)
        assert rows["Snapshot directory"] == str(present)
    finally:
        reset_settings_cache()


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
