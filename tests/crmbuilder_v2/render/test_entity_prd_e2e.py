"""End-to-end test — Entity PRD emitter against the access layer (PI-196).

Seeds a representative engagement (a confirmed entity with several fields
including an enum-with-options and a required field, a confirmed
association, and a confirmed ``required_when`` rule) through the
repositories, runs the emitter via an access-layer-backed
:class:`DesignClient`, and asserts:

* the rendered document contains the entity overview, a fields table
  whose rows match the seeded field records (name/type/required) — the
  REQ-147 acceptance bar;
* the association renders in prose;
* the rule renders in prose;
* two runs are byte-identical (determinism).
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import (
    association,
    entity,
    field,
    rule,
)
from crmbuilder_v2.adapters.espocrm.client import DesignClient
from crmbuilder_v2.render.entity_prd import (
    build_prd_model,
    fetch_prd_inputs,
    render_prd_markdown,
    write_documents,
)

RENDERED_AT = "2026-06-14T12:00:00+00:00"


class AccessDesignClient(DesignClient):
    """A GET-only design client reading straight from the access layer
    (the test analog of ``RestDesignClient``)."""

    engagement = "ENG-001"

    def list_entities(self) -> list[dict]:
        with session_scope() as s:
            return entity.list_entities(s)

    def list_fields(self) -> list[dict]:
        with session_scope() as s:
            entities = entity.list_entities(s)
            rows: list[dict] = []
            for ent in entities:
                eid = ent["entity_identifier"]
                for f in field.list_fields(s, entity_identifier=eid):
                    f["parent_entity_identifier"] = eid
                    rows.append(f)
            return rows

    def list_engine_overrides(self) -> list[dict]:
        return []

    def list_associations(self) -> list[dict]:
        with session_scope() as s:
            return association.list_associations(s)

    def list_rules(self) -> list[dict]:
        with session_scope() as s:
            return rule.list_rules(s)

    def list_views(self) -> list[dict]:
        return []

    def list_automations(self) -> list[dict]:
        return []

    def list_dedup_rules(self) -> list[dict]:
        return []

    def list_message_templates(self) -> list[dict]:
        return []


def _seed() -> dict:
    ids: dict = {}
    with session_scope() as s:
        org = entity.create_entity(
            s,
            name="Sponsor Organization",
            description="A sponsoring organization",
            kind="organization",
            status="confirmed",
        )
        org_id = org["entity_identifier"]
        app = entity.create_entity(
            s,
            name="Mentor Application",
            description="An application submitted by a prospective mentor",
            kind="person",
            status="confirmed",
            track_activity=True,
        )
        app_id = app["entity_identifier"]

        field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="Contact email",
            description="primary email",
            type="text",
            status="confirmed",
            format="email",
            required=True,
        )
        status_field = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="Application status",
            description="where the application is",
            type="enum",
            status="confirmed",
            options=[
                {"option_value": "submitted", "option_order": 1},
                {"option_value": "approved", "option_order": 2},
            ],
        )
        approver_field = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="Approver name",
            description="who approved it",
            type="text",
            status="confirmed",
        )
        # A candidate field — excluded by the confirmed-only filter.
        field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="Draft note",
            description="scratch",
            type="text",
            status="candidate",
        )

        association.create_association(
            s,
            name="Sponsor funds applications",
            source_entity=org_id,
            target_entity=app_id,
            cardinality="one_to_many",
            status="confirmed",
        )

        rule.create_rule(
            s,
            name="Approver required once approved",
            subject_type="field",
            subject_identifier=approver_field["field_identifier"],
            effect="required_when",
            condition={
                "field": status_field["field_identifier"],
                "op": "eq",
                "value": "approved",
            },
            status="confirmed",
        )

        ids["org"] = org_id
        ids["app"] = app_id
        ids["status_field"] = status_field["field_identifier"]
        ids["approver_field"] = approver_field["field_identifier"]
    return ids


def test_entity_prd_field_table_matches_source_and_prose(v2_env, tmp_path):
    _seed()
    client = AccessDesignClient()
    inputs = fetch_prd_inputs(client)
    model = build_prd_model(inputs, rendered_at=RENDERED_AT)

    # One document per confirmed entity (org + app), product-neutral.
    assert len(model.entities) == 2

    app_doc = next(d for d in model.entities if d.name == "Mentor Application")

    # --- Entity overview -----------------------------------------------------
    assert app_doc.overview["name"] == "Mentor Application"
    assert app_doc.overview["kind"] == "person"
    assert app_doc.overview["track_activity"] is True

    # --- Field table matches the seeded source records (REQ-147) -------------
    # The candidate "Draft note" is excluded; the three confirmed fields are
    # present with the neutral type + required flag read from the records.
    by_name = {f["name"]: f for f in app_doc.fields}
    assert set(by_name) == {"Contact email", "Application status", "Approver name"}
    assert by_name["Contact email"]["type"] == "text"
    assert by_name["Contact email"]["required"] == "Yes"
    assert by_name["Application status"]["type"] == "enum"
    assert by_name["Application status"]["options"] == ["submitted", "approved"]
    assert by_name["Approver name"]["required"] == "No"

    rendered = render_prd_markdown(app_doc, model)

    # The overview and a fields table are in the rendered Markdown.
    assert "## Entity Overview" in rendered
    assert "## Fields" in rendered
    assert "| Name | Type | Required |" in rendered
    # The seeded field rows are faithfully present.
    assert "| Contact email | text | Yes |" in rendered
    assert "| Application status | enum | No |" in rendered

    # --- Association in prose -------------------------------------------------
    assert "## Relationships" in rendered
    assert "Sponsor Organization" in rendered
    assert "one-to-many" in rendered

    # --- Rule in prose --------------------------------------------------------
    assert "## Rules" in rendered
    assert (
        "Required when Application status equals approved" in rendered
    )

    # No platform leakage anywhere in the document.
    for token in ("varchar", "Person", "cContact", "lowerCamel"):
        assert token not in rendered


def test_entity_prd_determinism_and_write(v2_env, tmp_path):
    _seed()
    client = AccessDesignClient()

    model1 = build_prd_model(fetch_prd_inputs(client), rendered_at=RENDERED_AT)
    written1 = write_documents(model1, tmp_path / "run1")

    model2 = build_prd_model(fetch_prd_inputs(client), rendered_at=RENDERED_AT)
    written2 = write_documents(model2, tmp_path / "run2")

    assert written1 == written2
    assert "Mentor-Application-PRD.md" in written1
    for name in written1:
        a = (tmp_path / "run1" / name).read_text(encoding="utf-8")
        b = (tmp_path / "run2" / name).read_text(encoding="utf-8")
        assert a == b  # byte-identical across runs


def test_entity_prd_single_entity_restriction(v2_env, tmp_path):
    ids = _seed()
    client = AccessDesignClient()
    model = build_prd_model(
        fetch_prd_inputs(client, entity=ids["app"]),
        rendered_at=RENDERED_AT,
        entity=ids["app"],
    )
    assert [d.identifier for d in model.entities] == [ids["app"]]
