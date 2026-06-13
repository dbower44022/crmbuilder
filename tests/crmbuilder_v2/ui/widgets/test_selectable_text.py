"""Tests for the selectable/copyable text helpers (PI-124 T1)."""

from __future__ import annotations

import re
from pathlib import Path

import crmbuilder_v2.ui as _ui_pkg
import pytest
from crmbuilder_v2.ui.widgets import selectable_text
from crmbuilder_v2.ui.widgets.selectable_text import (
    SELECTABLE_TEXT_FLAGS,
    CopyableMessageBox,
    copy_to_clipboard,
    make_selectable,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMessageBox, QTextEdit


def test_make_selectable_sets_exactly_the_two_flags(qapp, qtbot):
    label = QLabel("message")
    qtbot.addWidget(label)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    make_selectable(label)
    assert label.textInteractionFlags() == SELECTABLE_TEXT_FLAGS


def test_make_selectable_returns_widget_for_chaining(qapp, qtbot):
    label = QLabel("message")
    qtbot.addWidget(label)
    assert make_selectable(label) is label


def test_make_selectable_ors_into_existing_flags(qapp, qtbot):
    label = QLabel("<a href='https://example.test'>link</a>")
    qtbot.addWidget(label)
    label.setTextInteractionFlags(
        Qt.TextInteractionFlag.LinksAccessibleByMouse
    )
    make_selectable(label)
    flags = label.textInteractionFlags()
    assert flags & Qt.TextInteractionFlag.LinksAccessibleByMouse
    assert flags & SELECTABLE_TEXT_FLAGS == SELECTABLE_TEXT_FLAGS


def test_copyable_message_box_text_and_informative_labels_selectable(
    qapp, qtbot
):
    box = CopyableMessageBox()
    qtbot.addWidget(box)
    box.setText("main message")
    box.setInformativeText("informative message")
    labels = {
        label.text(): label for label in box.findChildren(QLabel)
    }
    for text in ("main message", "informative message"):
        flags = labels[text].textInteractionFlags()
        assert flags & SELECTABLE_TEXT_FLAGS == SELECTABLE_TEXT_FLAGS


@pytest.mark.parametrize(
    ("method_name", "icon"),
    [
        ("information", QMessageBox.Icon.Information),
        ("warning", QMessageBox.Icon.Warning),
        ("critical", QMessageBox.Icon.Critical),
        ("question", QMessageBox.Icon.Question),
    ],
)
def test_static_classmethods_return_clicked_button(
    qapp, qtbot, monkeypatch, method_name, icon
):
    # Drive the box with defaultButton().click() rather than a real
    # exec() loop — clicking routes through QMessageBox's internal
    # button protocol, so clickedButton() is populated identically.
    shown: list[CopyableMessageBox] = []

    def fake_exec(self):
        shown.append(self)
        self.defaultButton().click()
        return 0

    monkeypatch.setattr(CopyableMessageBox, "exec", fake_exec)
    method = getattr(CopyableMessageBox, method_name)
    result = method(
        None,
        "Title",
        "Body",
        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
        QMessageBox.StandardButton.Cancel,
    )
    assert result == QMessageBox.StandardButton.Cancel
    assert len(shown) == 1
    assert shown[0].icon() == icon
    assert shown[0].windowTitle() == "Title"
    assert shown[0].text() == "Body"


def test_static_classmethods_default_to_ok_button(qapp, qtbot, monkeypatch):
    # No buttons argument → the box carries a single Ok button.
    def fake_exec(self):
        ok = self.button(QMessageBox.StandardButton.Ok)
        assert ok is not None
        ok.click()
        return 0

    monkeypatch.setattr(CopyableMessageBox, "exec", fake_exec)
    result = CopyableMessageBox.information(None, "Title", "Body")
    assert result == QMessageBox.StandardButton.Ok


def test_copy_to_clipboard_round_trips(qapp, qtbot):
    assert copy_to_clipboard("copied payload") is True
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == "copied payload"


def test_copy_to_clipboard_returns_false_without_clipboard(
    qapp, qtbot, monkeypatch
):
    # Exercise the guarded branch: a headless process can have no
    # clipboard, in which case the helper reports failure rather than
    # raising.
    class _NoClipboard:
        @staticmethod
        def clipboard():
            return None

    monkeypatch.setattr(selectable_text, "QGuiApplication", _NoClipboard)
    assert copy_to_clipboard("dropped payload") is False


def test_copyable_message_box_detailed_text_pane_is_selectable(qapp, qtbot):
    # The detailed-text pane is a read-only QTextEdit; an operator must
    # be able to drag-select and Ctrl+C the diagnostic payload it holds.
    box = CopyableMessageBox()
    qtbot.addWidget(box)
    box.setText("main message")
    box.setDetailedText("detailed diagnostic payload")
    panes = box.findChildren(QTextEdit)
    assert len(panes) == 1
    pane = panes[0]
    assert pane.isReadOnly()
    assert pane.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_make_selectable_leaves_raw_qmessagebox_informative_mouse_only(
    qapp, qtbot
):
    # Documents the QMessageBox caveat in make_selectable's docstring:
    # the box-level flags don't reach the informative-text label, which
    # Qt creates mouse-only from the style hint. CopyableMessageBox is
    # the fix — the contrast that justifies the subclass.
    raw = QMessageBox()
    qtbot.addWidget(raw)
    raw.setText("main message")
    make_selectable(raw)
    raw.setInformativeText("informative message")
    raw_label = raw.findChild(QLabel, "qt_msgbox_informativelabel")
    assert raw_label is not None
    raw_flags = raw_label.textInteractionFlags()
    assert raw_flags & Qt.TextInteractionFlag.TextSelectableByMouse
    assert (raw_flags & SELECTABLE_TEXT_FLAGS) != SELECTABLE_TEXT_FLAGS

    box = CopyableMessageBox()
    qtbot.addWidget(box)
    box.setText("main message")
    box.setInformativeText("informative message")
    box_label = box.findChild(QLabel, "qt_msgbox_informativelabel")
    assert box_label is not None
    box_flags = box_label.textInteractionFlags()
    assert (box_flags & SELECTABLE_TEXT_FLAGS) == SELECTABLE_TEXT_FLAGS


# Raw popups whose text isn't selectable defeat the PI-124 mechanism, so
# the WTK-145 sweep routes every crmbuilder_v2 popup through
# CopyableMessageBox. This guard keeps a new raw QMessageBox from slipping
# back in. ``selectable_text`` itself is exempt — it subclasses QMessageBox
# to define the replacement.
_RAW_INSTANTIATION = re.compile(r"QMessageBox\(")
_RAW_STATIC_CALL = re.compile(
    r"QMessageBox\.(information|warning|critical|question)\("
)


def test_no_raw_qmessagebox_popups_in_v2_ui():
    ui_root = Path(_ui_pkg.__file__).parent
    offenders: list[str] = []
    for path in ui_root.rglob("*.py"):
        if path.name == "selectable_text.py":
            continue
        source = path.read_text(encoding="utf-8")
        if _RAW_INSTANTIATION.search(source) or _RAW_STATIC_CALL.search(source):
            offenders.append(str(path.relative_to(ui_root)))
    assert not offenders, (
        "Raw QMessageBox popups must route through CopyableMessageBox "
        f"(PI-124 / WTK-145); offending files: {offenders}"
    )
