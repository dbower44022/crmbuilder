"""PI-108 Slice C: created/last-edited timestamps on the methodology panels.

Covers the ten mutable (created + updated) methodology entity panels —
Domains / Entities / Fields / Requirements / Personas / Processes /
Manual Configs / Test Specs / CRM Candidates / Engagements. Each panel
exposes a formatted "Created" master column (via the synthetic
``created_at_display`` field synthesized in ``fetch_records`` /
``_post_process_records``) and a created/last-edited audit section in
the detail pane. Mirrors ``test_panel_timestamps_slice_a.py``.
"""

from __future__ import annotations

import httpx
from crmbuilder_v2.ui.panels.crm_candidates import CrmCandidatesPanel
from crmbuilder_v2.ui.panels.domains import DomainsPanel
from crmbuilder_v2.ui.panels.engagements import EngagementsPanel
from crmbuilder_v2.ui.panels.entities import EntitiesPanel
from crmbuilder_v2.ui.panels.field import FieldsPanel
from crmbuilder_v2.ui.panels.manual_config import ManualConfigPanel
from crmbuilder_v2.ui.panels.persona import PersonasPanel
from crmbuilder_v2.ui.panels.processes import ProcessesPanel
from crmbuilder_v2.ui.panels.requirements import RequirementsPanel
from crmbuilder_v2.ui.panels.test_spec import TestSpecsPanel
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp

from .conftest import build_client, envelope_ok

_CREATED = "2026-05-29T23:35:53.169304"
_UPDATED = "2026-05-30T08:15:00.000000"


def _list_handler(path: str, records: list[dict]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == path:
            return httpx.Response(200, json=envelope_ok(records))
        return httpx.Response(200, json=envelope_ok([]))

    return handler


def _assert_created_column_formatted(panel, *, raw_created: str) -> None:
    """Shared assertions: Created column present, formatted, not raw ISO."""
    assert "Created" in [c.title for c in panel.list_columns()]
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(raw_created)
    assert out[0]["created_at_display"] != raw_created


def test_domains_created_column_formatted(qtbot):
    rec = {
        "domain_identifier": "DOM-001",
        "domain_created_at": _CREATED,
        "domain_updated_at": _UPDATED,
    }
    panel = DomainsPanel(build_client(_list_handler("/domains", [rec])))
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_entities_created_column_formatted(qtbot):
    rec = {
        "entity_identifier": "ENT-001",
        "entity_created_at": _CREATED,
        "entity_updated_at": _UPDATED,
    }
    panel = EntitiesPanel(build_client(_list_handler("/entities", [rec])))
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_fields_created_column_formatted(qtbot):
    rec = {
        "field_identifier": "FLD-001",
        "field_created_at": _CREATED,
        "field_updated_at": _UPDATED,
    }
    panel = FieldsPanel(build_client(_list_handler("/fields", [rec])))
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_requirements_created_column_formatted(qtbot):
    rec = {
        "requirement_identifier": "REQ-001",
        "requirement_created_at": _CREATED,
        "requirement_updated_at": _UPDATED,
    }
    panel = RequirementsPanel(
        build_client(_list_handler("/requirements", [rec]))
    )
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_personas_created_column_formatted(qtbot):
    rec = {
        "persona_identifier": "PER-001",
        "persona_created_at": _CREATED,
        "persona_updated_at": _UPDATED,
    }
    panel = PersonasPanel(build_client(_list_handler("/personas", [rec])))
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_processes_created_column_formatted(qtbot):
    rec = {
        "process_identifier": "PROC-001",
        "process_created_at": _CREATED,
        "process_updated_at": _UPDATED,
    }
    panel = ProcessesPanel(build_client(_list_handler("/processes", [rec])))
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_manual_config_created_column_formatted(qtbot):
    rec = {
        "manual_config_identifier": "MC-001",
        "manual_config_created_at": _CREATED,
        "manual_config_updated_at": _UPDATED,
    }
    panel = ManualConfigPanel(
        build_client(_list_handler("/manual-configs", [rec]))
    )
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_test_spec_created_column_formatted(qtbot):
    rec = {
        "test_spec_identifier": "TS-001",
        "test_spec_created_at": _CREATED,
        "test_spec_updated_at": _UPDATED,
    }
    panel = TestSpecsPanel(build_client(_list_handler("/test-specs", [rec])))
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_crm_candidate_created_column_formatted(qtbot):
    rec = {
        "crm_candidate_identifier": "CRM-001",
        "crm_candidate_created_at": _CREATED,
        "crm_candidate_updated_at": _UPDATED,
    }
    panel = CrmCandidatesPanel(
        build_client(_list_handler("/crm_candidates", [rec]))
    )
    qtbot.addWidget(panel)
    _assert_created_column_formatted(panel, raw_created=_CREATED)


def test_engagements_created_column_formatted(qtbot):
    # Engagements synthesize created_at_display in _post_process_records,
    # which runs during refresh; fetch_records returns the raw list. Assert
    # the column is declared and that the decoration path formats it.
    rec = {
        "engagement_identifier": "ENG-001",
        "engagement_name": "Acme",
        "engagement_created_at": _CREATED,
        "engagement_updated_at": _UPDATED,
    }
    panel = EngagementsPanel(
        build_client(_list_handler("/engagements", [rec]))
    )
    qtbot.addWidget(panel)
    assert "Created" in [c.title for c in panel.list_columns()]
    decorated = panel._post_process_records(panel.fetch_records())
    assert decorated[0]["created_at_display"] == format_timestamp(_CREATED)
    assert decorated[0]["created_at_display"] != _CREATED
