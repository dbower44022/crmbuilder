"""Tests for the LinkFilterInput debounced filter widget.

PI-116 / WTK-061. The widget is a ``QLineEdit`` subclass shared by the
relationship link surfaces (``ReferencesSection``, ``ReferencesPanel``).
It debounces typing into a single ``filterChanged`` emission, emits
immediately on clear, and clears on ``Esc`` when the field has text.
Tests run under the offscreen Qt platform (see the ui conftest).
"""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.link_filter_input import (
    _FILTER_DEBOUNCE_MS,
    LinkFilterInput,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent


def _collector(widget) -> list[str]:
    seen: list[str] = []
    widget.filterChanged.connect(seen.append)
    return seen


def test_defaults_placeholder_and_clear_button(qapp, qtbot):
    widget = LinkFilterInput()
    qtbot.addWidget(widget)
    assert widget.placeholderText() == "Filter links…"
    assert widget.isClearButtonEnabled()
    # Default debounce is the documented 250 ms module constant.
    assert _FILTER_DEBOUNCE_MS == 250


def test_object_name_and_max_width_applied(qapp, qtbot):
    widget = LinkFilterInput(object_name="references_panel_filter", max_width=220)
    qtbot.addWidget(widget)
    assert widget.objectName() == "references_panel_filter"
    assert widget.maximumWidth() == 220


def test_typing_burst_emits_once_after_debounce(qapp, qtbot):
    # Short debounce keeps the test fast while still exercising the timer.
    widget = LinkFilterInput(delay_ms=40)
    qtbot.addWidget(widget)
    seen = _collector(widget)

    # Simulate a fast typist: several setText calls inside one window.
    for text in ("p", "po", "pos", "post"):
        widget.setText(text)

    # Before the debounce settles, nothing has been emitted.
    assert seen == []
    with qtbot.waitSignal(widget.filterChanged, timeout=1000):
        pass
    # Exactly one emission, carrying only the trailing value.
    assert seen == ["post"]


def test_clearing_emits_immediately_and_bypasses_debounce(qapp, qtbot):
    widget = LinkFilterInput(delay_ms=5000)  # long, so debounce can't fire
    qtbot.addWidget(widget)
    widget.setText("postgres")
    seen = _collector(widget)

    widget.clear()
    # Immediate empty emission — no waiting on the 5 s debounce.
    assert seen == [""]


def test_emptying_field_emits_immediately(qapp, qtbot):
    widget = LinkFilterInput(delay_ms=5000)
    qtbot.addWidget(widget)
    widget.setText("abc")
    seen = _collector(widget)
    widget.setText("")
    assert seen == [""]


def test_escape_with_text_clears_and_emits(qapp, qtbot):
    widget = LinkFilterInput(delay_ms=5000)
    qtbot.addWidget(widget)
    widget.setText("postgres")
    seen = _collector(widget)

    event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    widget.keyPressEvent(event)

    assert widget.text() == ""
    assert seen == [""]
    assert event.isAccepted()


def test_escape_on_empty_field_is_ignored(qapp, qtbot):
    widget = LinkFilterInput()
    qtbot.addWidget(widget)
    seen = _collector(widget)

    event = QKeyEvent(
        QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
    )
    widget.keyPressEvent(event)

    # Esc is not consumed so the host panel/dialog can handle it.
    assert not event.isAccepted()
    assert seen == []
