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
    PreviewAffordance,
    PreviewController,
    extract_preview_fields,
)
from crmbuilder_v2.ui.widgets.references_section import (
    EntityFieldsGridSection,
    ReferencesSection,
    WorkTaskGridSection,
)
from PySide6.QtCore import QModelIndex, QPoint, QRect, Qt

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
    # PI-121 added a per-row "Open <type>" action paired with each endpoint's
    # "Go to". The preview still does not otherwise alter the menu — which is
    # what this test guards.
    assert labels == [
        "Go to source",
        "Open Session",
        "Go to target",
        "Open Decision",
        "Delete reference",
    ]
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
    # PI-121 / WTK-079: the additive "Open <item type>" entry follows "Go to".
    assert labels == ["Delete reference", "Go to DEC-007", "Open Decision"]


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


# ---------------------------------------------------------------------------
# Regression — hover trigger requires mouse tracking on the viewport
# ---------------------------------------------------------------------------


def test_section_viewports_have_mouse_tracking_for_hover(qapp, qtbot):
    # The hover-dwell preview only fires if the viewport has mouse tracking
    # enabled — otherwise Qt delivers MouseMove only while a button is held and
    # the card never opens. The original WTK-071 build installed the event
    # filter but not tracking, so the hover trigger was dead in the real app.
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    assert section._table.viewport().hasMouseTracking()
    assert section._tree.viewport().hasMouseTracking()


def test_panel_viewport_has_mouse_tracking_for_hover(qapp, qtbot):
    panel = _seed_panel(qtbot, _panel_refs())
    assert panel._table.viewport().hasMouseTracking()


def test_section_real_hover_starts_dwell_and_opens_card(qapp, qtbot, monkeypatch):
    """End-to-end hover: a real MouseMove dispatched to the viewport must run
    the installed event filter, start the dwell timer, and open a card when it
    elapses. This is the chain the other tests skip (they call ``_open``
    directly), and the one the missing-mouse-tracking bug silently broke.
    """
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    section.resize(600, 400)
    section.show()
    qtbot.waitExposed(section)

    captured: dict[str, Any] = {}

    def _factory(*_a, **_kw):
        card = _FakeCard()
        captured["card"] = card
        return card

    monkeypatch.setattr(preview_mod, "LinkedRecordPreviewCard", _factory)

    ctrl = section._preview
    view = section._table
    index = section._proxy.index(0, _COL_DIRECTION)
    pos = view.visualRect(index).center()
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(pos),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    # Dispatch through the viewport so the *real* installed event filter runs.
    qapp.sendEvent(view.viewport(), move)
    assert ctrl._dwell_timer.isActive()  # hover registered → dwell pending
    ctrl._on_dwell_elapsed()  # fire the dwell deterministically
    assert captured.get("card") is not None  # card opened from the hover


# ---------------------------------------------------------------------------
# Discoverable peek-button affordance (PI-148 / WTK-153)
# ---------------------------------------------------------------------------


def _affordance_visible(ctrl: PreviewController) -> bool:
    """The controller's reused peek button exists and is not hidden."""
    return ctrl._affordance is not None and not ctrl._affordance.isHidden()


# --- PreviewAffordance widget-level -----------------------------------------


def test_affordance_is_focusable_icon_button_hidden_at_rest(qapp, qtbot):
    aff = PreviewAffordance()
    qtbot.addWidget(aff)
    # Icon-only chrome from the shared factory: 28×28, tooltip, no text.
    assert aff.toolTip() == "Preview"
    assert aff.text() == ""
    assert aff.property("buttonCategory") == "icon-only"
    assert (aff.width(), aff.height()) == (28, 28)
    # A real QPushButton is natively focusable (the accessibility win, §3.5).
    assert aff.focusPolicy() != Qt.FocusPolicy.NoFocus
    # Nothing at rest.
    assert aff.isHidden()


def test_affordance_show_at_labels_positions_and_reveals(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    aff = PreviewAffordance()
    qtbot.addWidget(aff)
    rect = QRect(0, 10, 200, 24)
    aff.show_at(section._table, viewport_rect=rect, identifier="PI-118")
    # accessibleName names the record (so a screen reader announces it).
    assert aff.accessibleName() == "Preview PI-118"
    # Reparented onto the view's viewport and shown at the trailing edge.
    assert aff.parentWidget() is section._table.viewport()
    assert not aff.isHidden()
    assert aff.x() + aff.width() <= rect.right()
    aff.hide_affordance()
    assert aff.isHidden()


# --- Controller reveal / hide -----------------------------------------------


def test_controller_reveals_affordance_on_previewable_row(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    ctrl = section._preview
    index = section._proxy.index(0, _COL_DIRECTION)
    ctrl._reveal_affordance(section._table, index)
    assert _affordance_visible(ctrl)
    # Remembers the (view, index) so a click targets exactly this row.
    assert ctrl._affordance_view is section._table
    assert ctrl._affordance_index.row() == index.row()
    # The accessibleName matches the resolved far-side record.
    expected = section._row_at(index)["other_id"]
    assert ctrl._affordance.accessibleName() == f"Preview {expected}"


def test_controller_group_node_reveals_no_affordance(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    section._group_combo.setCurrentIndex(1)  # group by Relationship
    group_model = section._group_model
    group_index = group_model.index(0, 0, QModelIndex())
    assert group_model.is_group_index(group_index)
    ctrl = section._preview
    ctrl._reveal_affordance(section._tree, group_index)
    # Resolver returns None for a group node → no button (mirrors "no card").
    assert not _affordance_visible(ctrl)


def test_controller_invalid_index_in_mousemove_hides_affordance(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    ctrl = section._preview
    # Reveal first, then a move over empty space (invalid index) hides it.
    ctrl._reveal_affordance(
        section._table, section._proxy.index(0, _COL_DIRECTION)
    )
    assert _affordance_visible(ctrl)
    ctrl._on_mouse_move(section._table, QPoint(5, 100_000))  # below all rows
    assert not _affordance_visible(ctrl)


def test_controller_dismiss_hides_affordance(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    ctrl = section._preview
    ctrl._reveal_affordance(
        section._table, section._proxy.index(0, _COL_DIRECTION)
    )
    assert _affordance_visible(ctrl)
    ctrl.dismiss()
    assert not _affordance_visible(ctrl)


def test_controller_sort_change_hides_affordance(qapp, qtbot):
    # A reorder dismisses via the surface's sortKeysChanged → dismiss wiring,
    # which now hides the button alongside the card.
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    ctrl = section._preview
    ctrl._reveal_affordance(
        section._table, section._proxy.index(0, _COL_DIRECTION)
    )
    assert _affordance_visible(ctrl)
    section._proxy.sortKeysChanged.emit()
    assert not _affordance_visible(ctrl)


def test_controller_current_changed_reveals_affordance_for_keyboard(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    ctrl = section._preview
    index = section._proxy.index(0, _COL_DIRECTION)
    # Keyboard focus/selection (no card pinned) still reveals the button.
    ctrl._on_current_changed(index, QModelIndex())
    assert _affordance_visible(ctrl)


def test_controller_affordance_enter_cancels_dismiss_grace(qapp, qtbot):
    from PySide6.QtCore import QEvent

    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    ctrl = section._preview
    ctrl._reveal_affordance(
        section._table, section._proxy.index(0, _COL_DIRECTION)
    )
    ctrl._grace_timer.start()  # pretend the row was just left
    assert ctrl._grace_timer.isActive()
    # Travelling onto the button cancels the pending dismiss so it is clickable.
    enter = QEvent(QEvent.Type.Enter)
    ctrl.eventFilter(ctrl._affordance, enter)
    assert not ctrl._grace_timer.isActive()


# --- Click opens the SAME card as the accelerators --------------------------


def test_affordance_click_opens_same_card_as_space(qapp, qtbot, monkeypatch):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    ctrl = section._preview
    index = section._proxy.index(0, _COL_DIRECTION)
    expected = section._row_at(index)["other_id"]

    cards: list[_FakeCard] = []

    def _factory(*_a, **_kw):
        card = _FakeCard()
        cards.append(card)
        return card

    monkeypatch.setattr(preview_mod, "LinkedRecordPreviewCard", _factory)

    # Click path: reveal the button on the row, then activate it.
    ctrl._reveal_affordance(section._table, index)
    ctrl._affordance.click()
    assert cards, "affordance click opened no card"
    click_card = cards[-1]
    assert click_card.shown["identifier"] == expected
    # The click opens the pinned (focusable) variant — like Space, not hover.
    assert click_card.shown["focusable"] is True

    # Space path on the same row: same identifier, same open path.
    section._table.setCurrentIndex(index)
    ctrl._open_for_selection(section._table)
    space_card = cards[-1]
    assert space_card.shown["identifier"] == expected
    assert space_card.shown["focusable"] is True


def test_accelerators_intact_after_affordance_installed(qapp, qtbot, monkeypatch):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    ctrl = section._preview
    assert ctrl is not None  # affordance machinery installed

    cards: list[_FakeCard] = []

    def _factory(*_a, **_kw):
        card = _FakeCard()
        cards.append(card)
        return card

    monkeypatch.setattr(preview_mod, "LinkedRecordPreviewCard", _factory)

    index = section._proxy.index(0, _COL_DIRECTION)
    # 400 ms hover-dwell still opens a transient (non-focusable) card.
    ctrl._hover_view = section._table
    ctrl._hover_index = QModelIndex(index)
    ctrl._on_dwell_elapsed()
    assert cards and cards[-1].shown["focusable"] is False

    # Space still opens a pinned (focusable) card.
    section._table.setCurrentIndex(index)
    ctrl._open_for_selection(section._table)
    assert cards[-1].shown["focusable"] is True


# --- Consistent across all three surfaces -----------------------------------


def _entity_field_rows() -> list[dict[str, Any]]:
    return [
        {
            "identifier": "FLD-1",
            "title": "Mentor status",
            "field_type": "enum",
            "status": "current",
            "other_type": "field",
            "other_id": "FLD-1",
        }
    ]


def test_affordance_reveals_on_all_three_grid_surfaces(qapp, qtbot):
    work = WorkTaskGridSection("workstream", "WSK-001", _multi_grid_work_rows())
    qtbot.addWidget(work)
    fields = EntityFieldsGridSection("entity", "ENT-1", _entity_field_rows())
    qtbot.addWidget(fields)
    refs = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(refs)

    for section in (work, fields, refs):
        ctrl = section._preview
        ctrl._reveal_affordance(section._table, section._proxy.index(0, 0))
        assert _affordance_visible(ctrl), (
            f"affordance did not reveal on {type(section).__name__}"
        )


def _multi_grid_work_rows() -> list[dict[str, Any]]:
    return [
        {
            "identifier": "WTK-001",
            "title": "Storage layer migration",
            "area": "storage",
            "status": "Complete",
            "claim_state": "Unclaimed",
            "other_type": "work_task",
            "other_id": "WTK-001",
        }
    ]


def test_affordance_reveals_on_panel_source_and_target_not_relationship(
    qapp, qtbot
):
    panel = _seed_panel(qtbot, _panel_refs())
    ctrl = panel._preview

    # Source cell (col 0) reveals the button.
    ctrl._reveal_affordance(panel._table, panel._model.index(0, 0))
    assert _affordance_visible(ctrl)
    assert ctrl._affordance.accessibleName() == "Preview SES-008"

    # Target cell (col 2) reveals it, naming the target endpoint.
    ctrl._reveal_affordance(panel._table, panel._model.index(0, 2))
    assert _affordance_visible(ctrl)
    assert ctrl._affordance.accessibleName() == "Preview DEC-032"

    # Relationship cell (col 1) is not previewable → no button.
    ctrl._reveal_affordance(panel._table, panel._model.index(0, 1))
    assert not _affordance_visible(ctrl)


def test_panel_affordance_is_cell_anchored(qapp, qtbot):
    panel = _seed_panel(qtbot, _panel_refs())
    # The standalone panel anchors on the hovered cell, not the whole row.
    assert panel._preview._cell_anchored is True


def test_section_affordance_is_row_anchored(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    # The grids anchor on the row band (default placement).
    assert section._preview._cell_anchored is False


# --- No model restructuring across the affordance lifecycle -----------------


def test_affordance_reveal_click_hide_calls_no_model_mutator(
    qapp, qtbot, monkeypatch
):
    section = ReferencesSection("decision", "DEC-001", _multi_row_payload())
    qtbot.addWidget(section)
    invalidate_spy = MagicMock(wraps=section._proxy.invalidate)
    reset_spy = MagicMock(wraps=section._model.beginResetModel)
    monkeypatch.setattr(section._proxy, "invalidate", invalidate_spy)
    monkeypatch.setattr(section._model, "beginResetModel", reset_spy)
    monkeypatch.setattr(
        preview_mod, "LinkedRecordPreviewCard", lambda *a, **k: _FakeCard()
    )

    before_cols = section._model.columnCount()
    ctrl = section._preview
    index = section._proxy.index(0, _COL_DIRECTION)
    ctrl._reveal_affordance(section._table, index)
    ctrl._affordance.click()
    ctrl._hide_affordance()

    invalidate_spy.assert_not_called()
    reset_spy.assert_not_called()
    assert section._model.columnCount() == before_cols
