"""PI-424 (REQ-346 audit half) — the V2 audit captures the entity options V1 does.

Oracle: ``tests/test_audit_entity_settings.py`` (V1) — icon/color/kanban/statusField
from clientDefs, optimistic concurrency and countDisabled from entityDefs,
multiple-assignment derived from an ``assignedUsers`` field or ``collaborators``
link. Absent-equals-default: an instance carrying none of these must not read as
drift against a design that holds the defaults (PI-312 rule).
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.introspect.entity_audit import reconcile_entity_slice
from crmbuilder_v2.introspect.reconcile import _audited_entity_attrs, reconcile_entities

from tests.crmbuilder_v2.access.test_instance_membership import (
    _custom,
    _FakeClient,
    _make_instance,
)

_CLIENT_DEFS = {
    "iconClass": "fas fa-anchor",
    "color": "#f01010",
    "kanbanViewMode": True,
    "statusField": "status",
}
_ENTITY_DEFS = {
    "optimisticConcurrencyControl": True,
    "collection": {"countDisabled": True},
    "fields": {"assignedUsers": {"type": "linkMultiple"}},
}


def _client_with_options(**kw):
    client = _FakeClient({"CEngagement": _custom()}, **kw)
    client._entity_defs = {"CEngagement": _ENTITY_DEFS}
    client._client_defs = {"CEngagement": _CLIENT_DEFS}
    return client


def test_audited_attrs_mirror_v1_capture():
    attrs = _audited_entity_attrs(
        {"type": "Person", "stream": True},
        {"countDisabled": True},
        _ENTITY_DEFS,
        _CLIENT_DEFS,
    )
    assert attrs["entity_base_type"] == "Person"
    assert attrs["entity_icon"] == "fas fa-anchor"
    assert attrs["entity_color"] == "#f01010"
    assert attrs["entity_status_field"] == "status"
    assert attrs["entity_kanban_view"] is True
    assert attrs["entity_count_disabled"] is True
    assert attrs["entity_optimistic_concurrency"] is True
    assert attrs["entity_multiple_assigned_users"] is True


def test_collaborators_link_also_means_multiple_assignment():
    attrs = _audited_entity_attrs({}, {}, {"links": {"collaborators": {}}}, {})
    assert attrs["entity_multiple_assigned_users"] is True


def test_absent_options_read_as_platform_defaults():
    attrs = _audited_entity_attrs({"type": "Base"}, {}, {}, {})
    assert attrs["entity_icon"] is None and attrs["entity_status_field"] is None
    assert attrs["entity_kanban_view"] is False
    assert attrs["entity_multiple_assigned_users"] is False


def test_reconcile_creates_entity_with_options_and_detects_drift(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        summary = reconcile_entities(s, instance_identifier=iid, client=_client_with_options())
        assert summary["created"] == 1 and summary["present"] == 1
        ent = entity_repo.list_entities(s)[0]
        assert ent["entity_icon"] == "fas fa-anchor"
        assert ent["entity_kanban_view"] is True
        assert ent["entity_optimistic_concurrency"] is True
        assert ent["entity_multiple_assigned_users"] is True
        assert ent["entity_base_type"] is None  # _custom() declares no type

        # Instance drops kanban and changes the icon -> drift with a sparse override.
        client2 = _client_with_options()
        client2._client_defs = {"CEngagement": {"iconClass": "fas fa-bell", "kanbanViewMode": False}}
        s2 = reconcile_entities(s, instance_identifier=iid, client=client2)
        assert s2["drifted"] == 1
        row = mb.list_memberships(s, instance_identifier=iid, member_type="entity")[0]
        assert row["override"]["entity_icon"] == "fas fa-bell"
        assert row["override"]["entity_kanban_view"] is False
        assert "entity_optimistic_concurrency" not in row["override"]


def test_base_type_is_learned_not_drifted(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Engagement", description="hand-authored")
        client = _FakeClient({"CEngagement": dict(_custom(), type="Person")})
        s1 = reconcile_entities(s, instance_identifier=iid, client=client)
        assert s1["drifted"] == 0 and s1["present"] == 1
        assert entity_repo.list_entities(s)[0]["entity_base_type"] == "Person"
        # Once known, a differing base type on an instance is drift.
        s2 = reconcile_entities(
            s, instance_identifier=iid,
            client=_FakeClient({"CEngagement": dict(_custom(), type="Company")}),
        )
        assert s2["drifted"] == 1


def test_absent_versus_default_is_not_drift(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        plain = _FakeClient({"CEngagement": _custom()})  # no clientDefs/entityDefs at all
        reconcile_entities(s, instance_identifier=iid, client=plain)
        s2 = reconcile_entities(s, instance_identifier=iid, client=plain)
        assert s2["drifted"] == 0 and s2["present"] == 1


def test_single_entity_audit_reads_options(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        reconcile_entities(s, instance_identifier=iid, client=_client_with_options())
        ent = entity_repo.list_entities(s)[0]
        client2 = _client_with_options()
        client2._client_defs = {"CEngagement": dict(_CLIENT_DEFS, color="#000000")}
        out = reconcile_entity_slice(
            s, instance_identifier=iid, entity_identifier=ent["entity_identifier"], client=client2
        )
        assert out["entity_state"] == "drifted"


def test_patch_and_replace_round_trip_options(v2_env):
    with session_scope() as s:
        e = entity_repo.create_entity(s, name="Widget", description="x", icon="fas fa-cog")
        assert e["entity_icon"] == "fas fa-cog" and e["entity_kanban_view"] is False
        p = entity_repo.patch_entity(s, e["entity_identifier"], kanban_view=True, icon="")
        assert p["entity_kanban_view"] is True and p["entity_icon"] is None
