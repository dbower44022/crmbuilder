"""End-to-end test — EspoCRM adapter against the access layer (PI-191).

Seeds a representative engagement (entity + fields covering varchar /
enum-with-options / number / bool / date, an engine override, and a
deferred reference field) through the repositories, runs the adapter via
an access-layer-backed :class:`DesignClient`, and asserts:

* every emitted YAML **passes ``validate_program()``** with zero errors
  (the hard acceptance bar — REQ-143);
* generation is byte-stable across two runs (determinism);
* the ``MANUAL-CONFIG.md`` companion lists the deferred items.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import engine_override, entity, field
from crmbuilder_v2.adapters.espocrm.adapter import EspoCrmAdapter, validate_yaml_text
from crmbuilder_v2.adapters.espocrm.client import DesignClient

RENDERED_AT = "2026-06-14T12:00:00+00:00"


class AccessDesignClient(DesignClient):
    """A GET-only design client reading straight from the access layer
    (the test analog of ``RestDesignClient``)."""

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
        with session_scope() as s:
            return engine_override.list_engine_overrides(s)


def _seed() -> None:
    with session_scope() as s:
        ent = entity.create_entity(
            s,
            name="Mentor Application",
            description="An application submitted by a prospective mentor",
            kind="person",
            status="confirmed",
            track_activity=True,
        )
        eid = ent["entity_identifier"]

        # varchar with an email format refinement + maxLength
        f_email = field.create_field(
            s,
            field_belongs_to_entity_identifier=eid,
            name="contact_email",
            description="primary email",
            type="text",
            status="confirmed",
            format="email",
            max_length=120,
            required=True,
        )
        # enum with ordered options
        field.create_field(
            s,
            field_belongs_to_entity_identifier=eid,
            name="application_status",
            description="where the application is",
            type="enum",
            status="confirmed",
            options=[
                {"option_value": "submitted", "option_order": 1},
                {"option_value": "approved", "option_order": 2},
            ],
        )
        # number (decimal scale → float) with bounds
        field.create_field(
            s,
            field_belongs_to_entity_identifier=eid,
            name="years_experience",
            description="years of experience",
            type="number",
            status="confirmed",
            numeric_scale="decimal",
            min="0",
            max="60",
        )
        # boolean with default + read-only
        field.create_field(
            s,
            field_belongs_to_entity_identifier=eid,
            name="background_check",
            description="passed background check",
            type="boolean",
            status="confirmed",
            default_value="false",
            read_only=True,
        )
        # date
        field.create_field(
            s,
            field_belongs_to_entity_identifier=eid,
            name="submitted_on",
            description="date submitted",
            type="date",
            status="confirmed",
        )
        # reference → deferred (slice 2 association)
        field.create_field(
            s,
            field_belongs_to_entity_identifier=eid,
            name="referring_partner",
            description="who referred the applicant",
            type="reference",
            status="confirmed",
        )
        # a candidate field — excluded by the scope filter
        field.create_field(
            s,
            field_belongs_to_entity_identifier=eid,
            name="draft_note",
            description="scratch",
            type="text",
            status="candidate",
        )

        # engine override: pin the email field's internal name
        engine_override.create_engine_override(
            s,
            target_engine="espocrm",
            subject_type="field",
            subject_identifier=f_email["field_identifier"],
            attribute="internal_name",
            value="emailAddress",
        )


def test_adapter_generates_valid_byte_stable_yaml(v2_env, tmp_path):
    _seed()
    client = AccessDesignClient()
    adapter = EspoCrmAdapter()

    result = adapter.run(
        client, tmp_path, rendered_at=RENDERED_AT, engagement="ENG-001"
    )

    # Exactly one program (the one confirmed entity).
    assert len(result.programs) == 1
    program = result.programs[0]
    assert program.filename == "Mentor-Application.yaml"

    # Hard bar: the written YAML passes validate_program() with zero errors.
    written = (tmp_path / program.filename).read_text(encoding="utf-8")
    assert validate_yaml_text(written) == []
    # The adapter's own self-check agrees (no failing files).
    assert adapter.self_check(result) == {}

    # The confirmed, mappable fields are present; the candidate + reference
    # fields are not.
    assert "contact_email" not in written  # business name never used directly
    assert "emailAddress" in written  # override-pinned internal name
    assert "applicationStatus" in written
    assert "draft_note" not in written
    assert "referringPartner" not in written

    # Determinism: a second generation is byte-identical.
    result2 = adapter.generate(
        client.list_entities(),
        client.list_fields(),
        client.list_engine_overrides(),
        rendered_at=RENDERED_AT,
        engagement="ENG-001",
    )
    assert result2.programs[0].content == program.content
    assert result2.manual_config.content == result.manual_config.content

    # MANUAL-CONFIG lists the deferred reference field + the standing
    # composite-constructs note.
    manual = (tmp_path / "MANUAL-CONFIG.md").read_text(encoding="utf-8")
    assert "referring_partner" in manual or "referringPartner" in manual.lower() \
        or "Reference fields" in manual
    assert "Reference fields" in manual
    assert "Composite constructs" in manual
    kinds = {d.kind for d in result.deferrals}
    assert "reference_field" in kinds
    assert "composite_constructs" in kinds


def test_adapter_yaml_has_expected_field_types(v2_env, tmp_path):
    _seed()
    adapter = EspoCrmAdapter()
    result = adapter.run(
        AccessDesignClient(), tmp_path, rendered_at=RENDERED_AT, engagement="ENG-001"
    )
    from espo_impl.core.config_loader import ConfigLoader

    loader = ConfigLoader()
    prog = loader.load_program(tmp_path / result.programs[0].filename)
    ent = prog.entities[0]
    by_name = {f.name: f for f in ent.fields}
    assert by_name["emailAddress"].type == "email"
    assert by_name["applicationStatus"].type == "enum"
    assert by_name["applicationStatus"].options == ["submitted", "approved"]
    assert by_name["yearsExperience"].type == "float"
    assert by_name["backgroundCheck"].type == "bool"
    assert by_name["submittedOn"].type == "date"
    assert ent.type == "Person"
    assert ent.settings.stream is True
