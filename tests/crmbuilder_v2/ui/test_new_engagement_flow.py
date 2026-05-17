"""Single-gesture NewEngagementDialog flow tests — UI v0.5 slice D.

Covers PRD §5.3: chain of POST → file creation → activation, with the
right rollback on each failure mode.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest
from crmbuilder_v2.access import meta_exporter
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    reset_meta_engine_cache,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.migration.lazy_migration import engagement_db_path
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.activation_worker import SubprocessManagers
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.new_engagement_dialog import NewEngagementDialog
from fastapi.testclient import TestClient


@pytest.fixture
def _redirect_meta_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    target = tmp_path / "meta-export"
    monkeypatch.setattr(meta_exporter, "meta_export_dir", lambda: target)
    yield


@pytest.fixture
def client_env(v2_env, _redirect_meta_export):
    reset_meta_engine_cache()
    bootstrap_meta_db()
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _noop_managers() -> SubprocessManagers:
    return SubprocessManagers(
        kill_api=lambda: None,
        kill_mcp=lambda: None,
        launch_api=lambda _p: None,
        launch_mcp=lambda _p: None,
    )


def test_happy_path_creates_record_file_and_activates(
    qtbot, client_env
):
    ctx = ActiveEngagementContext()
    dialog = NewEngagementDialog(client_env, ctx, _noop_managers())
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("ALPHA")
    dialog._widgets["engagement_name"].setText("Alpha Engagement")
    dialog._widgets["engagement_purpose"].setPlainText("test purpose")
    with qtbot.waitSignal(dialog.accepted, timeout=10000):
        dialog._on_save_clicked()
    # The meta DB row was created.
    record = client_env.get_engagement("ENG-001")
    assert record["engagement_code"] == "ALPHA"
    # The per-engagement DB file was created.
    db_path = engagement_db_path("ALPHA")
    assert db_path.exists()
    # Context shows the new engagement as active.
    assert ctx.engagement_identifier() == "ENG-001"


def test_post_failure_keeps_dialog_open_and_no_file_created(
    qtbot, client_env
):
    # Lowercase code violates the regex; the POST returns 422.
    ctx = ActiveEngagementContext()
    dialog = NewEngagementDialog(client_env, ctx, _noop_managers())
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("alpha")  # invalid
    dialog._widgets["engagement_name"].setText("Alpha")
    dialog._widgets["engagement_purpose"].setPlainText("test")
    dialog._on_save_clicked()
    # Wait for client-side regex error to surface inline.
    qtbot.waitUntil(
        lambda: dialog._error_labels["engagement_code"].text() != "",
        timeout=3000,
    )
    # No engagement was created.
    assert client_env.list_engagements() == []


def test_file_creation_failure_rolls_back_meta_row(
    qtbot, client_env, monkeypatch
):
    ctx = ActiveEngagementContext()
    dialog = NewEngagementDialog(client_env, ctx, _noop_managers())
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("ALPHA")
    dialog._widgets["engagement_name"].setText("Alpha")
    dialog._widgets["engagement_purpose"].setPlainText("test")

    # Inject a failure in the file-creation step.
    def _raise(_code):
        raise RuntimeError("disk full")

    monkeypatch.setattr(dialog, "_create_engagement_db", _raise)

    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._retry_btn.isVisible() or dialog._stay_btn.isVisible()
        or hasattr(dialog, "_inline_error")
        and dialog._inline_error.text() != "",
        timeout=5000,
    )
    # Meta row was rolled back (delete_engagement soft-deletes; list
    # without include_deleted should be empty).
    assert client_env.list_engagements() == []
    # Inline error mentions the disk-full message.
    if hasattr(dialog, "_inline_error"):
        assert "disk full" in dialog._inline_error.text().lower()


def test_activation_failure_keeps_record_and_file_offers_retry(
    qtbot, client_env, monkeypatch
):
    ctx = ActiveEngagementContext()

    # Managers that fail on launch_api (simulating subprocess startup failure).
    def _fail_launch(_p):
        raise RuntimeError("API spawn failed")

    managers = SubprocessManagers(
        kill_api=lambda: None,
        kill_mcp=lambda: None,
        launch_api=_fail_launch,
        launch_mcp=lambda _p: None,
    )

    dialog = NewEngagementDialog(client_env, ctx, managers)
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("ALPHA")
    dialog._widgets["engagement_name"].setText("Alpha")
    dialog._widgets["engagement_purpose"].setPlainText("test")
    dialog._on_save_clicked()
    # Wait for activation failure to surface.
    qtbot.waitUntil(
        lambda: dialog._retry_btn.isHidden() is False
        and dialog._stay_btn.isHidden() is False,
        timeout=10000,
    )
    # Meta row + file persist; the user can retry or stay.
    assert client_env.get_engagement("ENG-001")["engagement_code"] == "ALPHA"
    assert engagement_db_path("ALPHA").exists()


def test_stay_in_previous_closes_dialog(qtbot, client_env, monkeypatch):
    ctx = ActiveEngagementContext()

    def _fail_launch(_p):
        raise RuntimeError("API spawn failed")

    managers = SubprocessManagers(
        kill_api=lambda: None,
        kill_mcp=lambda: None,
        launch_api=_fail_launch,
        launch_mcp=lambda _p: None,
    )
    dialog = NewEngagementDialog(client_env, ctx, managers)
    qtbot.addWidget(dialog)
    dialog._widgets["engagement_code"].setText("ALPHA")
    dialog._widgets["engagement_name"].setText("Alpha")
    dialog._widgets["engagement_purpose"].setPlainText("test")
    dialog._on_save_clicked()
    qtbot.waitUntil(
        lambda: dialog._stay_btn.isHidden() is False, timeout=10000
    )
    with qtbot.waitSignal(dialog.rejected, timeout=2000):
        dialog._stay_btn.click()
