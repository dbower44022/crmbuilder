"""Layout diff tests — drive the comparator with real captured layout payloads.

Fixtures in tests/fixtures/layouts/ are verbatim EspoCRM 9.x API responses, so
these exercise diff_layouts against the exact shape both sides use. Drift
detection delegates to LayoutManager._layouts_match (the deploy comparator), so
identical payloads must be a no-op and a structural change must surface.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from espo_impl.core.reconcile.diff_engine import diff_layouts
from espo_impl.core.reconcile.locators import LayoutLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory

_FIX = Path(__file__).resolve().parents[1] / "fixtures" / "layouts"


def _load(name):
    return json.loads((_FIX / name).read_text())


def test_identical_layout_is_no_drift():
    detail = _load("Contact.detail.json")
    desired = {"Contact": {"detail": detail}}
    live = {"Contact": {"detail": copy.deepcopy(detail)}}

    assert diff_layouts(desired, live) == []


def test_changed_list_column_width_is_flagged():
    cols = _load("Contact.list.json")
    drifted = copy.deepcopy(cols)
    # Someone widened a column in the UI.
    drifted[1]["width"] = drifted[1].get("width", 0) + 7

    desired = {"Contact": {"list": cols}}
    live = {"Contact": {"list": drifted}}
    src = Path("MN/MN-Contact.yaml")

    diffs = diff_layouts(desired, live, source_files={"Contact": {"list": src}})

    assert len(diffs) == 1
    d = diffs[0]
    assert d.config_type is ConfigType.LAYOUT
    assert d.category is DiffCategory.CHANGED
    assert d.property == "list"
    assert d.locator == LayoutLocator("Contact", "list")
    assert d.crm_value == drifted
    assert d.source_file == src


def test_layout_added_in_crm_is_crm_only():
    kanban = _load("Contact.kanban.json")
    desired = {"Contact": {}}
    live = {"Contact": {"kanban": kanban}}

    diffs = diff_layouts(desired, live)

    assert len(diffs) == 1
    assert diffs[0].category is DiffCategory.CRM_ONLY
    assert diffs[0].full_crm_block == kanban
    assert diffs[0].source_file is None  # ask-per-addition


def test_layout_only_in_yaml_is_reported():
    cols = _load("Contact.list.json")
    src = Path("MN/MN-Contact.yaml")
    desired = {"Contact": {"list": cols}}
    live = {"Contact": {}}

    diffs = diff_layouts(desired, live, source_files={"Contact": {"list": src}})

    assert len(diffs) == 1
    assert diffs[0].category is DiffCategory.YAML_ONLY
    assert diffs[0].source_file == src


def test_multiple_layout_types_independent():
    detail = _load("Contact.detail.json")
    cols = _load("Contact.list.json")
    drifted_cols = copy.deepcopy(cols)
    drifted_cols.append({"name": "createdAt", "width": 12})  # extra column in UI

    desired = {"Contact": {"detail": detail, "list": cols}}
    live = {"Contact": {"detail": copy.deepcopy(detail), "list": drifted_cols}}

    diffs = diff_layouts(desired, live)

    # detail unchanged, list drifted -> exactly one CHANGED on 'list'.
    assert len(diffs) == 1
    assert diffs[0].property == "list"
