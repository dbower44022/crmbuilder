"""Tests for the selectable/copyable text helpers (PI-124 T1)."""

from __future__ import annotations

import pytest
from crmbuilder_v2.ui.widgets.selectable_text import (
    SELECTABLE_TEXT_FLAGS,
    CopyableMessageBox,
    copy_to_clipboard,
    make_selectable,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMessageBox


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
