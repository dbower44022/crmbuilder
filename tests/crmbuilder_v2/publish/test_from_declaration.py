"""Tests for turning a checked declaration into an apply plan
(PI-532 / REQ-618).
"""

from __future__ import annotations

from crmbuilder_v2.publish import entities as ent
from crmbuilder_v2.publish.declaration import parse
from crmbuilder_v2.publish.from_declaration import field_payload, plan_for

_ENTITY = """
version: "1.0.0"
entities:
  Engagement:
    action: create
    type: Base
    description: A mentoring engagement
    settings:
      labelSingular: Engagement
      labelPlural: Engagements
      stream: true
      orderBy: createdAt
      autoPlaceName: false
    fields:
      - name: stage
        type: enum
        label: Stage
        options: ["Active", "Closed"]
        description: where it has got to
        optionsDeferred: false
        visibleWhen:
          all: [{field: stage, op: equals, value: Active}]
    layout:
      detail:
        panels:
          - label: Overview
            rows: [[{name: stage}]]
    emailTemplates:
      - name: welcome
        subject: Welcome
        body: Hello
    filteredTabs:
      - label: Mine
        where: [{type: equals, attribute: stage, value: Active}]
relationships:
  - entity: Engagement
    entityForeign: Account
    link: account
    linkForeign: engagements
    linkType: manyToOne
"""

_SECURITY = """
version: "1.0.0"
entities: {}
roles:
  - name: Mentor
    scope_access:
      Account: {read: all, create: true}
    system_permissions:
      export: "no"
teams:
  - name: Mentors
    description: The cohort
fieldPermissions:
  - role: Mentor
    entity: Account
    field: revenue
    level: read
"""


def _plan(*texts: str):
    return plan_for(
        [parse(text, f"{i}.yaml") for i, text in enumerate(texts)]
    )


# --- what must never reach the platform -------------------------------------


def test_a_field_s_description_is_never_sent() -> None:
    """Sending it makes a field an administrator cannot edit afterwards."""
    payload = field_payload({"name": "stage", "type": "enum", "description": "x"})
    assert "description" not in payload


def test_the_marks_that_describe_the_design_are_never_sent() -> None:
    payload = field_payload(
        {
            "name": "stage",
            "type": "enum",
            "optionsDeferred": True,
            "externallyPopulated": True,
        }
    )
    assert set(payload) == {"name", "type"}


def test_a_rule_is_renamed_not_rewritten() -> None:
    rule = {"all": [{"field": "stage", "op": "equals", "value": "Active"}]}
    payload = field_payload({"name": "s", "type": "varchar", "visibleWhen": rule})
    assert payload["dynamicLogicVisible"] == rule
    assert "visibleWhen" not in payload


def test_everything_else_passes_through_untouched() -> None:
    payload = field_payload(
        {"name": "s", "type": "varchar", "required": True, "maxLength": 50}
    )
    assert payload == {
        "name": "s",
        "type": "varchar",
        "required": True,
        "maxLength": 50,
    }


# --- the object type --------------------------------------------------------


def test_the_object_type_carries_its_labels_and_stream() -> None:
    plan = _plan(_ENTITY)
    [entity] = plan.entities
    assert entity.entity is not None
    assert entity.entity.action == ent.CREATE
    assert entity.entity.label_plural == "Engagements"
    assert entity.entity.stream is True


def test_a_declaration_that_only_adds_to_an_object_type_asks_for_no_creation() -> None:
    plan = _plan(
        """
entities:
  Account:
    fields:
      - name: region
        type: varchar
"""
    )
    assert plan.entities[0].entity is None


def test_only_the_settings_this_system_applies_are_carried() -> None:
    """The layout emitter's own switch is not a setting to write."""
    plan = _plan(_ENTITY)
    values = plan.entities[0].settings.values
    assert "orderBy" in values
    assert "autoPlaceName" not in values


# --- the rest of an object type ---------------------------------------------


def test_fields_arrive_as_payloads() -> None:
    plan = _plan(_ENTITY)
    [field] = plan.entities[0].fields
    assert field.name == "stage"
    assert field.payload["options"] == ["Active", "Closed"]
    assert "description" not in field.payload


def test_layouts_arrive_by_kind_in_the_platform_s_shape() -> None:
    plan = _plan(_ENTITY)
    [layout] = plan.entities[0].layouts
    assert layout.layout_type == "detail"
    # The platform keeps a panel's title under its own key, and expects every
    # other property to be present rather than assumed.
    assert layout.body[0]["customLabel"] == "Overview"
    assert layout.body[0]["style"] == "default"
    assert "label" not in layout.body[0]


def test_templates_and_tabs_are_named_the_platform_s_way() -> None:
    plan = _plan(_ENTITY)
    [template] = plan.entities[0].templates
    assert template.entity == "CEngagement"
    [tab] = plan.tabs
    assert tab.entity == "CEngagement"
    assert tab.label == "Mine"


def test_a_link_carries_both_of_its_ends() -> None:
    plan = _plan(_ENTITY)
    [link] = plan.links
    assert (link.entity, link.entity_foreign) == ("Engagement", "Account")
    assert link.link_foreign == "engagements"


def test_a_link_missing_an_end_is_not_carried() -> None:
    plan = _plan(
        """
entities:
  Engagement: {}
relationships:
  - entity: Engagement
    link: account
"""
    )
    assert plan.links == []


# --- access, which is declared across files ---------------------------------


def test_roles_and_teams_are_carried() -> None:
    plan = _plan(_SECURITY)
    [role] = plan.roles
    [team] = plan.teams
    assert role.name == "Mentor"
    assert role.scope_access["Account"]["read"] == "all"
    assert role.system_permissions["export"] == "no"
    assert team.description == "The cohort"


def test_field_permissions_are_gathered_onto_their_role() -> None:
    """They are declared one per field, and a role needs them together."""
    plan = _plan(_SECURITY)
    [role] = plan.roles
    assert [(p.entity, p.field, p.level) for p in role.field_permissions] == [
        ("Account", "revenue", "read")
    ]


def test_a_permission_for_a_role_declared_in_another_file_still_lands() -> None:
    permissions = """
entities: {}
roles:
  - name: Mentor
    scope_access: {}
"""
    elsewhere = """
entities: {}
fieldPermissions:
  - role: Mentor
    entity: Account
    field: revenue
    level: "no"
"""
    plan = plan_for([parse(permissions, "a.yaml"), parse(elsewhere, "b.yaml")])
    assert plan.roles[0].field_permissions


def test_several_declarations_make_one_plan() -> None:
    plan = _plan(_ENTITY, _SECURITY)
    assert [e.name for e in plan.entities] == ["Engagement"]
    assert plan.roles and plan.teams and plan.links and plan.tabs


# --- layouts: the wrapper and the platform's prefix --------------------------


def test_a_record_view_is_unwrapped_to_the_list_the_platform_wants() -> None:
    from crmbuilder_v2.publish.from_declaration import layout_body

    body = layout_body({"panels": [{"label": "Overview", "rows": []}]})
    assert body == [{"label": "Overview", "rows": []}]


def test_a_list_view_names_each_column_s_field_the_platform_s_way() -> None:
    """The declaration says which field a column shows; the platform calls
    that the column's name. A column that loses it has no heading and
    nothing in it."""
    from crmbuilder_v2.publish.from_declaration import layout_body

    body = layout_body(
        {"columns": [{"field": "stage", "width": 30}]}, layout_type="list"
    )
    assert body == [{"name": "stage", "width": 30}]


def test_a_filter_list_is_a_list_of_names() -> None:
    from crmbuilder_v2.publish.from_declaration import layout_body

    assert layout_body(["stage"], layout_type="filters") == ["stage"]


def test_a_bare_list_and_a_panel_map_are_left_as_they_are() -> None:
    from crmbuilder_v2.publish.from_declaration import layout_body

    assert layout_body(["stage", "name"]) == ["stage", "name"]
    assert layout_body({"cDues": {"index": 1}}) == {"cDues": {"index": 1}}


def test_a_field_this_design_adds_to_a_platform_object_type_is_prefixed() -> None:
    """An unprefixed cell on a native object type shows nothing at all."""
    plan = _plan(
        """
entities:
  Contact:
    fields:
      - name: mentorStatus
        type: varchar
    layout:
      detail:
        panels:
          - rows: [[{name: mentorStatus}, {name: lastName}]]
"""
    )
    [layout] = plan.entities[0].layouts
    # The name field is placed first, so the declared row is the one after it.
    cells = layout.body[0]["rows"][-1]
    assert cells[0]["name"] == "cMentorStatus"
    # A field the platform ships keeps its own name.
    assert cells[1]["name"] == "lastName"


def test_a_field_on_a_custom_object_type_is_not_prefixed() -> None:
    plan = _plan(
        """
entities:
  Engagement:
    fields:
      - name: stage
        type: varchar
    layout:
      detail:
        panels:
          - rows: [[{name: stage}]]
"""
    )
    [layout] = plan.entities[0].layouts
    assert layout.body[0]["rows"][-1][0]["name"] == "stage"


def test_a_cell_written_as_a_bare_name_is_prefixed_too() -> None:
    from crmbuilder_v2.publish.from_declaration import layout_body

    body = layout_body(
        ["mentorStatus", "lastName"],
        layout_type="filters",
        entity_is_native=True,
        declared_fields=frozenset({"mentorStatus"}),
    )
    assert body == ["cMentorStatus", "lastName"]


# --- the field the platform insists on ---------------------------------------


def test_a_record_view_gets_the_name_field_when_the_design_left_it_out() -> None:
    """Without it the create form has nowhere to type the one value the
    platform requires, and nothing can be saved."""
    plan = _plan(
        """
entities:
  Engagement:
    fields:
      - name: stage
        type: varchar
    layout:
      detail:
        panels:
          - label: Overview
            rows: [[{name: stage}]]
"""
    )
    [layout] = plan.entities[0].layouts
    assert layout.body[0]["rows"][0] == [{"name": "name"}]


def test_a_design_that_places_the_name_field_itself_is_left_alone() -> None:
    plan = _plan(
        """
entities:
  Engagement:
    layout:
      detail:
        panels:
          - rows: [[{name: name}, {name: stage}]]
"""
    )
    [layout] = plan.entities[0].layouts
    assert len(layout.body[0]["rows"]) == 1


def test_a_design_can_say_it_left_the_name_field_out_on_purpose() -> None:
    plan = _plan(
        """
entities:
  Engagement:
    settings:
      autoPlaceName: false
    layout:
      detail:
        panels:
          - rows: [[{name: stage}]]
"""
    )
    [layout] = plan.entities[0].layouts
    assert layout.body[0]["rows"] == [[{"name": "stage"}]]


def test_the_name_field_never_lands_on_a_panel_that_may_be_hidden() -> None:
    """A conditional panel is just as absent as no panel when the condition
    is false."""
    from crmbuilder_v2.publish.from_declaration import place_name_field

    body = place_name_field(
        [
            {"label": "Only sometimes", "dynamicLogicVisible": {"all": []}, "rows": []},
            {"label": "Always", "rows": []},
        ]
    )
    assert body[0]["rows"] == []
    assert body[1]["rows"] == [[{"name": "name"}]]


def test_a_list_view_is_not_given_a_name_field() -> None:
    plan = _plan(
        """
entities:
  Engagement:
    layout:
      list:
        columns: [{name: stage}]
"""
    )
    [layout] = plan.entities[0].layouts
    assert layout.body == [{"name": "stage"}]


# --- a template's body, which lives in its own file --------------------------


def test_a_template_body_is_read_from_the_file_beside_the_declaration() -> None:
    """Published without it, the template is an empty message — and the
    instance accepts that quite happily."""
    from crmbuilder_v2.publish.from_declaration import plan_for as build

    declaration = parse(
        """
entities:
  Engagement:
    emailTemplates:
      - name: welcome
        subject: Welcome
        bodyFile: templates/welcome.html
""",
        "e.yaml",
    )
    plan = build(
        [declaration], companions={"templates/welcome.html": "<p>Hello</p>"}
    )
    [template] = plan.entities[0].templates
    assert template.body == "<p>Hello</p>"


def test_a_body_written_inline_still_wins() -> None:
    from crmbuilder_v2.publish.from_declaration import plan_for as build

    declaration = parse(
        """
entities:
  Engagement:
    emailTemplates:
      - name: welcome
        body: inline
        bodyFile: templates/welcome.html
""",
        "e.yaml",
    )
    plan = build([declaration], companions={"templates/welcome.html": "file"})
    assert plan.entities[0].templates[0].body == "inline"


def test_a_missing_companion_does_not_break_the_publish() -> None:
    from crmbuilder_v2.publish.from_declaration import plan_for as build

    declaration = parse(
        """
entities:
  Engagement:
    emailTemplates:
      - name: welcome
        bodyFile: gone.html
""",
        "e.yaml",
    )
    assert build([declaration]).entities[0].templates[0].body == ""
