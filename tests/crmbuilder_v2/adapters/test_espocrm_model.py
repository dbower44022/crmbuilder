"""Pure unit tests — EspoCRM adapter build model (PRJ-025 PI-191 slice 1).

No network, no DB: ``build_program_model`` is a pure function of fixture
design records. Covers entity/field type mapping, name/label derivation,
the override merge, enum-option handling, deferral routing, the scope
filter, and emit determinism.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.adapters.espocrm.emit import (
    emit_manual_config_md,
    emit_program_yaml,
)
from crmbuilder_v2.adapters.espocrm.model import (
    build_program_model,
    derive_internal_name,
    derive_label,
    pluralize,
)

RENDERED_AT = "2026-06-14T00:00:00+00:00"


def _entity(identifier="ENT-001", name="Mentor Application", **over):
    base = {
        "entity_identifier": identifier,
        "entity_name": name,
        "entity_status": "confirmed",
        "entity_kind": None,
        "entity_description": "An application to mentor",
        "entity_track_activity": False,
        "entity_default_sort_field": None,
        "entity_default_sort_direction": None,
    }
    base.update(over)
    return base


def _field(identifier="FLD-001", name="mentor_status", type="text", parent="ENT-001", **over):
    base = {
        "field_identifier": identifier,
        "field_name": name,
        "field_type": type,
        "field_status": "confirmed",
        "field_description": "",
        "field_required": False,
        "field_default_value": None,
        "field_read_only": False,
        "field_format": None,
        "field_numeric_scale": None,
        "field_max_length": None,
        "field_min": None,
        "field_max": None,
        "field_externally_populated": False,
        "field_tooltip": None,
        "field_unique": False,
        "field_usage_summary": None,
        "field_options": [],
        "parent_entity_identifier": parent,
    }
    base.update(over)
    return base


def _only_entity_block(model):
    assert len(model.programs) == 1
    program = model.programs[0].program
    name = model.programs[0].entity_name
    return program["entities"][name]


# ---------------------------------------------------------------------------
# Name / label derivation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("mentor_status", "mentorStatus"),
        ("Mentor Status", "mentorStatus"),
        ("Date of Birth", "dateOfBirth"),
        ("amount", "amount"),
        ("EIN", "ein"),
    ],
)
def test_derive_internal_name(raw, expected):
    name = derive_internal_name(raw)
    assert name == expected
    assert name[0].islower() and name[0].isalpha()


def test_derive_label():
    assert derive_label("mentor_status") == "Mentor Status"
    assert derive_label("Date of Birth") == "Date Of Birth"


def test_pluralize():
    assert pluralize("Mentor") == "Mentors"


# ---------------------------------------------------------------------------
# Type mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "semantic,extra,expected",
    [
        ("text", {}, "varchar"),
        ("long_text", {}, "text"),
        ("enum", {"field_options": [{"option_value": "a", "option_order": 0}]}, "enum"),
        ("multi_enum", {"field_options": [{"option_value": "a", "option_order": 0}]}, "multiEnum"),
        ("date", {}, "date"),
        ("datetime", {}, "datetime"),
        ("money", {}, "currency"),
        ("boolean", {}, "bool"),
        ("number", {}, "int"),
        ("number", {"field_numeric_scale": "integer"}, "int"),
        ("number", {"field_numeric_scale": "decimal"}, "float"),
        ("text", {"field_format": "email"}, "email"),
        ("text", {"field_format": "phone"}, "phone"),
        ("text", {"field_format": "url"}, "url"),
    ],
)
def test_field_type_mapping(semantic, extra, expected):
    model = build_program_model(
        [_entity()],
        [_field(type=semantic, **extra)],
        [],
        rendered_at=RENDERED_AT,
    )
    block = _only_entity_block(model)
    assert block["fields"][0]["type"] == expected


def test_text_with_unsupported_format_keeps_base_type():
    # percent/multiline have no first-class EspoCRM type → stay varchar.
    model = build_program_model(
        [_entity()], [_field(type="text", field_format="multiline")], [],
        rendered_at=RENDERED_AT,
    )
    assert _only_entity_block(model)["fields"][0]["type"] == "varchar"


# ---------------------------------------------------------------------------
# Entity mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("person", "Person"),
        ("organization", "Company"),
        ("event", "Event"),
        ("transaction", "Base"),
        ("other", "Base"),
        (None, "Base"),
    ],
)
def test_entity_kind_to_type(kind, expected):
    model = build_program_model(
        [_entity(entity_kind=kind)], [], [], rendered_at=RENDERED_AT
    )
    assert _only_entity_block(model)["type"] == expected


def test_entity_labels_and_stream():
    model = build_program_model(
        [_entity(name="Mentor", entity_track_activity=True)],
        [],
        [],
        rendered_at=RENDERED_AT,
    )
    block = _only_entity_block(model)
    assert block["action"] == "create"
    assert block["settings"]["labelSingular"] == "Mentor"
    assert block["settings"]["labelPlural"] == "Mentors"
    assert block["settings"]["stream"] is True


def test_no_stream_when_track_activity_false():
    model = build_program_model([_entity()], [], [], rendered_at=RENDERED_AT)
    assert "stream" not in _only_entity_block(model)["settings"]


# ---------------------------------------------------------------------------
# Field attributes
# ---------------------------------------------------------------------------


def test_field_required_default_readonly_maxlength_external():
    model = build_program_model(
        [_entity()],
        [
            _field(
                name="code",
                type="text",
                field_required=True,
                field_default_value="N/A",
                field_read_only=True,
                field_max_length=20,
                field_externally_populated=True,
            )
        ],
        [],
        rendered_at=RENDERED_AT,
    )
    f = _only_entity_block(model)["fields"][0]
    assert f["required"] is True
    assert f["default"] == "N/A"
    assert f["readOnly"] is True
    assert f["maxLength"] == 20
    assert f["externallyPopulated"] is True


def test_number_min_max_and_bool_default_coercion():
    model = build_program_model(
        [_entity()],
        [
            _field(identifier="FLD-001", name="age", type="number", field_min="0", field_max="120"),
            _field(identifier="FLD-002", name="active", type="boolean", field_default_value="true"),
        ],
        [],
        rendered_at=RENDERED_AT,
    )
    fields = {f["name"]: f for f in _only_entity_block(model)["fields"]}
    assert fields["age"]["min"] == 0 and fields["age"]["max"] == 120
    assert fields["active"]["default"] is True


def test_enum_options_ordered_and_deferred():
    with_opts = _field(
        identifier="FLD-001",
        name="status",
        type="enum",
        field_options=[
            {"option_value": "closed", "option_order": 2},
            {"option_value": "open", "option_order": 1},
        ],
    )
    no_opts = _field(identifier="FLD-002", name="tier", type="enum", field_options=[])
    model = build_program_model([_entity()], [with_opts, no_opts], [], rendered_at=RENDERED_AT)
    fields = {f["name"]: f for f in _only_entity_block(model)["fields"]}
    assert fields["status"]["options"] == ["open", "closed"]
    assert fields["tier"]["optionsDeferred"] is True
    assert "options" not in fields["tier"]


# ---------------------------------------------------------------------------
# Override merge
# ---------------------------------------------------------------------------


def test_override_merge_field_and_entity():
    overrides = [
        {
            "override_target_engine": "espocrm",
            "override_subject_type": "field",
            "override_subject_identifier": "FLD-001",
            "override_attribute": "internal_name",
            "override_value": "customStatusCode",
        },
        {
            "override_target_engine": "espocrm",
            "override_subject_type": "field",
            "override_subject_identifier": "FLD-001",
            "override_attribute": "label",
            "override_value": "Status Code",
        },
        {
            "override_target_engine": "espocrm",
            "override_subject_type": "entity",
            "override_subject_identifier": "ENT-001",
            "override_attribute": "label_plural",
            "override_value": "Applications",
        },
        # A hubspot-scoped override must be ignored by the EspoCRM adapter.
        {
            "override_target_engine": "hubspot",
            "override_subject_type": "field",
            "override_subject_identifier": "FLD-001",
            "override_attribute": "internal_name",
            "override_value": "ignore_me",
        },
    ]
    model = build_program_model(
        [_entity()], [_field(name="status_code", type="text")], overrides,
        rendered_at=RENDERED_AT,
    )
    block = _only_entity_block(model)
    assert block["settings"]["labelPlural"] == "Applications"
    f = block["fields"][0]
    assert f["name"] == "customStatusCode"
    assert f["label"] == "Status Code"


# ---------------------------------------------------------------------------
# Deferral routing + scope filter
# ---------------------------------------------------------------------------


def test_reference_and_derived_fields_deferred():
    model = build_program_model(
        [_entity()],
        [
            _field(identifier="FLD-001", name="account", type="reference"),
            _field(identifier="FLD-002", name="fullName", type="derived"),
            _field(identifier="FLD-003", name="email", type="text"),
        ],
        [],
        rendered_at=RENDERED_AT,
    )
    block = _only_entity_block(model)
    assert [f["name"] for f in block["fields"]] == ["email"]
    kinds = {(d.kind, d.identifier) for d in model.deferrals}
    assert ("reference_field", "FLD-001") in kinds
    assert ("derived_field", "FLD-002") in kinds


def test_field_attribute_and_default_sort_deferred():
    model = build_program_model(
        [_entity(entity_default_sort_field="createdAt", entity_default_sort_direction="desc")],
        [_field(name="note", type="text", field_tooltip="hint", field_unique=True)],
        [],
        rendered_at=RENDERED_AT,
    )
    attr_kinds = [d.detail for d in model.deferrals if d.kind == "field_attribute"]
    assert any("tooltip" in d for d in attr_kinds)
    assert any("unique" in d for d in attr_kinds)
    assert any(d.kind == "entity_default_sort" for d in model.deferrals)
    assert any(d.kind == "composite_constructs" for d in model.deferrals)


def test_scope_filter_excludes_non_confirmed():
    model = build_program_model(
        [
            _entity(identifier="ENT-001", name="Kept"),
            _entity(identifier="ENT-002", name="Dropped", entity_status="candidate"),
        ],
        [
            _field(identifier="FLD-001", name="kept", parent="ENT-001"),
            _field(identifier="FLD-002", name="dropped", parent="ENT-001", field_status="candidate"),
            _field(identifier="FLD-003", name="orphan", parent="ENT-002"),
        ],
        [],
        rendered_at=RENDERED_AT,
    )
    assert [p.entity_name for p in model.programs] == ["Kept"]
    block = model.programs[0].program["entities"]["Kept"]
    assert [f["name"] for f in block["fields"]] == ["kept"]


# ---------------------------------------------------------------------------
# Emit determinism
# ---------------------------------------------------------------------------


def test_emit_is_byte_stable():
    args = ([_entity()], [_field(type="enum", field_options=[{"option_value": "x", "option_order": 0}])], [])
    m1 = build_program_model(*args, rendered_at=RENDERED_AT)
    m2 = build_program_model(*args, rendered_at=RENDERED_AT)
    y1 = emit_program_yaml(m1.programs[0], rendered_at=RENDERED_AT)
    y2 = emit_program_yaml(m2.programs[0], rendered_at=RENDERED_AT)
    assert y1 == y2
    assert "Rendered at " + RENDERED_AT in y1
    mc1 = emit_manual_config_md(m1, rendered_at=RENDERED_AT)
    mc2 = emit_manual_config_md(m2, rendered_at=RENDERED_AT)
    assert mc1 == mc2
