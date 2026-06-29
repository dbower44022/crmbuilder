"""Per-area scoped membership writes — WTK-268 / PI-353 (REQ-394 §3.1, §3.4).

These tests pin the **write boundary** the audit pipeline must obey: each
reconcile pass has write authority over exactly one ``member_type`` — its audit
area — and may never create, modify, or sweep a membership row another pass of
the same audit owns. The inventory after an audit is therefore the union of
disjoint per-area slices: running one area's pass never alters another area's
slice, and a partial audit (some areas read, others not) preserves every
unwritten area's prior membership.

The :class:`reconcile._AreaMembershipWriter` is the mechanism that makes that
scoping a binding contract rather than a literal each call site repeats; these
tests exercise it both directly and through the passes. Companion to
``test_reconcile_scoping.py`` (the candidate-gated dispatch switch) and the
no-resolution preservation tests (REQ-394 §3.2, a sibling slice).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import instances as instances_repo
from crmbuilder_v2.introspect import reconcile


class _FakeClient:
    """Minimal introspection client: two custom entities, one custom field each."""

    def get_all_scopes(self):
        cust = {"entity": True, "customizable": True, "isCustom": True}
        return (200, {
            "CEngagement": {**cust, "stream": False},
            "CDues": {**cust, "stream": True},
        })

    def get_i18n(self, language="en_US"):
        return (200, {})

    def get_collection(self, entity):
        return (200, {})

    def get_entity_field_list(self, entity):
        return (200, {
            "name": {"type": "varchar"},
            "cStatus": {"type": "enum", "isCustom": True, "required": True},
        })

    def get_all_links(self, entity):
        return (200, {})


def _make_instance(s, role="both"):
    return instances_repo.create_instance(
        s, name=f"{role}-inst", url="https://x.example.org", role=role
    )["instance_identifier"]


# --- the writer's binding contract ------------------------------------------


def test_writer_rejects_unknown_member_type(v2_env):
    """The writer fails at construction on an area outside the member-type vocab."""
    with session_scope() as s:
        iid = _make_instance(s)
        with pytest.raises(reconcile.ReconcileError):
            reconcile._AreaMembershipWriter(
                s,
                instance_identifier=iid,
                member_type="not_an_area",
                last_audited_at=datetime.now(UTC),
            )


def test_writer_only_touches_its_bound_member_type(v2_env):
    """A writer's upsert + absent sweep act on its bound area only.

    A pre-existing row of a *different* area is left exactly as it was — the
    sweep is filtered to the writer's own ``member_type``.
    """
    with session_scope() as s:
        iid = _make_instance(s)
        # A prior audit recorded a field-area row.
        membership_repo.upsert_membership(
            s,
            instance_identifier=iid,
            member_type="field",
            member_identifier="FLD-900",
            state="present",
        )
        # An entity-area writer records one entity, then sweeps its own area.
        writer = reconcile._AreaMembershipWriter(
            s,
            instance_identifier=iid,
            member_type="entity",
            last_audited_at=datetime.now(UTC),
        )
        writer.upsert("ENT-001", "present")
        swept = writer.sweep_absent()

        # The sweep saw only entity rows (ENT-001 is present → nothing to flip).
        assert swept == 0
        # The field row from the prior audit is untouched — not swept to absent.
        field_rows = membership_repo.list_memberships(
            s, instance_identifier=iid, member_type="field"
        )
        assert len(field_rows) == 1
        assert field_rows[0]["member_identifier"] == "FLD-900"
        assert field_rows[0]["state"] == "present"
        # Only the entity row this writer wrote exists in the entity slice.
        entity_rows = membership_repo.list_memberships(
            s, instance_identifier=iid, member_type="entity"
        )
        assert {r["member_identifier"] for r in entity_rows} == {"ENT-001"}


# --- the passes compose as disjoint slices ----------------------------------


def test_entity_pass_does_not_disturb_other_area_membership(v2_env):
    """Running the entity pass never alters another area's membership slice.

    A field/role/team row recorded by a prior audit survives an entity-only
    re-audit unchanged — acceptance item 4 (one area's pass never touches
    another's slice) and item 5 (a partial audit preserves unwritten areas).
    """
    with session_scope() as s:
        iid = _make_instance(s)
        # Prior audit left present rows across three other areas.
        for member_type, member_id in (
            ("field", "FLD-700"),
            ("role", "ROL-700"),
            ("team", "TEAM-700"),
        ):
            membership_repo.upsert_membership(
                s,
                instance_identifier=iid,
                member_type=member_type,
                member_identifier=member_id,
                state="present",
            )

        # Run only the entity pass (drift path — ``both`` role).
        summary = reconcile.reconcile_entities(
            s, instance_identifier=iid, client=_FakeClient()
        )
        assert summary["created"] == 2  # the two entities are discovered

        # Every other area's prior row is preserved exactly — none swept absent.
        for member_type, member_id in (
            ("field", "FLD-700"),
            ("role", "ROL-700"),
            ("team", "TEAM-700"),
        ):
            rows = membership_repo.list_memberships(
                s, instance_identifier=iid, member_type=member_type
            )
            assert [r["member_identifier"] for r in rows] == [member_id]
            assert rows[0]["state"] == "present"


def test_two_area_passes_merge_into_disjoint_slices(v2_env):
    """Entity then field pass yield a union of disjoint slices.

    The field pass's absent sweep flags only stale field rows; the entity rows
    the entity pass recorded are never touched, so the inventory is the union of
    both areas (REQ-394 §3.4).
    """
    with session_scope() as s:
        iid = _make_instance(s)
        reconcile.reconcile_entities(
            s, instance_identifier=iid, client=_FakeClient()
        )
        entity_ids_before = {
            r["member_identifier"]
            for r in membership_repo.list_memberships(
                s, instance_identifier=iid, member_type="entity"
            )
        }
        assert entity_ids_before  # entities were recorded

        # A field pass now runs; it must not disturb the entity slice.
        reconcile.reconcile_fields(
            s, instance_identifier=iid, client=_FakeClient()
        )
        entity_rows_after = membership_repo.list_memberships(
            s, instance_identifier=iid, member_type="entity"
        )
        assert {r["member_identifier"] for r in entity_rows_after} == (
            entity_ids_before
        )
        assert all(r["state"] == "present" for r in entity_rows_after)
        # And the field slice is non-empty and disjoint from the entity slice.
        field_rows = membership_repo.list_memberships(
            s, instance_identifier=iid, member_type="field"
        )
        assert field_rows
        assert not (
            {r["member_identifier"] for r in field_rows} & entity_ids_before
        )
