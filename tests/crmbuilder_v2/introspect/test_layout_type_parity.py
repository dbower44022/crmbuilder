"""PI-423 (REQ-357 / REQ-158) — the V2 audit reads every layout type V1 reads.

The parity oracle is V1 itself: ``AuditManager._layout_types_to_extract`` with
default options is the set of EspoCRM layout names the V1 audit fetches. V2's
neutral vocabulary must map onto exactly that set, and ``reconcile_layouts``
must fetch each one.
"""

from __future__ import annotations

from crmbuilder_v2.access.db import session_scope
from crmbuilder_v2.access.repositories import entity as entity_repo
from crmbuilder_v2.access.repositories import layouts as layout_repo
from crmbuilder_v2.access.vocab import LAYOUT_TYPES
from crmbuilder_v2.introspect.reconcile import _LAYOUT_TYPE_TO_ESPO, reconcile_layouts

from espo_impl.core.reconcile.capture import AuditManager, AuditOptions
from tests.crmbuilder_v2.access.test_instance_membership import (
    _custom,
    _FakeClient,
    _make_instance,
)


def _v1_layout_names() -> set[str]:
    manager = AuditManager.__new__(AuditManager)
    manager._options = AuditOptions()
    return set(manager._layout_types_to_extract())


def test_vocabulary_and_map_agree():
    assert set(_LAYOUT_TYPE_TO_ESPO) == LAYOUT_TYPES


def test_v2_reads_exactly_the_v1_layout_set():
    assert set(_LAYOUT_TYPE_TO_ESPO.values()) == _v1_layout_names()
    assert len(_LAYOUT_TYPE_TO_ESPO) == 18


def test_reconcile_layouts_fetches_every_type(v2_env):
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Engagement", description="x")
        espo_layouts = {name: {"marker": name} for name in _v1_layout_names()}
        client = _FakeClient({"CEngagement": _custom()}, layouts={"CEngagement": espo_layouts})
        summary = reconcile_layouts(s, instance_identifier=iid, client=client)
        assert summary["created"] == 18 and summary["present"] == 18
        stored = {row["layout_type"]: row["layout_content"] for row in layout_repo.list_layouts(s)}
        assert set(stored) == LAYOUT_TYPES
        assert stored["edit"] == {"marker": "edit"}
        assert stored["side_panels_detail"] == {"marker": "sidePanelsDetail"}


def test_empty_layout_bodies_are_not_layouts(v2_env):
    """EspoCRM answers ``false`` / ``[]`` for a type with no stored layout; V1
    skips those (audit_manager._extract_layout) and so must V2 (PI-428 live
    parity finding: 200 of 378 stored bodies on the test instance were empty)."""
    with session_scope() as s:
        iid = _make_instance(s)
        entity_repo.create_entity(s, name="Engagement", description="x")
        client = _FakeClient(
            {"CEngagement": _custom()},
            layouts={"CEngagement": {"detail": {"rows": [["name"]]}, "edit": False,
                                     "filters": [], "sidePanelsDetail": {}}},
        )
        summary = reconcile_layouts(s, instance_identifier=iid, client=client)
        assert summary["created"] == 1
        assert [row["layout_type"] for row in layout_repo.list_layouts(s)] == ["detail"]
