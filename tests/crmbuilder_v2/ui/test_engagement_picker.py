"""Picker dropdown tests — UI v0.5 slice D.

Covers PRD §5.2 ordering rules, active-engagement marker, footer
"Manage engagements…" row, and the click-row-to-activate signal flow.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from crmbuilder_v2.ui.panels.engagements import ACTIVE_GLYPH
from crmbuilder_v2.ui.widgets.engagement_picker import EngagementPicker


def _record(
    identifier: str,
    *,
    code: str = "CODE",
    name: str = "Name",
    status: str = "active",
    last_opened: datetime | None = None,
    deleted: bool = False,
) -> dict:
    return {
        "engagement_identifier": identifier,
        "engagement_code": code,
        "engagement_name": name,
        "engagement_status": status,
        "engagement_last_opened_at": (
            last_opened.isoformat() if last_opened is not None else None
        ),
        "engagement_deleted_at": (
            datetime.now(UTC).isoformat() if deleted else None
        ),
    }


def test_picker_orders_live_by_last_opened_desc(qtbot, qapp):
    now = datetime.now(UTC)
    records = [
        _record("ENG-001", code="A", name="A", last_opened=now - timedelta(hours=2)),
        _record("ENG-002", code="B", name="B", last_opened=now),
        _record("ENG-003", code="C", name="C", last_opened=now - timedelta(days=1)),
    ]
    picker = EngagementPicker(records, active_identifier=None)
    qtbot.addWidget(picker)
    # First three rows (before the Manage footer) should be ENG-002, ENG-001, ENG-003
    identifiers = [
        btn.property("engagement_identifier") for btn in picker._rows
    ]
    assert identifiers == ["ENG-002", "ENG-001", "ENG-003"]


def test_picker_pins_active_engagement_to_top_of_live_tier(qtbot, qapp):
    now = datetime.now(UTC)
    records = [
        _record("ENG-001", code="A", name="A", last_opened=now - timedelta(hours=2)),
        _record("ENG-002", code="B", name="B", last_opened=now),
        _record("ENG-003", code="C", name="C", last_opened=now - timedelta(days=1)),
    ]
    # Active = ENG-003, but ENG-002 has most recent last_opened. Active
    # must be pinned to the top.
    picker = EngagementPicker(records, active_identifier="ENG-003")
    qtbot.addWidget(picker)
    identifiers = [
        btn.property("engagement_identifier") for btn in picker._rows
    ]
    assert identifiers[0] == "ENG-003"


def test_picker_non_live_appear_after_live_in_muted_color(qtbot, qapp):
    now = datetime.now(UTC)
    records = [
        _record("ENG-001", name="Alpha", last_opened=now),
        _record(
            "ENG-002",
            name="Bravo",
            status="paused",
            last_opened=now - timedelta(days=1),
        ),
        _record(
            "ENG-003",
            name="Charlie",
            status="archived",
            last_opened=now - timedelta(days=5),
        ),
    ]
    picker = EngagementPicker(records, active_identifier=None)
    qtbot.addWidget(picker)
    identifiers = [
        btn.property("engagement_identifier") for btn in picker._rows
    ]
    # ENG-001 (active) first; then ENG-002 (paused, more recent); then
    # ENG-003 (archived, older).
    assert identifiers == ["ENG-001", "ENG-002", "ENG-003"]


def test_picker_filters_soft_deleted(qtbot, qapp):
    records = [
        _record("ENG-001", name="A"),
        _record("ENG-002", name="B", deleted=True),
    ]
    picker = EngagementPicker(records, active_identifier=None)
    qtbot.addWidget(picker)
    identifiers = [
        btn.property("engagement_identifier") for btn in picker._rows
    ]
    assert identifiers == ["ENG-001"]


def test_picker_active_row_marked_with_check_glyph(qtbot, qapp):
    records = [_record("ENG-001", name="A"), _record("ENG-002", name="B")]
    picker = EngagementPicker(records, active_identifier="ENG-002")
    qtbot.addWidget(picker)
    by_id = {
        btn.property("engagement_identifier"): btn for btn in picker._rows
    }
    assert by_id["ENG-002"].text().startswith(ACTIVE_GLYPH)
    assert not by_id["ENG-001"].text().startswith(ACTIVE_GLYPH)


def test_picker_footer_present(qtbot, qapp):
    records = [_record("ENG-001", name="A")]
    picker = EngagementPicker(records, active_identifier="ENG-001")
    qtbot.addWidget(picker)
    assert picker._footer_button.text() == "Manage engagements…"


def test_picker_row_click_emits_activation_for_non_active(qtbot, qapp):
    records = [_record("ENG-001", name="A"), _record("ENG-002", name="B")]
    picker = EngagementPicker(records, active_identifier="ENG-001")
    qtbot.addWidget(picker)
    by_id = {
        btn.property("engagement_identifier"): btn for btn in picker._rows
    }
    with qtbot.waitSignal(picker.activation_requested, timeout=1000) as sig:
        by_id["ENG-002"].click()
    assert sig.args == ["ENG-002"]


def test_picker_row_click_on_active_just_closes(qtbot, qapp):
    records = [_record("ENG-001", name="A")]
    picker = EngagementPicker(records, active_identifier="ENG-001")
    qtbot.addWidget(picker)
    # Click on the active row should NOT emit activation_requested.
    captured: list = []
    picker.activation_requested.connect(lambda i: captured.append(i))
    picker._rows[0].click()
    assert captured == []


def test_picker_footer_emits_manage_requested(qtbot, qapp):
    records = [_record("ENG-001", name="A")]
    picker = EngagementPicker(records, active_identifier="ENG-001")
    qtbot.addWidget(picker)
    with qtbot.waitSignal(picker.manage_requested, timeout=1000):
        picker._footer_button.click()
