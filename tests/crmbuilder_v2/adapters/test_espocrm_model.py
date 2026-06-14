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


def _assoc(
    identifier="ASN-001",
    name="rel",
    source="ENT-001",
    target="ENT-002",
    cardinality="one_to_many",
    status="confirmed",
    source_role=None,
    target_role=None,
    description=None,
):
    return {
        "association_identifier": identifier,
        "association_name": name,
        "association_source_entity": source,
        "association_target_entity": target,
        "association_cardinality": cardinality,
        "association_source_role": source_role,
        "association_target_role": target_role,
        "association_description": description,
        "association_notes": None,
        "association_status": status,
    }


def _rule(
    identifier="RUL-001",
    name="gate",
    subject_type="field",
    subject="FLD-001",
    effect="required_when",
    condition=None,
    status="confirmed",
):
    return {
        "rule_identifier": identifier,
        "rule_name": name,
        "rule_subject_type": subject_type,
        "rule_subject_identifier": subject,
        "rule_effect": effect,
        "rule_condition": condition or {"field": "FLD-002", "op": "eq", "value": "x"},
        "rule_message": None,
        "rule_status": status,
    }


def _only_entity_block(model):
    assert len(model.programs) == 1
    program = model.programs[0].program
    name = model.programs[0].entity_name
    return program["entities"][name]


def _program_for(model, entity_name):
    for p in model.programs:
        if p.entity_name == entity_name:
            return p.program
    raise AssertionError(f"no program for {entity_name}")


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


# ---------------------------------------------------------------------------
# Associations → relationships: block (slice 2)
# ---------------------------------------------------------------------------


def _two_entities():
    return [
        _entity(identifier="ENT-001", name="Sponsor Org"),
        _entity(identifier="ENT-002", name="Mentor Application"),
    ]


@pytest.mark.parametrize(
    "cardinality,link_type",
    [
        ("one_to_one", "oneToOne"),
        ("one_to_many", "oneToMany"),
        ("many_to_many", "manyToMany"),
    ],
)
def test_cardinality_to_link_type(cardinality, link_type):
    model = build_program_model(
        _two_entities(),
        [],
        [],
        associations=[_assoc(cardinality=cardinality)],
        rendered_at=RENDERED_AT,
    )
    rels = _program_for(model, "Sponsor Org")["relationships"]
    assert len(rels) == 1
    rel = rels[0]
    assert rel["linkType"] == link_type
    assert rel["entity"] == "Sponsor Org"
    assert rel["entityForeign"] == "Mentor Application"
    # Required keys for validate_program.
    for key in ("name", "link", "linkForeign", "label", "labelForeign"):
        assert rel[key]
    if link_type == "manyToMany":
        assert rel["relationName"]


def test_link_names_derive_singular_plural_by_cardinality():
    model = build_program_model(
        _two_entities(), [], [],
        associations=[_assoc(cardinality="one_to_many")],
        rendered_at=RENDERED_AT,
    )
    rel = _program_for(model, "Sponsor Org")["relationships"][0]
    # source is the "one", reaches many targets → plural; target reaches one
    # source → singular.
    assert rel["link"] == "mentorApplications"
    assert rel["linkForeign"] == "sponsorOrg"


def test_link_names_use_roles_when_present():
    model = build_program_model(
        _two_entities(), [], [],
        associations=[
            _assoc(
                source_role="primary sponsor",
                target_role="funded applications",
            )
        ],
        rendered_at=RENDERED_AT,
    )
    rel = _program_for(model, "Sponsor Org")["relationships"][0]
    assert rel["link"] == "primarySponsor"
    assert rel["linkForeign"] == "fundedApplications"


def test_association_link_overrides():
    overrides = [
        {
            "override_target_engine": "espocrm",
            "override_subject_type": "association",
            "override_subject_identifier": "ASN-001",
            "override_attribute": "link_name_source",
            "override_value": "sponsoredApps",
        },
        {
            "override_target_engine": "espocrm",
            "override_subject_type": "association",
            "override_subject_identifier": "ASN-001",
            "override_attribute": "link_type",
            "override_value": "manyToMany",
        },
    ]
    model = build_program_model(
        _two_entities(), [], overrides,
        associations=[_assoc(cardinality="one_to_many")],
        rendered_at=RENDERED_AT,
    )
    rel = _program_for(model, "Sponsor Org")["relationships"][0]
    assert rel["link"] == "sponsoredApps"
    assert rel["linkType"] == "manyToMany"


def test_non_confirmed_or_dangling_association_deferred():
    model = build_program_model(
        _two_entities(), [], [],
        associations=[
            _assoc(identifier="ASN-001", status="candidate"),
            _assoc(identifier="ASN-002", target="ENT-099"),  # dangling endpoint
        ],
        rendered_at=RENDERED_AT,
    )
    # The candidate is skipped silently; the dangling one is a deferral.
    assert "relationships" not in _program_for(model, "Sponsor Org")
    assoc_defers = [d for d in model.deferrals if d.kind == "association"]
    assert {d.identifier for d in assoc_defers} == {"ASN-002"}


# ---------------------------------------------------------------------------
# Rules → requiredWhen / visibleWhen (slice 2)
# ---------------------------------------------------------------------------


def test_required_when_rule_attaches_and_drops_required():
    fields = [
        _field(identifier="FLD-001", name="approver", type="text", field_required=True),
        _field(identifier="FLD-002", name="status", type="text"),
    ]
    rule = _rule(
        subject="FLD-001",
        effect="required_when",
        condition={"field": "FLD-002", "op": "eq", "value": "approved"},
    )
    model = build_program_model(
        [_entity()], fields, [], rules=[rule], rendered_at=RENDERED_AT
    )
    fmap = {f["name"]: f for f in _only_entity_block(model)["fields"]}
    approver = fmap["approver"]
    assert approver["requiredWhen"] == {
        "field": "status", "op": "equals", "value": "approved",
    }
    # required: true is dropped — it is mutually exclusive with requiredWhen.
    assert "required" not in approver


def test_visible_when_rule_attaches():
    fields = [
        _field(identifier="FLD-001", name="approver", type="text"),
        _field(identifier="FLD-002", name="status", type="text"),
    ]
    rule = _rule(
        subject="FLD-001",
        effect="visible_when",
        condition={"field": "FLD-002", "op": "is_not_empty"},
    )
    model = build_program_model(
        [_entity()], fields, [], rules=[rule], rendered_at=RENDERED_AT
    )
    fmap = {f["name"]: f for f in _only_entity_block(model)["fields"]}
    assert fmap["approver"]["visibleWhen"] == {"field": "status", "op": "isNotNull"}


def test_valid_when_rule_deferred():
    rule = _rule(subject="FLD-001", effect="valid_when",
                 condition={"field": "FLD-001", "op": "is_not_empty"})
    model = build_program_model(
        [_entity()], [_field(identifier="FLD-001", name="approver")], [],
        rules=[rule], rendered_at=RENDERED_AT,
    )
    assert "requiredWhen" not in _only_entity_block(model)["fields"][0]
    assert any(d.kind == "field_rule" for d in model.deferrals)


def test_entity_subject_rule_deferred():
    rule = _rule(subject_type="entity", subject="ENT-001", effect="valid_when",
                 condition={"field": "FLD-001", "op": "is_not_empty"})
    model = build_program_model(
        [_entity()], [_field(identifier="FLD-001", name="approver")], [],
        rules=[rule], rendered_at=RENDERED_AT,
    )
    assert any(d.kind == "entity_rule" for d in model.deferrals)


def test_rule_for_unemitted_field_deferred():
    # Subject field is a deferred reference field → no payload to attach to.
    rule = _rule(subject="FLD-001", effect="required_when",
                 condition={"field": "FLD-002", "op": "eq", "value": "x"})
    model = build_program_model(
        [_entity()],
        [
            _field(identifier="FLD-001", name="account", type="reference"),
            _field(identifier="FLD-002", name="status", type="text"),
        ],
        [],
        rules=[rule],
        rendered_at=RENDERED_AT,
    )
    assert any(d.kind == "field_rule" for d in model.deferrals)


def test_candidate_rule_skipped_silently():
    rule = _rule(subject="FLD-001", status="candidate")
    model = build_program_model(
        [_entity()],
        [_field(identifier="FLD-001", name="approver"),
         _field(identifier="FLD-002", name="status")],
        [],
        rules=[rule],
        rendered_at=RENDERED_AT,
    )
    fmap = {f["name"]: f for f in _only_entity_block(model)["fields"]}
    assert "requiredWhen" not in fmap["approver"]
    assert not any(d.kind == "field_rule" for d in model.deferrals)


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
