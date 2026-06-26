"""instance_membership repo + entity reconcile tests — PI-185 (PRJ-027).

Covers the lightweight join repo (upsert insert/update, list filters,
mark-absent sweep) and the entity reconcile engine end to end against a fake
introspection client: create-on-first-sight, present/drifted classification with
sparse per-attribute override, absent sweep, and idempotency.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.exceptions import UnprocessableError
from crmbuilder_v2.access.repositories import association as association_repo
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.introspect.reconcile import (
    ReconcileError,
    reconcile_associations,
    reconcile_entities,
    reconcile_fields,
)


class _FakeClient:
    """Minimal introspection client: scopes + per-entity field/link lists."""

    def __init__(self, scopes, fields=None, links=None, layouts=None,
                 roles=None, teams=None, report_filters=None, status=200,
                 collections=None, i18n=None):
        self._scopes = scopes
        self._fields = fields or {}
        self._links = links or {}
        self._layouts = layouts or {}  # {scope: {espo_layout_type: content}}
        self._roles = roles or []
        self._teams = teams or []
        self._report_filters = report_filters or {}  # {scope: [filter rows]}
        self._status = status
        self._collections = collections or {}  # {scope: collection dict}
        self._i18n = i18n or {}  # {"Global": {"scopeNames": {...}, ...}}

    def get_all_scopes(self):
        return (self._status, self._scopes)

    def get_i18n(self, language="en_US"):
        return (200, self._i18n)

    def get_entity_field_list(self, entity):
        return (200, self._fields.get(entity, {}))

    def get_collection(self, entity):
        if entity in self._collections:
            return (200, self._collections[entity])
        return (404, None)

    def get_all_links(self, entity):
        return (200, self._links.get(entity, {}))

    def get_layout(self, entity, layout_type):
        content = self._layouts.get(entity, {}).get(layout_type)
        return (200, content) if content is not None else (404, None)

    def get_roles(self):
        return (200, {"list": self._roles})

    def get_teams(self):
        return (200, {"list": self._teams})

    def list_report_filters(self, entity_type):
        if entity_type in self._report_filters:
            return (200, {"list": self._report_filters[entity_type]})
        return (404, None)


def _custom(stream=False):
    return {
        "entity": True,
        "customizable": True,
        "isCustom": True,
        "stream": stream,
    }


def _make_instance(s, role="source"):
    return inst_repo.create_instance(
        s, name="src", url="https://src.example.org", role=role
    )["instance_identifier"]


# --- repo -------------------------------------------------------------------


def test_upsert_inserts_then_updates(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        a = mb.upsert_membership(
            s, instance_identifier=iid, member_type="entity",
            member_identifier="ENT-001", state="present",
        )
        assert a["state"] == "present" and a["override"] is None
        b = mb.upsert_membership(
            s, instance_identifier=iid, member_type="entity",
            member_identifier="ENT-001", state="drifted",
            override={"entity_track_activity": True},
        )
        # Same logical row updated, not duplicated.
        assert b["id"] == a["id"]
        assert b["state"] == "drifted"
        assert b["override"] == {"entity_track_activity": True}
        rows = mb.list_memberships(s, instance_identifier=iid)
        assert len(rows) == 1


def test_bad_enum_rejected(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        with pytest.raises(UnprocessableError):
            mb.upsert_membership(
                s, instance_identifier=iid, member_type="widget",
                member_identifier="ENT-001", state="present",
            )
        with pytest.raises(UnprocessableError):
            mb.upsert_membership(
                s, instance_identifier=iid, member_type="entity",
                member_identifier="ENT-001", state="maybe",
            )


def test_mark_absent_missing(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="entity",
            member_identifier="ENT-001", state="present",
        )
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="entity",
            member_identifier="ENT-002", state="present",
        )
        n = mb.mark_absent_missing(
            s, instance_identifier=iid, member_type="entity",
            present_member_identifiers={"ENT-001"},
        )
        assert n == 1
        states = {r["member_identifier"]: r["state"]
                  for r in mb.list_memberships(s, instance_identifier=iid)}
        assert states == {"ENT-001": "present", "ENT-002": "absent"}


# --- reconcile --------------------------------------------------------------


def test_reconcile_creates_and_marks_present(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient({
            "CEngagement": _custom(),
            "CDues": _custom(),
            "Account": {"entity": True, "isCustom": False},  # native -> skipped
            "Role": {"entity": True},  # system -> skipped
        })
        summary = reconcile_entities(s, instance_identifier=iid, client=client)
        assert summary["seen"] == 2
        assert summary["created"] == 2
        assert summary["present"] == 2
        assert summary["drifted"] == 0
        # Canonical entities created with neutral (c-stripped) names.
        names = {e["entity_name"] for e in entity_repo.list_entities(s)}
        assert {"Engagement", "Dues"} <= names
        rows = mb.list_memberships(s, instance_identifier=iid, member_type="entity")
        assert len(rows) == 2
        assert all(r["state"] == "present" for r in rows)


def test_reconcile_detects_drift_with_override(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        # Canonical entity says track_activity off; audit says stream on.
        entity_repo.create_entity(
            s, name="Engagement", description="x", track_activity=False
        )
        client = _FakeClient({"CEngagement": _custom(stream=True)})
        summary = reconcile_entities(s, instance_identifier=iid, client=client)
        assert summary["created"] == 0
        assert summary["drifted"] == 1
        row = mb.list_memberships(s, instance_identifier=iid)[0]
        assert row["state"] == "drifted"
        assert row["override"] == {"entity_track_activity": True}


def test_reconcile_captures_collection_settings(v2_env):
    # REQ-340 / PI-300: the five collection-search settings are captured from
    # the entityDefs.{Entity}.collection block on create.
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"CEngagement": _custom()},
            collections={
                "CEngagement": {
                    "orderBy": "createdAt",
                    "order": "desc",
                    "textFilterFields": ["name", "emailAddress"],
                    "fullTextSearch": True,
                    "fullTextSearchMinLength": 4,
                }
            },
        )
        summary = reconcile_entities(s, instance_identifier=iid, client=client)
        assert summary["created"] == 1
        row = [
            e for e in entity_repo.list_entities(s)
            if e["entity_name"] == "Engagement"
        ][0]
        assert row["entity_default_sort_field"] == "createdAt"
        assert row["entity_default_sort_direction"] == "desc"
        assert row["entity_text_filter_fields"] == ["name", "emailAddress"]
        assert row["entity_full_text_search"] is True
        assert row["entity_full_text_search_min_length"] == 4


def test_reconcile_detects_collection_settings_drift(v2_env):
    # An existing canonical entity with no collection settings drifts against
    # an audited instance that carries them.
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Engagement", description="x")
        client = _FakeClient(
            {"CEngagement": _custom()},
            collections={
                "CEngagement": {"orderBy": "name", "order": "asc"}
            },
        )
        summary = reconcile_entities(s, instance_identifier=iid, client=client)
        assert summary["created"] == 0
        assert summary["drifted"] == 1
        row = mb.list_memberships(s, instance_identifier=iid)[0]
        assert row["override"] == {
            "entity_default_sort_field": "name",
            "entity_default_sort_direction": "asc",
        }


def test_reconcile_marks_absent(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        # A canonical entity that the audited instance does not have.
        entity_repo.create_entity(s, name="Ghost", description="x")
        client = _FakeClient({"CEngagement": _custom()})
        summary = reconcile_entities(s, instance_identifier=iid, client=client)
        # Ghost is canonical but absent here; it only gets an absent row if it
        # already had a membership row — first audit it has none, so absent=0.
        assert summary["absent"] == 0
        # Now seed a membership for Ghost then re-audit without it.
        mb.upsert_membership(
            s, instance_identifier=iid, member_type="entity",
            member_identifier=[e for e in entity_repo.list_entities(s)
                               if e["entity_name"] == "Ghost"][0]["entity_identifier"],
            state="present",
        )
        summary2 = reconcile_entities(s, instance_identifier=iid, client=client)
        assert summary2["absent"] == 1
        ghost = [r for r in mb.list_memberships(s, instance_identifier=iid)
                 if r["state"] == "absent"]
        assert len(ghost) == 1


def test_reconcile_idempotent(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient({"CEngagement": _custom(), "CDues": _custom()})
        reconcile_entities(s, instance_identifier=iid, client=client)
        before = len(entity_repo.list_entities(s))
        reconcile_entities(s, instance_identifier=iid, client=client)
        after = len(entity_repo.list_entities(s))
        assert before == after  # no duplicate canonical entities
        rows = mb.list_memberships(s, instance_identifier=iid)
        assert len(rows) == 2  # no duplicate membership rows


def test_reconcile_raises_on_bad_response(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        with pytest.raises(ReconcileError):
            reconcile_entities(
                s, instance_identifier=iid, client=_FakeClient(None, status=500)
            )


# --- field reconcile (slice 2a) --------------------------------------------


def _field(ftype, *, required=False, custom=True):
    return {"type": ftype, "required": required, "isCustom": custom}


def test_reconcile_fields_creates_under_parent(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"CEngagement": _custom()},
            fields={"CEngagement": {
                "name": {"type": "varchar"},  # native base -> skipped
                # Custom-entity fields are stored under their natural names
                # (no platform c-prefix), so they round-trip unchanged.
                "status": _field("enum", required=True),
                "amount": _field("currency"),
            }},
        )
        summary = reconcile_fields(s, instance_identifier=iid, client=client)
        assert summary["seen"] == 2
        assert summary["created"] == 2
        assert summary["present"] == 2
        # Parent entity ensured + fields created with their natural names.
        ent = [e for e in entity_repo.list_entities(s)
               if e["entity_name"] == "Engagement"][0]
        flds = {f["field_name"]: f for f in
                field_repo.list_fields(s, entity_identifier=ent["entity_identifier"])}
        assert set(flds) == {"status", "amount"}
        assert flds["status"]["field_type"] == "enum"
        assert flds["status"]["field_required"] is True
        assert flds["amount"]["field_type"] == "money"
        rows = mb.list_memberships(s, instance_identifier=iid, member_type="field")
        assert len(rows) == 2 and all(r["state"] == "present" for r in rows)


def test_reconcile_fields_drift_with_override(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        ent = entity_repo.create_entity(s, name="Engagement", description="x")
        field_repo.create_field(
            s, field_belongs_to_entity_identifier=ent["entity_identifier"],
            name="status", description="x", type="text", required=False,
        )
        client = _FakeClient(
            {"CEngagement": _custom()},
            fields={"CEngagement": {"status": _field("enum", required=True)}},
        )
        summary = reconcile_fields(s, instance_identifier=iid, client=client)
        assert summary["created"] == 0 and summary["drifted"] == 1
        row = mb.list_memberships(s, instance_identifier=iid, member_type="field")[0]
        assert row["state"] == "drifted"
        assert row["override"] == {"field_type": "enum", "field_required": True}


def test_reconcile_fields_idempotent(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"CEngagement": _custom()},
            fields={"CEngagement": {"cStatus": _field("enum")}},
        )
        reconcile_fields(s, instance_identifier=iid, client=client)
        before = len(field_repo.list_fields(s))
        reconcile_fields(s, instance_identifier=iid, client=client)
        assert len(field_repo.list_fields(s)) == before
        assert len(mb.list_memberships(
            s, instance_identifier=iid, member_type="field")) == 1


# --- association reconcile (slice 2b) --------------------------------------


def _two_custom_entities(s):
    """Create canonical Engagement + Dues entities (custom-to-custom endpoints)."""
    entity_repo.create_entity(s, name="Engagement", description="x")
    entity_repo.create_entity(s, name="Dues", description="x")


def test_reconcile_associations_creates_custom_to_custom(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _two_custom_entities(s)
        client = _FakeClient(
            {"CEngagement": _custom(), "CDues": _custom()},
            links={
                "CEngagement": {
                    "dueses": {"type": "hasMany", "entity": "CDues"},
                    # link to a native entity -> skipped (not canonical)
                    "accounts": {"type": "hasMany", "entity": "Account"},
                },
                "CDues": {  # reciprocal belongsTo -> skipped
                    "engagement": {"type": "belongsTo", "entity": "CEngagement"},
                },
            },
        )
        summary = reconcile_associations(s, instance_identifier=iid, client=client)
        assert summary["seen"] == 1  # only the custom-to-custom hasMany
        assert summary["created"] == 1
        assert summary["present"] == 1
        assoc = association_repo.list_associations(s)
        assert len(assoc) == 1
        a = assoc[0]
        assert a["association_name"] == "dueses"
        assert a["association_cardinality"] == "one_to_many"
        ent = {e["entity_name"]: e["entity_identifier"]
               for e in entity_repo.list_entities(s)}
        assert a["association_source_entity"] == ent["Engagement"]
        assert a["association_target_entity"] == ent["Dues"]
        rows = mb.list_memberships(
            s, instance_identifier=iid, member_type="association")
        assert len(rows) == 1 and rows[0]["state"] == "present"


def test_reconcile_associations_manymany_deduped(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _two_custom_entities(s)
        mm = {"type": "manyMany", "relationName": "engagementDues"}
        client = _FakeClient(
            {"CEngagement": _custom(), "CDues": _custom()},
            links={
                "CEngagement": {"dueses": {**mm, "entity": "CDues"}},
                "CDues": {"engagements": {**mm, "entity": "CEngagement"}},
            },
        )
        summary = reconcile_associations(s, instance_identifier=iid, client=client)
        # The shared relationName de-duplicates the two sides to one association.
        assert summary["created"] == 1
        assoc = association_repo.list_associations(s)
        assert len(assoc) == 1
        assert assoc[0]["association_name"] == "engagementDues"
        assert assoc[0]["association_cardinality"] == "many_to_many"


def test_reconcile_associations_drift(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _two_custom_entities(s)
        ent = {e["entity_name"]: e["entity_identifier"]
               for e in entity_repo.list_entities(s)}
        association_repo.create_association(
            s, name="dueses", source_entity=ent["Engagement"],
            target_entity=ent["Dues"], cardinality="one_to_one",
        )
        client = _FakeClient(
            {"CEngagement": _custom()},
            links={"CEngagement": {"dueses": {"type": "hasMany", "entity": "CDues"}}},
        )
        summary = reconcile_associations(s, instance_identifier=iid, client=client)
        assert summary["created"] == 0 and summary["drifted"] == 1
        row = mb.list_memberships(
            s, instance_identifier=iid, member_type="association")[0]
        assert row["state"] == "drifted"
        assert row["override"] == {"association_cardinality": "one_to_many"}


def test_reconcile_associations_idempotent(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _two_custom_entities(s)
        client = _FakeClient(
            {"CEngagement": _custom()},
            links={"CEngagement": {"dueses": {"type": "hasMany", "entity": "CDues"}}},
        )
        reconcile_associations(s, instance_identifier=iid, client=client)
        reconcile_associations(s, instance_identifier=iid, client=client)
        assert len(association_repo.list_associations(s)) == 1
        assert len(mb.list_memberships(
            s, instance_identifier=iid, member_type="association")) == 1


# --- native-entity support (PI-192) ----------------------------------------


def _native(stream=False):
    return {"entity": True, "customizable": True, "isCustom": False, "stream": stream}


def test_reconcile_entities_includes_customized_native_only(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"Account": _native(), "Contact": _native()},
            fields={
                # Account carries a custom field -> customized native.
                "Account": {"website": {"type": "url"},
                            "cRegion": {"isCustom": True, "type": "enum"}},
                # Contact has only native base fields -> NOT customized.
                "Contact": {"firstName": {"type": "varchar"}},
            },
        )
        summary = reconcile_entities(s, instance_identifier=iid, client=client)
        names = {e["entity_name"] for e in entity_repo.list_entities(s)}
        assert "Account" in names      # customized native -> created
        assert "Contact" not in names  # bare native -> skipped
        assert summary["created"] == 1
        rows = mb.list_memberships(s, instance_identifier=iid, member_type="entity")
        assert len(rows) == 1 and rows[0]["state"] == "present"


def test_reconcile_native_entity_custom_fields(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"Account": _native()},
            fields={"Account": {
                "website": {"type": "url"},  # native base -> skipped
                "cRegion": {"isCustom": True, "type": "enum", "required": True},
            }},
        )
        reconcile_entities(s, instance_identifier=iid, client=client)
        fsummary = reconcile_fields(s, instance_identifier=iid, client=client)
        assert fsummary["created"] == 1  # only the custom field
        acct = [e for e in entity_repo.list_entities(s)
                if e["entity_name"] == "Account"][0]
        flds = {f["field_name"] for f in
                field_repo.list_fields(s, entity_identifier=acct["entity_identifier"])}
        assert flds == {"region"}  # strip_field_c_prefix("cRegion") == "region"


def test_reconcile_association_to_customized_native_endpoint(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"CEngagement": _custom(), "Account": _native()},
            fields={"Account": {"cRegion": {"isCustom": True, "type": "enum"}}},
            links={"CEngagement": {"account": {"type": "hasMany", "entity": "Account"}}},
        )
        reconcile_entities(s, instance_identifier=iid, client=client)  # +Engagement +Account
        asummary = reconcile_associations(s, instance_identifier=iid, client=client)
        assert asummary["created"] == 1
        a = association_repo.list_associations(s)[0]
        ent = {e["entity_name"]: e["entity_identifier"]
               for e in entity_repo.list_entities(s)}
        assert a["association_source_entity"] == ent["Engagement"]
        assert a["association_target_entity"] == ent["Account"]


def test_reconcile_association_to_uncustomized_native_skipped(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        # Account has no custom field -> no canonical record -> link skipped.
        client = _FakeClient(
            {"CEngagement": _custom(), "Account": _native()},
            fields={"Account": {"website": {"type": "url"}}},
            links={"CEngagement": {"account": {"type": "hasMany", "entity": "Account"}}},
        )
        reconcile_entities(s, instance_identifier=iid, client=client)
        asummary = reconcile_associations(s, instance_identifier=iid, client=client)
        assert asummary["created"] == 0
        assert association_repo.list_associations(s) == []


# --- layout reconcile (PI-193) ---------------------------------------------


def test_reconcile_layouts_create_and_drift(v2_env):
    from crmbuilder_v2.access.repositories import layouts as layout_repo
    from crmbuilder_v2.introspect.reconcile import reconcile_layouts
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Engagement", description="x")
        client = _FakeClient(
            {"CEngagement": _custom()},
            layouts={"CEngagement": {"detail": {"rows": [["name"]]}}},
        )
        summary = reconcile_layouts(s, instance_identifier=iid, client=client)
        assert summary["created"] == 1 and summary["present"] == 1
        lay = layout_repo.list_layouts(s)
        assert len(lay) == 1
        assert lay[0]["layout_type"] == "detail"
        assert lay[0]["layout_content"] == {"rows": [["name"]]}
        # Re-audit with changed content -> drift + override.
        client2 = _FakeClient(
            {"CEngagement": _custom()},
            layouts={"CEngagement": {"detail": {"rows": [["name"], ["status"]]}}},
        )
        s2 = reconcile_layouts(s, instance_identifier=iid, client=client2)
        assert s2["drifted"] == 1
        row = mb.list_memberships(s, instance_identifier=iid, member_type="layout")[0]
        assert row["state"] == "drifted"
        assert row["override"]["layout_content"] == {"rows": [["name"], ["status"]]}


# --- role / team reconcile (PI-194) ----------------------------------------


def test_reconcile_roles_create_and_drift(v2_env):
    from crmbuilder_v2.access.repositories import roles as role_repo
    from crmbuilder_v2.introspect.reconcile import reconcile_roles
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {}, roles=[{"name": "Mentor", "data": {"Contact": "yes"},
                        "assignmentPermission": "team"}],
        )
        summary = reconcile_roles(s, instance_identifier=iid, client=client)
        assert summary["created"] == 1
        r = role_repo.list_roles(s)[0]
        assert r["role_name"] == "Mentor"
        assert r["role_scope_access"] == {"Contact": "yes"}
        assert r["role_system_permissions"] == {"assignmentPermission": "team"}
        # drift on scope access
        client2 = _FakeClient(
            {}, roles=[{"name": "Mentor", "data": {"Contact": "no"},
                        "assignmentPermission": "team"}],
        )
        s2 = reconcile_roles(s, instance_identifier=iid, client=client2)
        assert s2["drifted"] == 1
        row = mb.list_memberships(s, instance_identifier=iid, member_type="role")[0]
        assert row["override"]["role_scope_access"] == {"Contact": "no"}


def test_reconcile_teams_create_and_absent(v2_env):
    from crmbuilder_v2.access.repositories import teams as team_repo
    from crmbuilder_v2.introspect.reconcile import reconcile_teams
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient({}, teams=[{"name": "Coordinators", "description": "Ops"}])
        summary = reconcile_teams(s, instance_identifier=iid, client=client)
        assert summary["created"] == 1
        t = team_repo.list_teams(s)[0]
        assert t["team_name"] == "Coordinators" and t["team_description"] == "Ops"
        # Re-audit with the team gone -> absent.
        s2 = reconcile_teams(s, instance_identifier=iid, client=_FakeClient({}, teams=[]))
        assert s2["absent"] == 1
        row = mb.list_memberships(s, instance_identifier=iid, member_type="team")[0]
        assert row["state"] == "absent"


# --- filtered-tab reconcile (PI-195) ---------------------------------------


def test_reconcile_filtered_tabs_create_drift_and_advanced_pack_absent(v2_env):
    from crmbuilder_v2.access.repositories import filtered_tabs as ft_repo
    from crmbuilder_v2.introspect.reconcile import reconcile_filtered_tabs
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Engagement", description="x")
        client = _FakeClient(
            {"CEngagement": _custom()},
            report_filters={"CEngagement": [
                {"name": "Active", "data": {"status": "open"}},
            ]},
        )
        summary = reconcile_filtered_tabs(s, instance_identifier=iid, client=client)
        assert summary["created"] == 1 and summary["present"] == 1
        ft = ft_repo.list_filtered_tabs(s)
        assert len(ft) == 1
        assert ft[0]["filtered_tab_label"] == "Active"
        assert ft[0]["filtered_tab_filter"] == {"status": "open"}
        # Re-audit with a changed filter -> drift + override.
        client2 = _FakeClient(
            {"CEngagement": _custom()},
            report_filters={"CEngagement": [
                {"name": "Active", "data": {"status": "closed"}},
            ]},
        )
        s2 = reconcile_filtered_tabs(s, instance_identifier=iid, client=client2)
        assert s2["drifted"] == 1
        row = mb.list_memberships(
            s, instance_identifier=iid, member_type="filtered_tab")[0]
        assert row["override"]["filtered_tab_filter"] == {"status": "closed"}
        # No Advanced Pack (list_report_filters 404) -> nothing seen, tab absent.
        s3 = reconcile_filtered_tabs(
            s, instance_identifier=iid, client=_FakeClient({"CEngagement": _custom()}))
        assert s3["seen"] == 0 and s3["absent"] == 1


def test_reconcile_associations_strips_native_link_prefix(v2_env):
    """A custom link on a NATIVE entity reconciles under its natural name,
    not the platform-prefixed form (REQ-344)."""
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Account", description="x")
        entity_repo.create_entity(s, name="Contribution", description="x")
        client = _FakeClient(
            {"Account": _native(), "CContribution": _custom()},
            links={
                "Account": {"cContributions": {
                    "type": "hasMany", "entity": "CContribution"}},
                "CContribution": {"donorAccount": {
                    "type": "belongsTo", "entity": "Account"}},
            },
        )
        reconcile_associations(s, instance_identifier=iid, client=client)
        names = {a["association_name"]
                 for a in association_repo.list_associations(s)}
        assert "contributions" in names      # native link prefix stripped
        assert "cContributions" not in names


def test_reconcile_captures_entity_label_from_i18n(v2_env):
    """REL-025 / REQ-364: the audit captures the source display label (singular +
    plural) from i18n and stores it on the canonical entity, keyed by the
    concrete scope name while the canonical record uses the neutral name."""
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            fields={"CMentorProfile": {}},
            i18n={"Global": {
                "scopeNames": {"CMentorProfile": "CBM Member"},
                "scopeNamesPlural": {"CMentorProfile": "CBM Members"},
            }},
        )
        reconcile_entities(s, instance_identifier=iid, client=client)
        ent = next(
            e for e in entity_repo.list_entities(s)
            if e["entity_name"] == "MentorProfile"
        )
        assert ent["entity_label"] == "CBM Member"
        assert ent["entity_label_plural"] == "CBM Members"


def test_reconcile_without_i18n_leaves_label_empty(v2_env):
    """No i18n labels -> structure still reconciles, label stays empty."""
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(scopes={"CMentorProfile": _custom()},
                             fields={"CMentorProfile": {}})
        reconcile_entities(s, instance_identifier=iid, client=client)
        ent = next(
            e for e in entity_repo.list_entities(s)
            if e["entity_name"] == "MentorProfile"
        )
        assert ent["entity_label"] is None


def test_reconcile_fields_captures_field_label(v2_env):
    """REL-025 / REQ-366: the audit captures each field's display label from
    i18n (<Entity>.fields.<field>) and stores it on the canonical field."""
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(
            {"CEngagement": _custom()},
            fields={"CEngagement": {"amount": _field("currency")}},
            i18n={"CEngagement": {"fields": {"amount": "Deal Amount"}}},
        )
        reconcile_fields(s, instance_identifier=iid, client=client)
        ent = [e for e in entity_repo.list_entities(s)
               if e["entity_name"] == "Engagement"][0]
        fld = [f for f in field_repo.list_fields(
            s, entity_identifier=ent["entity_identifier"]
        ) if f["field_name"] == "amount"][0]
        assert fld["field_label"] == "Deal Amount"
