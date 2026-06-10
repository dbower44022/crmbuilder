"""Reconcile UI entry tests (offscreen QApplication, no live CRM/worker).

Covers the empty-state gating, tree population + default selection (CHANGED
pre-checked, others not), and the checked-collection helper. The worker and the
live client are not exercised here — detection/apply are tested at the engine
level.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from espo_impl.core.reconcile.engine import DriftReport
from espo_impl.core.reconcile.locators import FieldLocator
from espo_impl.core.reconcile.models import ConfigType, DiffCategory, Difference


@pytest.fixture(scope="module", autouse=True)
def _qapplication():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def _changed(entity="Contact", name="title"):
    return Difference(
        config_type=ConfigType.FIELD,
        category=DiffCategory.CHANGED,
        entity=entity,
        locator=FieldLocator(entity, name, "label"),
        property="label",
        yaml_value="Title",
        crm_value="Account Title",
        source_file=Path("MN-Contact.yaml"),
    )


def _crm_only(entity="Contact", name="newField"):
    return Difference(
        config_type=ConfigType.FIELD,
        category=DiffCategory.CRM_ONLY,
        entity=entity,
        locator=FieldLocator(entity, name, None),
        full_crm_block={"type": "varchar"},
    )


def test_empty_state_when_no_instances():
    from automation.ui.deployment.reconcile_entry import ReconcileEntry

    entry = ReconcileEntry()
    entry.refresh(conn=object(), instance=None, project_folder=None, has_instances=False)

    # isVisibleTo() reports logical visibility without needing the window shown.
    assert entry._empty_label.isVisibleTo(entry)
    assert not entry._content.isVisibleTo(entry)
    assert entry._empty_label.text()
    assert not entry._apply_btn.isEnabled()


def test_tree_populates_and_preselects_changed_only():
    from automation.ui.deployment.reconcile_entry import ReconcileEntry

    entry = ReconcileEntry()
    report = DriftReport(differences=[_changed(), _crm_only()])
    entry._report = report
    entry._populate_tree(report)

    # One entity header -> one config-type group -> two leaf rows.
    assert entry._tree.topLevelItemCount() == 1
    ent = entry._tree.topLevelItem(0)
    assert ent.text(0) == "Contact"
    type_item = ent.child(0)
    assert type_item.childCount() == 2

    # Only the CHANGED row is checked by default; _checked_diffs reflects that.
    checked = entry._checked_diffs()
    assert len(checked) == 1
    assert checked[0].category is DiffCategory.CHANGED
    assert checked[0].property == "label"


def test_diff_label_and_helpers_are_compact():
    from automation.ui.deployment.reconcile_entry import (
        _diff_label,
        _locator_name,
        _short,
    )

    assert _locator_name(_changed()) == "title"
    assert "title.label" in _diff_label(_changed())
    assert "add from CRM" in _diff_label(_crm_only())
    assert len(_short("x" * 500)) <= 70

    # A difference that owns a YAML file names it in its label; a CRM-only
    # addition (no source file yet) does not.
    assert "[MN-Contact.yaml]" in _diff_label(_changed())
    assert "[" not in _diff_label(_crm_only())
