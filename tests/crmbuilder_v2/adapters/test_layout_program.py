"""The ``layout:`` block — PI-427 (REQ-519, DEC-951; schema §7.1).

A layout is entity-bound, so it files with its entity like a field or a
filtered tab. What closed the publish direction was that nothing rendered it:
the audit captured and compared layouts, and a designed layout could be seen
to differ from an instance but never pushed to one.
"""

from __future__ import annotations

import pathlib
import tempfile

import pytest
import yaml as pyyaml
from crmbuilder_v2.adapters.espocrm.adapter import validate_yaml_text
from crmbuilder_v2.adapters.espocrm.emit import (
    emit_manual_config_md,
    emit_program_yaml,
)
from crmbuilder_v2.adapters.espocrm.layouts import (
    LAYOUT_TYPE_TO_ESPO,
    LayoutRenderError,
    render_layout,
)
from crmbuilder_v2.adapters.espocrm.model import build_program_model

from espo_impl.core.config_loader import ConfigLoader
from espo_impl.core.layout_types import DEPLOYABLE_LAYOUT_TYPES
from tests.crmbuilder_v2.adapters.test_espocrm_model import _entity, _field

RENDERED = "2026-09-03T00:00:00Z"

#: A detail layout as the CRM returns it and the audit stores it: panels of
#: rows of ``{name}`` cells, ``false`` for an empty cell.
DETAIL = [
    {"label": "Overview", "rows": [[{"name": "name"}, {"name": "mentorStatus"}], [{"name": "mentorStatus", "fullWidth": True}, False]]},
]
LIST = [{"name": "name", "width": 30, "link": True}, {"name": "mentorStatus"}]
FILTERS = ["name", "mentorStatus"]
SIDE = {"stream": {"index": 0}, "_delimiter_": {"disabled": True}}


def _layout(identifier="LAY-001", entity="ENT-001", layout_type="detail",
            content=None, status="confirmed"):
    return {
        "layout_identifier": identifier,
        "layout_entity_identifier": entity,
        "layout_type": layout_type,
        "layout_content": DETAIL if content is None else content,
        "layout_status": status,
        "layout_notes": None,
    }


def _model(layouts, entities=None, fields=None, **kw):
    return build_program_model(
        entities or [_entity()], fields or [_field()], [], layouts=layouts,
        rendered_at=RENDERED, **kw,
    )


def _block(model, entity="Mentor Application"):
    program = next(p for p in model.programs if p.entity_name == entity)
    return program.program["entities"][entity].get("layout")


# --- the block ----------------------------------------------------------------

def test_a_confirmed_detail_layout_emits_on_its_entity_s_program():
    model = _model([_layout()])
    assert _block(model) == {
        "detail": {"panels": [{
            "label": "Overview",
            "rows": [["name", "mentorStatus"], [{"name": "mentorStatus", "fullWidth": True}, None]],
        }]}
    }
    assert model.deferrals == []


def test_every_structure_class_renders_its_yaml_shape():
    """Panels for the record views, columns for the list views, a bare name
    list for filters, and the panel map verbatim (schema §7.1)."""
    model = _model([
        _layout("LAY-001", layout_type="detail", content=DETAIL),
        _layout("LAY-002", layout_type="list_small", content=LIST),
        _layout("LAY-003", layout_type="filters", content=FILTERS),
        _layout("LAY-004", layout_type="side_panels_detail", content=SIDE),
    ])
    block = _block(model)
    assert set(block) == {"detail", "listSmall", "filters", "sidePanelsDetail"}
    assert block["listSmall"] == {"columns": [
        {"field": "name", "width": 30, "link": True}, {"field": "mentorStatus"},
    ]}
    assert block["filters"] == ["name", "mentorStatus"]
    assert block["sidePanelsDetail"] == SIDE
    assert model.deferrals == []


def test_the_type_map_covers_exactly_the_engine_s_deployable_types():
    """The emitter renders what the deploy engine writes — no more (a type
    the engine defers would publish as NOT SUPPORTED) and no less."""
    assert set(LAYOUT_TYPE_TO_ESPO.values()) == set(DEPLOYABLE_LAYOUT_TYPES)


def test_a_candidate_layout_is_not_emitted_and_not_a_deferral():
    """Unfinished design is skipped silently, as every other construct is."""
    model = _model([_layout(status="candidate")])
    assert _block(model) is None
    assert model.deferrals == []


def test_a_layout_of_an_unemitted_entity_defers_by_name():
    model = _model([_layout(entity="ENT-999")])
    assert _block(model) is None
    (d,) = model.deferrals
    assert d.kind == "layout" and d.identifier == "LAY-001"
    assert "not confirmed/emitted" in d.detail


def test_a_second_confirmed_layout_of_the_same_type_defers():
    model = _model([_layout("LAY-001"), _layout("LAY-002")])
    assert list(_block(model)) == ["detail"]
    (d,) = model.deferrals
    assert d.identifier == "LAY-002" and "already rendered" in d.detail


# --- field resolution ---------------------------------------------------------

def test_a_layout_placing_a_field_the_program_does_not_emit_defers_naming_it():
    """A candidate field's name in the layout would reach the instance as a
    cell showing nothing; the layout defers and the reason names the field."""
    content = [{"label": "Overview", "rows": [[{"name": "name"}, {"name": "secretScore"}]]}]
    model = _model([_layout(content=content)])
    assert _block(model) is None
    (d,) = model.deferrals
    assert "secretScore" in d.detail and "does not emit" in d.detail


def test_a_platform_entity_s_prefixed_custom_field_reverses_to_the_emitted_name():
    """On Contact the CRM spells the design's field ``cMentorStatus``; the
    program declares ``mentorStatus`` and the engine re-prefixes at deploy.
    Its own built-in fields pass through as the CRM spelled them."""
    contact = _entity(identifier="ENT-002", name="Contact", entity_kind="person")
    fld = _field(identifier="FLD-002", parent="ENT-002")
    content = [{"label": "", "rows": [[{"name": "cMentorStatus"}, {"name": "emailAddress"}], [{"name": "accountName"}, False]]}]
    model = _model([_layout(entity="ENT-002", content=content)], entities=[contact], fields=[fld])
    assert _block(model, "Contact") == {"detail": {"panels": [{
        "rows": [["mentorStatus", "emailAddress"], ["accountName", None]],
    }]}}
    assert model.deferrals == []


def test_a_platform_entity_s_prefixed_field_the_design_does_not_emit_defers():
    contact = _entity(identifier="ENT-002", name="Contact", entity_kind="person")
    fld = _field(identifier="FLD-002", parent="ENT-002")
    content = [{"label": "", "rows": [[{"name": "cMentorStatus"}, {"name": "cOldScore"}]]}]
    model = _model([_layout(entity="ENT-002", content=content)], entities=[contact], fields=[fld])
    assert _block(model, "Contact") is None
    (d,) = model.deferrals
    assert "cOldScore" in d.detail


def test_a_link_field_from_the_relationships_block_resolves():
    """A record view routinely places a link (``sponsor``); it is not a field
    the program emits, but the relationships block declares it."""
    org = _entity(identifier="ENT-002", name="Sponsor")
    assoc = {
        "association_identifier": "ASC-001", "association_name": "Sponsor funds applications",
        "association_source_entity": "ENT-002", "association_target_entity": "ENT-001",
        "association_cardinality": "one_to_many", "association_status": "confirmed",
        "association_source_role": None, "association_target_role": None,
        "association_description": None,
    }
    content = [{"label": "Overview", "rows": [[{"name": "name"}, {"name": "sponsor"}]]}]
    model = _model(
        [_layout(content=content)], entities=[_entity(), org],
        associations=[assoc],
    )
    assert _block(model)["detail"]["panels"][0]["rows"] == [["name", "sponsor"]]
    assert model.deferrals == []


# --- autoPlaceName ------------------------------------------------------------

def _settings(model, entity="Mentor Application"):
    program = next(p for p in model.programs if p.entity_name == entity)
    return program.program["entities"][entity]["settings"]


def test_a_panel_layout_that_places_name_leaves_the_engine_default():
    model = _model([_layout()])
    assert "autoPlaceName" not in _settings(model)


def test_a_panel_layout_without_name_turns_auto_placement_off():
    """The engine would otherwise prepend ``name`` and publish a layout the
    design does not describe."""
    content = [{"label": "Overview", "rows": [[{"name": "mentorStatus"}]]}]
    model = _model([_layout(content=content)])
    assert _settings(model)["autoPlaceName"] is False


def test_a_list_layout_without_name_does_not_touch_auto_placement():
    """Only the record-view panel layouts are subject to the engine's rule."""
    model = _model([_layout(layout_type="list", content=[{"name": "mentorStatus"}])])
    assert "autoPlaceName" not in _settings(model)


# --- what the validator rejects -----------------------------------------------

def test_two_panels_sharing_a_label_defer_rather_than_sink_the_program():
    content = [
        {"label": "", "rows": [[{"name": "name"}]]},
        {"label": "", "rows": [[{"name": "mentorStatus"}]]},
    ]
    model = _model([_layout(content=content)])
    assert _block(model) is None
    (d,) = model.deferrals
    assert "duplicate panel label" in d.detail


def test_an_empty_payload_defers():
    with pytest.raises(LayoutRenderError, match="no content"):
        render_layout(
            "detail", [], entity_name="Mentor Application", entity_espo_type="Base",
            emitted_field_names={"mentorStatus"}, link_names=set(),
        )


def test_a_portal_variant_defers_naming_the_platform_s_limit():
    """PI-418 / REQ-520: the audit captures the five portal variants so they
    can be shown as differences; the emitter never renders one, because the
    deploy engine has no write path for it, and MANUAL-CONFIG says so."""
    model = _model([_layout(layout_type="list_portal", content=LIST)])
    assert _block(model) is None
    (d,) = model.deferrals
    assert d.kind == "layout" and "portal" in d.detail and "REQ-520" in d.detail


def test_an_unmapped_type_defers():
    with pytest.raises(LayoutRenderError, match="no deployable"):
        render_layout(
            "not_a_type", LIST, entity_name="Mentor Application", entity_espo_type="Base",
            emitted_field_names={"mentorStatus"}, link_names=set(),
        )


# --- the deploy engine is the arbiter (LSN-070, LSN-071) ----------------------

def _emit_all_types():
    return _model([
        _layout("LAY-001", layout_type="detail", content=DETAIL),
        _layout("LAY-002", layout_type="edit", content=DETAIL),
        _layout("LAY-003", layout_type="list", content=LIST),
        _layout("LAY-004", layout_type="kanban", content=LIST),
        _layout("LAY-005", layout_type="filters", content=FILTERS),
        _layout("LAY-006", layout_type="mass_update", content=FILTERS),
        _layout("LAY-007", layout_type="relationships", content=["sponsor"]),
        _layout("LAY-008", layout_type="side_panels_detail", content=SIDE),
        _layout("LAY-009", layout_type="bottom_panels_edit", content=SIDE),
    ])


def test_the_emitted_program_passes_the_deploy_validator():
    model = _emit_all_types()
    assert model.deferrals == []
    text = emit_program_yaml(model.programs[0], rendered_at=RENDERED)
    assert validate_yaml_text(text) == []


def test_the_engine_s_own_reader_sees_the_layouts_the_emitter_wrote():
    """Read back with PyYAML (the engine's dialect, not the writer's) and then
    through the loader the Configure flow runs, so a writer/reader disagreement
    cannot hide the way LSN-070 did."""
    model = _emit_all_types()
    text = emit_program_yaml(model.programs[0], rendered_at=RENDERED)

    plain = pyyaml.safe_load(text)["entities"]["Mentor Application"]["layout"]
    assert set(plain) == {
        "detail", "edit", "list", "kanban", "filters", "massUpdate",
        "relationships", "sidePanelsDetail", "bottomPanelsEdit",
    }
    assert plain["detail"]["panels"][0]["rows"][1] == [
        {"name": "mentorStatus", "fullWidth": True}, None,
    ]
    assert plain["list"]["columns"][0] == {"field": "name", "width": 30, "link": True}

    path = pathlib.Path(tempfile.mkdtemp()) / model.programs[0].filename
    path.write_text(text)
    loaded = ConfigLoader().load_program(path)
    (entity,) = loaded.entities
    assert set(entity.layouts) == set(plain)
    detail = entity.layouts["detail"]
    assert [p.label for p in detail.panels] == ["Overview"]
    assert detail.panels[0].rows == [
        ["name", "mentorStatus"], [{"name": "mentorStatus", "fullWidth": True}, None],
    ]
    assert [c.field for c in entity.layouts["list"].columns] == ["name", "mentorStatus"]
    assert entity.layouts["list"].columns[0].width == 30
    assert entity.layouts["filters"].raw == ["name", "mentorStatus"]
    assert entity.layouts["sidePanelsDetail"].raw == SIDE


def test_a_deferred_layout_is_listed_in_manual_config():
    model = _model([_layout(entity="ENT-999")])
    text = emit_manual_config_md(model, rendered_at=RENDERED)
    assert "LAY-001" in text and "not confirmed/emitted" in text


# --- the port is the V1 mapper, fixture for fixture ---------------------------

_FIXTURES = sorted(
    p for p in (pathlib.Path(__file__).resolve().parents[2] / "fixtures" / "layouts").glob("*.json")
)


@pytest.mark.parametrize("fixture", _FIXTURES, ids=[p.stem for p in _FIXTURES])
def test_the_ported_reverse_mapper_agrees_with_the_v1_mapper_on_every_fixture(fixture):
    """The V1 audit's reverse mappers are the tested, lossless payload→YAML
    translation; V2 ports them rather than importing them (REQ-549). Every
    live-captured fixture must reverse identically through both, with the
    native entity's custom fields stripped and the custom entity's kept."""
    import json

    from crmbuilder_v2.adapters.espocrm.layouts import reverse_layout_payload

    from espo_impl.core.reconcile.layout_reverse import (
        reverse_layout_payload as v1_reverse,
    )

    entity, espo_type = fixture.stem.split(".", 1)
    payload = json.loads(fixture.read_text())
    custom = set()
    if entity == "Contact":
        # Every c-prefixed name the fixture places is a custom field there.
        text = fixture.read_text()
        import re
        custom = set(re.findall(r'"(c[A-Z][A-Za-z0-9]*)"', text))
    assert reverse_layout_payload(espo_type, payload, custom) == v1_reverse(
        espo_type, payload, custom
    )
