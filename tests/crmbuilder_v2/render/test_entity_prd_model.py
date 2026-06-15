"""Pure unit tests for the Entity PRD model (PI-196).

These exercise :func:`build_prd_model` / :func:`render_prd_markdown` on
hand-built fixture inputs — no DB, no API. They assert: the field-table
rows match the source records (REQ-147); neutral type names are used
verbatim (no platform type leakage); association/rule prose reads in
business terms; and empty sections are omitted cleanly.
"""

from __future__ import annotations

from crmbuilder_v2.render.entity_prd import (
    PrdInputs,
    build_document,
    build_prd_model,
    render_prd_markdown,
)

RENDERED_AT = "2026-06-14T12:00:00+00:00"


def _entity(identifier: str, name: str, **kw) -> dict:
    row = {
        "entity_identifier": identifier,
        "entity_name": name,
        "entity_status": "confirmed",
        "entity_kind": kw.get("kind", "person"),
        "entity_description": kw.get("description", ""),
        "entity_track_activity": kw.get("track_activity", False),
        "entity_default_sort_field": kw.get("default_sort_field"),
        "entity_default_sort_direction": kw.get("default_sort_direction"),
    }
    return row


def _field(identifier: str, parent: str, name: str, ftype: str, **kw) -> dict:
    return {
        "field_identifier": identifier,
        "parent_entity_identifier": parent,
        "field_name": name,
        "field_type": ftype,
        "field_status": "confirmed",
        "field_required": kw.get("required", False),
        "field_default_value": kw.get("default"),
        "field_format": kw.get("format"),
        "field_numeric_scale": kw.get("numeric_scale"),
        "field_min": kw.get("min"),
        "field_max": kw.get("max"),
        "field_max_length": kw.get("max_length"),
        "field_description": kw.get("description", ""),
        "field_read_only": kw.get("read_only", False),
        "field_unique": kw.get("unique", False),
        "field_externally_populated": kw.get("externally_populated", False),
        "field_tooltip": kw.get("tooltip"),
        "field_usage_summary": kw.get("usage_summary"),
        "field_options": kw.get("options", []),
    }


def _empty_inputs(**kw) -> PrdInputs:
    return PrdInputs(
        entities=kw.get("entities", []),
        fields=kw.get("fields", []),
        associations=kw.get("associations", []),
        rules=kw.get("rules", []),
        views=kw.get("views", []),
        dedup_rules=kw.get("dedup_rules", []),
        automations=kw.get("automations", []),
        message_templates=kw.get("message_templates", []),
        engagement=kw.get("engagement", "ENG-001"),
    )


def test_field_table_rows_match_source_records():
    """The rendered field table is a faithful projection of the records."""
    inputs = _empty_inputs(
        entities=[_entity("ENT-001", "Mentor Application", kind="person")],
        fields=[
            _field(
                "FLD-001", "ENT-001", "Contact email", "text",
                format="email", required=True, max_length=120,
                description="primary email",
            ),
            _field(
                "FLD-002", "ENT-001", "Application status", "enum",
                options=[
                    {"option_value": "submitted", "option_label": "Submitted",
                     "option_order": 1},
                    {"option_value": "approved", "option_label": "Approved",
                     "option_order": 2},
                ],
            ),
            _field(
                "FLD-003", "ENT-001", "Years experience", "number",
                numeric_scale="decimal", min="0", max="60",
            ),
        ],
    )
    model = build_prd_model(inputs, rendered_at=RENDERED_AT)
    assert len(model.entities) == 1
    doc = model.entities[0]

    by_name = {f["name"]: f for f in doc.fields}
    # Name / Type / Required / Default match the source field records exactly.
    assert by_name["Contact email"]["type"] == "text"  # neutral type, not varchar
    assert by_name["Contact email"]["required"] == "Yes"
    assert by_name["Application status"]["type"] == "enum"
    assert by_name["Application status"]["required"] == "No"
    assert by_name["Years experience"]["type"] == "number"

    # Enum options are listed (label + value), in option_order.
    assert by_name["Application status"]["options"] == [
        "Submitted (submitted)", "Approved (approved)"
    ]
    # Format column carries the neutral format + numeric scale + bounds.
    assert "email" in by_name["Contact email"]["format"]
    assert "max length 120" in by_name["Contact email"]["format"]
    assert "decimal" in by_name["Years experience"]["format"]
    assert "0–60" in by_name["Years experience"]["format"]


def test_no_platform_type_names_leak():
    """The neutral field_type vocabulary is used verbatim — no EspoCRM
    platform type names (varchar/multiEnum/currency/...) appear."""
    inputs = _empty_inputs(
        entities=[_entity("ENT-001", "Donation", kind="transaction")],
        fields=[
            _field("FLD-001", "ENT-001", "Amount", "money"),
            _field("FLD-002", "ENT-001", "Tags", "multi_enum",
                   options=[{"option_value": "vip", "option_order": 1}]),
            _field("FLD-003", "ENT-001", "Notes", "long_text"),
        ],
    )
    model = build_prd_model(inputs, rendered_at=RENDERED_AT)
    rendered = render_prd_markdown(model.entities[0], model)
    for platform_token in ("varchar", "multiEnum", "currency", "Person", "Base"):
        assert platform_token not in rendered
    # Neutral types are present.
    assert "money" in rendered
    assert "multi_enum" in rendered
    assert "long_text" in rendered


def test_association_and_rule_prose():
    """Associations and rules render in readable business prose."""
    inputs = _empty_inputs(
        entities=[
            _entity("ENT-001", "Sponsor Organization", kind="organization"),
            _entity("ENT-002", "Mentor Application", kind="person"),
        ],
        fields=[
            _field("FLD-001", "ENT-002", "Application status", "enum",
                   options=[{"option_value": "approved", "option_order": 1}]),
            _field("FLD-002", "ENT-002", "Approver name", "text"),
        ],
        associations=[
            {
                "association_identifier": "ASC-001",
                "association_name": "Sponsor funds applications",
                "association_source_entity": "ENT-001",
                "association_target_entity": "ENT-002",
                "association_cardinality": "one_to_many",
                "association_source_role": "funds",
                "association_target_role": None,
                "association_description": None,
                "association_status": "confirmed",
            }
        ],
        rules=[
            {
                "rule_identifier": "RUL-001",
                "rule_name": "Approver required once approved",
                "rule_subject_type": "field",
                "rule_subject_identifier": "FLD-002",
                "rule_effect": "required_when",
                "rule_condition": {
                    "field": "FLD-001", "op": "eq", "value": "approved"
                },
                "rule_message": None,
                "rule_status": "confirmed",
            }
        ],
    )
    model = build_prd_model(inputs, rendered_at=RENDERED_AT)
    by_id = {d.identifier: d for d in model.entities}

    # The association appears on both endpoints, in plain cardinality terms.
    app = by_id["ENT-002"]
    assert any(
        "Sponsor Organization" in line and "Mentor Application" in line
        and "one-to-many" in line and "funds" in line
        for line in app.relationships
    )

    # The rule reads as a sentence with field business names.
    assert app.rules == [
        "**Approver name** — Required when Application status equals approved"
    ]


def test_empty_sections_omitted():
    """An entity with only fields has no Relationships/Rules/Views/etc.
    sections in the rendered document."""
    inputs = _empty_inputs(
        entities=[_entity("ENT-001", "Lone Entity")],
        fields=[_field("FLD-001", "ENT-001", "Name", "text")],
    )
    model = build_prd_model(inputs, rendered_at=RENDERED_AT)
    doc = model.entities[0]
    document = build_document(doc, model)
    titles = {s.title for s in document.sections}
    assert "Entity Overview" in titles
    assert "Fields" in titles
    assert "Relationships" not in titles
    assert "Rules" not in titles
    assert "Views" not in titles
    assert "Duplicate Detection" not in titles
    assert "Automation" not in titles
    assert "Notification Templates" not in titles

    rendered = render_prd_markdown(doc, model)
    assert "## Relationships" not in rendered
    assert "## Rules" not in rendered


def test_entity_filter_restricts_documents():
    inputs = _empty_inputs(
        entities=[
            _entity("ENT-001", "First"),
            _entity("ENT-002", "Second"),
        ],
        fields=[_field("FLD-001", "ENT-002", "Name", "text")],
    )
    model = build_prd_model(inputs, rendered_at=RENDERED_AT, entity="ENT-002")
    assert [d.identifier for d in model.entities] == ["ENT-002"]


def test_determinism_two_builds_equal():
    inputs = _empty_inputs(
        entities=[_entity("ENT-001", "Mentor Application")],
        fields=[
            _field("FLD-002", "ENT-001", "B field", "text"),
            _field("FLD-001", "ENT-001", "A field", "enum",
                   options=[
                       {"option_value": "y", "option_order": 2},
                       {"option_value": "x", "option_order": 1},
                   ]),
        ],
    )
    m1 = build_prd_model(inputs, rendered_at=RENDERED_AT)
    m2 = build_prd_model(inputs, rendered_at=RENDERED_AT)
    r1 = render_prd_markdown(m1.entities[0], m1)
    r2 = render_prd_markdown(m2.entities[0], m2)
    assert r1 == r2
    # Field ordering is by identifier, deterministic.
    assert [f["name"] for f in m1.entities[0].fields] == ["A field", "B field"]
