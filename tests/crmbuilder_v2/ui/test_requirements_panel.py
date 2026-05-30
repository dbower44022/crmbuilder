"""Requirements panel / dialog tests — PI-004 cohort (v0.5+).

Covers ``requirement.md`` §3.7 acceptance criteria 10, 11, 12 smoke-
level: the "Requirements" sidebar entry under Methodology, the five-
column master pane (AC-11), and the detail pane renders for an empty
state and a single-record state.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.requirements import RequirementsPanel
from crmbuilder_v2.ui.refresh import _FILENAME_TO_ENTITY_TYPE
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def requirement_client(v2_env) -> StorageClient:
    return StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )


def _seed_requirement(c: StorageClient, name: str = "Capture mentor slots") -> dict:
    body = {
        "requirement_name": name,
        "requirement_description": "d",
        "requirement_acceptance_summary": "a",
        "requirement_priority": "must",
    }
    return c.create_requirement(body)


def test_requirements_appears_in_methodology_group():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert "Requirements" in methodology


def test_entity_type_map_has_requirement_entry():
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL.get("requirement") == "Requirements"


def test_requirements_json_refresh_mapping_present():
    assert _FILENAME_TO_ENTITY_TYPE.get("requirements.json") == "requirement"


def test_panel_master_has_five_columns(qtbot, requirement_client):
    """AC-11: master pane shows Identifier / Name / Priority / Status / Created."""
    panel = RequirementsPanel(requirement_client)
    qtbot.addWidget(panel)
    cols = panel.list_columns()
    assert len(cols) == 5
    titles = [c.title for c in cols]
    assert titles == ["Identifier", "Name", "Priority", "Status", "Created"]
    fields = [c.field for c in cols]
    assert fields == [
        "requirement_identifier",
        "requirement_name",
        "requirement_priority",
        "requirement_status",
        "created_at_display",
    ]


def test_panel_renders_with_no_requirements(qtbot, requirement_client):
    panel = RequirementsPanel(requirement_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 0, timeout=3000)


def test_panel_renders_with_one_requirement(qtbot, requirement_client):
    _seed_requirement(requirement_client)
    panel = RequirementsPanel(requirement_client)
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=3000)
    assert panel._model.rowCount() == 1
    # fetch_detail_extras returns the references payload structure.
    extras = panel.fetch_detail_extras(panel._records[0])
    assert "references" in extras
    assert "as_source" in extras["references"]


def test_create_dialog_field_schema_excludes_identifier(qtbot, requirement_client):
    """Create-mode dialog should not include the identifier field (server-assigned)."""
    from crmbuilder_v2.ui.dialogs._requirement_schema import requirement_fields

    create_fields = requirement_fields(include_identifier=False)
    edit_fields = requirement_fields(include_identifier=True)
    create_keys = [f.key for f in create_fields]
    edit_keys = [f.key for f in edit_fields]
    assert "requirement_identifier" not in create_keys
    assert "requirement_identifier" in edit_keys
    # Verify all seven core fields present in both modes.
    for k in (
        "requirement_name",
        "requirement_description",
        "requirement_acceptance_summary",
        "requirement_notes",
        "requirement_priority",
        "requirement_status",
    ):
        assert k in create_keys, k
        assert k in edit_keys, k
