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
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.introspect.reconcile import ReconcileError, reconcile_entities


class _FakeClient:
    """Minimal introspection client: returns a canned scopes payload."""

    def __init__(self, scopes, status=200):
        self._scopes = scopes
        self._status = status

    def get_all_scopes(self):
        return (self._status, self._scopes)


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
