"""Governance Rules panel — effective view and supersedes provenance (REQ-537 / REQ-538, PI-441).

The panel's ``View:`` selector switches between the stored rows and the
override-resolved ruleset for the active engagement (PI-435); the Shadows
column and the detail pane's Supersedes / Superseded by rows expose the
``supersedes`` provenance edges recorded when an override is created.
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.panels.registry_rules import (
    VIEW_ALL,
    VIEW_EFFECTIVE,
    GovernanceRulesPanel,
)
from fastapi.testclient import TestClient
from PySide6.QtWidgets import QLabel


@pytest.fixture
def registry_client(v2_env) -> StorageClient:
    sc = StorageClient(base_url="http://testserver", client=TestClient(create_app()))
    sc.set_active_engagement("ENG-001")
    return sc


def _rule(client, *, body, rule_type=None, scope="system"):
    payload = {"body": body, "enforcement": "advisory", "scope": scope}
    if rule_type is not None:
        payload["rule_type"] = rule_type
    return client.create_governance_rule(payload)["identifier"]


def _ids(panel) -> list[str]:
    return [panel._model.record_at(i)["identifier"] for i in range(panel._model.rowCount())]


def _row(panel, identifier):
    return next(
        panel._model.record_at(i)
        for i in range(panel._model.rowCount())
        if panel._model.record_at(i)["identifier"] == identifier
    )


def _wait_rows(qtbot, panel, count: int) -> None:
    qtbot.waitUntil(lambda: panel._model.rowCount() == count, timeout=3000)


def _select_view(qtbot, panel, mode: str) -> None:
    combo = panel._view_combo
    combo.setCurrentIndex(combo.findData(mode))


def test_view_selector_switches_between_stored_and_effective(qtbot, registry_client):
    react = _rule(registry_client, body="Custom apps use React.", rule_type="ui_framework")
    angular = _rule(
        registry_client, body="ENG-001 apps use Angular.", rule_type="ui_framework", scope="ENG-001"
    )
    other = _rule(registry_client, body="Never force-push.", rule_type="no_force_push")

    panel = GovernanceRulesPanel(registry_client)
    qtbot.addWidget(panel)
    assert panel.view_mode == VIEW_ALL
    assert panel._view_combo.itemText(1) == "Effective for ENG-001"

    # Stored rows: both the default and the override are listed, no shadows.
    panel.refresh()
    _wait_rows(qtbot, panel, 3)
    assert set(_ids(panel)) == {react, angular, other}
    assert _row(panel, angular)["shadows_display"] == ""

    # Effective view: the override displaces the default and names it.
    _select_view(qtbot, panel, VIEW_EFFECTIVE)
    assert panel.view_mode == VIEW_EFFECTIVE
    _wait_rows(qtbot, panel, 2)
    assert set(_ids(panel)) == {angular, other}
    assert _row(panel, angular)["shadows_display"] == react

    # Back to stored rows: both rows return.
    _select_view(qtbot, panel, VIEW_ALL)
    _wait_rows(qtbot, panel, 3)
    assert set(_ids(panel)) == {react, angular, other}


def test_effective_view_without_overrides_equals_active_system_rules(qtbot, registry_client):
    kept = _rule(registry_client, body="Kept default.", rule_type="k1")
    retired = _rule(registry_client, body="Retired default.", rule_type="k2")
    registry_client.patch_governance_rule(retired, {"status": "retired"})

    panel = GovernanceRulesPanel(registry_client)
    qtbot.addWidget(panel)
    _select_view(qtbot, panel, VIEW_EFFECTIVE)
    _wait_rows(qtbot, panel, 1)
    assert _ids(panel) == [kept]


def test_detail_pane_shows_supersedes_provenance_both_ways(qtbot, registry_client):
    react = _rule(registry_client, body="Custom apps use React.", rule_type="ui_framework")
    angular = _rule(
        registry_client, body="ENG-001 apps use Angular.", rule_type="ui_framework", scope="ENG-001"
    )
    plain = _rule(registry_client, body="Unrelated default.", rule_type="unrelated")

    panel = GovernanceRulesPanel(registry_client)
    qtbot.addWidget(panel)

    def labels(widget) -> list[str]:
        return [lbl.text() for lbl in widget.findChildren(QLabel)]

    # The override supersedes the default it shadows.
    override = registry_client.get_governance_rule(angular)
    extras = panel.fetch_detail_extras(override)
    assert extras == {"supersedes": [react], "superseded_by": []}
    texts = labels(panel.render_detail(override, extras))
    assert "Supersedes" in texts and react in texts
    assert "Superseded by" not in texts

    # The default is superseded by the override, shown with its engagement.
    default = registry_client.get_governance_rule(react)
    extras = panel.fetch_detail_extras(default)
    assert extras == {"supersedes": [], "superseded_by": [(angular, "ENG-001")]}
    texts = labels(panel.render_detail(default, extras))
    assert "Superseded by" in texts and f"{angular} (ENG-001)" in texts
    assert "Supersedes" not in texts

    # A rule with no supersedes edges shows neither row.
    untouched = registry_client.get_governance_rule(plain)
    extras = panel.fetch_detail_extras(untouched)
    assert extras == {"supersedes": [], "superseded_by": []}
    texts = labels(panel.render_detail(untouched, extras))
    assert "Supersedes" not in texts and "Superseded by" not in texts
