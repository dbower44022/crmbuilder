"""v0.5 slice A — ActiveEngagementContext tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from PySide6.QtCore import QCoreApplication

from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.ui.active_engagement_context import (
    ActiveEngagementContext,
    current_engagement_path,
)


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
        engagement_export_dir=None,
        engagement_created_at=now,
        engagement_updated_at=now,
        engagement_deleted_at=None,
    )


def test_default_state_is_none(qapp, v2_env):
    ctx = ActiveEngagementContext()
    assert ctx.engagement() is None
    assert ctx.engagement_identifier() is None
    assert ctx.engagement_code() is None


def test_set_engagement_emits_signal(qapp, v2_env):
    ctx = ActiveEngagementContext()
    received: list = []
    ctx.active_engagement_changed.connect(received.append)

    eng = _make_engagement()
    ctx.set_engagement(eng)

    assert received == [eng]
    assert ctx.engagement() is eng
    assert ctx.engagement_identifier() == "ENG-001"
    assert ctx.engagement_code() == "CRMBUILDER"


def test_clear_emits_none(qapp, v2_env):
    ctx = ActiveEngagementContext()
    received: list = []
    ctx.active_engagement_changed.connect(received.append)

    ctx.set_engagement(_make_engagement())
    ctx.clear()

    assert received[-1] is None
    assert ctx.engagement() is None


def test_load_from_disk_missing_file(qapp, v2_env):
    ctx = ActiveEngagementContext()
    received: list = []
    ctx.active_engagement_changed.connect(received.append)

    assert not current_engagement_path().exists()
    result = ctx.load_from_disk()

    assert result is None
    assert ctx.engagement() is None
    assert received == [None]


def test_load_from_disk_populates_state(qapp, v2_env):
    path = current_engagement_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "engagement_identifier": "ENG-001",
                "engagement_code": "CRMBUILDER",
                "set_at": datetime.now(UTC).isoformat(),
            }
        )
    )

    ctx = ActiveEngagementContext()
    result = ctx.load_from_disk()

    assert result is not None
    assert result.engagement_identifier == "ENG-001"
    assert result.engagement_code == "CRMBUILDER"
    assert ctx.engagement_identifier() == "ENG-001"


def test_load_from_disk_with_resolver(qapp, v2_env):
    path = current_engagement_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "engagement_identifier": "ENG-007",
                "engagement_code": "CUSTOM",
                "set_at": datetime.now(UTC).isoformat(),
            }
        )
    )

    seen: list = []

    def resolver(identifier: str):
        seen.append(identifier)
        return _make_engagement(identifier=identifier, code="CUSTOM")

    ctx = ActiveEngagementContext()
    result = ctx.load_from_disk(resolver=resolver)

    assert seen == ["ENG-007"]
    assert result is not None
    assert result.engagement_code == "CUSTOM"


def test_load_from_disk_resolver_returns_none_clears_state(qapp, v2_env):
    path = current_engagement_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "engagement_identifier": "ENG-099",
                "engagement_code": "DELETED",
                "set_at": datetime.now(UTC).isoformat(),
            }
        )
    )

    def resolver(identifier: str):
        return None

    ctx = ActiveEngagementContext()
    result = ctx.load_from_disk(resolver=resolver)

    assert result is None
    assert ctx.engagement() is None


def test_load_from_disk_malformed_file_clears_state(qapp, v2_env):
    path = current_engagement_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all{")

    ctx = ActiveEngagementContext()
    result = ctx.load_from_disk()

    assert result is None
    assert ctx.engagement() is None


def test_persist_to_disk_round_trip(qapp, v2_env):
    ctx = ActiveEngagementContext()
    ctx.set_engagement(_make_engagement())
    ctx.persist_to_disk()

    payload = json.loads(current_engagement_path().read_text())
    assert payload["engagement_identifier"] == "ENG-001"
    assert payload["engagement_code"] == "CRMBUILDER"
    assert "set_at" in payload


def test_persist_to_disk_noop_when_no_engagement(qapp, v2_env):
    ctx = ActiveEngagementContext()
    ctx.persist_to_disk()
    assert not current_engagement_path().exists()


def test_clear_disk_removes_file(qapp, v2_env):
    ctx = ActiveEngagementContext()
    ctx.set_engagement(_make_engagement())
    ctx.persist_to_disk()
    assert current_engagement_path().exists()

    ctx.clear_disk()
    assert not current_engagement_path().exists()

    # Idempotent: second clear is a no-op.
    ctx.clear_disk()
