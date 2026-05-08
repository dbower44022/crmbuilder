"""Tests for the TopicsPanel hierarchical view build."""

from __future__ import annotations

from crmbuilder_v2.ui.panels.topics import TopicsPanel


def _topic(identifier: str, name: str, parent: str | None = None) -> dict:
    return {
        "identifier": identifier,
        "name": name,
        "parent_topic_identifier": parent,
        "description": "",
    }


def _build_panel(qtbot, qapp):
    """Construct a TopicsPanel with no client; we exercise the build helper."""

    class _Stub:
        def list_topics(self):
            return []

    panel = TopicsPanel(client=_Stub())
    qtbot.addWidget(panel)
    return panel


def test_hierarchy_orders_parents_before_children_with_indent(qapp, qtbot):
    panel = _build_panel(qtbot, qapp)
    topics = [
        _topic("TOP-1", "Root one"),
        _topic("TOP-2", "Child of one", parent="TOP-1"),
        _topic("TOP-3", "Root three"),
        _topic("TOP-4", "Child of three", parent="TOP-3"),
    ]

    out = panel._build_hierarchical_view(topics)

    assert [r["identifier"] for r in out] == ["TOP-1", "TOP-2", "TOP-3", "TOP-4"]
    assert out[0]["_display_name"] == "Root one"
    assert out[1]["_display_name"] == "    Child of one"
    assert out[2]["_display_name"] == "Root three"
    assert out[3]["_display_name"] == "    Child of three"


def test_orphan_topics_are_appended_with_indicator(qapp, qtbot):
    panel = _build_panel(qtbot, qapp)
    topics = [
        _topic("TOP-A", "A root"),
        _topic("TOP-X", "Orphaned X", parent="MISSING"),
    ]

    out = panel._build_hierarchical_view(topics)

    assert [r["identifier"] for r in out] == ["TOP-A", "TOP-X"]
    assert out[1]["_display_name"].endswith("(orphan)")


def test_cycle_does_not_recurse_infinitely(qapp, qtbot):
    panel = _build_panel(qtbot, qapp)
    # TOP-A -> TOP-B and TOP-B -> TOP-A. Neither has a None parent, so
    # neither appears as a root; they fall through to the orphan path.
    topics = [
        _topic("TOP-A", "A", parent="TOP-B"),
        _topic("TOP-B", "B", parent="TOP-A"),
    ]

    out = panel._build_hierarchical_view(topics)
    identifiers = [r["identifier"] for r in out]
    assert sorted(identifiers) == ["TOP-A", "TOP-B"]
    # Each appears at most once.
    assert len(set(identifiers)) == len(identifiers)


def test_deep_hierarchy_indents_proportional_to_depth(qapp, qtbot):
    panel = _build_panel(qtbot, qapp)
    topics = [
        _topic("TOP-1", "Level zero"),
        _topic("TOP-2", "Level one", parent="TOP-1"),
        _topic("TOP-3", "Level two", parent="TOP-2"),
    ]

    out = panel._build_hierarchical_view(topics)

    assert out[0]["_display_name"] == "Level zero"
    assert out[1]["_display_name"] == "    Level one"
    assert out[2]["_display_name"] == "        Level two"
