"""Tests for the inline linked-record preview (PI-118 / WTK-071).

Covers the two reusable presentation classes and their composition with the
PI-116 filter / PI-117 sort + grouping rebuild on the embedded
``ReferencesSection`` and the standalone ``ReferencesPanel``:

- :class:`LinkedRecordPreviewCard` — header + always-available field render,
  the four non-happy states, ``set_enriched`` placement, accessibility.
- :class:`PreviewController` — resolver-driven target resolution, the
  stale-token guard, and the not-found / error read mapping.
- Composition — the controller previews the correct underlying record under
  multi-column sort, under grouping (and offers no card for a group node), and
  only for filtered-in rows; any reorder / regroup / refilter dismisses an open
  card. A no-mutation guard asserts no model mutator runs across an
  open→enrich→dismiss cycle.
- Context-menu regression guard — both surfaces keep their menus byte-identical
  with the preview feature installed.

Follows the offscreen-Qt widget convention (``qtbot.addWidget``, reading
``section._proxy`` / ``section._table`` / ``panel._model``, the ``_payload``
helper shape from ``test_references_section.py``).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.widgets import linked_record_preview as preview_mod
from crmbuilder_v2.ui.widgets.linked_record_preview import (
    LinkedRecordPreviewCard,
    PreviewController,
    extract_preview_fields,
)
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection
from PySide6.QtCore import QModelIndex, QPoint

# Column indices (mirror _COLUMNS order in the section widget).
_COL_DIRECTION = 0
_COL_IDENTIFIER = 2


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _payload(*, as_target=None, as_source=None) -> dict:
    return {
        "as_target": list(as_target or ()),
        "as_source": list(as_source or ()),
    }


def _grid_pairs(card: LinkedRecordPreviewCard) -> list[tuple[str, str]]:
    """Read the card's 2-column label/value grid as ``(label, value)`` pairs."""
    pairs: list[tuple[str, str]] = []
    grid = card._grid
    for r in range(grid.rowCount()):
        label_item = grid.itemAtPosition(r, 0)
        value_item = grid.itemAtPosition(r, 1)
        if label_item is None or value_item is None:
            continue
        pairs.append(
            (label_item.widget().text(), value_item.widget().text())
        )
    return pairs


class _FakeCard:
    """Records the controller's calls without building real chrome."""

    def __init__(self) -> None:
        self.shown: dict[str, Any] | None = None
        self.state: str | None = None
        self.enriched: list[tuple[str, str]] | None = None
        self.dismissed = False
        self._base_rows: list[tuple[str, str]] = []

    def show_for(self, record, **kwargs):  # noqa: ANN001
        self.shown = {"record": record, **kwargs}
        # Mirror the real card: base rows present when status/dates are.
        if record.get("status") or record.get("created"):
            self._base_rows = [("Status", str(record.get("status")))]

    def set_enriched(self, fields):  # noqa: ANN001
        self.enriched = list(fields)

    def set_state(self, state):  # noqa: ANN001
        self.state = state

    def dismiss(self):
        self.dismissed = True


class _StubClient:
    """A client whose ``get_<type>`` returns a canned record or raises."""

    def __init__(self, record=None, error=None):
        self._record = record
        self._error = error

    def get_decision(self, identifier):  # noqa: ANN001
        if self._error is not None:
            raise self._error
        return self._record


# ---------------------------------------------------------------------------
# extract_preview_fields
# ---------------------------------------------------------------------------


def test_extract_preview_fields_known_type():
    record = {"item_type": "pending_work", "status": "In Progress"}
    assert extract_preview_fields("planning_item", record) == [
        ("Item type", "pending_work"),
        ("Status", "In Progress"),
    ]


def test_extract_preview_fields_unknown_type_is_empty():
    assert extract_preview_fields("charter", {"version": 2}) == []


def test_extract_preview_fields_drops_empties():
    assert extract_preview_fields("decision", {"status": ""}) == []


# ---------------------------------------------------------------------------
# LinkedRecordPreviewCard (widget-level)
# ---------------------------------------------------------------------------


def test_card_show_for_renders_header_and_base_fields(qapp, qtbot):
    card = LinkedRecordPreviewCard()
    qtbot.addWidget(card)
    record = {
        "title": "Storage v0.1 build",
        "status": "complete",
        "created": "2026-05-09T10:00:00+00:00",
        "updated": "2026-05-10T11:30:00+00:00",
    }
    card.show_for(
        record,
        entity_type="session",
        identifier="SES-002",
        relationship="Decided in",
        anchor_global=QPoint(0, 0),
    )
    assert card._header_label.text() == "Session · SES-002"
    assert card._title_label.text() == "Storage v0.1 build"
    pairs = _grid_pairs(card)
    labels = [label for label, _ in pairs]
    assert labels == ["Relationship", "Status", "Created", "Updated"]
    assert ("Relationship", "Decided in") in pairs
    assert ("Status", "complete") in pairs
    # Dates use the grid's _fmt_dt shape.
    assert ("Created", "2026-05-09 10:00") in pairs
    # Loaded with base rows → no body line.
    assert not card._state_label.isVisibleTo(card)
    # Accessibility announced.
    assert card.accessibleName() == "Session SES-002"
    assert "Status: complete" in card.accessibleDescription()


def test_card_minimal_record_opens_loading(qapp, qtbot):
    card = LinkedRecordPreviewCard()
    qtbot.addWidget(card)
    card.show_for(
        {},
        entity_type="decision",
        identifier="DEC-032",
        relationship=None,
        anchor_global=QPoint(0, 0),
    )
    assert card._header_label.text() == "Decision · DEC-032"
    assert _grid_pairs(card) == []
    assert card._state_label.text() == "Loading…"
    assert card._state_label.isVisibleTo(card)


def test_card_set_state_texts(qapp, qtbot):
    card = LinkedRecordPreviewCard()
    qtbot.addWidget(card)
    card.set_state("not_found")
    assert card._state_label.text() == "Record not found (it may have been deleted)."
    card.set_state("error")
    assert card._state_label.text() == "Couldn't load details."
    card.set_state("empty")
    assert card._state_label.text() == "No additional details."
    card.set_state("loaded")
    assert card._state_label.text() == ""
    assert not card._state_label.isVisibleTo(card)


def test_card_set_enriched_appends_below_base_rows(qapp, qtbot):
    card = LinkedRecordPreviewCard()
    qtbot.addWidget(card)
    card.show_for(
        {"title": "x", "status": "Draft"},
        entity_type="planning_item",
        identifier="PI-118",
        relationship="Blocked by",
        anchor_global=QPoint(0, 0),
    )
    card.set_enriched([("Item type", "pending_work")])
    pairs = _grid_pairs(card)
    # Base rows first, enriched row last.
    assert pairs[-1] == ("Item type", "pending_work")
    assert ("Status", "Draft") in pairs
    assert "Item type: pending_work" in card.accessibleDescription()


# ---------------------------------------------------------------------------
# PreviewController (logic-level, resolver injected)
# ---------------------------------------------------------------------------


def _controller(host, resolver, client, extractor):
    return PreviewController(host, resolver, client, extractor)


def test_controller_apply_enrichment_fills_fields(qapp, qtbot):
    host = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(host)
    ctrl = _controller(host, lambda i: None, MagicMock(), lambda r, c: None)
    card = _FakeCard()
    ctrl._card = card
    ctrl._token = 5
    ctrl._apply_enrichment(
        {"item_type": "pending_work", "status": "Ready"},
        "planning_item",
        token=5,
    )
    assert card.enriched == [("Item type", "pending_work"), ("Status", "Ready")]
    assert card.state == "loaded"


def test_controller_stale_token_is_dropped(qapp, qtbot):
    host = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(host)
    ctrl = _controller(host, lambda i: None, MagicMock(), lambda r, c: None)
    card = _FakeCard()
    ctrl._card = card
    ctrl._token = 9  # current
    # A late read stamped with an older token must not repaint.
    ctrl._apply_enrichment({"status": "X"}, "decision", token=3)
    assert card.enriched is None
    assert card.state is None


def test_controller_empty_enrichment_sets_empty_state(qapp, qtbot):
    host = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(host)
    ctrl = _controller(host, lambda i: None, MagicMock(), lambda r, c: None)
    card = _FakeCard()
    ctrl._card = card
    ctrl._token = 1
    ctrl._apply_enrichment({"version": 2}, "charter", token=1)
    assert card.enriched is None
    assert card.state == "empty"


def test_controller_not_found_maps_to_not_found_state(qapp, qtbot):
    host = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(host)
    ctrl = _controller(host, lambda i: None, MagicMock(), lambda r, c: None)
    card = _FakeCard()
    ctrl._card = card
    ctrl._token = 2
    ctrl._apply_enrich_error(
        NotFoundError(errors=[], message="gone"), token=2
    )
    assert card.state == "not_found"


def test_controller_connection_error_maps_to_error_state(qapp, qtbot):
    host = ReferencesSection("decision", "DEC-001", _payload())
    qtbot.addWidget(host)
    ctrl = _controller(host, lambda i: None, MagicMock(), lambda r, c: None)
    card = _FakeCard()
    ctrl._card = card
    ctrl._token = 2
    ctrl._apply_enrich_error(StorageConnectionError("down"), token=2)
    assert card.state == "error"


# ---------------------------------------------------------------------------
# Composition — ReferencesSection
# ---------------------------------------------------------------------------


def _multi_row_payload() -> dict:
    return _payload(
        as_target=[
            {
                "source_type": "session",
                "source_id": "SES-050",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
            {
                "source_type": "session",
                "source_id": "SES-002",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
            },
            {
                "source_type": "topic",
                "source_id": "TOP-9",
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "is_about",
            },
        ]
    )


def _open_and_capture(monkeypatch, ctrl, view, index):
    """Drive ``_open`` with a fake card and return it (no real worker)."""
    captured: dict[str, Any] = {}

    def _factory(*_a, **_kw):
        card = _FakeCard()
        captured["card"] = card
        return card

    monkeypatch.setattr(preview_mod, "LinkedRecordPreviewCard", _factory)
    ctrl._open(view, index, focusable=True)
    return captured.get("card")


def test_section_resolves_correct_record_under_multisort(qapp, qtbot, monkeypatch):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    # Sort by Identifier ascending → SES-002, SES-050, TOP-9.
    section._proxy.set_primary(_COL_IDENTIFIER)
    proxy = section._proxy
    visual_first = proxy.data(proxy.index(0, _COL_IDENTIFIER))
    assert visual_first == "SES-002"
    index = proxy.index(0, _COL_DIRECTION)
    card = _open_and_capture(monkeypatch, section._preview, section._table, index)
    assert card is not None
    assert card.shown["identifier"] == "SES-002"


def test_section_group_node_opens_no_card(qapp, qtbot, monkeypatch):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    # Group by Relationship (combo index 1).
    section._group_combo.setCurrentIndex(1)
    group_model = section._group_model
    assert group_model is not None and group_model.group_count() >= 1
    group_index = group_model.index(0, 0, QModelIndex())
    assert group_model.is_group_index(group_index)
    # Resolver returns None for a group node → controller opens no card.
    card = _open_and_capture(
        monkeypatch, section._preview, section._tree, group_index
    )
    assert card is None


def test_section_group_child_resolves_record(qapp, qtbot, monkeypatch):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    section._group_combo.setCurrentIndex(1)
    group_model = section._group_model
    # Find a group with at least one child and resolve that child.
    child_index = None
    for g in range(group_model.group_count()):
        group_index = group_model.index(g, 0, QModelIndex())
        if group_model.child_count(g) > 0:
            child_index = group_model.index(0, 0, group_index)
            break
    assert child_index is not None
    record = section._row_at(child_index)
    assert record is not None
    card = _open_and_capture(
        monkeypatch, section._preview, section._tree, child_index
    )
    assert card is not None
    assert card.shown["identifier"] == record["other_id"]


def test_section_filter_excludes_row_no_card(qapp, qtbot, monkeypatch):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText("nomatchwhatsoever")
    assert section._proxy.rowCount() == 0
    # The empty state is shown; there is no visual row to open a card for.
    assert section._empty_state.isVisibleTo(section)


def test_section_dismiss_on_sort_change(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    card = _FakeCard()
    section._preview._card = card
    section._proxy.sortKeysChanged.emit()
    assert card.dismissed
    assert section._preview._card is None


def test_section_dismiss_on_group_change(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    card = _FakeCard()
    section._preview._card = card
    section._group_combo.setCurrentIndex(1)
    assert card.dismissed
    assert section._preview._card is None


def test_section_dismiss_on_filter_change(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    card = _FakeCard()
    section._preview._card = card
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText("SES")
    assert card.dismissed
    assert section._preview._card is None


def test_section_open_enrich_dismiss_calls_no_model_mutator(
    qapp, qtbot, monkeypatch
):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    invalidate_spy = MagicMock(wraps=section._proxy.invalidate)
    reset_spy = MagicMock(wraps=section._model.beginResetModel)
    monkeypatch.setattr(section._proxy, "invalidate", invalidate_spy)
    monkeypatch.setattr(section._model, "beginResetModel", reset_spy)

    index = section._proxy.index(0, _COL_DIRECTION)
    ctrl = section._preview
    card = _open_and_capture(monkeypatch, ctrl, section._table, index)
    assert card is not None
    ctrl._apply_enrichment({"status": "X"}, "decision", token=ctrl._token)
    ctrl.dismiss()

    invalidate_spy.assert_not_called()
    reset_spy.assert_not_called()


# ---------------------------------------------------------------------------
# Composition — ReferencesPanel (column-aware target)
# ---------------------------------------------------------------------------


class _PanelClient:
    def __init__(self, records):
        self._records = list(records)

    def list_references(self):
        return list(self._records)


def _panel_refs() -> list[dict[str, Any]]:
    return [
        {
            "id": 1,
            "source_type": "session",
            "source_id": "SES-008",
            "target_type": "decision",
            "target_id": "DEC-032",
            "relationship": "decided_in",
            "_source_display": "session:SES-008",
            "_target_display": "decision:DEC-032",
        }
    ]


def _seed_panel(qtbot, records):
    panel = ReferencesPanel(client=_PanelClient(records))
    qtbot.addWidget(panel)
    panel._records = list(records)
    panel._model.set_records(records)
    return panel


def test_panel_preview_target_is_column_aware(qapp, qtbot):
    panel = _seed_panel(qtbot, _panel_refs())
    record = panel._records[0]
    assert panel._preview_target(record, 0) == ("session", "SES-008", None, None)
    assert panel._preview_target(record, 2) == ("decision", "DEC-032", None, None)
    # Relationship column is not previewable.
    assert panel._preview_target(record, 1) is None


def test_panel_source_cell_opens_source_endpoint(qapp, qtbot, monkeypatch):
    panel = _seed_panel(qtbot, _panel_refs())
    index = panel._model.index(0, 0)  # Source column
    card = _open_and_capture(monkeypatch, panel._preview, panel._table, index)
    assert card is not None
    assert card.shown["entity_type"] == "session"
    assert card.shown["identifier"] == "SES-008"


def test_panel_relationship_cell_opens_no_card(qapp, qtbot, monkeypatch):
    panel = _seed_panel(qtbot, _panel_refs())
    index = panel._model.index(0, 1)  # Relationship column
    card = _open_and_capture(monkeypatch, panel._preview, panel._table, index)
    assert card is None


def test_panel_dismiss_on_filter_change(qapp, qtbot):
    panel = _seed_panel(qtbot, _panel_refs())
    card = _FakeCard()
    panel._preview._card = card
    panel._source_filter.setCurrentIndex(0)  # currentIndexChanged → dismiss
    # A genuine index change to trigger the signal.
    panel._source_filter.addItem("session")
    panel._source_filter.setCurrentIndex(panel._source_filter.count() - 1)
    assert card.dismissed


# ---------------------------------------------------------------------------
# Context-menu regression guard (preview feature present)
# ---------------------------------------------------------------------------


def test_panel_context_menu_unchanged_with_preview(qapp, qtbot):
    panel = _seed_panel(qtbot, _panel_refs())
    assert panel._preview is not None  # preview installed
    row_menu = panel._build_context_menu(panel._model.index(0, 0))
    labels = [a.text() for a in row_menu.actions() if not a.isSeparator()]
    assert labels == ["Go to source", "Go to target", "Delete reference"]
    whitespace = panel._build_context_menu(QModelIndex())
    assert [a.text() for a in whitespace.actions()] == ["New reference"]


def _one_row_section_payload() -> dict:
    return _payload(
        as_source=[
            {
                "id": 7,
                "source_type": "session",
                "source_id": "SES-001",
                "target_type": "decision",
                "target_id": "DEC-007",
                "relationship": "decided_in",
            }
        ]
    )


def test_section_context_menu_unchanged_with_preview(qapp, qtbot):
    section = ReferencesSection(
        "decision", "DEC-007", _one_row_section_payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    assert section._preview is not None
    index = section._proxy.index(0, _COL_DIRECTION)
    menu = section._build_row_menu(section._table, section._row_at(index))
    labels = [a.text() for a in menu.actions()]
    assert labels == ["Delete reference", "Go to DEC-007"]


def test_section_right_click_dismisses_open_card(qapp, qtbot, monkeypatch):
    section = ReferencesSection(
        "decision", "DEC-007", _one_row_section_payload(), client=MagicMock()
    )
    qtbot.addWidget(section)
    # Return None so _show_row_menu dismisses then returns before the blocking
    # menu.exec — the dismiss is what we are asserting.
    monkeypatch.setattr(section, "_build_row_menu", lambda *a, **k: None)
    card = _FakeCard()
    section._preview._card = card
    index = section._proxy.index(0, _COL_DIRECTION)
    section._show_row_menu(section._table, index, QPoint(0, 0))
    assert card.dismissed
    assert section._preview._card is None


def test_panel_right_click_dismisses_open_card(qapp, qtbot):
    panel = _seed_panel(qtbot, _panel_refs())
    card = _FakeCard()
    panel._preview._card = card
    panel._build_context_menu(panel._model.index(0, 0))
    assert card.dismissed
    assert panel._preview._card is None
