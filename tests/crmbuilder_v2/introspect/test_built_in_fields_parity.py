"""PI-425 (REQ-523) — built-in fields of built-in entities are audited.

A built-in entity's platform-shipped fields are inventoried once the entity is
in the design; system bookkeeping fields stay excluded; a change to a built-in
field's requiredness on one instance is drift for that instance; and publish
never creates a built-in field (it is compare/capture only) while rules that
reference one still compile.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.reconcile_compare import _attribute_capabilities
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.introspect.reconcile import reconcile_fields

from tests.crmbuilder_v2.access.test_instance_membership import (
    _FakeClient,
    _make_instance,
    _native,
)

_CONTACT_FIELDS = {
    "id": {"type": "id"},  # system — never audited
    "firstName": {"type": "varchar", "required": False},
    "cRegion": {"type": "varchar", "isCustom": True},
}


def test_built_in_fields_audited_on_customised_native_entity(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient({"Contact": _native()}, fields={"Contact": _CONTACT_FIELDS})
        summary = reconcile_fields(s, instance_identifier=iid, client=client)
        assert summary["created"] == 2
        by_name = {f["field_name"]: f for f in field_repo.list_fields(s)}
        assert set(by_name) == {"firstName", "region"}
        assert by_name["firstName"]["field_built_in"] is True
        assert by_name["region"]["field_built_in"] is False

        # An administrator makes firstName required on this instance -> drift.
        changed = dict(_CONTACT_FIELDS, firstName={"type": "varchar", "required": True})
        client2 = _FakeClient({"Contact": _native()}, fields={"Contact": changed})
        s2 = reconcile_fields(s, instance_identifier=iid, client=client2)
        assert s2["drifted"] == 1
        row = next(
            m for m in mb.list_memberships(s, instance_identifier=iid, member_type="field")
            if m["member_identifier"] == by_name["firstName"]["field_identifier"]
        )
        assert row["state"] == "drifted" and row["override"] == {"field_required": True}


def test_uncustomised_native_entity_outside_the_design_is_skipped(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"Account": _native()}, fields={"Account": {"website": {"type": "url"}}}
        )
        summary = reconcile_fields(s, instance_identifier=iid, client=client)
        assert summary["created"] == 0 and entity_repo.list_entities(s) == []


def test_native_entity_already_in_the_design_gets_its_built_in_fields(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Account", description="x")
        client = _FakeClient(
            {"Account": _native()}, fields={"Account": {"website": {"type": "url"}}}
        )
        summary = reconcile_fields(s, instance_identifier=iid, client=client)
        assert summary["created"] == 1
        f = field_repo.list_fields(s)[0]
        assert f["field_name"] == "website" and f["field_built_in"] is True


def test_built_in_field_is_capture_only_in_reconcile():
    assert _attribute_capabilities("field", "field_required", {"field_built_in": True}) == (
        True,
        False,
    )
    assert _attribute_capabilities("field", "field_required", {"field_built_in": False}) == (
        True,
        True,
    )


def test_publish_never_creates_a_built_in_field_but_rules_still_resolve():
    from crmbuilder_v2.adapters.espocrm.model import build_program_model

    from tests.crmbuilder_v2.adapters.test_espocrm_model import (
        RENDERED_AT,
        _entity,
        _field,
        _only_entity_block,
        _rule,
    )

    fields = [
        _field("FLD-001", "mentor_status", "text", field_built_in=False),
        _field("FLD-002", "firstName", "text", field_built_in=True),
    ]
    rule = _rule(
        subject="FLD-001",
        condition={"field": "firstName", "op": "is_not_empty"},
    )
    model = build_program_model(
        [_entity()], fields, [], rules=[rule], rendered_at=RENDERED_AT
    )
    block = _only_entity_block(model)
    names = [f["name"] for f in block["fields"]]
    assert names == ["mentorStatus"]
    assert block["fields"][0]["requiredWhen"] == {"field": "firstName", "op": "isNotNull"}
    assert not [d for d in model.deferrals if d.identifier == "FLD-002"]


def test_layout_only_native_entity_becomes_canonical(v2_env):
    """PI-429: a built-in entity whose only customisation is a stored layout is
    inventoried (with its built-in fields), while one with neither custom field
    nor stored layout still is not."""
    from crmbuilder_v2.access.repositories import layouts as layout_repo
    from crmbuilder_v2.introspect.reconcile import reconcile_entities, reconcile_layouts
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"Lead": _native(), "Task": _native()},
            fields={"Lead": {"website": {"type": "url"}}, "Task": {"name": {"type": "varchar"}}},
            layouts={"Lead": {"detail": {"rows": [["website"]]}, "edit": False}},
        )
        assert reconcile_entities(s, instance_identifier=iid, client=client)["created"] == 1
        assert [e["entity_name"] for e in entity_repo.list_entities(s)] == ["Lead"]
        assert reconcile_fields(s, instance_identifier=iid, client=client)["created"] == 1
        assert field_repo.list_fields(s)[0]["field_built_in"] is True
        assert reconcile_layouts(s, instance_identifier=iid, client=client)["created"] == 1
        assert layout_repo.list_layouts(s)[0]["layout_type"] == "detail"

