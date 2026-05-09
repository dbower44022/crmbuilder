"""Tests for ReferencesSection widget."""

from __future__ import annotations

from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from PySide6.QtWidgets import QLabel


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


# ---------------------------------------------------------------------------
# v0.3 slice C — write surface (Add reference + per-row right-click delete)
# ---------------------------------------------------------------------------


def _ref_outbound(target_id: str = "DEC-007", ref_id: int = 7) -> dict:
    return {
        "id": ref_id,
        "source_type": "session",
        "source_id": "SES-001",
        "target_type": "decision",
        "target_id": target_id,
        "relationship": "decided_in",
    }


def test_add_reference_button_absent_when_no_client(qapp, qtbot):
    """The button is opt-in: read-only callers (client=None) get no button."""
    from PySide6.QtWidgets import QPushButton

    section = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(section)
    assert (
        section.findChild(QPushButton, "references_section_add_button")
        is None
    )


def test_add_reference_button_renders_when_client_supplied(qapp, qtbot):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QPushButton

    section = ReferencesSection(
        "decision", "DEC-001", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    btn = section.findChild(QPushButton, "references_section_add_button")
    assert btn is not None
    assert btn.text() == "Add reference"


def test_add_reference_click_opens_create_dialog_with_pre_populated_source(
    qapp, qtbot, monkeypatch
):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QDialog, QPushButton

    captured = {}

    class _StubDialog:
        def __init__(self, client, *, pre_populated_source=None, parent=None):
            captured["pre_populated_source"] = pre_populated_source
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_create.ReferenceCreateDialog",
        _StubDialog,
    )
    section = ReferencesSection(
        "decision", "DEC-018", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    btn = section.findChild(QPushButton, "references_section_add_button")
    btn.click()
    assert captured["pre_populated_source"] == ("decision", "DEC-018")
    assert captured["parent"] is section


def test_add_reference_dialog_accept_emits_references_changed(
    qapp, qtbot, monkeypatch
):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QDialog

    class _AcceptDialog:
        def __init__(self, *_a, **_kw):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_create.ReferenceCreateDialog",
        _AcceptDialog,
    )
    section = ReferencesSection(
        "decision", "DEC-018", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    with qtbot.waitSignal(section.references_changed, timeout=2000):
        section._on_add_clicked()


def test_row_right_click_context_menu_present_when_client_supplied(
    qapp, qtbot
):
    """Each rendered link label has a CustomContextMenu policy when
    write surfaces are reachable."""
    from unittest.mock import MagicMock

    section = ReferencesSection(
        "decision",
        "DEC-007",
        _payload(as_source=[_ref_outbound()]),
        client=MagicMock(),
    )
    qtbot.addWidget(section)
    # Find any link-shaped QLabel; it should have CustomContextMenu policy.
    from PySide6.QtCore import Qt

    link_labels = [
        lbl
        for lbl in section.findChildren(QLabel)
        if "<a href=" in lbl.text()
    ]
    assert link_labels  # at least one link rendered
    assert all(
        lbl.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
        for lbl in link_labels
    )


def test_delete_reference_action_opens_delete_dialog(qapp, qtbot, monkeypatch):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QDialog

    captured = {}

    class _StubDialog:
        def __init__(
            self, client, *, reference_id, edge, parent=None
        ):
            captured["reference_id"] = reference_id
            captured["edge"] = edge
            captured["parent"] = parent

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_delete.ReferenceDeleteDialog",
        _StubDialog,
    )
    section = ReferencesSection(
        "decision", "DEC-007", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    section._on_delete_clicked(_ref_outbound(target_id="DEC-007", ref_id=42))
    assert captured["reference_id"] == 42
    assert captured["edge"] == "SES-001 → DEC-007: decided_in"
    assert captured["parent"] is section


def test_delete_reference_dialog_accept_emits_references_changed(
    qapp, qtbot, monkeypatch
):
    from unittest.mock import MagicMock

    from PySide6.QtWidgets import QDialog

    class _AcceptDialog:
        def __init__(self, *_a, **_kw):
            pass

        def exec(self):  # noqa: A003
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(
        "crmbuilder_v2.ui.dialogs.reference_delete.ReferenceDeleteDialog",
        _AcceptDialog,
    )
    section = ReferencesSection(
        "decision", "DEC-007", _payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    with qtbot.waitSignal(section.references_changed, timeout=2000):
        section._on_delete_clicked(_ref_outbound(ref_id=99))


def test_existing_click_to_navigate_preserved(qapp, qtbot):
    """v0.2's left-click-to-navigate stays functional after slice C
    extensions."""
    from unittest.mock import MagicMock

    section = ReferencesSection(
        "decision",
        "DEC-007",
        _payload(as_source=[_ref_outbound()]),
        client=MagicMock(),
    )
    qtbot.addWidget(section)
    received: list[tuple[str, str]] = []
    section.navigate_requested.connect(lambda t, i: received.append((t, i)))
    section._on_link_activated("decision:DEC-007")
    assert received == [("decision", "DEC-007")]
