"""Field-permission audit-IN + drift reconcile tests — PI-051 (REQ-129).

Covers :func:`reconcile_field_permissions`: capturing a live Role's ``fieldData``
matrix as ``field_permission_rule`` design records, drift-flagging confirmed
rules via ``deployment_status`` without mutating intent, skipping+logging orphan
cells, the empty-cell skip, and the absent sweep.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import field as field_repo
from crmbuilder_v2.access.repositories import (
    field_permission_rule as fpr_repo,
)
from crmbuilder_v2.access.repositories import instances as inst_repo
from crmbuilder_v2.access.repositories import roles as role_repo
from crmbuilder_v2.introspect.reconcile import (
    ReconcileError,
    reconcile_field_permissions,
)


def _custom():
    return {"entity": True, "customizable": True, "isCustom": True}


class _FakeClient:
    """Scopes + roles the field-permission reconcile reads."""

    def __init__(self, scopes, roles, *, scope_status=200, role_status=200):
        self._scopes = scopes
        self._roles = roles
        self._scope_status = scope_status
        self._role_status = role_status

    def get_all_scopes(self):
        return (self._scope_status, self._scopes)

    def get_roles(self):
        return (self._role_status, {"list": self._roles})


def _make_instance(s):
    return inst_repo.create_instance(
        s, name="src", url="https://src.example.org", role="source"
    )["instance_identifier"]


def _seed_entity_with_fields(s, *, entity_name, field_names):
    eid = entity_repo.create_entity(s, name=entity_name, description="x")[
        "entity_identifier"
    ]
    fids = {}
    for fn in field_names:
        fids[fn] = field_repo.create_field(
            s,
            field_belongs_to_entity_identifier=eid,
            name=fn,
            description="x",
            type="text",
        )["field_identifier"]
    return eid, fids


def _role(s, name):
    return role_repo.create_role(s, name=name)["role_identifier"]


# --- capture ---------------------------------------------------------------


def test_create_candidate_rules_from_field_data(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _seed_entity_with_fields(
            s, entity_name="MentorProfile",
            field_names=["valueProvided", "notes", "secret"],
        )
        _role(s, "Coordinator")
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            roles=[{
                "name": "Coordinator",
                "fieldData": {"CMentorProfile": {
                    "valueProvided": {"read": "yes", "edit": "yes"},
                    "notes": {"read": "yes", "edit": "no"},
                    "secret": {"read": "no", "edit": "no"},
                }},
            }],
        )
        summary = reconcile_field_permissions(
            s, instance_identifier=iid, client=client
        )
        assert summary["seen"] == 3
        assert summary["created"] == 3
        assert summary["skipped"] == 0
        rules = fpr_repo.list_field_permission_rules(s)
        by_level = {
            r["field_permission_rule_permission_level"] for r in rules
        }
        assert by_level == {"read_write", "read_only", "no_access"}
        # Captured as design intent awaiting confirmation.
        assert all(
            r["field_permission_rule_status"] == "candidate"
            and r["field_permission_rule_deployment_status"] == "pending"
            for r in rules
        )


def test_empty_cell_skipped(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _seed_entity_with_fields(
            s, entity_name="MentorProfile", field_names=["valueProvided"]
        )
        _role(s, "Coordinator")
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            roles=[{"name": "Coordinator", "fieldData": {
                "CMentorProfile": {"valueProvided": {"read": "", "edit": ""}}
            }}],
        )
        summary = reconcile_field_permissions(
            s, instance_identifier=iid, client=client
        )
        # An empty/inherit cell is not a restriction rule — not even "seen".
        assert summary["seen"] == 0
        assert summary["created"] == 0
        assert fpr_repo.list_field_permission_rules(s) == []


def test_orphan_field_skipped_and_logged(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _seed_entity_with_fields(
            s, entity_name="MentorProfile", field_names=["valueProvided"]
        )
        _role(s, "Coordinator")
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            roles=[{"name": "Coordinator", "fieldData": {"CMentorProfile": {
                "valueProvided": {"read": "yes", "edit": "no"},
                "ghostField": {"read": "no", "edit": "no"},  # no design field
            }}}],
        )
        log: list[tuple[str, str]] = []
        summary = reconcile_field_permissions(
            s, instance_identifier=iid, client=client,
            progress=lambda m, lvl: log.append((m, lvl)),
        )
        assert summary["seen"] == 2
        assert summary["created"] == 1
        assert summary["skipped"] == 1
        assert len(fpr_repo.list_field_permission_rules(s)) == 1
        assert any(
            "ghostField" in m and lvl == "warning" for m, lvl in log
        )


# --- drift -----------------------------------------------------------------


def _confirmed_rule(s, *, role, field, level, deployment_status="pending"):
    return fpr_repo.create_field_permission_rule(
        s, name=f"r {field}", role=role, target_field=field,
        permission_level=level, status="confirmed",
        deployment_status=deployment_status,
    )


def test_confirmed_rule_marked_deployed_when_matches(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _, fids = _seed_entity_with_fields(
            s, entity_name="MentorProfile", field_names=["valueProvided"]
        )
        rid = _role(s, "Coordinator")
        _confirmed_rule(
            s, role=rid, field=fids["valueProvided"], level="read_write"
        )
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            roles=[{"name": "Coordinator", "fieldData": {"CMentorProfile": {
                "valueProvided": {"read": "yes", "edit": "yes"},
            }}}],
        )
        summary = reconcile_field_permissions(
            s, instance_identifier=iid, client=client
        )
        assert summary["created"] == 0
        assert summary["deployed"] == 1
        assert summary["drifted"] == 0
        rule = fpr_repo.list_field_permission_rules(s)[0]
        assert rule["field_permission_rule_deployment_status"] == "deployed"


def test_confirmed_rule_drift_when_level_diverges(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _, fids = _seed_entity_with_fields(
            s, entity_name="MentorProfile", field_names=["valueProvided"]
        )
        rid = _role(s, "Coordinator")
        _confirmed_rule(
            s, role=rid, field=fids["valueProvided"], level="read_only"
        )
        # Live grants edit — diverges from the design's read_only intent.
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            roles=[{"name": "Coordinator", "fieldData": {"CMentorProfile": {
                "valueProvided": {"read": "yes", "edit": "yes"},
            }}}],
        )
        summary = reconcile_field_permissions(
            s, instance_identifier=iid, client=client
        )
        assert summary["drifted"] == 1
        rule = fpr_repo.list_field_permission_rules(s)[0]
        assert rule["field_permission_rule_deployment_status"] == "drift"
        # Intent is never overwritten by the audit.
        assert rule["field_permission_rule_permission_level"] == "read_only"


def test_absent_sweep_drifts_deployed_rule(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _, fids = _seed_entity_with_fields(
            s, entity_name="MentorProfile", field_names=["valueProvided"]
        )
        rid = _role(s, "Coordinator")
        # A rule previously verified deployed, but the live cell is now gone.
        _confirmed_rule(
            s, role=rid, field=fids["valueProvided"], level="read_write",
            deployment_status="deployed",
        )
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            roles=[{"name": "Coordinator", "fieldData": {}}],
        )
        summary = reconcile_field_permissions(
            s, instance_identifier=iid, client=client
        )
        assert summary["absent"] == 1
        rule = fpr_repo.list_field_permission_rules(s)[0]
        assert rule["field_permission_rule_deployment_status"] == "drift"


def test_non_confirmed_rule_left_untouched(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _, fids = _seed_entity_with_fields(
            s, entity_name="MentorProfile", field_names=["valueProvided"]
        )
        rid = _role(s, "Coordinator")
        # A candidate rule already exists for this cell.
        fpr_repo.create_field_permission_rule(
            s, name="cand", role=rid, target_field=fids["valueProvided"],
            permission_level="read_write",
        )
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            roles=[{"name": "Coordinator", "fieldData": {"CMentorProfile": {
                "valueProvided": {"read": "yes", "edit": "yes"},
            }}}],
        )
        summary = reconcile_field_permissions(
            s, instance_identifier=iid, client=client
        )
        assert summary["created"] == 0
        assert summary["present"] == 1
        rule = fpr_repo.list_field_permission_rules(s)[0]
        # Untouched — still candidate/pending (the deploy gate forbids a
        # non-pending status on a non-confirmed rule).
        assert rule["field_permission_rule_status"] == "candidate"
        assert rule["field_permission_rule_deployment_status"] == "pending"


def test_role_not_in_inventory_skipped(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        _seed_entity_with_fields(
            s, entity_name="MentorProfile", field_names=["valueProvided"]
        )
        # No Coordinator role record seeded.
        client = _FakeClient(
            scopes={"CMentorProfile": _custom()},
            roles=[{"name": "Coordinator", "fieldData": {"CMentorProfile": {
                "valueProvided": {"read": "yes", "edit": "yes"},
            }}}],
        )
        log: list[tuple[str, str]] = []
        summary = reconcile_field_permissions(
            s, instance_identifier=iid, client=client,
            progress=lambda m, lvl: log.append((m, lvl)),
        )
        assert summary["created"] == 0
        assert fpr_repo.list_field_permission_rules(s) == []
        assert any("not in inventory" in m for m, _ in log)


def test_bad_status_raises(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient(scopes={}, roles=[], scope_status=500)
        with pytest.raises(ReconcileError):
            reconcile_field_permissions(
                s, instance_identifier=iid, client=client
            )
