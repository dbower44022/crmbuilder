"""One phase tab: a phase-scoped sidebar plus its own panel stack (REQ-526 / PI-432).

A ``PhasePage`` is what each tab of the main window hosts. It owns the
three-group sidebar for its phase (Every session · Phase N steps · All
panels), a filter box above it, and a ``QStackedWidget`` of panels built on
first visit — so a tab keeps its own selected step, selected record and
scroll position while the user works in another tab (DEC-953).

The page does not talk to the network itself: panel construction and the
cross-panel wiring (connection-lost, navigate, open) come in through the
``panel_builder`` callable the main window supplies, and "Chat" is a request
the window answers by switching to the pinned Chat tab.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ListDetailPanel
from crmbuilder_v2.ui.navigation import (
    ALL_PANELS_GROUP_TITLE,
    PHASES_BY_KEY,
    Phase,
    PhaseMap,
)
from crmbuilder_v2.ui.panel_registry import ALL_PANEL_LABELS
from crmbuilder_v2.ui.sidebar import Sidebar
from crmbuilder_v2.ui.widgets.link_filter_input import LinkFilterInput

_log = logging.getLogger("crmbuilder_v2.ui.phase_page")

CHAT_LABEL = "Chat"


class _LazyPagesByEntry(dict):
    """label → stack index; indexing an unbuilt label builds its panel.

    Panels are built on first visit, but callers (and the existing tests)
    address them as ``stack.widget(pages_by_entry[label])``. Resolving a
    missing label through ``ensure_panel`` keeps that contract without
    eager construction. ``get``/``in`` stay non-building.
    """

    def __init__(self, page: PhasePage) -> None:
        super().__init__()
        self._page = page

    def __missing__(self, label: str) -> int:
        panel = self._page.ensure_panel(label)
        if panel is None:
            raise KeyError(label)
        return self[label]


class PhasePage(QWidget):
    """Sidebar + lazily-built panel stack for one phase."""

    #: A sidebar entry was selected (label). The window decides whether to
    #: refresh the panel, based on lifecycle readiness.
    entry_selected = Signal(str)
    #: The user picked "Chat" — the window switches to the pinned Chat tab.
    chat_requested = Signal()

    def __init__(
        self,
        phase: Phase,
        phase_map: PhaseMap,
        panel_builder: Callable[[str], QWidget],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._phase = phase
        self._phase_map = phase_map
        self._panel_builder = panel_builder
        self._pages_by_entry: dict[str, int] = _LazyPagesByEntry(self)
        self._record_counts: dict[str, int] = {}
        self.setObjectName(f"phase_page_{phase.key.replace('.', '_')}")

        groups = phase_map.sidebar_groups(phase.key, ALL_PANEL_LABELS)
        self._sidebar = Sidebar(
            groups,
            numbered_groups=(phase.steps_group_title,),
            collapsed_groups=(ALL_PANELS_GROUP_TITLE,),
        )
        self._sidebar_search = LinkFilterInput(object_name="sidebar_search_input")
        self._sidebar_search.setPlaceholderText("Filter navigation…")
        self._sidebar_search.filterChanged.connect(self._sidebar.filter_entries)
        self._stack = QStackedWidget()

        sidebar_col = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_col)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar_layout.addWidget(self._sidebar_search)
        sidebar_layout.addWidget(self._sidebar, stretch=1)
        sidebar_col.setFixedWidth(self._sidebar.width())

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(sidebar_col)
        layout.addWidget(self._stack, stretch=1)

        self._sidebar.selection_changed.connect(self._on_sidebar_selected)

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def phase(self) -> Phase:
        return self._phase

    @property
    def sidebar(self) -> Sidebar:
        return self._sidebar

    @property
    def stack(self) -> QStackedWidget:
        return self._stack

    @property
    def pages_by_entry(self) -> dict[str, int]:
        """label → stack index for panels built so far."""
        return self._pages_by_entry

    def steps(self) -> tuple[str, ...]:
        return self._phase_map.steps_for(self._phase.key)

    def first_step(self) -> str | None:
        steps = self.steps()
        return steps[0] if steps else None

    def current_entry(self) -> str:
        return self._sidebar.current_text()

    def current_panel(self) -> QWidget | None:
        return self._stack.currentWidget()

    def panel_for(self, label: str) -> QWidget | None:
        """The built panel for ``label``, or ``None`` if not built yet."""
        index = self._pages_by_entry.get(label)
        return self._stack.widget(index) if index is not None else None

    def built_panels(self) -> list[tuple[str, QWidget]]:
        return [
            (label, self._stack.widget(index))
            for label, index in self._pages_by_entry.items()
        ]

    # ------------------------------------------------------------------
    # Panel lifecycle
    # ------------------------------------------------------------------

    def ensure_panel(self, label: str) -> QWidget | None:
        """Build ``label``'s panel on first use; return it. ``None`` for Chat."""
        if label == CHAT_LABEL:
            return None
        panel = self.panel_for(label)
        if panel is not None:
            return panel
        panel = self._panel_builder(label)
        if isinstance(panel, ListDetailPanel):
            panel.records_loaded.connect(
                lambda count, lbl=label: self._on_records_loaded(lbl, count)
            )
        index = self._stack.addWidget(panel)
        self._pages_by_entry[label] = index
        return panel

    def show_entry(self, label: str) -> QWidget | None:
        """Select ``label`` in the sidebar and raise its panel (no refresh)."""
        panel = self.ensure_panel(label)
        if panel is not None:
            self._stack.setCurrentWidget(panel)
        self._sidebar.select_entry(label)
        return panel

    def _on_sidebar_selected(self, label: str) -> None:
        if label == CHAT_LABEL:
            self.chat_requested.emit()
            return
        panel = self.ensure_panel(label)
        if panel is not None:
            self._stack.setCurrentWidget(panel)
        self.entry_selected.emit(label)

    # ------------------------------------------------------------------
    # Step markers — derived from counts the panels already fetched
    # ------------------------------------------------------------------

    def _on_records_loaded(self, label: str, count: int) -> None:
        self._record_counts[label] = count
        self.update_step_markers()

    def record_counts(self) -> dict[str, int]:
        return dict(self._record_counts)

    def reset_record_counts(self) -> None:
        """Forget counts (engagement switch) so markers reload from fresh data."""
        self._record_counts.clear()
        self.update_step_markers()

    def update_step_markers(self) -> None:
        """Recompute ✓ / ▶ from known counts.

        A step is *done* when its panel has at least one record; the first
        step whose panel is known to be empty is *next*. Steps whose panels
        have not loaded yet carry no marker. Advisory only.
        """
        next_marked = False
        for label in self.steps():
            count = self._record_counts.get(label)
            if count is None:
                self._sidebar.set_step_marker(label, None)
            elif count > 0:
                self._sidebar.set_step_marker(label, "done")
            elif not next_marked:
                self._sidebar.set_step_marker(label, "next")
                next_marked = True
            else:
                self._sidebar.set_step_marker(label, None)
        self._sidebar.viewport().update()

    def step_panels(self) -> list[tuple[str, QWidget]]:
        """Build (if needed) and return the phase's step panels in order."""
        result = []
        for label in self.steps():
            panel = self.ensure_panel(label)
            if panel is not None:
                result.append((label, panel))
        return result

    # ------------------------------------------------------------------
    # Enable/disable during reconnect
    # ------------------------------------------------------------------

    def set_content_enabled(self, enabled: bool) -> None:
        self._sidebar.setEnabled(enabled)
        self._stack.setEnabled(enabled)


def phase_for_key(key: str) -> Phase:
    return PHASES_BY_KEY[key]
