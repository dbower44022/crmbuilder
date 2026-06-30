"""Multi-area concurrent pass isolation — WTK-272 / PI-353 (REQ-394 §3.4).

Companion to ``test_reconcile_area_scoping.py``: where that file pins the
two-area entity→field merge, these tests pin the property at the full
``member_type`` width and under *concurrent* passes — several area writers
coexisting within one audit (one ``session``), their upserts and absent sweeps
interleaved. The contract WTK-268 made binding (``_AreaMembershipWriter`` fixes
the audit area at construction) must hold not just pairwise and sequentially but
for every one of the seven areas at once: each pass writes only its own area's
resolved membership, and a pass's absent sweep — even a *real* sweep that flips
its own stale rows — never touches a row another pass of the same audit recorded.

These tests close the gaps the area-scoping suite leaves open:

* a **non-empty** sweep (the area-scoping suite only ever sweeps zero rows, so it
  proves the sweep is *scoped* but never that a genuinely active sweep stays
  scoped while sibling areas hold stale rows of their own);
* **all seven** member types coexisting in a single audit, not just entity+field;
* **interleaved** upserts/sweeps across writers, modelling passes that run
  concurrently within one audit rather than strictly one-then-the-next.
"""

from __future__ import annotations

from datetime import UTC, datetime

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import instances as instances_repo
from crmbuilder_v2.access.vocab import INSTANCE_MEMBERSHIP_MEMBER_TYPES
from crmbuilder_v2.introspect import reconcile


def _make_instance(s, role="both"):
    return instances_repo.create_instance(
        s, name=f"{role}-inst", url="https://x.example.org", role=role
    )["instance_identifier"]


def _writer(s, iid, member_type, stamp):
    return reconcile._AreaMembershipWriter(
        s,
        instance_identifier=iid,
        member_type=member_type,
        last_audited_at=stamp,
    )


def _ids(s, iid, member_type):
    return {
        r["member_identifier"]
        for r in membership_repo.list_memberships(
            s, instance_identifier=iid, member_type=member_type
        )
    }


def _state_of(s, iid, member_type, member_id):
    rows = membership_repo.list_memberships(
        s,
        instance_identifier=iid,
        member_type=member_type,
        member_identifier=member_id,
    )
    return rows[0]["state"] if rows else None


# --- all seven areas coexist as disjoint slices in one audit -----------------


def test_seven_area_writers_each_own_only_their_slice(v2_env):
    """One writer per member type in one audit; each owns exactly its own rows.

    Every one of the seven areas runs a pass within the same audit (the same
    ``session``). After all passes complete, each area's slice contains exactly
    the rows its own writer upserted and nothing from any sibling pass — the
    inventory is the union of seven disjoint per-area slices (§3.4).
    """
    with session_scope() as s:
        iid = _make_instance(s)
        stamp = datetime.now(UTC)
        # One row per area, identifier tagged with the area so a cross-area leak
        # would be unmistakable.
        per_area = {
            mt: f"{mt}-001" for mt in sorted(INSTANCE_MEMBERSHIP_MEMBER_TYPES)
        }
        for member_type, member_id in per_area.items():
            w = _writer(s, iid, member_type, stamp)
            w.upsert(member_id, "present")
            # A pass with everything it wrote still present sweeps nothing.
            assert w.sweep_absent() == 0

        for member_type, member_id in per_area.items():
            assert _ids(s, iid, member_type) == {member_id}
            assert _state_of(s, iid, member_type, member_id) == "present"


# --- a real (non-empty) sweep stays inside its own area ----------------------


def test_active_sweep_flips_only_its_own_area(v2_env):
    """A pass whose sweep genuinely flips stale rows leaves sibling areas intact.

    Two areas each carry a prior present row that the new audit will *not*
    re-observe. Running only the ``entity`` writer (which re-confirms nothing in
    its own area) sweeps the stale entity row to ``absent`` — proving the sweep
    is active — while the stale ``field`` row, owned by a different pass, is
    preserved exactly. Absence is recorded for the swept area only.
    """
    with session_scope() as s:
        iid = _make_instance(s)
        # A prior audit left a present row in two different areas.
        for member_type, member_id in (("entity", "ENT-900"), ("field", "FLD-900")):
            membership_repo.upsert_membership(
                s,
                instance_identifier=iid,
                member_type=member_type,
                member_identifier=member_id,
                state="present",
            )

        # The entity pass this audit observes nothing (its seen set is empty) and
        # sweeps. Its read succeeded — the area was genuinely empty — so the sweep
        # is real, not the read-failed no-op.
        writer = _writer(s, iid, "entity", datetime.now(UTC))
        swept = writer.sweep_absent()

        assert swept == 1  # the stale entity row was flipped
        assert _state_of(s, iid, "entity", "ENT-900") == "absent"
        # The field row a different pass owns is untouched by the entity sweep.
        assert _state_of(s, iid, "field", "FLD-900") == "present"


def test_read_failed_pass_preserves_every_area(v2_env):
    """A failed-read pass sweeps nothing, in its own area or any other (§3.2).

    The read-success signal disarms the sweep, so even the pass's own area keeps
    its prior membership — and a sibling area, which the failed pass has no
    authority over regardless, is likewise preserved. Guards the REL-038 defect
    at the multi-area boundary.
    """
    with session_scope() as s:
        iid = _make_instance(s)
        for member_type, member_id in (("role", "ROL-900"), ("team", "TEAM-900")):
            membership_repo.upsert_membership(
                s,
                instance_identifier=iid,
                member_type=member_type,
                member_identifier=member_id,
                state="present",
            )

        # The role pass could not read its area; its sweep must be a no-op.
        writer = _writer(s, iid, "role", datetime.now(UTC))
        writer.mark_read_failed()
        assert writer.sweep_absent() == 0

        assert _state_of(s, iid, "role", "ROL-900") == "present"
        assert _state_of(s, iid, "team", "TEAM-900") == "present"


# --- interleaved passes within one audit preserve each other -----------------


def test_interleaved_writers_preserve_each_others_membership(v2_env):
    """Two writers' upserts and sweeps interleaved leave both slices correct.

    Models passes running concurrently within one audit: ``entity`` and ``team``
    writers alternate upserts, then each sweeps its own area in turn. A stale row
    each writer does *not* re-observe is flipped absent within its own area, yet
    neither sweep disturbs the other's freshly-written rows. The final inventory
    is exactly the union the two passes intended.
    """
    with session_scope() as s:
        iid = _make_instance(s)
        # Each area starts with one stale row neither pass will re-observe.
        membership_repo.upsert_membership(
            s, instance_identifier=iid, member_type="entity",
            member_identifier="ENT-OLD", state="present",
        )
        membership_repo.upsert_membership(
            s, instance_identifier=iid, member_type="team",
            member_identifier="TEAM-OLD", state="present",
        )

        stamp = datetime.now(UTC)
        ent = _writer(s, iid, "entity", stamp)
        team = _writer(s, iid, "team", stamp)

        # Interleave the two passes' writes.
        ent.upsert("ENT-001", "present")
        team.upsert("TEAM-001", "present")
        ent.upsert("ENT-002", "drifted", {"entity_track_activity": True})
        team.upsert("TEAM-002", "present")

        # Sweep in turn; each flips only its own stale row.
        assert ent.sweep_absent() == 1
        assert team.sweep_absent() == 1

        # Entity slice: the two fresh rows present/drifted, the stale one absent.
        assert _ids(s, iid, "entity") == {"ENT-OLD", "ENT-001", "ENT-002"}
        assert _state_of(s, iid, "entity", "ENT-001") == "present"
        assert _state_of(s, iid, "entity", "ENT-002") == "drifted"
        assert _state_of(s, iid, "entity", "ENT-OLD") == "absent"
        # Team slice mirrors it — and the entity sweep never reached it.
        assert _ids(s, iid, "team") == {"TEAM-OLD", "TEAM-001", "TEAM-002"}
        assert _state_of(s, iid, "team", "TEAM-001") == "present"
        assert _state_of(s, iid, "team", "TEAM-002") == "present"
        assert _state_of(s, iid, "team", "TEAM-OLD") == "absent"


# --- the real passes compose against pre-existing sibling-area membership -----


class _FakeClient:
    """Minimal introspection client: two custom entities, one custom field each.

    Mirrors the fake in ``test_reconcile_area_scoping.py`` so the real entity and
    field passes run end-to-end against pre-seeded membership in the other areas.
    """

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


def test_real_entity_and_field_passes_preserve_other_seeded_areas(v2_env):
    """Entity + field reconcile leave every non-audited area's slice untouched.

    The five areas the entity/field passes never write — association, role, team,
    layout, filtered_tab — carry a prior present row. Running both real passes in
    one audit creates the entity and field slices without sweeping any of the
    five sibling areas to absent (acceptance items 4 and 5 at full width).
    """
    other_areas = {
        "association": "ASC-700",
        "role": "ROL-700",
        "team": "TEAM-700",
        "layout": "LAY-700",
        "filtered_tab": "FTB-700",
    }
    with session_scope() as s:
        iid = _make_instance(s)
        for member_type, member_id in other_areas.items():
            membership_repo.upsert_membership(
                s,
                instance_identifier=iid,
                member_type=member_type,
                member_identifier=member_id,
                state="present",
            )

        reconcile.reconcile_entities(s, instance_identifier=iid, client=_FakeClient())
        reconcile.reconcile_fields(s, instance_identifier=iid, client=_FakeClient())

        # The two audited areas now have rows.
        assert _ids(s, iid, "entity")
        assert _ids(s, iid, "field")
        # Every other area's prior row survives present — none swept absent.
        for member_type, member_id in other_areas.items():
            assert _ids(s, iid, member_type) == {member_id}
            assert _state_of(s, iid, member_type, member_id) == "present"
