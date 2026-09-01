"""The governed-settings audit area — PI-406 (REQ-485 / REQ-488).

Pins the area's observational honesty: what the carrier holds is recorded as
membership, a value the design has not declared stays an observation (the
not-captured verdict belongs to the comparison), a key the carrier lacks sweeps
to absent, and a *failed* read never infers absence — while an absent carrier
(404) is a positive observation that the instance holds no governed values.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import instance_membership as membership_repo
from crmbuilder_v2.access.repositories import instances as instances_repo
from crmbuilder_v2.access.repositories import system_settings as settings_repo
from crmbuilder_v2.introspect.reconcile import reconcile_system_settings


class _CarrierClient:
    """Serves the one settings-read call with a canned status/body."""

    def __init__(self, status=200, values=None, record=True):
        if status != 200:
            self._response = (status, None)
        elif not record:
            self._response = (200, {"total": 0, "list": []})
        else:
            self._response = (
                200,
                {"total": 1, "list": [{"id": "r1", "settings": values or {}}]},
            )

    def get_records(self, entity, **kwargs):
        return self._response


def _setup(s, *, declared=...):
    """One instance + one governed setting; ``declared`` sets its value row."""
    iid = instances_repo.create_instance(
        s, name="chapter", url="https://x.example.org", role="both"
    )["instance_identifier"]
    sid = settings_repo.create_system_setting(
        s, key="orgName", name="Organization name", value_type="text",
        status="confirmed",
    )["system_setting_identifier"]
    if declared is not ...:
        settings_repo.set_value(
            s, system_setting_identifier=sid, instance_identifier=iid,
            value=declared,
        )
    return iid, sid


def _membership(s, iid, sid):
    rows = membership_repo.list_memberships(
        s, instance_identifier=iid, member_type="system_setting",
        member_identifier=sid,
    )
    return rows[0] if rows else None


def test_carried_value_matching_the_declaration_is_present(v2_env):
    with session_scope() as s:
        iid, sid = _setup(s, declared="Cleveland")
        summary = reconcile_system_settings(
            s, instance_identifier=iid,
            client=_CarrierClient(values={"orgName": "Cleveland"}),
        )
        assert summary["present"] == 1
        row = _membership(s, iid, sid)
        assert row["state"] == "present"
        assert row["override"] is None


def test_carried_value_differing_from_the_declaration_is_drifted(v2_env):
    with session_scope() as s:
        iid, sid = _setup(s, declared="Cleveland")
        summary = reconcile_system_settings(
            s, instance_identifier=iid,
            client=_CarrierClient(values={"orgName": "Akron"}),
        )
        assert summary["drifted"] == 1
        row = _membership(s, iid, sid)
        assert row["state"] == "drifted"
        assert row["override"] == {"value": "Akron"}


def test_a_value_the_design_never_declared_stays_an_observation(v2_env):
    """The audit records what it saw; not-captured is the comparison's verdict
    to report, never the audit's to suppress (REQ-485)."""
    with session_scope() as s:
        iid, sid = _setup(s)
        reconcile_system_settings(
            s, instance_identifier=iid,
            client=_CarrierClient(values={"orgName": "Akron"}),
        )
        row = _membership(s, iid, sid)
        assert row["state"] == "present"
        assert row["override"] == {"value": "Akron"}


def test_a_key_the_carrier_lacks_sweeps_to_absent(v2_env):
    with session_scope() as s:
        iid, sid = _setup(s, declared="Cleveland")
        summary = reconcile_system_settings(
            s, instance_identifier=iid, client=_CarrierClient(values={}),
        )
        assert summary["absent"] == 1
        assert _membership(s, iid, sid)["state"] == "absent"


def test_an_absent_carrier_is_a_positive_no_values_observation(v2_env):
    with session_scope() as s:
        iid, sid = _setup(s, declared="Cleveland")
        summary = reconcile_system_settings(
            s, instance_identifier=iid, client=_CarrierClient(status=404),
        )
        assert summary["outcome"] == "absent"
        assert summary["absent"] == 1
        assert _membership(s, iid, sid)["state"] == "absent"


def test_a_failed_read_never_infers_absence(v2_env):
    """The exact trap REQ-488 names: a missing grant must not read as an
    instance that holds nothing. Prior membership survives untouched."""
    with session_scope() as s:
        iid, sid = _setup(s, declared="Cleveland")
        membership_repo.upsert_membership(
            s, instance_identifier=iid, member_type="system_setting",
            member_identifier=sid, state="present",
        )
        summary = reconcile_system_settings(
            s, instance_identifier=iid, client=_CarrierClient(status=403),
        )
        assert summary["outcome"] == "forbidden"
        assert "reason" in summary
        assert summary["absent"] == 0
        assert _membership(s, iid, sid)["state"] == "present"


def test_an_unconfirmed_setting_is_not_audited(v2_env):
    with session_scope() as s:
        iid, _ = _setup(s, declared="Cleveland")
        candidate = settings_repo.create_system_setting(
            s, key="oldKey", name="Candidate", value_type="text",
            status="candidate",
        )["system_setting_identifier"]
        reconcile_system_settings(
            s, instance_identifier=iid,
            client=_CarrierClient(values={"oldKey": "x", "orgName": "Cleveland"}),
        )
        assert _membership(s, iid, candidate) is None
