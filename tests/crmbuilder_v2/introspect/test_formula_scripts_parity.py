"""PI-422 (REQ-122 audit half / DEC-947) — formula scripts captured verbatim.

Oracle: ``tests/test_audit_formula_scripts.py`` (V1): every non-empty script
keyed by hook is kept; sentinel (underscore) keys and blank bodies are dropped;
no formula / non-200 is a no-op. Capture-only (DEC-420): the value lands on the
entity record and drifts when an instance's scripts differ.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import instance_membership as mb
from crmbuilder_v2.introspect.reconcile import _formula_scripts, reconcile_entities

from tests.crmbuilder_v2.access.test_instance_membership import (
    _custom,
    _FakeClient,
    _make_instance,
)

_SCRIPT = "availableCapacity = maximumClientCapacity - currentActiveClients;"


def test_keeps_non_empty_scripts_drops_sentinels_and_blanks():
    assert _formula_scripts(
        {
            "_parse_failed": True,
            "beforeSaveCustomScript": "   ",
            "beforeSaveApiScript": _SCRIPT,
        }
    ) == {"beforeSaveApiScript": _SCRIPT}


def test_no_formula_is_none():
    assert _formula_scripts({"_parse_failed": True}) is None
    assert _formula_scripts(None) is None
    assert _formula_scripts({}) is None


def test_reconcile_captures_scripts_and_reports_drift(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient({"CEngagement": _custom()})
        client._formulas = {"CEngagement": {"beforeSaveCustomScript": _SCRIPT}}
        reconcile_entities(s, instance_identifier=iid, client=client)
        ent = entity_repo.list_entities(s)[0]
        assert ent["entity_formula_scripts"] == {"beforeSaveCustomScript": _SCRIPT}

        client2 = _FakeClient({"CEngagement": _custom()})
        client2._formulas = {"CEngagement": {"beforeSaveCustomScript": "name = 'x';"}}
        s2 = reconcile_entities(s, instance_identifier=iid, client=client2)
        assert s2["drifted"] == 1
        row = mb.list_memberships(s, instance_identifier=iid, member_type="entity")[0]
        assert row["override"]["entity_formula_scripts"] == {
            "beforeSaveCustomScript": "name = 'x';"
        }


def test_instance_without_formula_matches_design_without_formula(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        client = _FakeClient({"CEngagement": _custom()})
        reconcile_entities(s, instance_identifier=iid, client=client)
        assert entity_repo.list_entities(s)[0]["entity_formula_scripts"] is None
        s2 = reconcile_entities(s, instance_identifier=iid, client=client)
        assert s2["drifted"] == 0


def test_repository_patch_normalises_scripts(v2_env):
    with session_scope() as s:
        e = entity_repo.create_entity(
            s, name="Widget", description="x", formula_scripts={"a": _SCRIPT, "b": " "}
        )
        assert e["entity_formula_scripts"] == {"a": _SCRIPT}
        p = entity_repo.patch_entity(s, e["entity_identifier"], formula_scripts={})
        assert p["entity_formula_scripts"] is None
