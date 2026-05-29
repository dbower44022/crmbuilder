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
from crmbuilder_v2.access.db import bootstrap_database, session_scope
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
from crmbuilder_v2.migration.lazy_migration import engagement_db_path
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


def _make_decision(identifier: str, title: str) -> None:
    with session_scope() as s:
        decisions.create(
            s,
            identifier=identifier,
            title=title,
            decision_date="05-07-26",
            status="Active",
            executive_summary="PI-102 test executive summary. " * 7,
        )


@pytest.fixture
def two_engagements(v2_env, tmp_path: Path) -> SimpleNamespace:
    reset_meta_engine_cache()
    bootstrap_meta_db()
    crm_export = tmp_path / "crm_export"
    cbm_export = tmp_path / "cbm_export"
    crm_export.mkdir()
    cbm_export.mkdir()
    _seed_meta("ENG-001", "CRMBUILDER", str(crm_export))
    _seed_meta("ENG-002", "CBM", str(cbm_export))
    yield SimpleNamespace(crm_export=crm_export, cbm_export=cbm_export)
    reset_meta_engine_cache()


def test_switch_engagements_routes_to_correct_db(two_engagements):
    # Activate CRMBUILDER and write a record.
    route_settings_to_engagement("CRMBUILDER")
    bootstrap_database()
    _make_decision("DEC-001", "crm decision")
    crm_db = engagement_db_path("CRMBUILDER")
    assert crm_db.exists()

    # Activate CBM and write a different record.
    route_settings_to_engagement("CBM")
    bootstrap_database()
    _make_decision("DEC-002", "cbm decision")
    cbm_db = engagement_db_path("CBM")
    assert cbm_db != crm_db

    # CBM's DB holds only DEC-002 (no cross-contamination).
    with session_scope(export=False) as s:
        assert [d["identifier"] for d in decisions.list_all(s)] == ["DEC-002"]

    # Switching back to CRMBUILDER shows only DEC-001.
    route_settings_to_engagement("CRMBUILDER")
    with session_scope(export=False) as s:
        assert [d["identifier"] for d in decisions.list_all(s)] == ["DEC-001"]


def test_switch_engagements_routes_to_correct_export_dir(two_engagements):
    route_settings_to_engagement("CRMBUILDER")
    bootstrap_database()
    _make_decision("DEC-001", "crm decision")
    crm_snapshot = json.loads(
        (two_engagements.crm_export / "decisions.json").read_text()
    )
    assert [d["identifier"] for d in crm_snapshot] == ["DEC-001"]

    route_settings_to_engagement("CBM")
    bootstrap_database()
    _make_decision("DEC-002", "cbm decision")
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
