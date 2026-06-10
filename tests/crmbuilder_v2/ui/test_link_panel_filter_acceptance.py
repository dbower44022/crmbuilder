"""WTK-062 — acceptance verification for the PI-116 link-panel filter.

Independent verification of the WTK-061 deliverable (debounced client-side
search/filter on relationship link panels) against the WTK-059 design
acceptance criteria (``pi-116-link-panel-search-filter-ui-design.md`` §5).

The WTK-061 unit tests (``test_link_filter_input.py``,
``test_references_section.py``, ``test_references_panel.py``) already cover
debounce-once, immediate-clear, empty-state, and AND-composition on small
fixtures. This module closes the gaps those leave against the *stated* ACs:

- **AC-1 at design scale** — the design specifies "a record/list of ≥ 20
  link rows" and "the table re-fits to the filtered count so no scroll is
  needed." The existing section tests use 2-row payloads, so neither the
  ≥20-row case nor the ``_fit_height`` re-fit is asserted.
- **AC-2 by display *title*** — the existing tests narrow by *identifier*
  only; the AC also requires matching a partial display **title**.
- **AC-7 navigation through the proxy on the *filtered* view** — the
  existing navigation test runs on the unfiltered grid; the AC requires
  the row under the cursor to map correctly through the proxy *after* a
  filter is applied.
- **Paging / lazy-loading interaction (WTK-062 scope)** — the filter must
  narrow the *already-loaded* rows without a re-fetch (the §3.6
  client-side-over-loaded-rows contract). Asserted by counting client
  fetches across a filter change.

Tests run under the offscreen Qt platform (see the ui conftest).
"""

from __future__ import annotations

from typing import Any

from crmbuilder_v2.ui.panels.references import ReferencesPanel
from crmbuilder_v2.ui.widgets.references_section import (
    _ROW_HEIGHT,
    ReferencesSection,
)

# Column indices mirror _COLUMNS order in references_section.py.
_COL_DIRECTION = 0
_COL_IDENTIFIER = 2


# ---------------------------------------------------------------------------
# Fixtures / builders
# ---------------------------------------------------------------------------


def _section_payload_many(n: int = 21) -> dict[str, Any]:
    """A references payload with ``n`` inbound rows (design AC-1 scale).

    One row carries a distinctive display **title** ("Postgres foundation")
    so the title-match AC can be exercised; the rest are plain numbered
    sessions. Every row is inbound (``as_target``) for simplicity.
    """
    rows: list[dict[str, Any]] = []
    for i in range(n):
        ident = f"SES-{i:03d}"
        rows.append(
            {
                "source_type": "session",
                "source_id": ident,
                "target_type": "decision",
                "target_id": "DEC-001",
                "relationship": "decided_in",
                "other_summary": {
                    "identifier": ident,
                    "entity_type": "session",
                    "title": (
                        "Postgres foundation" if i == 0 else f"Session number {i}"
                    ),
                    "status": "complete",
                },
            }
        )
    return {"as_target": rows, "as_source": []}


def _apply_filter_sync(section: ReferencesSection, qtbot, text: str) -> None:
    """Type ``text`` and wait for the debounced ``filterChanged`` to settle."""
    with qtbot.waitSignal(section._filter.filterChanged, timeout=2000):
        section._filter.setText(text)


# ---------------------------------------------------------------------------
# AC-1 — typing narrows a ≥20-row list and the table re-fits to the
#        filtered count (no scroll needed to see all matches).
# ---------------------------------------------------------------------------


def test_ac1_large_list_narrows_and_table_refits(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _section_payload_many(21))
    qtbot.addWidget(section)
    assert section._proxy.rowCount() == 21
    full_height = section._table.height()

    # A substring that matches exactly one identifier (SES-000).
    _apply_filter_sync(section, qtbot, "SES-000")
    assert section._proxy.rowCount() == 1
    assert (
        section._proxy.data(section._proxy.index(0, _COL_IDENTIFIER)) == "SES-000"
    )

    # The table shrank to the filtered count: the height delta is exactly
    # the 20 removed rows × the fixed row height (so all matches are
    # visible without scrolling). This is the AC-1 "re-fits" guarantee.
    filtered_height = section._table.height()
    assert filtered_height < full_height
    assert full_height - filtered_height == _ROW_HEIGHT * (21 - 1)


# ---------------------------------------------------------------------------
# AC-2 — a partial display *title* matches (not just the identifier).
# ---------------------------------------------------------------------------


def test_ac2_partial_title_matches(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _section_payload_many(21))
    qtbot.addWidget(section)

    # "postgres" appears only in row 0's title, lower-cased — proves
    # case-insensitive substring matching against the Title column.
    _apply_filter_sync(section, qtbot, "postgres")
    assert section._proxy.rowCount() == 1
    assert (
        section._proxy.data(section._proxy.index(0, _COL_IDENTIFIER)) == "SES-000"
    )


def test_ac2_partial_identifier_still_matches(qapp, qtbot):
    # Companion to the title case: a shared identifier stem ("SES-01")
    # matches the SES-010..SES-019 band — substring, not exact.
    section = ReferencesSection("decision", "DEC-001", _section_payload_many(21))
    qtbot.addWidget(section)
    _apply_filter_sync(section, qtbot, "SES-01")
    assert section._proxy.rowCount() == 10


# ---------------------------------------------------------------------------
# AC-7 — navigation/sort behave on the *filtered* view (row under the
#        cursor mapped through the proxy, not the source row).
# ---------------------------------------------------------------------------


def test_ac7_double_click_navigates_correct_row_after_filter(qapp, qtbot):
    section = ReferencesSection("decision", "DEC-001", _section_payload_many(21))
    qtbot.addWidget(section)

    received: list[tuple[str, str]] = []
    section.navigate_requested.connect(lambda t, i: received.append((t, i)))

    # Filter down to a single surviving row whose *source* position in the
    # unfiltered model is not row 0 — so a proxy→source mapping bug would
    # navigate to the wrong identifier.
    _apply_filter_sync(section, qtbot, "SES-013")
    assert section._proxy.rowCount() == 1

    proxy_index = section._proxy.index(0, _COL_DIRECTION)
    section._table.doubleClicked.emit(proxy_index)
    assert received == [("session", "SES-013")]


def test_ac7_sort_operates_on_filtered_view(qapp, qtbot):
    from PySide6.QtCore import Qt

    section = ReferencesSection("decision", "DEC-001", _section_payload_many(21))
    qtbot.addWidget(section)

    # Band of ten rows, then sort descending: the proxy must order the
    # filtered subset, not the whole model.
    _apply_filter_sync(section, qtbot, "SES-01")
    section._table.sortByColumn(_COL_IDENTIFIER, Qt.SortOrder.DescendingOrder)
    assert section._proxy.rowCount() == 10
    first = section._proxy.data(section._proxy.index(0, _COL_IDENTIFIER))
    assert first == "SES-019"


# ---------------------------------------------------------------------------
# Paging / lazy-loading interaction (WTK-062 scope) — the filter narrows
# the already-loaded rows with no re-fetch.
# ---------------------------------------------------------------------------


class _CountingClient:
    """A list_references client that counts how many times it is fetched."""

    def __init__(self, records: list[dict[str, Any]]) -> None:
        self._records = list(records)
        self.fetch_count = 0

    def list_references(self) -> list[dict[str, Any]]:
        self.fetch_count += 1
        return list(self._records)


def _panel_refs(n: int = 21) -> list[dict[str, Any]]:
    return [
        {
            "source_type": "session",
            "source_id": f"SES-{i:03d}",
            "target_type": "decision",
            "target_id": "DEC-001",
            "relationship": "decided_in",
        }
        for i in range(n)
    ]


def test_panel_filter_does_not_refetch_loaded_rows(qapp, qtbot):
    """AC scope: filtering is client-side over the loaded set.

    The standalone panel fetches once on refresh; changing the free-text
    filter re-filters the cached ``_all_records`` and must not trigger
    another ``list_references`` round-trip. This is the §3.6
    "client-side filter over loaded rows" contract that keeps the filter
    from being mistaken for a server-side relationship query.
    """
    client = _CountingClient(_panel_refs(21))
    panel = ReferencesPanel(client=client)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 21, timeout=2000)
    fetches_after_load = client.fetch_count

    with qtbot.waitSignal(panel._text_filter.filterChanged, timeout=2000):
        panel._text_filter.setText("SES-007")
    qtbot.waitUntil(lambda: panel._model.rowCount() == 1, timeout=2000)

    # Filtering narrowed the loaded rows with zero additional fetches.
    assert client.fetch_count == fetches_after_load
    assert panel._records[0]["source_id"] == "SES-007"

    # Clearing restores the full loaded list — still no re-fetch.
    panel._text_filter.setText("")
    assert panel._model.rowCount() == 21
    assert client.fetch_count == fetches_after_load


def test_panel_no_filter_box_collision_with_dropdown_refetch(qapp, qtbot):
    """Changing a type dropdown also re-filters in memory (no re-fetch)."""
    client = _CountingClient(_panel_refs(21))
    panel = ReferencesPanel(client=client)
    qtbot.addWidget(panel)

    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 21, timeout=2000)
    baseline = client.fetch_count

    index = panel._source_filter.findText("session")
    assert index >= 0
    panel._source_filter.setCurrentIndex(index)
    qtbot.waitUntil(lambda: panel._model.rowCount() == 21, timeout=2000)
    assert client.fetch_count == baseline
