"""Test specs panel / dialog tests — PI-004 cohort closer (v0.5+).

Covers ``test_spec.md`` §3.7 acceptance criteria 11, 12, 13 smoke-
level: the "Test Specs" sidebar entry under Methodology, the
five-column master pane (AC-12 — Identifier / Name / Status / Last Run
/ Updated) with the color-cued Last Run delegate (UI deviation
rationale §3.6.2), and the three-subsection detail pane (AC-13 —
identity-and-methodology / Test body / Last run + collapsible
Internal notes + ReferencesSection).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import ENTITY_TYPE_TO_SIDEBAR_LABEL
from crmbuilder_v2.ui.panels.test_spec import (
    TestSpecsPanel,
    _LastRunColorDelegate,
    _resolve_outcome_color,
)
from crmbuilder_v2.ui.refresh import _FILENAME_TO_ENTITY_TYPE
from crmbuilder_v2.ui.sidebar import SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def test_spec_client(v2_env) -> StorageClient:
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


def _seed(c: StorageClient, name: str = "Mentor app smoke") -> dict:
    body = {
        "test_spec_name": name,
        "test_spec_description": "Verifies a happy path.",
        "test_spec_steps": "1. Open. 2. Fill. 3. Submit.",
        "test_spec_expected": "Confirmation email within 2 minutes.",
    }
    return c.create_test_spec(body)


def test_test_specs_appears_in_methodology_group():
    methodology = dict(SIDEBAR_GROUPS)["Methodology"]
    assert "Test Specs" in methodology


def test_entity_type_map_has_test_spec_entry():
    assert ENTITY_TYPE_TO_SIDEBAR_LABEL.get("test_spec") == "Test Specs"


def test_test_specs_json_refresh_mapping_present():
    assert _FILENAME_TO_ENTITY_TYPE.get("test_specs.json") == "test_spec"


def test_panel_lists_five_columns(qtbot, test_spec_client):
    """AC-12: master pane shows Identifier / Name / Status / Last Run / Created."""
    panel = TestSpecsPanel(test_spec_client)
    qtbot.addWidget(panel)
    cols = panel.list_columns()
    assert len(cols) == 5
    titles = [c.title for c in cols]
    assert titles == ["Identifier", "Name", "Status", "Last Run", "Created"]
    fields = [c.field for c in cols]
    assert fields == [
        "test_spec_identifier",
        "test_spec_name",
        "test_spec_status",
        "test_spec_last_run_outcome",
        "created_at_display",
    ]


def test_master_pane_color_cue_applied_for_each_outcome():
    """AC-12 / §3.6.2 deviation: each outcome maps to its own color."""
    passing = _resolve_outcome_color("passing")
    failing = _resolve_outcome_color("failing")
    not_run = _resolve_outcome_color("not_run")
    skipped = _resolve_outcome_color("skipped")
    # All four must be valid QColor and distinct from each other (the
    # whole point of the cue is to differentiate them).
    colors = [passing, failing, not_run, skipped]
    for c in colors:
        assert c.isValid()
    # Distinctness check — Qt's QColor equality compares all channels.
    distinct = {c.name() for c in colors}
    assert len(distinct) == 4


def test_unknown_outcome_falls_back_to_not_run_color():
    """An unrecognised outcome value defers to the not_run gray cue."""
    not_run = _resolve_outcome_color("not_run")
    fallback = _resolve_outcome_color("bogus")
    assert fallback.name() == not_run.name()


def test_detail_pane_shows_three_subsection_headers(qtbot, test_spec_client):
    """AC-13: detail pane carries the three subsection-grouped headers."""
    record = _seed(test_spec_client)
    panel = TestSpecsPanel(test_spec_client)
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )
    # Collect text from every QLabel descendant.
    from PySide6.QtWidgets import QLabel  # noqa: PLC0415

    labels = detail.findChildren(QLabel)
    texts = {label.text() for label in labels}
    assert "Test body" in texts
    assert "Last run" in texts
    # The CollapsibleSection's title; the test asserts the section
    # widget exists by object name set on the toggle.
    notes_toggle = detail.findChild(object, "test_spec_notes_toggle")
    assert notes_toggle is not None


def test_detail_pane_exposes_record_run_button(qtbot, test_spec_client):
    """Record Run button is in the action strip for live records."""
    record = _seed(test_spec_client)
    panel = TestSpecsPanel(test_spec_client)
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        record, {"references": {"as_source": [], "as_target": []}}
    )
    record_run_btn = detail.findChild(object, "record_run_test_spec_button")
    assert record_run_btn is not None


def test_color_delegate_attached_to_last_run_column(qtbot, test_spec_client):
    """The color-cued delegate is installed on the Last Run column."""
    panel = TestSpecsPanel(test_spec_client)
    qtbot.addWidget(panel)
    master = panel._master_view
    # The Last Run column is the fourth (index 3).
    delegate = master.itemDelegateForColumn(3)
    assert isinstance(delegate, _LastRunColorDelegate)


def test_create_dialog_field_schema_excludes_identifier():
    """Create-mode dialog should not include the identifier field."""
    from crmbuilder_v2.ui.dialogs._test_spec_schema import (  # noqa: PLC0415
        test_spec_fields,
    )

    create_fields = test_spec_fields(include_identifier=False)
    edit_fields = test_spec_fields(include_identifier=True)
    create_keys = [f.key for f in create_fields]
    edit_keys = [f.key for f in edit_fields]
    assert "test_spec_identifier" not in create_keys
    assert "test_spec_identifier" in edit_keys
    for k in (
        "test_spec_name",
        "test_spec_description",
        "test_spec_setup",
        "test_spec_steps",
        "test_spec_expected",
        "test_spec_notes",
        "test_spec_status",
        "test_spec_last_run_outcome",
        "test_spec_last_run_at",
        "test_spec_last_run_notes",
    ):
        assert k in create_keys, k
        assert k in edit_keys, k
