"""The ``filteredTabs:`` block — PI-417 (REQ-519, schema §5.9).

A filtered tab is entity-bound (DEC-998 names it as the construct that files
normally, beside the entity-less security program), so it emits with its
entity. What closed the publish direction was that nothing rendered it.
"""

from __future__ import annotations

import pathlib
import tempfile

from crmbuilder_v2.adapters.espocrm.adapter import validate_yaml_text
from crmbuilder_v2.adapters.espocrm.emit import (
    emit_manual_config_md,
    emit_program_yaml,
)
from crmbuilder_v2.adapters.espocrm.model import (
    _scope_name,
    build_program_model,
)

from espo_impl.core.config_loader import ConfigLoader
from tests.crmbuilder_v2.adapters.test_espocrm_model import _entity, _field

RENDERED = "2026-09-03T00:00:00Z"


def _tab(identifier="FTB-001", label="Approved applications", entity="ENT-001",
         status="confirmed", **over):
    base = {
        "filtered_tab_identifier": identifier,
        "filtered_tab_entity_identifier": entity,
        "filtered_tab_label": label,
        "filtered_tab_filter": {"field": "FLD-001", "op": "eq", "value": "approved"},
        "filtered_tab_status": status,
        "filtered_tab_notes": None,
    }
    base.update(over)
    return base


def _model(tabs, **kw):
    return build_program_model(
        [_entity()], [_field()], [], filtered_tabs=tabs, rendered_at=RENDERED, **kw
    )


def _block(model):
    return model.programs[0].program["entities"]["Mentor Application"].get(
        "filteredTabs"
    )


# --- the block ----------------------------------------------------------------

def test_a_confirmed_tab_emits_on_its_entity_s_program():
    model = _model([_tab()])
    assert _block(model) == [{
        "id": "ftb-001",
        "scope": "ApprovedApplications",
        "label": "Approved applications",
        "filter": {"field": "mentorStatus", "op": "equals", "value": "approved"},
    }]
    assert model.deferrals == []
    # Nothing about a filtered tab belongs in the security program.
    assert all(not p.is_security for p in model.programs)


def test_the_emitted_program_passes_the_deploy_validator_and_loader():
    """The arbiter is the loader the deploy engine uses: ``filteredTabs:`` has
    required keys and a PascalCase scope rule, and a filter that references a
    field the entity does not carry is rejected outright."""
    model = _model([_tab()])
    text = emit_program_yaml(model.programs[0], rendered_at=RENDERED)
    assert validate_yaml_text(text) == []

    path = pathlib.Path(tempfile.mkdtemp()) / model.programs[0].filename
    path.write_text(text)
    loaded = ConfigLoader().load_program(path)
    tabs = loaded.entities[0].filtered_tabs
    assert [t.scope for t in tabs] == ["ApprovedApplications"]
    assert tabs[0].label == "Approved applications"
    assert tabs[0].filter is not None
    assert tabs[0].acl == "boolean"


def test_a_candidate_tab_is_unfinished_design_and_is_skipped():
    model = _model([_tab(status="candidate")])
    assert _block(model) is None
    assert model.deferrals == []


def test_tabs_emit_in_identifier_order_whatever_order_they_arrive():
    model = _model([_tab("FTB-002", "Second"), _tab("FTB-001", "First")])
    assert [t["id"] for t in _block(model)] == ["ftb-001", "ftb-002"]


# --- what defers, by name -----------------------------------------------------

def test_a_tab_on_an_unemitted_entity_defers():
    model = _model([_tab(entity="ENT-999")])
    assert _block(model) is None
    (d,) = model.deferrals
    assert (d.kind, d.identifier) == ("filtered_tab", "FTB-001")
    assert "owning entity" in d.detail


def test_a_tab_without_a_filter_defers_because_the_schema_requires_one():
    model = _model([_tab(filtered_tab_filter=None)])
    assert _block(model) is None
    (d,) = model.deferrals
    assert "requires a filter" in d.detail


def test_a_filter_on_a_field_the_entity_does_not_emit_defers():
    """The strict resolver: emitting the reference would produce a program
    ``validate_program`` rejects, which would block the entity beside it."""
    model = _model([_tab(filtered_tab_filter={
        "field": "FLD-404", "op": "eq", "value": "x",
    })])
    assert _block(model) is None
    (d,) = model.deferrals
    assert "not compilable" in d.detail and "FLD-404" in d.detail


def test_an_audit_captured_engine_native_filter_defers_rather_than_guessing():
    """The audit stores the CRM's own report-filter payload; there is no
    neutral reading for it yet, so it is named, not translated by guesswork."""
    for native in (
        {"where": [{"type": "equals", "attribute": "status", "value": "Open"}]},
        [{"type": "equals", "attribute": "status", "value": "Open"}],
    ):
        model = _model([_tab(filtered_tab_filter=native)])
        assert _block(model) is None
        (d,) = model.deferrals
        assert "report-filter form" in d.detail


def test_deferred_tabs_have_their_own_manual_config_section():
    model = _model([_tab(filtered_tab_filter=None)])
    md = emit_manual_config_md(model, rendered_at=RENDERED)
    assert "## Filtered tabs not rendered as filteredTabs" in md
    assert "FTB-001" in md


# --- derivation ---------------------------------------------------------------

def test_scope_is_the_label_in_pascal_case():
    assert _scope_name("My Open Engagements", "FTB-001") == "MyOpenEngagements"
    assert _scope_name("SBA loans (2024)", "FTB-002") == "SBALoans2024"


def test_a_scope_that_cannot_start_with_a_letter_is_prefixed_not_dropped():
    assert _scope_name("2024 cohort", "FTB-003") == "Tab2024Cohort"
    assert _scope_name("***", "FTB-004") == "TabFTB004"


def test_a_scope_never_exceeds_the_schema_s_sixty_characters():
    assert len(_scope_name("word " * 40, "FTB-005")) == 60


def test_two_tabs_spelling_the_same_scope_stay_distinct():
    """EspoCRM scope names share one namespace and the schema requires them
    unique per program; the second takes the identifier's digits."""
    model = _model([
        _tab("FTB-001", "My clients"), _tab("FTB-002", "My Clients!"),
    ])
    assert [t["scope"] for t in _block(model)] == ["MyClients", "MyClients002"]
    text = emit_program_yaml(model.programs[0], rendered_at=RENDERED)
    assert validate_yaml_text(text) == []
