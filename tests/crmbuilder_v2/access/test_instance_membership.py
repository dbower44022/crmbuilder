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

    def __init__(self, scopes, fields=None, links=None, status=200):
        self._scopes = scopes
        self._fields = fields or {}
        self._links = links or {}
        self._status = status

    def get_all_scopes(self):
        return (self._status, self._scopes)

    def get_entity_field_list(self, entity):
        return (200, self._fields.get(entity, {}))

    def get_all_links(self, entity):
        return (200, self._links.get(entity, {}))


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
                "cStatus": _field("enum", required=True),
                "cAmount": _field("currency"),
            }},
        )
        summary = reconcile_fields(s, instance_identifier=iid, client=client)
        assert summary["seen"] == 2
        assert summary["created"] == 2
        assert summary["present"] == 2
        # Parent entity ensured + fields created with neutral names + mapped type.
        ent = [e for e in entity_repo.list_entities(s)
               if e["entity_name"] == "Engagement"][0]
        flds = {f["field_name"]: f for f in
                field_repo.list_fields(s, entity_identifier=ent["entity_identifier"])}
        # Neutral field names are lowercase-first (cStatus -> status).
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
            fields={"CEngagement": {"cStatus": _field("enum", required=True)}},
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
