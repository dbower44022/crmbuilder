"""Mapping-candidate (defer-for-review) workflow scoping — WTK-263 / PI-255.

These tests pin the *dispatch* decision in
:mod:`crmbuilder_v2.introspect.reconcile`: the candidate-gated "defer-for-review"
workflow runs **only** for a purely external ``source`` instance migrating in
from a separate system, and **never** for a ``both``-role instance (a deployed-to
instance whose live structure maps to the design by neutral name — the 06-26 CBM
defect this scoping closes, DEC-648 narrowed by REQ-393 / WTK-256).

Existing coverage in :mod:`tests.crmbuilder_v2.api.test_instance_audit_api`
exercises the same branching end-to-end through the multi-area audit endpoint;
this module proves the switch directly at the reconcile-function level for each
of the three candidate-gated object kinds (entities / fields / associations), so
a regression in the dispatch surfaces without the API in the loop. The presence
of the ``candidates`` key in a reconcile summary is the observable proof that the
candidate-gated path ran (the drift path's summary has no such key).
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import instances as instances_repo
from crmbuilder_v2.access.repositories import mapping_candidate as candidate_repo
from crmbuilder_v2.introspect import reconcile


class _FakeClient:
    """A minimal introspection client: two custom entities, one link.

    Mirrors the shape the reconcile functions read (scopes / fields / links /
    collection / i18n) without any of the security or report-filter surface the
    candidate-gated path does not touch.
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
        if entity == "CEngagement":
            return (200, {"dueses": {"type": "hasMany", "entity": "CDues"}})
        return (200, {"engagement": {"type": "belongsTo", "entity": "CEngagement"}})


def _make_instance(s, role):
    return instances_repo.create_instance(
        s, name=f"{role}-inst", url="https://x.example.org", role=role
    )["instance_identifier"]


# --- the switch itself ------------------------------------------------------


def test_audit_is_source_gates_only_external_source(v2_env):
    """Only a ``source`` instance is candidate-gated; ``both`` / ``target`` are not."""
    with session_scope() as s:
        src = _make_instance(s, "source")
        both = _make_instance(s, "both")
        tgt = _make_instance(s, "target")
        assert reconcile._audit_is_source(s, src) is True
        assert reconcile._audit_is_source(s, both) is False
        assert reconcile._audit_is_source(s, tgt) is False
    # A missing instance defaults to the drift path (the 404 is handled upstream).
    with session_scope() as s:
        assert reconcile._audit_is_source(s, "INST-999") is False


# --- entities ---------------------------------------------------------------


def test_source_entities_run_defer_for_review_workflow(v2_env):
    """A ``source`` audit surfaces undecided entities as candidates and creates
    no canonical objects — the defer-for-review workflow runs."""
    with session_scope() as s:
        iid = _make_instance(s, "source")
        summary = reconcile.reconcile_entities(
            s, instance_identifier=iid, client=_FakeClient()
        )
        # The candidate-gated path's summary carries a ``candidates`` key.
        assert "candidates" in summary
        assert summary["created"] == 0
        assert summary["candidates"] == 2
        cands = candidate_repo.list_candidates(
            s, instance_identifier=iid, candidate_type="entity"
        )
        assert {c["source_entity_name"] for c in cands} == {"CEngagement", "CDues"}


def test_both_entities_skip_defer_for_review_workflow(v2_env):
    """A ``both`` audit runs the drift reconcile — canonical objects are created
    by neutral name and no mapping candidate is ever raised."""
    with session_scope() as s:
        iid = _make_instance(s, "both")
        summary = reconcile.reconcile_entities(
            s, instance_identifier=iid, client=_FakeClient()
        )
        # The drift path's summary has no ``candidates`` key at all.
        assert "candidates" not in summary
        assert summary["created"] == 2
        assert summary["present"] == 2
        # Nothing was deferred for review — the failure mode this scoping closes.
        assert candidate_repo.list_candidates(s, instance_identifier=iid) == []


# --- fields -----------------------------------------------------------------


def test_source_fields_run_defer_for_review_workflow(v2_env):
    """A ``source`` field audit is candidate-gated: with no entity yet mapped,
    every field is deferred (seen == 0) but the candidate-gated path still ran."""
    with session_scope() as s:
        iid = _make_instance(s, "source")
        summary = reconcile.reconcile_fields(
            s, instance_identifier=iid, client=_FakeClient()
        )
        assert "candidates" in summary
        # Fields defer until the parent entity is mapped (DEC-651).
        assert summary["seen"] == 0


def test_both_fields_skip_defer_for_review_workflow(v2_env):
    """A ``both`` field audit runs the drift reconcile with no candidate gating."""
    with session_scope() as s:
        iid = _make_instance(s, "both")
        summary = reconcile.reconcile_fields(
            s, instance_identifier=iid, client=_FakeClient()
        )
        assert "candidates" not in summary
        # The one custom field on each entity reconciles to present.
        assert summary["seen"] == 2
        assert summary["present"] == 2
        assert candidate_repo.list_candidates(s, instance_identifier=iid) == []


# --- associations -----------------------------------------------------------


def test_source_associations_run_defer_for_review_workflow(v2_env):
    """A ``source`` association audit is candidate-gated: with neither endpoint
    mapped, the relationship is deferred but the candidate-gated path ran."""
    with session_scope() as s:
        iid = _make_instance(s, "source")
        summary = reconcile.reconcile_associations(
            s, instance_identifier=iid, client=_FakeClient()
        )
        assert "candidates" in summary
        # Both endpoints unmapped → nothing is seen (DEC-654 deferral).
        assert summary["seen"] == 0


def test_both_associations_skip_defer_for_review_workflow(v2_env):
    """A ``both`` association audit runs the drift reconcile with no candidate
    gating, matching both endpoints by neutral name."""
    with session_scope() as s:
        iid = _make_instance(s, "both")
        # Seed canonical endpoints first (the drift path anchors links to them).
        reconcile.reconcile_entities(
            s, instance_identifier=iid, client=_FakeClient()
        )
        summary = reconcile.reconcile_associations(
            s, instance_identifier=iid, client=_FakeClient()
        )
        assert "candidates" not in summary
        # The one owning link (CEngagement -> CDues) reconciles to a present
        # association between the two canonical entities.
        assert summary["seen"] == 1
        assert summary["present"] == 1
        assert candidate_repo.list_candidates(s, instance_identifier=iid) == []
