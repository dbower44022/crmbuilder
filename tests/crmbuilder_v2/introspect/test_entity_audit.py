"""Entity-only re-audit tests — PI-351 (REL-037 / REQ-392)."""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import association as association_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.introspect.entity_audit import reconcile_entity_slice


class _FakeClient:
    """A live instance carrying CWidget (one drifted field, one layout, one link)."""

    def get_all_scopes(self):
        return (200, {
            "CWidget": {"isCustom": True, "customizable": True, "entity": True,
                        "stream": False, "type": "Base"},
        })

    def get_i18n(self, language="en_US"):
        return (200, {})

    def get_collection(self, entity):
        return (200, {})

    def get_entity_field_list(self, entity):
        if entity == "CWidget":
            return (200, {"status": {"type": "enum", "isCustom": True}})
        return (200, {})

    def get_layout(self, entity, layout_type):
        if entity == "CWidget" and layout_type == "detail":
            return (200, {"rows": [["status"]]})
        return (404, None)

    def get_all_links(self, entity):
        if entity == "CWidget":
            return (200, {"dueses": {"type": "hasMany", "entity": "CDues"}})
        return (200, {})


def _setup(s):
    iid = inst_repo.create_instance(
        s, name="tgt", url="https://tgt.example.org", role="target"
    )["instance_identifier"]
    wid = entity_repo.create_entity(s, name="Widget", description="x")["entity_identifier"]
    did = entity_repo.create_entity(s, name="Dues", description="x")["entity_identifier"]
    # canonical field declared as text; the live instance has it as enum -> drift
    fid = field_repo.create_field(
        s, field_belongs_to_entity_identifier=wid, name="status",
        description="x", type="text", required=False,
    )["field_identifier"]
    lid = layout_repo.create_layout(
        s, entity_identifier=wid, layout_type="detail", content={"rows": [["status"]]}
    )["layout_identifier"]
    aid = association_repo.create_association(
        s, name="dueses", source_entity=wid, target_entity=did,
        cardinality="one_to_many",
    )["association_identifier"]
    return iid, wid, fid, lid, aid, did


def test_entity_slice_refreshes_the_entity_members(v2_env):
    with session_scope() as s:
        iid, wid, fid, lid, aid, did = _setup(s)
        out = reconcile_entity_slice(
            s, instance_identifier=iid, entity_identifier=wid, client=_FakeClient(),
        )
        assert out["present"] is True
        assert out["entity_state"] == "present"
        # the field drifts (text -> enum); layout + relationship are present
        assert out["fields"] == {"present": 0, "drifted": 1, "absent": 0}
        assert out["layouts"]["present"] == 1
        assert out["relationships"]["present"] == 1
        # membership rows were written for this entity's members
        fm = mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                 member_identifier=fid)[0]
        assert fm["state"] == "drifted"
        assert fm["override"] == {"field_type": "enum"}
        em = mb.list_memberships(s, instance_identifier=iid, member_type="entity",
                                 member_identifier=wid)[0]
        assert em["state"] == "present"


def test_entity_slice_does_not_touch_other_entities(v2_env):
    """The safety property: a slice audit writes ONLY this entity's members and
    never marks an unrelated entity/field absent (no global sweep)."""
    with session_scope() as s:
        iid, wid, fid, lid, aid, did = _setup(s)
        # an unrelated entity with a present membership row
        oid = entity_repo.create_entity(s, name="Other", description="x")["entity_identifier"]
        ofid = field_repo.create_field(
            s, field_belongs_to_entity_identifier=oid, name="code",
            description="x", type="text", required=False,
        )["field_identifier"]
        mb.upsert_membership(s, instance_identifier=iid, member_type="entity",
                             member_identifier=oid, state="present")
        mb.upsert_membership(s, instance_identifier=iid, member_type="field",
                             member_identifier=ofid, state="present")

        reconcile_entity_slice(
            s, instance_identifier=iid, entity_identifier=wid, client=_FakeClient(),
        )
        # the unrelated entity + field are untouched (still present, not absent)
        assert mb.list_memberships(s, instance_identifier=iid, member_type="entity",
                                   member_identifier=oid)[0]["state"] == "present"
        assert mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                   member_identifier=ofid)[0]["state"] == "present"


def test_entity_slice_marks_absent_when_entity_gone(v2_env):
    """If the entity is not present on the instance, it and its members read absent."""
    class _Empty(_FakeClient):
        def get_all_scopes(self):
            return (200, {})  # CWidget not present live

    with session_scope() as s:
        iid, wid, fid, lid, aid, did = _setup(s)
        out = reconcile_entity_slice(
            s, instance_identifier=iid, entity_identifier=wid, client=_Empty(),
        )
        assert out["present"] is False
        assert out["entity_state"] == "absent"
        assert out["fields"] == {"present": 0, "drifted": 0, "absent": 1}
        assert mb.list_memberships(s, instance_identifier=iid, member_type="field",
                                   member_identifier=fid)[0]["state"] == "absent"
