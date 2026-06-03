"""ActiveEngagementContext tests.

PI-β removed the ``current_engagement.json`` marker: the active engagement is
purely in-memory client-side desktop state (mirrored onto the StorageClient's
``X-Engagement`` header). The former disk load/persist/clear tests are gone.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from PySide6.QtCore import QCoreApplication


@pytest.fixture
def qapp():
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication([])
    return app


def _make_engagement(identifier: str = "ENG-001", code: str = "CRMBUILDER"):
    now = datetime.now(UTC)
    return Engagement(
        engagement_identifier=identifier,
        engagement_code=code,
        engagement_name=f"Engagement {code}",
        engagement_purpose="test purpose",
        engagement_status=EngagementStatus.ACTIVE,
        engagement_last_opened_at=None,
        engagement_created_at=now,
        engagement_updated_at=now,
        engagement_deleted_at=None,
    )


def test_default_state_is_none(qapp):
    ctx = ActiveEngagementContext()
    assert ctx.engagement() is None
    assert ctx.engagement_identifier() is None
    assert ctx.engagement_code() is None


def test_set_engagement_emits_signal(qapp):
    ctx = ActiveEngagementContext()
    received: list = []
    ctx.active_engagement_changed.connect(received.append)

    eng = _make_engagement()
    ctx.set_engagement(eng)

    assert received == [eng]
    assert ctx.engagement() is eng
    assert ctx.engagement_identifier() == "ENG-001"
    assert ctx.engagement_code() == "CRMBUILDER"


def test_clear_emits_none(qapp):
    ctx = ActiveEngagementContext()
    received: list = []
    ctx.active_engagement_changed.connect(received.append)

    ctx.set_engagement(_make_engagement())
    ctx.clear()

    assert received[-1] is None
    assert ctx.engagement() is None
