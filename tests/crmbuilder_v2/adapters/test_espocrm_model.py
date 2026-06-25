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
        "entity_tracks_activities": False,
        "entity_default_sort_field": None,
        "entity_default_sort_direction": None,
        "entity_text_filter_fields": None,
        "entity_full_text_search": False,
        "entity_full_text_search_min_length": None,
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
        "field_derived_result_type": None,
        "field_formula": None,
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


@pytest.mark.parametrize(
    "kind, tracks, expected",
    [
        # REQ-337 / PI-297 — activity-tracking lifts an otherwise-Base
        # entity to BasePlus; the person/organization/event templates
        # already carry activities and are left unchanged.
        (None, True, "BasePlus"),
        (None, False, "Base"),
        ("transaction", True, "BasePlus"),
        ("other", True, "BasePlus"),
        ("event", True, "Event"),
        ("person", True, "Person"),
        ("organization", True, "Company"),
    ],
)
def test_entity_tracks_activities_maps_to_baseplus(kind, tracks, expected):
    model = build_program_model(
        [_entity(entity_kind=kind, entity_tracks_activities=tracks)],
        [],
        [],
        rendered_at=RENDERED_AT,
    )
    assert _only_entity_block(model)["type"] == expected


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


# ---------------------------------------------------------------------------
# Derived / formula fields (PI-197)
# ---------------------------------------------------------------------------


def _derived_block(model):
    block = _only_entity_block(model)
    return {f["name"]: f for f in block.get("fields", [])}


def test_derived_concat_renders_readonly_formula_field():
    model = build_program_model(
        [_entity()],
        [
            _field(identifier="FLD-001", name="first_name", type="text"),
            _field(identifier="FLD-002", name="last_name", type="text"),
            _field(
                identifier="FLD-003",
                name="full_name",
                type="derived",
                field_derived_result_type="text",
                field_formula={
                    "kind": "concat",
                    "parts": [
                        {"field": "FLD-001"},
                        {"literal": " "},
                        {"field": "last_name"},
                    ],
                },
            ),
        ],
        [],
        rendered_at=RENDERED_AT,
    )
    fields = _derived_block(model)
    fn = fields["fullName"]
    assert fn["type"] == "varchar"
    assert fn["readOnly"] is True
    assert fn["formula"] == {
        "type": "concat",
        "parts": [
            {"field": "firstName"},
            {"literal": " "},
            {"field": "lastName"},
        ],
    }
    assert not any(d.kind == "derived_field" for d in model.deferrals)


def test_derived_arithmetic_renders_infix_expression():
    model = build_program_model(
        [_entity()],
        [
            _field(identifier="FLD-001", name="capacity", type="number"),
            _field(identifier="FLD-002", name="used", type="number"),
            _field(
                identifier="FLD-003",
                name="available",
                type="derived",
                field_derived_result_type="number",
                field_numeric_scale="integer",
                field_formula={
                    "kind": "arithmetic",
                    "expression": {
                        "op": "-",
                        "left": {"field": "capacity"},
                        "right": {"field": "used"},
                    },
                },
            ),
        ],
        [],
        rendered_at=RENDERED_AT,
    )
    fields = _derived_block(model)
    av = fields["available"]
    assert av["type"] == "int"
    assert av["readOnly"] is True
    assert av["formula"] == {
        "type": "arithmetic",
        "expression": "capacity - used",
    }


def test_derived_arithmetic_parenthesises_lower_precedence():
    model = build_program_model(
        [_entity()],
        [
            _field(identifier="FLD-001", name="a", type="number"),
            _field(identifier="FLD-002", name="b", type="number"),
            _field(identifier="FLD-003", name="c", type="number"),
            _field(
                identifier="FLD-004",
                name="scaled",
                type="derived",
                field_derived_result_type="number",
                field_formula={
                    "kind": "arithmetic",
                    "expression": {
                        "op": "*",
                        "left": {"field": "a"},
                        "right": {
                            "op": "+",
                            "left": {"field": "b"},
                            "right": {"field": "c"},
                        },
                    },
                },
            ),
        ],
        [],
        rendered_at=RENDERED_AT,
    )
    assert _derived_block(model)["scaled"]["formula"]["expression"] == (
        "a * (b + c)"
    )


def test_derived_aggregate_resolves_related_entity_and_via():
    # Dues (source, "one") relates to many Sessions (target). The derived
    # field lives on Dues and sums Session.hours via the link back to Dues.
    entities = [
        _entity(identifier="ENT-001", name="Dues"),
        _entity(identifier="ENT-002", name="Session"),
    ]
    fields = [
        _field(
            identifier="FLD-001",
            name="total_hours",
            type="derived",
            parent="ENT-001",
            field_derived_result_type="number",
            field_numeric_scale="decimal",
            field_formula={
                "kind": "aggregate",
                "function": "sum",
                "association": "ASN-001",
                "field": "hours",
            },
        ),
    ]
    associations = [
        _assoc(
            identifier="ASN-001",
            name="Dues has Sessions",
            source="ENT-001",
            target="ENT-002",
            cardinality="one_to_many",
        )
    ]
    model = build_program_model(
        entities, fields, [], associations=associations, rendered_at=RENDERED_AT
    )
    dues = _program_for(model, "Dues")["entities"]["Dues"]
    total = {f["name"]: f for f in dues["fields"]}["totalHours"]
    assert total["type"] == "float"
    assert total["readOnly"] is True
    assert total["formula"] == {
        "type": "aggregate",
        "function": "sum",
        "relatedEntity": "Session",
        "via": "dues",  # link on Session pointing back to Dues (singular)
        "field": "hours",
    }


def test_derived_no_formula_source_defers():
    model = build_program_model(
        [_entity()],
        [_field(identifier="FLD-001", name="computed", type="derived")],
        [],
        rendered_at=RENDERED_AT,
    )
    block = _only_entity_block(model)
    assert "fields" not in block or all(
        f["name"] != "computed" for f in block.get("fields", [])
    )
    assert any(
        d.kind == "derived_field" and d.identifier == "FLD-001"
        for d in model.deferrals
    )


def test_derived_engine_override_formula_used_verbatim():
    override = {
        "override_target_engine": "espocrm",
        "override_subject_type": "field",
        "override_subject_identifier": "FLD-001",
        "override_attribute": "formula",
        "override_value": {
            "type": "concat",
            "parts": [{"literal": "X"}],
        },
    }
    model = build_program_model(
        [_entity()],
        [
            _field(
                identifier="FLD-001",
                name="computed",
                type="derived",
                field_derived_result_type="text",
            )
        ],
        [override],
        rendered_at=RENDERED_AT,
    )
    computed = _derived_block(model)["computed"]
    assert computed["formula"] == {"type": "concat", "parts": [{"literal": "X"}]}
    assert not any(d.kind == "derived_field" for d in model.deferrals)


def test_derived_aggregate_dangling_association_defers_formula():
    model = build_program_model(
        [_entity()],
        [
            _field(
                identifier="FLD-001",
                name="total",
                type="derived",
                field_derived_result_type="number",
                field_formula={
                    "kind": "aggregate",
                    "function": "count",
                    "association": "ASN-404",
                },
            )
        ],
        [],
        rendered_at=RENDERED_AT,
    )
    # The read-only base field is still emitted (valid YAML), but the formula
    # could not be compiled → deferral, and no formula key attached.
    field_block = _derived_block(model)["total"]
    assert field_block["readOnly"] is True
    assert "formula" not in field_block
    assert any(d.kind == "derived_field" for d in model.deferrals)


def test_field_attribute_deferred():
    model = build_program_model(
        [_entity(entity_default_sort_field="createdAt", entity_default_sort_direction="desc")],
        [_field(name="note", type="text", field_tooltip="hint", field_unique=True)],
        [],
        rendered_at=RENDERED_AT,
    )
    attr_kinds = [d.detail for d in model.deferrals if d.kind == "field_attribute"]
    assert any("tooltip" in d for d in attr_kinds)
    assert any("unique" in d for d in attr_kinds)
    # REQ-340 / PI-300: the default-sort intent now emits to settings:
    # (v1.3.2 §5.4), so it is no longer deferred.
    assert not any(d.kind == "entity_default_sort" for d in model.deferrals)
    # Slice 3 emits the composite-construct blocks, so the standing
    # composite_constructs deferral no longer exists.
    assert not any(d.kind == "composite_constructs" for d in model.deferrals)


def test_collection_settings_emit_to_settings():
    # REQ-340 / PI-300: all five collection settings render into the
    # entity-level settings: block per the v1.3.2 EspoCRM schema keys.
    model = build_program_model(
        [
            _entity(
                entity_default_sort_field="createdAt",
                entity_default_sort_direction="desc",
                entity_text_filter_fields=["name", "emailAddress"],
                entity_full_text_search=True,
                entity_full_text_search_min_length=4,
            )
        ],
        [],
        [],
        rendered_at=RENDERED_AT,
    )
    program = model.programs[0].program
    settings = program["entities"]["Mentor Application"]["settings"]
    assert settings["orderBy"] == "createdAt"
    assert settings["order"] == "desc"
    assert settings["textFilterFields"] == ["name", "emailAddress"]
    assert settings["fullTextSearch"] is True
    assert settings["fullTextSearchMinLength"] == 4
    # No default-sort deferral is produced when the settings emit.
    assert not any(d.kind == "entity_default_sort" for d in model.deferrals)


def test_collection_settings_omitted_when_unset():
    # An entity with no collection settings emits only the label keys (+ no
    # collection keys), and orderBy defaults order to asc when only the sort
    # field is set.
    model = build_program_model(
        [_entity(entity_default_sort_field="name")],
        [],
        [],
        rendered_at=RENDERED_AT,
    )
    settings = model.programs[0].program["entities"]["Mentor Application"][
        "settings"
    ]
    assert settings["orderBy"] == "name"
    assert settings["order"] == "asc"
    assert "textFilterFields" not in settings
    assert "fullTextSearch" not in settings
    assert "fullTextSearchMinLength" not in settings


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


# ---------------------------------------------------------------------------
# Security rules → fieldPermissions: / fieldVisibility: (PI-051, REQ-128/129)
# ---------------------------------------------------------------------------


def _role(identifier="ROL-001", name="Coordinator"):
    return {"role_identifier": identifier, "role_name": name}


def _fpr(
    identifier="FPR-001",
    name="perm",
    role="ROL-001",
    target_field="FLD-001",
    level="read_only",
    status="confirmed",
):
    return {
        "field_permission_rule_identifier": identifier,
        "field_permission_rule_name": name,
        "field_permission_rule_role": role,
        "field_permission_rule_target_field": target_field,
        "field_permission_rule_permission_level": level,
        "field_permission_rule_status": status,
    }


def _fvr(
    identifier="FVR-001",
    name="vis",
    role="ROL-001",
    target_field="FLD-001",
    visible=False,
    status="confirmed",
):
    return {
        "field_visibility_rule_identifier": identifier,
        "field_visibility_rule_name": name,
        "field_visibility_rule_role": role,
        "field_visibility_rule_target_field": target_field,
        "field_visibility_rule_visible": visible,
        "field_visibility_rule_status": status,
    }


@pytest.mark.parametrize("level", ["read_write", "read_only", "no_access"])
def test_field_permission_renders_entry(level):
    model = build_program_model(
        [_entity()],
        [_field(identifier="FLD-001", name="ssn", type="text")],
        [],
        field_permission_rules=[_fpr(level=level)],
        roles=[_role(name="Coordinator")],
        rendered_at=RENDERED_AT,
    )
    fps = _program_for(model, "Mentor Application")["fieldPermissions"]
    assert fps == [
        {
            "role": "Coordinator",
            "entity": "Mentor Application",
            "field": "ssn",
            "level": level,
        }
    ]
    assert not any(
        d.kind == "field_permission" for d in model.deferrals
    )


def test_field_visibility_renders_entry():
    model = build_program_model(
        [_entity()],
        [_field(identifier="FLD-001", name="ssn", type="text")],
        [],
        field_visibility_rules=[_fvr(visible=False)],
        roles=[_role(name="Coordinator")],
        rendered_at=RENDERED_AT,
    )
    fvs = _program_for(model, "Mentor Application")["fieldVisibility"]
    assert fvs == [
        {
            "role": "Coordinator",
            "entity": "Mentor Application",
            "field": "ssn",
            "visible": False,
        }
    ]


def test_candidate_security_rule_skipped_silently():
    model = build_program_model(
        [_entity()],
        [_field(identifier="FLD-001", name="ssn", type="text")],
        [],
        field_permission_rules=[_fpr(status="candidate")],
        roles=[_role()],
        rendered_at=RENDERED_AT,
    )
    assert "fieldPermissions" not in _program_for(model, "Mentor Application")
    assert not any(d.kind == "field_permission" for d in model.deferrals)


def test_permission_rule_for_unemitted_field_deferred():
    # The target field is a deferred reference field → not emitted → deferral.
    model = build_program_model(
        [_entity()],
        [_field(identifier="FLD-001", name="account", type="reference")],
        [],
        field_permission_rules=[_fpr(target_field="FLD-001")],
        roles=[_role()],
        rendered_at=RENDERED_AT,
    )
    assert "fieldPermissions" not in _program_for(model, "Mentor Application")
    assert any(d.kind == "field_permission" for d in model.deferrals)


def test_permission_rule_on_nonconfirmed_entity_deferred():
    # The field's parent entity is candidate → never emitted → deferral.
    model = build_program_model(
        [_entity(identifier="ENT-001", entity_status="candidate")],
        [_field(identifier="FLD-001", name="ssn", parent="ENT-001")],
        [],
        field_permission_rules=[_fpr(target_field="FLD-001")],
        roles=[_role()],
        rendered_at=RENDERED_AT,
    )
    assert model.programs == []
    assert any(d.kind == "field_permission" for d in model.deferrals)


def test_permission_rule_with_unresolvable_role_deferred():
    model = build_program_model(
        [_entity()],
        [_field(identifier="FLD-001", name="ssn", type="text")],
        [],
        field_permission_rules=[_fpr(role="ROL-999")],
        roles=[_role(identifier="ROL-001")],  # no ROL-999
        rendered_at=RENDERED_AT,
    )
    assert "fieldPermissions" not in _program_for(model, "Mentor Application")
    assert any(d.kind == "field_permission" for d in model.deferrals)


def test_security_blocks_byte_stable():
    args = (
        [_entity()],
        [_field(identifier="FLD-001", name="ssn", type="text")],
        [],
    )
    kw = {
        "field_permission_rules": [_fpr()],
        "field_visibility_rules": [_fvr()],
        "roles": [_role()],
    }
    m1 = build_program_model(*args, **kw, rendered_at=RENDERED_AT)
    m2 = build_program_model(*args, **kw, rendered_at=RENDERED_AT)
    y1 = emit_program_yaml(m1.programs[0], rendered_at=RENDERED_AT)
    y2 = emit_program_yaml(m2.programs[0], rendered_at=RENDERED_AT)
    assert y1 == y2
    assert "fieldPermissions:" in y1
    assert "fieldVisibility:" in y1


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


# ---------------------------------------------------------------------------
# Slice 3 — views/automations/dedup_rules/message_templates → config blocks
# ---------------------------------------------------------------------------


def _view(identifier="VEW-001", name="Active", entity="ENT-001", **over):
    base = {
        "view_identifier": identifier,
        "view_name": name,
        "view_entity": entity,
        "view_columns": ["FLD-001"],
        "view_filter": {"field": "FLD-001", "op": "eq", "value": "x"},
        "view_sort_field": None,
        "view_sort_direction": None,
        "view_description": None,
        "view_notes": None,
        "view_status": "confirmed",
    }
    base.update(over)
    return base


def _automation(identifier="AUT-001", name="Stamp", entity="ENT-001", **over):
    base = {
        "automation_identifier": identifier,
        "automation_name": name,
        "automation_entity": entity,
        "automation_trigger": "on_update",
        "automation_condition": None,
        "automation_actions": [
            {"type": "set_field", "field": "FLD-001", "value": "done"}
        ],
        "automation_description": None,
        "automation_notes": None,
        "automation_status": "confirmed",
    }
    base.update(over)
    return base


def _dedup(identifier="DUP-001", name="No dup email", entity="ENT-001", **over):
    base = {
        "dedup_rule_identifier": identifier,
        "dedup_rule_name": name,
        "dedup_rule_entity": entity,
        "dedup_rule_match_fields": ["FLD-001"],
        "dedup_rule_normalize": None,
        "dedup_rule_on_match": "block",
        "dedup_rule_message": "Already exists",
        "dedup_rule_description": None,
        "dedup_rule_notes": None,
        "dedup_rule_status": "confirmed",
    }
    base.update(over)
    return base


def _message(identifier="MSG-001", name="Welcome", entity="ENT-001", **over):
    base = {
        "message_template_identifier": identifier,
        "message_template_name": name,
        "message_template_entity": entity,
        "message_template_channel": "email",
        "message_template_subject": "Hello {{whoever}}",
        "message_template_body": "Welcome to the program.",
        "message_template_merge_fields": ["FLD-001"],
        "message_template_audience": None,
        "message_template_description": None,
        "message_template_notes": None,
        "message_template_status": "confirmed",
    }
    base.update(over)
    return base


def _build(**kw):
    return build_program_model(
        kw.pop("entities", [_entity()]),
        kw.pop("fields", [_field(name="mentor_status", type="text")]),
        kw.pop("overrides", []),
        rendered_at=RENDERED_AT,
        **kw,
    )


def test_view_compiles_filter_columns_and_sort():
    model = _build(
        views=[
            _view(
                view_columns=["FLD-001"],
                view_filter={"field": "FLD-001", "op": "eq", "value": "x"},
                view_sort_field="FLD-001",
                view_sort_direction="desc",
            )
        ]
    )
    block = _only_entity_block(model)
    sv = block["savedViews"][0]
    assert sv["id"] == "vew-001"
    assert sv["name"] == "Active"
    assert sv["columns"] == ["mentorStatus"]
    # neutral op 'eq' compiled to the EspoCRM 'equals'; ref to internal name
    assert sv["filter"] == {"field": "mentorStatus", "op": "equals", "value": "x"}
    assert sv["orderBy"] == {"field": "mentorStatus", "direction": "desc"}


def test_view_without_filter_defers():
    model = _build(views=[_view(view_filter=None)])
    block = _only_entity_block(model)
    assert "savedViews" not in block
    assert any(d.kind == "view" for d in model.deferrals)


def test_view_filter_on_unemitted_field_defers():
    # condition references a field that is not emitted → defer (never emit a
    # field reference validate_program would reject).
    model = _build(
        views=[_view(view_filter={"field": "FLD-404", "op": "eq", "value": "x"})]
    )
    block = _only_entity_block(model)
    assert "savedViews" not in block
    assert any(d.kind == "view" for d in model.deferrals)


def test_automation_trigger_and_action_mapping():
    model = _build(
        automations=[
            _automation(
                automation_trigger="on_update",
                automation_condition={"field": "FLD-001", "op": "eq", "value": "x"},
                automation_actions=[
                    {"type": "set_field", "field": "FLD-001", "value": "done"}
                ],
            )
        ]
    )
    wf = _only_entity_block(model)["workflows"][0]
    assert wf["id"] == "aut-001"
    assert wf["trigger"] == {"event": "onUpdate"}
    assert wf["where"] == {"field": "mentorStatus", "op": "equals", "value": "x"}
    assert wf["actions"] == [
        {"type": "setField", "field": "mentorStatus", "value": "done"}
    ]


def test_automation_scheduled_trigger_defers():
    model = _build(automations=[_automation(automation_trigger="scheduled")])
    block = _only_entity_block(model)
    assert "workflows" not in block
    assert any(d.kind == "automation" for d in model.deferrals)


def test_automation_unmappable_action_defers_whole_workflow():
    model = _build(
        automations=[_automation(automation_actions=[{"type": "webhook"}])]
    )
    block = _only_entity_block(model)
    assert "workflows" not in block
    assert any(d.kind == "workflow_action" for d in model.deferrals)
    assert any(d.kind == "automation" for d in model.deferrals)


def test_dedup_onmatch_and_normalize_mapping():
    model = _build(
        dedup_rules=[
            _dedup(
                dedup_rule_on_match="block",
                dedup_rule_message="Dup!",
                dedup_rule_normalize={"FLD-001": "lowercase"},
            )
        ]
    )
    dc = _only_entity_block(model)["duplicateChecks"][0]
    assert dc["id"] == "dup-001"
    assert dc["fields"] == ["mentorStatus"]
    assert dc["onMatch"] == "block"
    assert dc["message"] == "Dup!"
    # neutral 'lowercase' → EspoCRM 'lowercase-trim'
    assert dc["normalize"] == {"mentorStatus": "lowercase-trim"}


def test_dedup_block_without_message_gets_default():
    model = _build(dedup_rules=[_dedup(dedup_rule_message=None)])
    dc = _only_entity_block(model)["duplicateChecks"][0]
    assert dc["onMatch"] == "block"
    assert dc["message"]  # synthesized non-empty message for block


def test_dedup_unmappable_normalize_token_drops_with_note():
    model = _build(
        dedup_rules=[_dedup(dedup_rule_normalize={"FLD-001": "digits_only"})]
    )
    dc = _only_entity_block(model)["duplicateChecks"][0]
    assert "normalize" not in dc  # digits_only has no EspoCRM value → dropped
    assert any(d.kind == "dedup_normalize" for d in model.deferrals)


def test_message_template_emits_block_and_companion_body():
    model = _build(
        message_templates=[
            _message(
                message_template_subject="Hi {{x}}",
                message_template_body="Body text {{y}}.",
                message_template_merge_fields=["FLD-001"],
            )
        ]
    )
    et = _only_entity_block(model)["emailTemplates"][0]
    assert et["id"] == "msg-001"
    assert et["entity"] == "Mentor Application"
    # stray neutral placeholders stripped from subject
    assert "{{" not in et["subject"]
    assert et["bodyFile"] == "templates/msg-001.html"
    assert et["mergeFields"] == ["mentorStatus"]
    # one companion body file emitted, using exactly the merge field
    assert len(model.companions) == 1
    comp = model.companions[0]
    assert comp.filename == "templates/msg-001.html"
    assert "{{mentorStatus}}" in comp.content
    assert "{{x}}" not in comp.content and "{{y}}" not in comp.content


def test_message_template_non_email_channel_defers():
    model = _build(message_templates=[_message(message_template_channel="sms")])
    block = _only_entity_block(model)
    assert "emailTemplates" not in block
    assert not model.companions
    assert any(d.kind == "message_template" for d in model.deferrals)


def test_message_template_null_entity_defers():
    model = _build(message_templates=[_message(message_template_entity=None)])
    assert not model.companions
    assert any(d.kind == "message_template" for d in model.deferrals)


def test_message_template_no_resolvable_merge_field_defers():
    model = _build(
        message_templates=[_message(message_template_merge_fields=["FLD-404"])]
    )
    block = _only_entity_block(model)
    assert "emailTemplates" not in block
    assert any(d.kind == "message_template" for d in model.deferrals)


def test_composite_block_override_applies():
    model = _build(
        views=[_view()],
        overrides=[
            {
                "override_target_engine": "espocrm",
                "override_subject_type": "view",
                "override_subject_identifier": "VEW-001",
                "override_attribute": "name",
                "override_value": "Pinned Name",
            }
        ],
    )
    sv = _only_entity_block(model)["savedViews"][0]
    assert sv["name"] == "Pinned Name"


def test_record_for_unconfirmed_entity_defers():
    # entity ENT-002 is not in the confirmed set → its view defers.
    model = _build(views=[_view(entity="ENT-002")])
    assert any(d.kind == "view" for d in model.deferrals)
