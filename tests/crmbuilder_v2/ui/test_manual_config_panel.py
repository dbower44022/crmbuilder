"""Manual config panel / dialog tests — PI-004 cohort (v0.5+).

Covers ``manual_config.md`` §3.7 acceptance criteria 11, 12, 13
smoke-level: the "Manual Configs" sidebar entry under Methodology,
the five-column master pane (AC-12 — Identifier / Name / Category /
Status / Updated), and the detail-pane completion-field reveal rule
(AC-13 — completion widgets present only when status is ``completed``).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.manual_config import ManualConfigPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def manual_config_client(v2_env) -> StorageClient:
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    # PI-β: mirror the desktop, which sends the active engagement as the
    # X-Engagement header on every request, so scoped reads/writes resolve
    # v2_env's seeded ENG-001 through the per-request scope middleware
    # (the TestClient runs the app in a portal thread that does not inherit
    # the test thread's active-engagement ContextVar).
    sc.set_active_engagement("ENG-001")
    return sc


def _seed_candidate(
    c: StorageClient, name: str = "Saved view: Smoke"
) -> dict:
    body = {
        "manual_config_name": name,
        "manual_config_category": "saved_view",
        "manual_config_description": "Operator must edit clientDefs.",
        "manual_config_instructions": "1. Admin → ... 2. Save.",
    }
    return c.create_manual_config(body)


def _seed_completed(
    c: StorageClient, name: str = "Workflow: Smoke completed"
) -> dict:
    """Create a record and walk it candidate → confirmed → completed."""
    created = c.create_manual_config(
        {
            "manual_config_name": name,
            "manual_config_category": "workflow",
            "manual_config_description": "d",
            "manual_config_instructions": "i",
        }
    )
    identifier = created["manual_config_identifier"]
    c.patch_manual_config(
        identifier, {"manual_config_status": "confirmed"}
    )
    return c.patch_manual_config(
        identifier,
        {
            "manual_config_status": "completed",
            "manual_config_completed_by": "doug@example.com",
        },
    )


def test_manual_configs_appears_in_methodology_group():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert "Manual Configs" in methodology


def test_entity_type_map_has_manual_config_entry():
    assert (
        ENTITY_TYPE_TO_SIDEBAR_LABEL.get("manual_config") == "Manual Configs"
    )
def test_panel_master_pane_columns(qtbot, manual_config_client):
    """AC-12: master pane shows Identifier / Name / Category / Status / Created."""
    panel = ManualConfigPanel(manual_config_client)
    qtbot.addWidget(panel)
    cols = panel.list_columns()
    assert len(cols) == 5
    titles = [c.title for c in cols]
    assert titles == ["Identifier", "Name", "Category", "Status", "Created"]
    fields = [c.field for c in cols]
    assert fields == [
        "manual_config_identifier",
        "manual_config_name",
        "manual_config_category",
        "manual_config_status",
        "created_at_display",
    ]


def test_panel_renders_with_no_records(qtbot, manual_config_client):
    panel = ManualConfigPanel(manual_config_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 0, timeout=3000)


def test_detail_pane_reveals_completion_fields_when_status_completed(
    qtbot, manual_config_client
):
    """AC-13: completion widgets present only when status is ``completed``."""
    candidate_record = _seed_candidate(manual_config_client)
    completed_record = _seed_completed(manual_config_client)
    panel = ManualConfigPanel(manual_config_client)
    qtbot.addWidget(panel)

    # Candidate record: render and assert completion widgets absent.
    candidate_detail = panel.render_detail(
        candidate_record, {"references": {"as_source": [], "as_target": []}}
    )
    assert (
        candidate_detail.findChild(
            object, "manual_config_completed_at_value"
        )
        is None
    )
    assert (
        candidate_detail.findChild(
            object, "manual_config_completed_by_value"
        )
        is None
    )

    # Completed record: render and assert completion widgets present.
    completed_detail = panel.render_detail(
        completed_record, {"references": {"as_source": [], "as_target": []}}
    )
    completed_at_widget = completed_detail.findChild(
        object, "manual_config_completed_at_value"
    )
    completed_by_widget = completed_detail.findChild(
        object, "manual_config_completed_by_value"
    )
    assert completed_at_widget is not None
    assert completed_by_widget is not None


def test_create_dialog_field_schema_excludes_identifier(
    qtbot, manual_config_client
):
    """Create-mode dialog should not include the identifier field."""
    from crmbuilder_v2.ui.dialogs._manual_config_schema import (
        manual_config_fields,
    )

    create_fields = manual_config_fields(include_identifier=False)
    edit_fields = manual_config_fields(include_identifier=True)
    create_keys = [f.key for f in create_fields]
    edit_keys = [f.key for f in edit_fields]
    assert "manual_config_identifier" not in create_keys
    assert "manual_config_identifier" in edit_keys
    for k in (
        "manual_config_name",
        "manual_config_category",
        "manual_config_description",
        "manual_config_instructions",
        "manual_config_notes",
        "manual_config_status",
        "manual_config_completed_at",
        "manual_config_completed_by",
    ):
        assert k in create_keys, k
        assert k in edit_keys, k
