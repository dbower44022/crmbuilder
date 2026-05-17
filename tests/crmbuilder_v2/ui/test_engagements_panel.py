"""Engagements panel tests — UI v0.5 slice C.

Covers PRD §5.1 / §5.6: master-pane columns and sort order, active-
engagement marker, soft-deleted toggle and treatment, right-click menu,
detail-pane field layout, refresh hooks (file-watch + signal), empty-
state, and the slice-A sidebar entry routing.

The ``engagement_client`` fixture wires a ``StorageClient`` over a real
FastAPI ``TestClient`` against the per-test meta DB so the panel
exercises the genuine access → REST → DB path.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from crmbuilder_v2.access import meta_exporter
from crmbuilder_v2.access.meta_db import (
    bootstrap_meta_db,
    reset_meta_engine_cache,
)
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.engagement_crud import (
    EngagementCreateDialog,
)
from crmbuilder_v2.ui.main_window import (
    ENTITY_TYPE_TO_SIDEBAR_LABEL,
    MainWindow,
)
from crmbuilder_v2.ui.panels.engagements import (
    ACTIVE_GLYPH,
    SOFT_DELETED_GLYPH,
    EngagementsPanel,
    format_relative_date,
)
from crmbuilder_v2.ui.refresh import (
    _FILENAME_TO_ENTITY_TYPE,
    _SUBDIR_FILENAME_TO_ENTITY_TYPE,
)
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS, Sidebar
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QDialog, QLineEdit


@pytest.fixture
def _redirect_meta_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        meta_exporter, "meta_export_dir", lambda: tmp_path / "meta-export"
    )
    yield


@pytest.fixture
def engagement_client(v2_env, _redirect_meta_export) -> StorageClient:
    """A StorageClient over a real TestClient bound to the per-test meta DB."""
    reset_meta_engine_cache()
    bootstrap_meta_db()
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _seed(client: StorageClient, code: str, name: str, **overrides) -> dict:
    body = {
        "engagement_code": code,
        "engagement_name": name,
        "engagement_purpose": overrides.pop("engagement_purpose", f"Test {code}"),
    }
    body.update(overrides)
    return client.create_engagement(body)


def _wait_rows(qtbot, panel: EngagementsPanel, count: int) -> None:
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


# ---------------------------------------------------------------------------
# Sidebar wiring
# ---------------------------------------------------------------------------


def test_engagements_is_single_entry_in_engagements_group():
    groups = dict(SIDEBAR_GROUPS)
    assert groups["Engagements"] == ("Engagements",)


def test_sidebar_renders_engagements_above_governance(qtbot):
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)
    rendered = [sidebar.item(r).text() for r in range(sidebar.count())]
    assert "ENGAGEMENTS" in rendered
    assert "Engagements" in rendered
    # The Engagements entry appears under the ENGAGEMENTS header and
    # before the GOVERNANCE header.
    eng_idx = rendered.index("Engagements")
    gov_idx = rendered.index("GOVERNANCE")
    assert eng_idx < gov_idx


def test_main_window_engagements_page_is_panel(
    qtbot, lifecycle_stub, engagement_client
):
    window = MainWindow(lifecycle=lifecycle_stub, client=engagement_client)
    qtbot.addWidget(window)
    page = window._stack.widget(window._pages_by_entry["Engagements"])
    assert isinstance(page, EngagementsPanel)


# ---------------------------------------------------------------------------
# Master-pane columns + sort
# ---------------------------------------------------------------------------


def test_master_pane_five_columns(qtbot, engagement_client):
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    columns = panel.list_columns()
    assert [c.title for c in columns] == [
        "Identifier",
        "Code",
        "Name",
        "Status",
        "Last Opened",
    ]


def test_default_sort_is_last_opened_desc(qtbot, engagement_client):
    # Three engagements; PATCH last_opened_at to set known ordering.
    _seed(engagement_client, "ALPHA", "Alpha")
    _seed(engagement_client, "BRAVO", "Bravo")
    _seed(engagement_client, "CHARLIE", "Charlie")
    now = datetime.now(UTC)
    engagement_client.patch_engagement(
        "ENG-001",
        {"engagement_last_opened_at": (now - timedelta(hours=2)).isoformat()},
    )
    engagement_client.patch_engagement(
        "ENG-002",
        {"engagement_last_opened_at": now.isoformat()},
    )
    engagement_client.patch_engagement(
        "ENG-003",
        {"engagement_last_opened_at": (now - timedelta(days=1)).isoformat()},
    )

    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 3)
    ids = [
        panel._model.record_at(r)["engagement_identifier"]
        for r in range(panel._model.rowCount())
    ]
    assert ids == ["ENG-002", "ENG-001", "ENG-003"]


def test_soft_deleted_rows_sort_to_bottom(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    _seed(engagement_client, "BRAVO", "Bravo")
    engagement_client.delete_engagement("ENG-001")
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    panel._show_deleted_check.setChecked(True)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=3000)
    ids = [
        panel._model.record_at(r)["engagement_identifier"]
        for r in range(panel._model.rowCount())
    ]
    # Bravo is live and stays on top; Alpha (deleted) sinks to the bottom.
    assert ids == ["ENG-002", "ENG-001"]


# ---------------------------------------------------------------------------
# Active-engagement marker
# ---------------------------------------------------------------------------


def test_active_engagement_marker_in_identifier_cell(
    qtbot, qapp, engagement_client
):
    _seed(engagement_client, "ALPHA", "Alpha")
    _seed(engagement_client, "BRAVO", "Bravo")
    active_ctx = ActiveEngagementContext()
    # Stub: synthesise an active engagement matching ENG-002.
    from crmbuilder_v2.access.engagement_models import (
        Engagement,
        EngagementStatus,
    )

    now = datetime.now(UTC)
    active_ctx.set_engagement(
        Engagement(
            engagement_identifier="ENG-002",
            engagement_code="BRAVO",
            engagement_name="Bravo",
            engagement_purpose="",
            engagement_status=EngagementStatus.ACTIVE,
            engagement_last_opened_at=None,
            engagement_export_dir=None,
            engagement_created_at=now,
            engagement_updated_at=now,
            engagement_deleted_at=None,
        )
    )
    panel = EngagementsPanel(engagement_client, active_context=active_ctx)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 2)
    bravo_row = next(
        r
        for r in range(panel._model.rowCount())
        if panel._model.record_at(r)["engagement_identifier"] == "ENG-002"
    )
    alpha_row = next(
        r
        for r in range(panel._model.rowCount())
        if panel._model.record_at(r)["engagement_identifier"] == "ENG-001"
    )
    bravo_display = panel._model.record_at(bravo_row)["_display_identifier"]
    alpha_display = panel._model.record_at(alpha_row)["_display_identifier"]
    assert bravo_display.startswith(ACTIVE_GLYPH)
    assert "ENG-002" in bravo_display
    assert not alpha_display.startswith(ACTIVE_GLYPH)


def test_active_engagement_signal_triggers_refresh(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    active_ctx = ActiveEngagementContext()
    panel = EngagementsPanel(engagement_client, active_context=active_ctx)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    # Switch active engagement: the panel should refresh and the marker
    # repaint. We can observe via _display_identifier changing.
    initial = panel._model.record_at(0)["_display_identifier"]
    assert not initial.startswith(ACTIVE_GLYPH)
    from crmbuilder_v2.access.engagement_models import (
        Engagement,
        EngagementStatus,
    )

    now = datetime.now(UTC)
    active_ctx.set_engagement(
        Engagement(
            engagement_identifier="ENG-001",
            engagement_code="ALPHA",
            engagement_name="Alpha",
            engagement_purpose="",
            engagement_status=EngagementStatus.ACTIVE,
            engagement_last_opened_at=None,
            engagement_export_dir=None,
            engagement_created_at=now,
            engagement_updated_at=now,
            engagement_deleted_at=None,
        )
    )
    qtbot.waitUntil(
        lambda: panel._model.record_at(0)["_display_identifier"].startswith(
            ACTIVE_GLYPH
        ),
        timeout=3000,
    )


# ---------------------------------------------------------------------------
# Soft-deleted treatment + Show-soft-deleted toggle
# ---------------------------------------------------------------------------


def test_soft_deleted_glyph_and_strikethrough(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    engagement_client.delete_engagement("ENG-001")
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    # Toggle on the soft-deleted filter; row appears.
    panel._show_deleted_check.setChecked(True)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    record = panel._model.record_at(0)
    assert record["_display_identifier"].startswith(SOFT_DELETED_GLYPH)
    assert panel._strikethrough_for_record(record) is True


def test_soft_deleted_hidden_by_default(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    engagement_client.delete_engagement("ENG-001")
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 0)


# ---------------------------------------------------------------------------
# Context menu
# ---------------------------------------------------------------------------


def test_context_menu_live_row_has_four_actions(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "New" in labels
    assert "Edit" in labels
    assert "Delete" in labels
    assert "Restore" not in labels
    # Activate is NOT in the menu — switching happens via the picker
    # (slice D), not the context menu.
    assert "Activate" not in labels


def test_context_menu_offers_restore_on_soft_deleted(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    engagement_client.delete_engagement("ENG-001")
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    panel._show_deleted_check.setChecked(True)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in menu.actions()]
    assert "Restore" in labels
    assert "Delete" not in labels


# ---------------------------------------------------------------------------
# Detail pane
# ---------------------------------------------------------------------------


def test_detail_pane_renders_form_fields(qtbot, engagement_client):
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    now = datetime.now(UTC)
    record = {
        "engagement_identifier": "ENG-001",
        "engagement_code": "ALPHA",
        "engagement_name": "Alpha",
        "engagement_purpose": "test",
        "engagement_status": "active",
        "engagement_export_dir": "/tmp/x",
        "engagement_created_at": now.isoformat(),
        "engagement_updated_at": now.isoformat(),
        "engagement_deleted_at": None,
        "engagement_last_opened_at": None,
        "_is_active_engagement": False,
    }
    detail = panel.render_detail(record, {})
    # All expected fields are present with the correct objectNames.
    expected = [
        "engagement_identifier_value",
        "engagement_code_value",
        "engagement_name_value",
        "engagement_purpose_value",
        "engagement_status_value",
        "engagement_export_dir_value",
        "engagement_created_at_value",
        "engagement_updated_at_value",
    ]
    for name in expected:
        assert detail.findChild(object, name) is not None, name


def test_detail_pane_shows_deleted_at_when_soft_deleted(
    qtbot, engagement_client
):
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    now = datetime.now(UTC)
    record = {
        "engagement_identifier": "ENG-001",
        "engagement_code": "ALPHA",
        "engagement_name": "Alpha",
        "engagement_purpose": "test",
        "engagement_status": "active",
        "engagement_export_dir": None,
        "engagement_created_at": now.isoformat(),
        "engagement_updated_at": now.isoformat(),
        "engagement_deleted_at": now.isoformat(),
        "engagement_last_opened_at": None,
        "_is_active_engagement": False,
    }
    detail = panel.render_detail(record, {})
    assert (
        detail.findChild(QLineEdit, "engagement_deleted_at_value") is not None
    )


# ---------------------------------------------------------------------------
# Empty state
# ---------------------------------------------------------------------------


def test_empty_state_visible_when_no_engagements(qtbot, engagement_client):
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    panel.refresh()
    # The empty-state widget is toggled on by _post_process_records when
    # the fetch returns an empty list; isHidden() reflects the explicit
    # setVisible state regardless of whether the parent panel is shown.
    qtbot.waitUntil(
        lambda: panel._empty_state.isHidden() is False, timeout=3000
    )
    assert panel._master_view.isHidden() is True


def test_empty_state_hidden_when_records_exist(qtbot, engagement_client):
    _seed(engagement_client, "ALPHA", "Alpha")
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 1)
    assert panel._empty_state.isHidden() is True
    assert panel._master_view.isHidden() is False


def test_empty_state_create_button_opens_create_dialog(
    qtbot, engagement_client, monkeypatch
):
    panel = EngagementsPanel(engagement_client)
    qtbot.addWidget(panel)
    _wait_rows(qtbot, panel, 0)

    opened: dict = {"count": 0}

    class _StubCreate:
        def __init__(self, client, parent=None):
            opened["count"] += 1

        def exec(self):  # noqa: A003 — Qt naming
            return QDialog.DialogCode.Rejected

        def created_identifier(self):
            return None

    monkeypatch.setattr(
        "crmbuilder_v2.ui.panels.engagements.EngagementCreateDialog",
        _StubCreate,
    )
    btn = panel._empty_state.findChild(
        object, "empty_state_create_engagement_button"
    )
    assert btn is not None
    btn.click()
    assert opened["count"] == 1


# ---------------------------------------------------------------------------
# Refresh registration: file-watch + signal
# ---------------------------------------------------------------------------


def test_engagements_subdir_filename_is_mapped():
    assert (
        _SUBDIR_FILENAME_TO_ENTITY_TYPE[("meta", "engagements.json")]
        == "engagement"
    )
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL["engagement"] == "Engagements"
    # The bare-filename map does NOT contain ``engagements.json`` (the
    # meta snapshot lives one level down).
    assert "engagements.json" not in _FILENAME_TO_ENTITY_TYPE


def test_external_write_refreshes_current_engagements_panel(
    qtbot, lifecycle_stub, engagement_client, export_dir
):
    window = MainWindow(
        lifecycle=lifecycle_stub,
        client=engagement_client,
        snapshot_dir=export_dir,
    )
    qtbot.addWidget(window)
    window._sidebar.select_entry("Engagements")
    panel = window._stack.widget(window._pages_by_entry["Engagements"])
    _wait_rows(qtbot, panel, 0)

    _seed(engagement_client, "ALPHA", "Alpha")
    window._on_data_changed("engagement")
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    assert (
        panel._model.record_at(0)["engagement_identifier"] == "ENG-001"
    )


# ---------------------------------------------------------------------------
# format_relative_date helper
# ---------------------------------------------------------------------------


def test_format_relative_date_handles_null():
    assert format_relative_date(None) == "—"


def test_format_relative_date_minutes():
    now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    dt = now - timedelta(minutes=5)
    assert format_relative_date(dt, now=now) == "5 minutes ago"


def test_format_relative_date_hours():
    now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    dt = now - timedelta(hours=3)
    assert format_relative_date(dt, now=now) == "3 hours ago"


def test_format_relative_date_days():
    now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    dt = now - timedelta(days=5)
    assert format_relative_date(dt, now=now) == "5 days ago"


def test_format_relative_date_iso_after_30_days():
    now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    dt = now - timedelta(days=45)
    # Older than 30 days falls back to ISO date.
    assert format_relative_date(dt, now=now) == dt.date().isoformat()
