"""Tests for DateField widget."""

from __future__ import annotations

from PySide6.QtCore import QDate

from crmbuilder_v2.ui.widgets.date_field import DateField


def test_default_is_today(qapp, qtbot):
    field = DateField()
    qtbot.addWidget(field)
    expected = QDate.currentDate().toString("MM-dd-yy")
    assert field.date_text() == expected


def test_set_and_read_round_trip(qapp, qtbot):
    field = DateField()
    qtbot.addWidget(field)
    field.set_date("05-08-26")
    assert field.date_text() == "05-08-26"


def test_set_empty_resets_to_today(qapp, qtbot):
    field = DateField()
    qtbot.addWidget(field)
    field.set_date("01-01-20")
    assert field.date_text() == "01-01-20"
    field.set_date("")
    assert field.date_text() == QDate.currentDate().toString("MM-dd-yy")


def test_invalid_string_falls_back_to_today(qapp, qtbot):
    field = DateField()
    qtbot.addWidget(field)
    field.set_date("not-a-date")
    assert field.date_text() == QDate.currentDate().toString("MM-dd-yy")


def test_calendar_popup_enabled(qapp, qtbot):
    field = DateField()
    qtbot.addWidget(field)
    assert field._edit.calendarPopup() is True


def test_date_changed_signal_fires_on_external_change(qapp, qtbot):
    field = DateField()
    qtbot.addWidget(field)
    received: list[str] = []
    field.dateChanged.connect(received.append)
    field.set_date("12-31-25")
    assert received == ["12-31-25"]
