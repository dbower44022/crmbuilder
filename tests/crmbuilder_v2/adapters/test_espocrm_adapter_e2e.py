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
from crmbuilder_v2.access.repositories import (
    association,
    automation,
    dedup_rule,
    engine_override,
    entity,
    field,
    field_permission_rule,
    field_visibility_rule,
    message_template,
    roles,
    rule,
    view,
)
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

    def list_associations(self) -> list[dict]:
        with session_scope() as s:
            return association.list_associations(s)

    def list_rules(self) -> list[dict]:
        with session_scope() as s:
            return rule.list_rules(s)

    def list_views(self) -> list[dict]:
        with session_scope() as s:
            return view.list_views(s)

    def list_automations(self) -> list[dict]:
        with session_scope() as s:
            return automation.list_automations(s)

    def list_dedup_rules(self) -> list[dict]:
        with session_scope() as s:
            return dedup_rule.list_dedup_rules(s)

    def list_message_templates(self) -> list[dict]:
        with session_scope() as s:
            return message_template.list_message_templates(s)

    def list_field_permission_rules(self) -> list[dict]:
        with session_scope() as s:
            return field_permission_rule.list_field_permission_rules(s)

    def list_field_visibility_rules(self) -> list[dict]:
        with session_scope() as s:
            return field_visibility_rule.list_field_visibility_rules(s)

    def list_roles(self) -> list[dict]:
        with session_scope() as s:
            return roles.list_roles(s)


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

    # MANUAL-CONFIG lists the deferred reference field. (Slice 3 emits the
    # composite-construct blocks, so the standing composite-constructs note
    # from slices 1–2 is gone — no views/automations/dedup/templates seeded
    # here means no such block and no deferral.)
    manual = (tmp_path / "MANUAL-CONFIG.md").read_text(encoding="utf-8")
    assert "referring_partner" in manual or "referringPartner" in manual.lower() \
        or "Reference fields" in manual
    assert "Reference fields" in manual
    kinds = {d.kind for d in result.deferrals}
    assert "reference_field" in kinds
    assert "composite_constructs" not in kinds


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


# ---------------------------------------------------------------------------
# Slice 2 — associations → relationships:, rules → requiredWhen/visibleWhen
# ---------------------------------------------------------------------------


def _seed_slice2() -> dict:
    """Two confirmed entities, a one_to_many association between them, a
    field with a confirmed required_when rule (condition referencing a
    sibling field), and a deferred valid_when rule. Returns key identifiers.
    """
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
        )
        app_id = app["entity_identifier"]

        # Sibling enum the rule's condition references.
        status_field = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="application_status",
            description="where the application is",
            type="enum",
            status="confirmed",
            options=[
                {"option_value": "submitted", "option_order": 1},
                {"option_value": "approved", "option_order": 2},
            ],
        )
        # The rule subject: required only when the sibling is "approved".
        approver_field = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="approver_name",
            description="who approved it",
            type="text",
            status="confirmed",
        )

        assoc = association.create_association(
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
        # A valid_when rule has no field-level YAML key → deferred.
        rule.create_rule(
            s,
            name="Approver non-empty invariant",
            subject_type="field",
            subject_identifier=approver_field["field_identifier"],
            effect="valid_when",
            condition={"field": approver_field["field_identifier"], "op": "is_not_empty"},
            status="confirmed",
        )

        ids["org"] = org_id
        ids["app"] = app_id
        ids["assoc"] = assoc["association_identifier"]
    return ids


def test_adapter_emits_relationship_and_conditional_field(v2_env, tmp_path):
    _seed_slice2()
    adapter = EspoCrmAdapter()
    result = adapter.run(
        AccessDesignClient(), tmp_path, rendered_at=RENDERED_AT, engagement="ENG-002"
    )

    # The relationship lives in the SOURCE entity's program file.
    by_file = {p.filename: p.content for p in result.programs}
    assert "Sponsor-Organization.yaml" in by_file
    app_yaml = by_file["Mentor-Application.yaml"]

    # Hard bar: every emitted program passes validate_program() with zero
    # errors, with the new relationships:/requiredWhen blocks present.
    for content in by_file.values():
        assert validate_yaml_text(content) == []
    assert adapter.self_check(result) == {}

    from espo_impl.core.config_loader import ConfigLoader

    loader = ConfigLoader()

    # Relationship: a one_to_many association → oneToMany linkType on the
    # source entity, both link names present.
    src_prog = loader.load_program(tmp_path / "Sponsor-Organization.yaml")
    assert len(src_prog.relationships) == 1
    rel = src_prog.relationships[0]
    assert rel.entity == "Sponsor Organization"
    assert rel.entity_foreign == "Mentor Application"
    assert rel.link_type == "oneToMany"
    assert rel.link and rel.link_foreign
    # The "one" side reaches many → plural; the "many" side reaches one →
    # singular (schema §8.2).
    assert rel.link == "mentorApplications"
    assert rel.link_foreign == "sponsorOrganization"

    # The target program carries no relationships block (links live on the
    # source only).
    assert "relationships:" not in app_yaml

    # Field rule: the approver field carries the compiled requiredWhen, with
    # the EspoCRM operator and the sibling field ref in lowerCamelCase.
    app_prog = loader.load_program(tmp_path / "Mentor-Application.yaml")
    fields = {f.name: f for f in app_prog.entities[0].fields}
    approver = fields["approverName"]
    assert approver.required_when_raw == {
        "field": "applicationStatus",
        "op": "equals",
        "value": "approved",
    }

    # valid_when routed to a deferral; required_when did not.
    manual = (tmp_path / "MANUAL-CONFIG.md").read_text(encoding="utf-8")
    kinds = {d.kind for d in result.deferrals}
    assert "field_rule" in kinds  # the valid_when rule
    assert "association" not in kinds  # the association rendered cleanly
    assert "valid_when" in manual

    # Determinism: a second run is byte-identical for every program.
    result2 = adapter.run(
        AccessDesignClient(), tmp_path / "again", rendered_at=RENDERED_AT,
        engagement="ENG-002",
    )
    by_file2 = {p.filename: p.content for p in result2.programs}
    assert by_file2 == by_file


def test_manytomany_association_has_relation_name(v2_env, tmp_path):
    with session_scope() as s:
        a = entity.create_entity(
            s, name="Tag", description="a tag", kind="other", status="confirmed"
        )
        b = entity.create_entity(
            s, name="Mentor", description="a mentor", kind="person", status="confirmed"
        )
        association.create_association(
            s,
            name="Mentors are tagged",
            source_entity=a["entity_identifier"],
            target_entity=b["entity_identifier"],
            cardinality="many_to_many",
            status="confirmed",
        )
    adapter = EspoCrmAdapter()
    result = adapter.run(
        AccessDesignClient(), tmp_path, rendered_at=RENDERED_AT, engagement="ENG-003"
    )
    for p in result.programs:
        assert validate_yaml_text(p.content) == []

    from espo_impl.core.config_loader import ConfigLoader

    loader = ConfigLoader()
    prog = loader.load_program(tmp_path / "Tag.yaml")
    rel = prog.relationships[0]
    assert rel.link_type == "manyToMany"
    assert rel.relation_name  # required for manyToMany
    assert rel.link == "mentors" and rel.link_foreign == "tags"


# ---------------------------------------------------------------------------
# Slice 3 — composite construct blocks (savedViews / workflows /
# duplicateChecks / emailTemplates) + the bodyFile companion
# ---------------------------------------------------------------------------


def _seed_slice3() -> None:
    with session_scope() as s:
        app = entity.create_entity(
            s,
            name="Mentor Application",
            description="An application submitted by a prospective mentor",
            kind="person",
            status="confirmed",
        )
        app_id = app["entity_identifier"]

        status_field = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="application_status",
            description="where the application is",
            type="enum",
            status="confirmed",
            options=[
                {"option_value": "submitted", "option_order": 1},
                {"option_value": "approved", "option_order": 2},
            ],
        )
        status_fid = status_field["field_identifier"]
        approver_field = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="approver_name",
            description="who approved it",
            type="text",
            status="confirmed",
        )
        approver_fid = approver_field["field_identifier"]
        email_field = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="contact_email",
            description="primary email",
            type="text",
            status="confirmed",
            format="email",
        )
        email_fid = email_field["field_identifier"]

        # A confirmed view: columns + filter + sort, all on emitted fields.
        view.create_view(
            s,
            name="Approved applications",
            entity=app_id,
            columns=[approver_fid, status_fid],
            filter={"field": status_fid, "op": "eq", "value": "approved"},
            sort_field=status_fid,
            sort_direction="desc",
            status="confirmed",
        )

        # A confirmed dedup rule: match on email, normalized lowercase, block.
        dedup_rule.create_dedup_rule(
            s,
            name="No duplicate email",
            entity=app_id,
            match_fields=[email_fid],
            normalize={email_fid: "lowercase"},
            on_match="block",
            message="A Mentor Application with this email already exists.",
            status="confirmed",
        )

        # A confirmed automation: on_update + condition + a set_field action.
        automation.create_automation(
            s,
            name="Stamp approver on approval",
            entity=app_id,
            trigger="on_update",
            condition={"field": status_fid, "op": "eq", "value": "approved"},
            actions=[
                {"type": "set_field", "field": approver_fid, "value": "system"}
            ],
            status="confirmed",
        )
        # A scheduled automation → no v1.1 event → deferred.
        automation.create_automation(
            s,
            name="Nightly sweep",
            entity=app_id,
            trigger="scheduled",
            actions=[{"type": "set_field", "field": approver_fid, "value": "x"}],
            status="confirmed",
        )

        # A confirmed email message template → emailTemplates + bodyFile.
        message_template.create_message_template(
            s,
            name="Application received",
            entity=app_id,
            channel="email",
            subject="Thanks for applying",
            body="We received your application and will be in touch.",
            merge_fields=[email_fid],
            status="confirmed",
        )
        # A non-email template → deferred (only email maps to emailTemplates).
        message_template.create_message_template(
            s,
            name="SMS nudge",
            entity=app_id,
            channel="sms",
            body="Reminder: finish your application.",
            status="confirmed",
        )


def test_adapter_emits_composite_construct_blocks(v2_env, tmp_path):
    _seed_slice3()
    adapter = EspoCrmAdapter()
    result = adapter.run(
        AccessDesignClient(), tmp_path, rendered_at=RENDERED_AT, engagement="ENG-004"
    )

    # Hard bar: every emitted program passes validate_program() with zero
    # errors — WITH the four new blocks present and the body file written.
    assert adapter.self_check(result) == {}

    program = result.programs[0]
    written = (tmp_path / program.filename).read_text(encoding="utf-8")
    # The savedViews/duplicateChecks/workflows/emailTemplates blocks are all
    # present in the deployable YAML.
    assert "savedViews:" in written
    assert "duplicateChecks:" in written
    assert "workflows:" in written
    assert "emailTemplates:" in written

    # Re-validate the WRITTEN file (companion bodyFile present on disk).
    from espo_impl.core.config_loader import ConfigLoader

    loader = ConfigLoader()
    prog = loader.load_program(tmp_path / program.filename)
    ent = prog.entities[0]
    assert loader.validate_program(prog) == []
    assert len(ent.saved_views) == 1
    assert len(ent.duplicate_checks) == 1
    assert len(ent.workflows) == 1
    assert len(ent.email_templates) == 1

    # savedView: filter compiled, columns + sort resolved to internal names.
    sv = ent.saved_views[0]
    assert sv.columns == ["approverName", "applicationStatus"]
    assert sv.filter is not None

    # duplicateCheck: block + normalized email.
    dc = ent.duplicate_checks[0]
    assert dc.fields == ["contactEmail"]
    assert dc.onMatch == "block"
    assert dc.normalize == {"contactEmail": "lowercase-trim"}

    # workflow: onUpdate + a setField action.
    wf = ent.workflows[0]
    assert wf.trigger.event == "onUpdate"
    assert wf.actions[0].type == "setField"
    assert wf.actions[0].field == "approverName"

    # emailTemplate: bodyFile companion written to disk and uses the merge field.
    et = ent.email_templates[0]
    assert et.body_file == "templates/msg-001.html"
    body_path = tmp_path / "templates" / "msg-001.html"
    assert body_path.exists()
    body = body_path.read_text(encoding="utf-8")
    assert "{{contactEmail}}" in body
    assert et.merge_fields == ["contactEmail"]

    # MANUAL-CONFIG documents the deploy-NOT_SUPPORTED treatment of
    # savedViews / duplicateChecks / workflows.
    manual = (tmp_path / "MANUAL-CONFIG.md").read_text(encoding="utf-8")
    assert "NOT_SUPPORTED" in manual
    assert "savedViews" in manual
    assert "duplicateChecks" in manual
    assert "workflows" in manual

    # Deferrals: the scheduled automation and the SMS (non-email) template.
    kinds = {d.kind for d in result.deferrals}
    assert "automation" in kinds  # the scheduled one
    assert "message_template" in kinds  # the SMS one

    # Determinism: a second run is byte-identical for programs AND companions.
    result2 = adapter.run(
        AccessDesignClient(), tmp_path / "again", rendered_at=RENDERED_AT,
        engagement="ENG-004",
    )
    assert result2.programs[0].content == program.content
    assert {c.filename: c.content for c in result2.companions} == {
        c.filename: c.content for c in result.companions
    }


# ---------------------------------------------------------------------------
# PI-197 — derived/formula fields render as readOnly formula fields
# ---------------------------------------------------------------------------


def _seed_derived() -> None:
    """One entity with concat + arithmetic derived fields and their operand
    fields, plus a second entity + association for an aggregate derived field
    that sums a related field."""
    with session_scope() as s:
        person = entity.create_entity(
            s,
            name="Mentor",
            description="A mentor",
            kind="person",
            status="confirmed",
        )
        pid = person["entity_identifier"]
        ses = entity.create_entity(
            s,
            name="Session",
            description="A mentoring session",
            kind="event",
            status="confirmed",
        )
        sid = ses["entity_identifier"]

        field.create_field(
            s, field_belongs_to_entity_identifier=pid, name="first_name",
            description="given name", type="text", status="confirmed",
        )
        field.create_field(
            s, field_belongs_to_entity_identifier=pid, name="last_name",
            description="family name", type="text", status="confirmed",
        )
        field.create_field(
            s, field_belongs_to_entity_identifier=pid, name="capacity",
            description="max clients", type="number", status="confirmed",
        )
        field.create_field(
            s, field_belongs_to_entity_identifier=pid, name="active_clients",
            description="current clients", type="number", status="confirmed",
        )
        # The aggregated field lives on the related (Session) entity.
        field.create_field(
            s, field_belongs_to_entity_identifier=sid, name="hours",
            description="session hours", type="number", status="confirmed",
        )

        # concat derived field.
        field.create_field(
            s, field_belongs_to_entity_identifier=pid, name="display_name",
            description="full name", type="derived", status="confirmed",
            derived_result_type="text",
            formula={
                "kind": "concat",
                "parts": [
                    {"field": "first_name"},
                    {"literal": " "},
                    {"field": "last_name"},
                ],
            },
        )
        # arithmetic derived field.
        field.create_field(
            s, field_belongs_to_entity_identifier=pid, name="available_capacity",
            description="spare slots", type="derived", status="confirmed",
            derived_result_type="number",
            formula={
                "kind": "arithmetic",
                "expression": {
                    "op": "-",
                    "left": {"field": "capacity"},
                    "right": {"field": "active_clients"},
                },
            },
        )

        assoc = association.create_association(
            s,
            name="Mentor runs Sessions",
            source_entity=pid,
            target_entity=sid,
            cardinality="one_to_many",
            status="confirmed",
        )
        # aggregate derived field — sum Session.hours via the association.
        field.create_field(
            s, field_belongs_to_entity_identifier=pid, name="total_hours",
            description="total mentoring hours", type="derived",
            status="confirmed",
            derived_result_type="number",
            formula={
                "kind": "aggregate",
                "function": "sum",
                "association": assoc["association_identifier"],
                "field": "hours",
            },
        )


def test_adapter_renders_derived_formula_fields_valid(v2_env, tmp_path):
    _seed_derived()
    adapter = EspoCrmAdapter()
    result = adapter.run(
        AccessDesignClient(), tmp_path, rendered_at=RENDERED_AT,
        engagement="ENG-005",
    )

    # Hard bar (REQ-143): every emitted program passes validate_program()
    # with zero errors — WITH the three formula fields present.
    by_file = {p.filename: p.content for p in result.programs}
    for content in by_file.values():
        assert validate_yaml_text(content) == []
    assert adapter.self_check(result) == {}

    from espo_impl.core.config_loader import ConfigLoader

    loader = ConfigLoader()
    prog = loader.load_program(tmp_path / "Mentor.yaml")
    assert loader.validate_program(prog) == []
    fields = {f.name: f for f in prog.entities[0].fields}

    # concat
    display = fields["displayName"]
    assert display.readOnly is True
    assert display.formula.type == "concat"

    # arithmetic
    avail = fields["availableCapacity"]
    assert avail.readOnly is True
    assert avail.formula.type == "arithmetic"
    assert avail.formula.arithmetic.expression == "capacity - activeClients"

    # aggregate
    total = fields["totalHours"]
    assert total.readOnly is True
    assert total.formula.type == "aggregate"
    assert total.formula.aggregate.function == "sum"
    assert total.formula.aggregate.related_entity == "Session"
    assert total.formula.aggregate.field == "hours"

    # No derived field was deferred.
    assert not any(d.kind == "derived_field" for d in result.deferrals)


def test_adapter_uses_engine_override_formula(v2_env, tmp_path):
    with session_scope() as s:
        ent = entity.create_entity(
            s, name="Mentor", description="A mentor", kind="person",
            status="confirmed",
        )
        eid = ent["entity_identifier"]
        f = field.create_field(
            s, field_belongs_to_entity_identifier=eid, name="hand_tuned",
            description="hand-tuned computed", type="derived",
            status="confirmed", derived_result_type="text",
        )
        # No neutral formula — only an engine_override carrying the EspoCRM
        # formula block (the §9 hand-tuned residue, in the engine's own shape).
        engine_override.create_engine_override(
            s, target_engine="espocrm", subject_type="field",
            subject_identifier=f["field_identifier"], attribute="formula",
            value={"type": "concat", "parts": [{"literal": "fixed"}]},
        )
    adapter = EspoCrmAdapter()
    result = adapter.run(
        AccessDesignClient(), tmp_path, rendered_at=RENDERED_AT,
        engagement="ENG-006",
    )
    for p in result.programs:
        assert validate_yaml_text(p.content) == []

    from espo_impl.core.config_loader import ConfigLoader

    loader = ConfigLoader()
    prog = loader.load_program(tmp_path / "Mentor.yaml")
    fields = {f.name: f for f in prog.entities[0].fields}
    assert fields["handTuned"].formula.type == "concat"
    assert not any(d.kind == "derived_field" for d in result.deferrals)


# ---------------------------------------------------------------------------
# PI-051 — security rules → fieldPermissions: / fieldVisibility: (REQ-128/129)
# ---------------------------------------------------------------------------


def _seed_security() -> None:
    """One confirmed entity + field, a role, a confirmed field_permission_rule
    and a confirmed field_visibility_rule on that field, plus a candidate
    permission rule (excluded) and a permission rule on a candidate field
    (deferred — not emitted)."""
    with session_scope() as s:
        app = entity.create_entity(
            s,
            name="Mentor Application",
            description="An application submitted by a prospective mentor",
            kind="person",
            status="confirmed",
        )
        app_id = app["entity_identifier"]

        ssn_field = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="ssn",
            description="sensitive id",
            type="text",
            status="confirmed",
        )
        ssn_fid = ssn_field["field_identifier"]
        # A candidate field — never emitted; a rule targeting it must defer.
        draft = field.create_field(
            s,
            field_belongs_to_entity_identifier=app_id,
            name="draft_only",
            description="scratch",
            type="text",
            status="candidate",
        )
        draft_fid = draft["field_identifier"]

        role = roles.create_role(s, name="Mentor Coordinator", status="confirmed")
        rol_id = role["role_identifier"]

        # Confirmed permission rule: read_only on the ssn field.
        field_permission_rule.create_field_permission_rule(
            s,
            name="Coordinator read-only SSN",
            role=rol_id,
            target_field=ssn_fid,
            permission_level="read_only",
            status="confirmed",
        )
        # Confirmed visibility rule: hide ssn from the role.
        field_visibility_rule.create_field_visibility_rule(
            s,
            name="Coordinator cannot see SSN",
            role=rol_id,
            target_field=ssn_fid,
            visible=False,
            status="confirmed",
        )
        # A confirmed permission rule on a candidate (non-emitted) field →
        # deferred.
        field_permission_rule.create_field_permission_rule(
            s,
            name="Coordinator on draft field",
            role=rol_id,
            target_field=draft_fid,
            permission_level="read_write",
            status="confirmed",
        )


def test_adapter_emits_security_rule_blocks(v2_env, tmp_path):
    _seed_security()
    adapter = EspoCrmAdapter()
    result = adapter.run(
        AccessDesignClient(), tmp_path, rendered_at=RENDERED_AT,
        engagement="ENG-008",
    )

    # Hard bar: the emitted YAML (with the new blocks) passes validate_program.
    program = result.programs[0]
    written = (tmp_path / program.filename).read_text(encoding="utf-8")
    assert validate_yaml_text(written) == []
    assert adapter.self_check(result) == {}
    assert "fieldPermissions:" in written
    assert "fieldVisibility:" in written

    from espo_impl.core.config_loader import ConfigLoader

    loader = ConfigLoader()
    prog = loader.load_program(tmp_path / program.filename)
    assert loader.validate_program(prog) == []

    # One confirmed permission cell — role NAME (not the ROL- id), the entity
    # key the program uses, the emitted internal field name, the level.
    assert len(prog.field_permissions) == 1
    fp = prog.field_permissions[0]
    assert fp.role == "Mentor Coordinator"
    assert fp.entity == "Mentor Application"
    assert fp.field == "ssn"
    assert fp.level == "read_only"

    # One confirmed visibility cell.
    assert len(prog.field_visibility) == 1
    fv = prog.field_visibility[0]
    assert fv.role == "Mentor Coordinator"
    assert fv.entity == "Mentor Application"
    assert fv.field == "ssn"
    assert fv.visible is False

    # The rule on the non-emitted (candidate) field deferred.
    kinds = {d.kind for d in result.deferrals}
    assert "field_permission" in kinds  # the draft-field rule
    manual = (tmp_path / "MANUAL-CONFIG.md").read_text(encoding="utf-8")
    assert "fieldPermissions" in manual

    # Determinism: a second run is byte-identical.
    result2 = adapter.run(
        AccessDesignClient(), tmp_path / "again", rendered_at=RENDERED_AT,
        engagement="ENG-008",
    )
    assert result2.programs[0].content == program.content


def test_adapter_defers_derived_field_without_formula(v2_env, tmp_path):
    with session_scope() as s:
        ent = entity.create_entity(
            s, name="Mentor", description="A mentor", kind="person",
            status="confirmed",
        )
        # A derived field with a result type but NO formula and NO override.
        field.create_field(
            s, field_belongs_to_entity_identifier=ent["entity_identifier"],
            name="orphan_calc", description="no formula", type="derived",
            status="confirmed", derived_result_type="text",
        )
    adapter = EspoCrmAdapter()
    result = adapter.run(
        AccessDesignClient(), tmp_path, rendered_at=RENDERED_AT,
        engagement="ENG-007",
    )
    # Still valid YAML; the orphan derived field routes to MANUAL-CONFIG.
    for p in result.programs:
        assert validate_yaml_text(p.content) == []
    written = (tmp_path / "Mentor.yaml").read_text(encoding="utf-8")
    assert "orphanCalc" not in written
    manual = (tmp_path / "MANUAL-CONFIG.md").read_text(encoding="utf-8")
    assert "Derived / formula fields" in manual
    assert any(d.kind == "derived_field" for d in result.deferrals)
