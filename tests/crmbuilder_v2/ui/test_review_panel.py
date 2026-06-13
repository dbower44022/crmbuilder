"""Requirements Review panel tests (requirements-provenance Phase 6b).

Covers the topic-first review surface: sidebar/registration wiring, a live
refresh against a real TestClient (topics + the three queues), the one write
the panel does (a sign-off round-trip), and the synthetic render paths for the
requirement tree / detail pane / coverage queue that don't depend on the corpus
carrying provenance edges yet (those arrive with Phase 7).
"""

from __future__ import annotations

import pytest
from crmbuilder_v2.api.main import create_app
from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import build_panel
from crmbuilder_v2.ui.panels.review import ReviewPanel
from crmbuilder_v2.ui.sidebar import SIDEBAR_ENTRIES, SIDEBAR_GROUPS
from fastapi.testclient import TestClient


@pytest.fixture
def review_client(v2_env) -> StorageClient:
    sc = StorageClient(
        base_url="http://testserver", client=TestClient(create_app())
    )
    sc.set_active_engagement("ENG-001")
    return sc


def _node(**over) -> dict:
    base = {
        "identifier": "REQ-001",
        "name": "Demo requirement",
        "status": "confirmed",
        "review_state": "needs_review",
        "origin": "human_defined",
        "priority": "high",
        "acceptance_summary": "It does the thing.",
        "defined_in_conversations": ["CNV-001"],
        "planned": False,
        "verified": False,
        "children": [],
    }
    base.update(over)
    return base


# -- registration / wiring ------------------------------------------------


def test_review_entry_registered_in_governance_group():
    assert "Requirements Review" in SIDEBAR_ENTRIES
    for label, entries in SIDEBAR_GROUPS:
        if label == "Governance":
            assert "Requirements Review" in entries
            # It sits after the ADO monitoring panels.
            assert entries.index("Requirements Review") > entries.index("Work Tasks")
            return
    raise AssertionError("Governance group not found")


def test_build_panel_returns_review_panel(review_client, qtbot):
    panel = build_panel("Requirements Review", review_client)
    qtbot.addWidget(panel)
    assert isinstance(panel, ReviewPanel)
    # Subclassing ListDetailPanel is what earns the main-window wiring
    # (connection_lost / navigate_requested signals, refresh-on-select).
    assert isinstance(panel, ListDetailPanel)


# -- live refresh ---------------------------------------------------------


def test_refresh_loads_topics_and_queues(review_client, qtbot):
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel.refresh()
    # The overview fetch (topics + approval + drift + coverage) settles the
    # status label; an empty engagement still reports a topic count.
    qtbot.waitUntil(
        lambda: panel._status_label.text().endswith("topics"), timeout=3000
    )
    # Coverage tab always has the three group rows.
    assert panel._coverage_tree.topLevelItemCount() == 3
    # The coverage summary line is populated.
    assert "Orphan planning items" in panel._coverage_summary.text()


def test_signoff_round_trips_through_panel(review_client, qtbot):
    # A topic to sign off on (topics carry no provenance gates).
    topic = review_client.create_topic(
        {"name": "Review target", "description": "d"}
    )
    topic_id = topic["identifier"]

    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._current_topic_id = topic_id

    panel._submit_signoff(topic_id, "Doug", "Reviewed and attested.")
    qtbot.waitUntil(
        lambda: panel._signoff_list.count() >= 1
        and "Doug" in panel._signoff_list.item(0).text(),
        timeout=3000,
    )
    assert "Reviewed and attested." in panel._signoff_list.item(0).text()
    # And it is queryable through the client surface the panel uses.
    assert any(
        s["signoff_reviewer"] == "Doug"
        for s in review_client.list_signoffs(topic_id)
    )


# -- synthetic render paths (provenance-free corpus) ----------------------


def test_requirement_tree_and_detail_render(review_client, qtbot):
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    child = _node(identifier="REQ-002", name="Child", children=[])
    root = _node(children=[child])
    panel._fill_req_tree([root])
    assert panel._req_tree.topLevelItemCount() == 1
    top = panel._req_tree.topLevelItem(0)
    assert top.childCount() == 1
    # Flags column surfaces NEEDS REVIEW + unbuilt + unverified.
    flags = top.text(2)
    assert "NEEDS REVIEW" in flags and "unbuilt" in flags and "unverified" in flags

    detail = panel._render_req_detail(root)
    assert detail is not None  # builds without error (spine + provenance button)


def test_coverage_fill_groups_and_counts(review_client, qtbot):
    panel = ReviewPanel(review_client)
    qtbot.addWidget(panel)
    panel._fill_coverage(
        {
            "orphan_planning_items": [
                {"identifier": "PI-9", "title": "t", "item_type": "feature", "status": "Draft"}
            ],
            "unbuilt_requirements": [],
            "conversations_without_requirement": [],
            "summary": {
                "orphan_planning_items": 1,
                "unbuilt_requirements": 0,
                "conversations_without_requirement": 0,
            },
        }
    )
    assert panel._coverage_tree.topLevelItemCount() == 3
    orphan_group = panel._coverage_tree.topLevelItem(0)
    assert "Orphan planning items (1)" in orphan_group.text(0)
    assert orphan_group.childCount() == 1
