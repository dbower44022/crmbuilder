"""Integration tests for the UI-launched engagement-routing path (slice B).

Multi-tenancy routing fix slice B (B8): the desktop UI routes the API at
the active engagement through ``runtime.engagement_routing`` — the same
helpers the CLI uses — so a write lands in the active engagement's DB and
export directory and nowhere else. These tests exercise that shared path
across a two-engagement state (CRMBUILDER + CBM), plus the operator
affordances that surface an unusable export directory (B4 / B5 / B6).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from crmbuilder_v2.access import meta_exporter
from crmbuilder_v2.access.db import (
    bootstrap_database,
    reset_engine_cache,
    session_scope,
)
from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    get_meta_session_factory,
    reset_meta_engine_cache,
)
from crmbuilder_v2.access.meta_models import EngagementRow
from crmbuilder_v2.access.repositories import decisions
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.config import reset_settings_cache
from crmbuilder_v2.runtime.engagement_routing import (
    route_settings_to_engagement,
)
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.engagement_crud import EngagementEditDialog
from crmbuilder_v2.ui.panels.engagements import EngagementsPanel
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Routing across two engagements (B8) — direct against the slice-A helper,
# which is exactly what ui/app.py:_route_api_at_active_engagement calls.
# ---------------------------------------------------------------------------


def _seed_meta(identifier: str, code: str, export_dir: str) -> None:
    factory = get_meta_session_factory()
    session = factory()
    try:
        now = datetime.now(UTC)
        session.add(
            EngagementRow(
                engagement_identifier=identifier,
                engagement_code=code,
                engagement_name=f"Engagement {code}",
                engagement_purpose="routing test",
                engagement_status="active",
                engagement_export_dir=export_dir,
                engagement_created_at=now,
                engagement_updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()


def _seed_unified(identifier: str, code: str, export_dir: str) -> None:
    from crmbuilder_v2.access.db import get_session_factory
    from crmbuilder_v2.access.models import EngagementRow as UnifiedEngagementRow

    factory = get_session_factory()
    s = factory()
    now = datetime.now(UTC)
    s.add(
        UnifiedEngagementRow(
            engagement_identifier=identifier,
            engagement_code=code,
            engagement_name=f"Engagement {code}",
            engagement_purpose="routing test",
            engagement_status="active",
            engagement_export_dir=export_dir,
            engagement_created_at=now,
            engagement_updated_at=now,
        )
    )
    s.commit()
    s.close()


def _make_decision(identifier: str, title: str, engagement: str) -> None:
    # PI-123 cutover: writes are row-scoped by the active engagement. The real
    # app sets it per request via the scope middleware; here we set it directly.
    from crmbuilder_v2.access import engagement_scope

    with engagement_scope.active_engagement(engagement), session_scope() as s:
        decisions.create(
            s,
            identifier=identifier,
            title=title,
            decision_date="05-07-26",
            status="Active",
            executive_summary="PI-102 test executive summary. " * 7,
        )


@pytest.fixture
def two_engagements(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    # PI-123 cutover: one unified DB, engagements row-scoped. Seed CRMBUILDER +
    # CBM into both the unified engagements table (FK target / resolver) and the
    # meta DB (route_settings_to_engagement still validates against it).
    monkeypatch.setenv("CRMBUILDER_V2_DB_PATH", str(tmp_path / "v2-unified.db"))
    monkeypatch.setenv("CRMBUILDER_V2_EXPORT_DIR", str(tmp_path / "exp"))
    (tmp_path / "exp").mkdir()
    monkeypatch.setenv("CRMBUILDER_V2_ENGAGEMENT_SCOPING_ENABLED", "true")
    reset_settings_cache()
    reset_engine_cache()
    reset_meta_engine_cache()
    bootstrap_database()
    bootstrap_meta_db()
    crm_export = tmp_path / "crm_export"
    cbm_export = tmp_path / "cbm_export"
    crm_export.mkdir()
    cbm_export.mkdir()
    _seed_meta("ENG-001", "CRMBUILDER", str(crm_export))
    _seed_meta("ENG-002", "CBM", str(cbm_export))
    _seed_unified("ENG-001", "CRMBUILDER", str(crm_export))
    _seed_unified("ENG-002", "CBM", str(cbm_export))
    yield SimpleNamespace(crm_export=crm_export, cbm_export=cbm_export)
    reset_meta_engine_cache()
    reset_engine_cache()
    reset_settings_cache()


def test_switch_engagements_routes_to_correct_db(two_engagements):
    # PI-123 cutover: both engagements share the one unified DB; isolation is
    # row-level (engagement_id), not per-file. Write a record under each.
    from crmbuilder_v2.access import engagement_scope

    route_settings_to_engagement("CRMBUILDER")
    _make_decision("DEC-001", "crm decision", "ENG-001")
    route_settings_to_engagement("CBM")
    _make_decision("DEC-002", "cbm decision", "ENG-002")

    # Under CBM's scope, only DEC-002 is visible (no cross-contamination).
    with engagement_scope.active_engagement("ENG-002"), session_scope(export=False) as s:
        assert [d["identifier"] for d in decisions.list_all(s)] == ["DEC-002"]

    # Under CRMBUILDER's scope, only DEC-001 is visible.
    with engagement_scope.active_engagement("ENG-001"), session_scope(export=False) as s:
        assert [d["identifier"] for d in decisions.list_all(s)] == ["DEC-001"]


def test_switch_engagements_routes_to_correct_export_dir(two_engagements):
    # Each engagement's snapshot still lands in its own export dir (D7), driven
    # by route_settings_to_engagement setting CRMBUILDER_V2_EXPORT_DIR.
    route_settings_to_engagement("CRMBUILDER")
    _make_decision("DEC-001", "crm decision", "ENG-001")
    crm_snapshot = json.loads(
        (two_engagements.crm_export / "decisions.json").read_text()
    )
    assert [d["identifier"] for d in crm_snapshot] == ["DEC-001"]

    route_settings_to_engagement("CBM")
    _make_decision("DEC-002", "cbm decision", "ENG-002")
    cbm_snapshot = json.loads(
        (two_engagements.cbm_export / "decisions.json").read_text()
    )
    assert [d["identifier"] for d in cbm_snapshot] == ["DEC-002"]

    # CRMBUILDER's export directory is untouched by the CBM write.
    crm_after = json.loads(
        (two_engagements.crm_export / "decisions.json").read_text()
    )
    assert [d["identifier"] for d in crm_after] == ["DEC-001"]


# ---------------------------------------------------------------------------
# Warning-band states (B4 / B5) and save-confirm (B6) — through the widgets.
# ---------------------------------------------------------------------------


@pytest.fixture
def _redirect_meta_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        meta_exporter, "meta_export_dir", lambda: tmp_path / "meta-export"
    )
    yield


@pytest.fixture
def engagement_client(v2_env, _redirect_meta_export) -> StorageClient:
    reset_meta_engine_cache()
    bootstrap_meta_db()
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _seed(client: StorageClient, code: str, name: str, **overrides) -> dict:
    body = {
        "engagement_code": code,
        "engagement_name": name,
        "engagement_purpose": f"Test {code}",
    }
    body.update(overrides)
    return client.create_engagement(body)


def _active_ctx(identifier: str, code: str) -> ActiveEngagementContext:
    ctx = ActiveEngagementContext()
    now = datetime.now(UTC)
    ctx.set_engagement(
        Engagement(
            engagement_identifier=identifier,
            engagement_code=code,
            engagement_name=code,
            engagement_purpose="",
            engagement_status=EngagementStatus.ACTIVE,
            engagement_last_opened_at=None,
            engagement_export_dir=None,
            engagement_created_at=now,
            engagement_updated_at=now,
            engagement_deleted_at=None,
        )
    )
    return ctx


def _wait_rows(qtbot, panel: EngagementsPanel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


def test_activate_engagement_with_null_export_dir_shows_yellow_warning_band(
    qtbot, engagement_client
):
    # No export_dir supplied → stored null.
    _seed(engagement_client, "CBM", "CBM Engagement")
    panel = EngagementsPanel(
        engagement_client, active_context=_active_ctx("ENG-001", "CBM")
    )
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    assert panel._warning_band.state == "null"
    assert panel._warning_band.isHidden() is False


def test_activate_engagement_with_missing_export_dir_shows_red_warning_band(
    qtbot, engagement_client, tmp_path
):
    missing = tmp_path / "gone"  # absolute, does not exist
    _seed(
        engagement_client,
        "CBM",
        "CBM Engagement",
        engagement_export_dir=str(missing),
    )
    panel = EngagementsPanel(
        engagement_client, active_context=_active_ctx("ENG-001", "CBM")
    )
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    assert panel._warning_band.state == "missing"
    assert panel._warning_band.isHidden() is False


def test_warning_band_hidden_when_export_dir_present(
    qtbot, engagement_client, tmp_path
):
    present = tmp_path / "present"
    present.mkdir()
    _seed(
        engagement_client,
        "CBM",
        "CBM Engagement",
        engagement_export_dir=str(present),
    )
    panel = EngagementsPanel(
        engagement_client, active_context=_active_ctx("ENG-001", "CBM")
    )
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    assert panel._warning_band.state == "hidden"
    assert panel._warning_band.isHidden() is True


def test_save_engagement_with_nonexistent_export_dir_prompts_confirm(
    qtbot, engagement_client, monkeypatch
):
    _seed(engagement_client, "CBM", "CBM Engagement")
    record = engagement_client.get_engagement("ENG-001")
    dialog = EngagementEditDialog(engagement_client, record)
    qtbot.addWidget(dialog)

    calls: dict = {"count": 0}

    def fake_confirm(value: str) -> bool:
        calls["count"] += 1
        calls["value"] = value
        return True

    monkeypatch.setattr(dialog, "_confirm_nonexistent_export_dir", fake_confirm)

    missing = "/nonexistent/zzz-save-anyway"
    dialog._widgets["engagement_export_dir"].setText(missing)
    with qtbot.waitSignal(dialog.accepted, timeout=3000):
        dialog._on_save_clicked()

    assert calls["count"] == 1
    assert calls["value"] == missing
    refreshed = engagement_client.get_engagement("ENG-001")
    assert refreshed["engagement_export_dir"] == missing


def test_save_engagement_cancel_confirm_keeps_dialog_open(
    qtbot, engagement_client, monkeypatch
):
    _seed(engagement_client, "CBM", "CBM Engagement")
    record = engagement_client.get_engagement("ENG-001")
    dialog = EngagementEditDialog(engagement_client, record)
    qtbot.addWidget(dialog)

    monkeypatch.setattr(
        dialog, "_confirm_nonexistent_export_dir", lambda _value: False
    )
    dialog._widgets["engagement_export_dir"].setText("/nonexistent/zzz")
    dialog._on_save_clicked()

    # Cancelling the confirm leaves the dialog open and unsaved.
    from PySide6.QtWidgets import QDialog

    assert dialog.result() != QDialog.DialogCode.Accepted
    refreshed = engagement_client.get_engagement("ENG-001")
    assert refreshed["engagement_export_dir"] is None
