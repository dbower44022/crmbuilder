"""No-resolution membership preservation — WTK-269 / PI-353 (REQ-394 §3.2).

The sibling slice to ``test_reconcile_area_scoping.py`` (§3.4, the per-area write
boundary). These tests pin the **read-success gate** on the absent sweep: a
reconcile pass whose live read of its area did **not** succeed must not sweep
that area's inventory to ``absent`` — recording absence from a non-observation
is the REL-038 defect that wiped CBM Prod while reporting success. REQ-394's
operational rule (sentence 3): an object is set ``absent`` *only* when the live
instance was read successfully and that object is absent from it.

The discriminator is therefore **read success**, not "the pass resolved nothing":
a successful read that genuinely enumerated an empty area still sweeps (an empty
"seen" set with ``read_succeeded=True``), while a failed / inconclusive read
preserves the prior inventory whatever it resolved.

The chokepoint is :class:`reconcile._AreaMembershipWriter`, which carries the
read-success signal into :meth:`~reconcile._AreaMembershipWriter.sweep_absent`
(threaded on to the storage gate WTK-267 added). All ten membership-writing
passes route through it (WTK-268). Companion to ``test_instance_membership.py``,
which pins the genuinely-empty / source-vanished sweeps from a *successful* read.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import instances as instances_repo
from crmbuilder_v2.introspect import reconcile


def _make_instance(s, role="both"):
    return instances_repo.create_instance(
        s, name=f"{role}-inst", url="https://x.example.org", role=role
    )["instance_identifier"]


def _writer(s, iid, *, read_succeeded):
    return reconcile._AreaMembershipWriter(
        s,
        instance_identifier=iid,
        member_type="entity",
        last_audited_at=datetime.now(UTC),
        read_succeeded=read_succeeded,
    )


def _seed_present(s, iid, *member_ids, state="present"):
    for mid in member_ids:
        membership_repo.upsert_membership(
            s,
            instance_identifier=iid,
            member_type="entity",
            member_identifier=mid,
            state=state,
        )


def _entity_states(s, iid):
    return {
        r["member_identifier"]: r["state"]
        for r in membership_repo.list_memberships(
            s, instance_identifier=iid, member_type="entity"
        )
    }


# --- a failed/inconclusive read preserves -----------------------------------


def test_failed_read_preserves_inventory(v2_env):
    """``read_succeeded=False`` makes the sweep a no-op — prior rows preserved.

    The defining WTK-269 behaviour: a pass whose live read did not succeed leaves
    the area's existing ``present`` / ``drifted`` rows unchanged rather than
    wiping them from a non-observation (REQ-394 §3.2).
    """
    with session_scope() as s:
        iid = _make_instance(s)
        _seed_present(s, iid, "ENT-500")
        _seed_present(s, iid, "ENT-501", state="drifted")
        writer = _writer(s, iid, read_succeeded=False)
        # The failed read resolved nothing; the sweep must touch nothing.
        swept = writer.sweep_absent()
        assert swept == 0
        assert _entity_states(s, iid) == {"ENT-500": "present", "ENT-501": "drifted"}


def test_mark_read_failed_disarms_the_sweep(v2_env):
    """A writer flipped to read-failed mid-pass preserves the prior inventory."""
    with session_scope() as s:
        iid = _make_instance(s)
        _seed_present(s, iid, "ENT-510")
        writer = _writer(s, iid, read_succeeded=True)
        writer.mark_read_failed()
        assert writer.sweep_absent() == 0
        assert _entity_states(s, iid) == {"ENT-510": "present"}


# --- a successful read records absence (the gate is read-success, not empty) -


def test_successful_empty_read_sweeps_genuinely_empty_area(v2_env):
    """A successful read that enumerated an empty area sweeps prior rows absent.

    ``read_succeeded=True`` with an empty "seen" set is a positive observation
    that the area genuinely holds nothing — the legitimate absent transition the
    no-resolution gate must NOT suppress (REQ-394 sentence 3; WTK-267).
    """
    with session_scope() as s:
        iid = _make_instance(s)
        _seed_present(s, iid, "ENT-520", "ENT-521")
        writer = _writer(s, iid, read_succeeded=True)
        # Nothing resolved, but the read succeeded → genuinely empty → sweep.
        swept = writer.sweep_absent()
        assert swept == 2
        assert _entity_states(s, iid) == {"ENT-520": "absent", "ENT-521": "absent"}


def test_successful_partial_read_marks_only_unseen_absent(v2_env):
    """With ≥1 object resolved, only the rows missing from the read go absent."""
    with session_scope() as s:
        iid = _make_instance(s)
        _seed_present(s, iid, "ENT-600", "ENT-601")
        writer = _writer(s, iid, read_succeeded=True)
        writer.upsert("ENT-600", "present")  # re-resolved; ENT-601 genuinely gone
        swept = writer.sweep_absent()
        assert swept == 1
        assert _entity_states(s, iid) == {"ENT-600": "present", "ENT-601": "absent"}


# --- the gate is per-area (composes with WTK-268 scoping) -------------------


def test_failed_read_does_not_disturb_other_areas(v2_env):
    """A failed-read entity pass preserves its own AND every other area's slice."""
    with session_scope() as s:
        iid = _make_instance(s)
        membership_repo.upsert_membership(
            s,
            instance_identifier=iid,
            member_type="field",
            member_identifier="FLD-700",
            state="present",
        )
        _seed_present(s, iid, "ENT-700")
        _writer(s, iid, read_succeeded=False).sweep_absent()
        assert _entity_states(s, iid) == {"ENT-700": "present"}
        field_rows = membership_repo.list_memberships(
            s, instance_identifier=iid, member_type="field"
        )
        assert [r["member_identifier"] for r in field_rows] == ["FLD-700"]
        assert field_rows[0]["state"] == "present"


def test_drift_pass_threads_read_success_true_by_default(v2_env):
    """A pass reaching the sweep had a successful area read → it sweeps.

    Reaching :meth:`sweep_absent` implies the pass validated its area read (a
    failed read raises :class:`reconcile.ReconcileError` before the writer is
    built), so the writer's default ``read_succeeded=True`` is the correct signal
    and the genuinely-empty / vanished sweeps remain intact.
    """
    with session_scope() as s:
        iid = _make_instance(s)
        # A writer built on the happy path defaults to read_succeeded=True.
        writer = reconcile._AreaMembershipWriter(
            s,
            instance_identifier=iid,
            member_type="entity",
            last_audited_at=datetime.now(UTC),
        )
        assert writer._read_succeeded is True
        # Construction still rejects an unknown area (WTK-268 contract intact).
        with pytest.raises(reconcile.ReconcileError):
            reconcile._AreaMembershipWriter(
                s,
                instance_identifier=iid,
                member_type="nope",
                last_audited_at=datetime.now(UTC),
                read_succeeded=False,
            )
