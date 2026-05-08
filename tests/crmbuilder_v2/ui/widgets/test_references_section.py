"""Tests for ReferencesSection widget."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel

from crmbuilder_v2.ui.widgets.references_section import ReferencesSection


def _payload(*, as_target=None, as_source=None) -> dict:
    return {
        "as_target": list(as_target or ()),
        "as_source": list(as_source or ()),
    }


def _label_texts(widget) -> list[str]:
    return [lbl.text() for lbl in widget.findChildren(QLabel)]


def test_empty_payload_renders_none_placeholder(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(section)
    texts = _label_texts(section)
    assert any("References" in t for t in texts)
    assert any("(none)" in t for t in texts)


def test_inbound_only_renders_inbound_section_with_count(qapp, qtbot):
    payload = _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            }
        ]
    )
    section = ReferencesSection("decision", "DEC-001", payload)
    qtbot.addWidget(section)
    texts = _label_texts(section)
    assert any("Inbound (1)" in t for t in texts)
    assert any("Outbound (0)" in t for t in texts)
    assert any("decided_in (1)" in t for t in texts)
    assert any("SES-002" in t for t in texts)


def test_outbound_only_renders_outbound_section(qapp, qtbot):
    payload = _payload(
        as_source=[
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "decision",
                "target_id": "DEC-007",
                "relationship": "supersedes",
            }
        ]
    )
    section = ReferencesSection("decision", "DEC-018", payload)
    qtbot.addWidget(section)
    texts = _label_texts(section)
    assert any("Inbound (0)" in t for t in texts)
    assert any("Outbound (1)" in t for t in texts)
    assert any("supersedes (1)" in t for t in texts)
    assert any("DEC-007" in t for t in texts)


def test_grouping_by_relationship_with_multiple_per_group(qapp, qtbot):
    payload = _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
            {
                "source_type": "session",
                "source_id": "SES-003",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
            {
                "source_type": "topic",
                "source_id": "TOP-1",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "is_about",
            },
        ]
    )
    section = ReferencesSection("decision", "DEC-001", payload)
    qtbot.addWidget(section)
    texts = _label_texts(section)
    assert any("Inbound (3)" in t for t in texts)
    assert any("decided_in (2)" in t for t in texts)
    assert any("is_about (1)" in t for t in texts)


def test_exclude_relationships_filters_outbound(qapp, qtbot):
    payload = _payload(
        as_source=[
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "decision",
                "target_id": "DEC-007",
                "relationship": "supersedes",
            },
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "topic",
                "target_id": "TOP-1",
                "relationship": "is_about",
            },
        ]
    )
    section = ReferencesSection(
        "decision",
        "DEC-018",
        payload,
        exclude_relationships={"supersedes"},
    )
    qtbot.addWidget(section)
    texts = _label_texts(section)
    assert any("Outbound (1)" in t for t in texts)
    assert not any("supersedes" in t for t in texts)
    assert any("is_about (1)" in t for t in texts)


def test_link_click_emits_navigate_requested(qapp, qtbot):
    payload = _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            }
        ]
    )
    section = ReferencesSection("decision", "DEC-001", payload)
    qtbot.addWidget(section)
    received: list[tuple[str, str]] = []
    section.navigate_requested.connect(lambda t, i: received.append((t, i)))
    # Find the link label and emit linkActivated directly (offscreen Qt
    # platform doesn't render or hit-test, matching existing test patterns).
    link_label = None
    for label in section.findChildren(QLabel):
        text = label.text() or ""
        if "SES-002" in text and "<a href" in text:
            link_label = label
            break
    assert link_label is not None, "expected a link label for SES-002"
    link_label.linkActivated.emit("session:SES-002")
    assert received == [("session", "SES-002")]


def test_excluded_relationship_with_no_remaining_renders_none(qapp, qtbot):
    payload = _payload(
        as_source=[
            {
                "source_type": "decision",
                "source_id": "DEC-018",
                "target_type": "decision",
                "target_id": "DEC-007",
                "relationship": "supersedes",
            }
        ]
    )
    section = ReferencesSection(
        "decision",
        "DEC-018",
        payload,
        exclude_relationships={"supersedes"},
    )
    qtbot.addWidget(section)
    texts = _label_texts(section)
    # The single outbound is filtered, and no inbound exists, so the
    # widget should render the single (none) placeholder under the
    # main References heading.
    assert any("(none)" in t for t in texts)
