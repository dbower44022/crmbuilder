"""Top-strip widget tests — UI v0.5 slice D.

Covers PRD §5.2: the top-strip shows the active engagement, updates on
context change, and emits ``clicked`` when activated by the user.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access.engagement_models import Engagement, EngagementStatus
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.widgets.engagement_top_strip import EngagementTopStrip
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent


def _eng(identifier="ENG-001", code="ALPHA", name="Alpha") -> Engagement:
    now = datetime.now(UTC)
    return Engagement(
        engagement_identifier=identifier,
        engagement_code=code,
        engagement_name=name,
        engagement_purpose="",
        engagement_status=EngagementStatus.ACTIVE,
        engagement_last_opened_at=None,
        engagement_export_dir=None,
        engagement_created_at=now,
        engagement_updated_at=now,
        engagement_deleted_at=None,
    )


def test_top_strip_renders_active_engagement_name_and_code(qtbot, qapp):
    ctx = ActiveEngagementContext()
    ctx.set_engagement(_eng())
    strip = EngagementTopStrip(ctx)
    qtbot.addWidget(strip)
    rendered = strip._label.text()
    assert "Alpha" in rendered
    assert "ALPHA" in rendered


def test_top_strip_renders_placeholder_when_no_engagement(qtbot, qapp):
    ctx = ActiveEngagementContext()
    strip = EngagementTopStrip(ctx)
    qtbot.addWidget(strip)
    assert "No engagement selected" in strip._label.text()


def test_top_strip_re_renders_on_active_engagement_changed(qtbot, qapp):
    ctx = ActiveEngagementContext()
    strip = EngagementTopStrip(ctx)
    qtbot.addWidget(strip)
    initial = strip._label.text()
    assert "No engagement selected" in initial
    ctx.set_engagement(_eng(identifier="ENG-002", code="BRAVO", name="Bravo"))
    assert "Bravo" in strip._label.text()
    assert "BRAVO" in strip._label.text()


def test_top_strip_emits_clicked_on_left_press(qtbot, qapp):
    ctx = ActiveEngagementContext()
    ctx.set_engagement(_eng())
    strip = EngagementTopStrip(ctx)
    qtbot.addWidget(strip)
    with qtbot.waitSignal(strip.clicked, timeout=1000):
        event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPoint(5, 5),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        strip.mousePressEvent(event)
