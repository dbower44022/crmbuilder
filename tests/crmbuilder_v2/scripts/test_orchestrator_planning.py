"""Wave-planning tests for the orchestrator driver (PI-081)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MOD = (
    Path(__file__).resolve().parents[3]
    / "crmbuilder-v2"
    / "scripts"
    / "orchestrator"
    / "planning.py"
)
_spec = importlib.util.spec_from_file_location("orch_planning", _MOD)
planning = importlib.util.module_from_spec(_spec)
sys.modules["orch_planning"] = planning  # dataclasses need the module registered
_spec.loader.exec_module(planning)


def _item(ident, area, claimed_by=None):
    return {"identifier": ident, "area": area, "claimed_by": claimed_by}


def test_shared_area_forms_one_cluster():
    plan = planning.partition_wave(
        [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-api"])]
    )
    assert len(plan.clusters) == 1
    assert plan.clusters[0].identifiers == ["PI-001", "PI-002"]
    assert plan.clusters[0].areas == {"v2-api"}


def test_disjoint_areas_form_separate_clusters():
    plan = planning.partition_wave(
        [_item("PI-001", ["v2-api"]), _item("PI-002", ["v2-ui"])]
    )
    assert len(plan.clusters) == 2
    planning.assert_clusters_disjoint(plan.clusters)


def test_transitive_merge_via_shared_areas():
    # A~B share v2-api; B~C share v2-ui => all one cluster.
    plan = planning.partition_wave(
        [
            _item("PI-001", ["v2-api"]),
            _item("PI-002", ["v2-api", "v2-ui"]),
            _item("PI-003", ["v2-ui"]),
        ]
    )
    assert len(plan.clusters) == 1
    assert plan.clusters[0].areas == {"v2-api", "v2-ui"}
    assert plan.clusters[0].identifiers == ["PI-001", "PI-002", "PI-003"]


def test_claimed_items_skipped():
    plan = planning.partition_wave(
        [_item("PI-001", ["v2-api"], claimed_by="CNV-9"), _item("PI-002", ["v2-ui"])]
    )
    assert [it["identifier"] for it in plan.skipped_claimed] == ["PI-001"]
    assert len(plan.clusters) == 1
    assert plan.clusters[0].identifiers == ["PI-002"]


def test_arealess_items_unclustered():
    plan = planning.partition_wave(
        [_item("PI-001", None), _item("PI-002", []), _item("PI-003", ["v2-api"])]
    )
    assert {it["identifier"] for it in plan.unclustered} == {"PI-001", "PI-002"}
    assert len(plan.clusters) == 1


def test_assert_disjoint_raises_on_overlap():
    from copy import deepcopy

    plan = planning.partition_wave([_item("PI-001", ["v2-api"])])
    # Fabricate an overlapping second cluster and confirm the guard fires.
    bad = deepcopy(plan.clusters[0])
    with pytest.raises(AssertionError):
        planning.assert_clusters_disjoint([plan.clusters[0], bad])


def test_depth_is_recorded():
    plan = planning.partition_wave([_item("PI-001", ["v2-api"])], depth=2)
    assert plan.depth == 2
