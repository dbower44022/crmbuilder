"""PI-108 Slice B: created/last-edited timestamps on the governance panels.

Covers the mutable governance panels (Decisions, Risks, Reference Books,
Work Tickets, Close-Out Payloads), the immutable ones (Topics tree,
Deposit Events), and the singleton versioned panels (Charter, Status).

For mutable panels the synthetic ``created_at_display`` column must be
present and formatted (never the raw ISO string); panels that already
showed a raw ``*_updated_at`` column gain the formatted ``updated_at_display``
in its place. For immutable / singleton panels the detail pane renders a
Created value plus an em dash for Last Updated.
"""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.charter import CharterPanel
from crmbuilder_v2.ui.panels.close_out_payloads import CloseOutPayloadsPanel
from crmbuilder_v2.ui.panels.decisions import DecisionsPanel
from crmbuilder_v2.ui.panels.deposit_events import DepositEventsPanel
from crmbuilder_v2.ui.panels.reference_books import ReferenceBooksPanel
from crmbuilder_v2.ui.panels.risks import RisksPanel
from crmbuilder_v2.ui.panels.status import StatusPanel
from crmbuilder_v2.ui.panels.topics import TopicsPanel
from crmbuilder_v2.ui.panels.work_tickets import WorkTicketsPanel
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from PySide6.QtWidgets import QLabel

from .conftest import build_client, envelope_ok

_CREATED = "2026-05-29T23:35:53.169304"
_UPDATED = "2026-05-30T08:15:00.000000"


def _list_handler(path: str, records: list[dict]):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == path:
            return httpx.Response(200, json=envelope_ok(records))
        if req.method == "GET" and req.url.path.startswith("/references/touching/"):
            return httpx.Response(
                200, json=envelope_ok({"as_source": [], "as_target": []})
            )
        return httpx.Response(200, json=envelope_ok([]))

    return handler


# --- mutable panels: Created + Updated synthetic columns --------------------


def test_decisions_created_column_formatted(qtbot):
    rec = {
        "identifier": "DEC-001",
        "created_at": _CREATED,
        "updated_at": _UPDATED,
    }
    panel = DecisionsPanel(build_client(_list_handler("/decisions", [rec])))
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    assert "Created" in titles
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)
    assert out[0]["created_at_display"] != _CREATED


def test_decisions_detail_shows_created_and_updated(qtbot):
    rec = {
        "identifier": "DEC-001",
        "title": "D",
        "created_at": _CREATED,
        "updated_at": _UPDATED,
    }
    panel = DecisionsPanel(build_client(_list_handler("/decisions", [rec])))
    qtbot.addWidget(panel)
    detail = panel.render_detail(rec, {"references": {"as_source": [], "as_target": []}})
    texts = {w.text() for w in detail.findChildren(QLabel)}
    assert "Created" in texts
    assert "Last Updated" in texts
    assert format_timestamp(_CREATED) in texts
    assert format_timestamp(_UPDATED) in texts


def test_risks_created_column_formatted(qtbot):
    rec = {
        "identifier": "RSK-001",
        "created_at": _CREATED,
        "updated_at": _UPDATED,
    }
    panel = RisksPanel(build_client(_list_handler("/risks", [rec])))
    qtbot.addWidget(panel)
    assert "Created" in [c.title for c in panel.list_columns()]
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)
    assert out[0]["created_at_display"] != _CREATED


def test_reference_books_created_and_updated_columns(qtbot):
    rec = {
        "reference_book_identifier": "RB-001",
        "reference_book_created_at": _CREATED,
        "reference_book_updated_at": _UPDATED,
    }
    panel = ReferenceBooksPanel(
        build_client(_list_handler("/reference-books", [rec]))
    )
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    fields = [c.field for c in panel.list_columns()]
    assert "Created" in titles and "Updated" in titles
    # The raw ISO column must be gone, replaced by the formatted synthetic.
    assert "reference_book_updated_at" not in fields
    assert "updated_at_display" in fields
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)
    assert out[0]["updated_at_display"] == format_timestamp(_UPDATED)


def test_work_tickets_created_and_updated_columns(qtbot):
    rec = {
        "work_ticket_identifier": "WT-001",
        "work_ticket_created_at": _CREATED,
        "work_ticket_updated_at": _UPDATED,
    }
    panel = WorkTicketsPanel(build_client(_list_handler("/work-tickets", [rec])))
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    fields = [c.field for c in panel.list_columns()]
    assert "Created" in titles and "Updated" in titles
    assert "work_ticket_updated_at" not in fields
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)
    assert out[0]["updated_at_display"] == format_timestamp(_UPDATED)


def test_close_out_payloads_created_and_updated_columns(qtbot):
    rec = {
        "close_out_payload_identifier": "COP-001",
        "close_out_payload_created_at": _CREATED,
        "close_out_payload_updated_at": _UPDATED,
    }
    panel = CloseOutPayloadsPanel(
        build_client(_list_handler("/close-out-payloads", [rec]))
    )
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    fields = [c.field for c in panel.list_columns()]
    assert "Created" in titles and "Updated" in titles
    assert "close_out_payload_updated_at" not in fields
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)
    assert out[0]["updated_at_display"] == format_timestamp(_UPDATED)


# --- immutable panels: Created-only -----------------------------------------


def test_deposit_events_created_column_replaced_with_formatted(qtbot):
    rec = {
        "deposit_event_identifier": "DEP-001",
        "deposit_event_outcome": "success",
        "deposit_event_created_at": _CREATED,
    }
    panel = DepositEventsPanel(
        build_client(_list_handler("/deposit-events", [rec]))
    )
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    fields = [c.field for c in panel.list_columns()]
    assert "Created" in titles
    # The raw ISO created column is gone, replaced by the formatted synthetic.
    assert "deposit_event_created_at" not in fields
    assert "created_at_display" in fields
    out = panel.fetch_records()
    assert out[0]["created_at_display"] == format_timestamp(_CREATED)
    assert out[0]["created_at_display"] != _CREATED


def test_deposit_events_detail_immutable_em_dash(qtbot):
    rec = {
        "deposit_event_identifier": "DEP-001",
        "deposit_event_outcome": "success",
        "deposit_event_created_at": _CREATED,
    }
    panel = DepositEventsPanel(
        build_client(_list_handler("/deposit-events", [rec]))
    )
    qtbot.addWidget(panel)
    detail = panel.render_detail(rec, {"references": {"as_source": [], "as_target": []}})
    texts = [w.text() for w in detail.findChildren(QLabel)]
    assert "Last Updated" in texts
    assert format_timestamp(_CREATED) in texts
    assert "—" in texts


def test_topics_detail_immutable_em_dash(qtbot):
    rec = {
        "identifier": "TOP-001",
        "name": "Topic",
        "created_at": _CREATED,
    }
    panel = TopicsPanel(build_client(_list_handler("/topics", [rec])))
    qtbot.addWidget(panel)
    detail = panel.render_detail(rec, {"references": {"as_source": [], "as_target": []}})
    texts = [w.text() for w in detail.findChildren(QLabel)]
    assert "Created" in texts
    assert "Last Updated" in texts
    assert format_timestamp(_CREATED) in texts
    assert "—" in texts


# --- singleton versioned panels: detail-only, immutable ---------------------


def _version_rec() -> dict[str, Any]:
    return {
        "version": 1,
        "is_current": True,
        "payload": {"summary": "x"},
        "created_at": _CREATED,
    }


def test_charter_detail_shows_created_em_dash(qtbot):
    panel = CharterPanel(build_client(_list_handler("/charter/versions", [])))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_version_rec(), {"references": {"as_source": [], "as_target": []}})
    texts = [w.text() for w in detail.findChildren(QLabel)]
    assert "Created" in texts
    assert "Last Updated" in texts
    assert format_timestamp(_CREATED) in texts
    assert "—" in texts


def test_status_detail_shows_created_em_dash(qtbot):
    panel = StatusPanel(build_client(_list_handler("/status/versions", [])))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_version_rec(), {"references": {"as_source": [], "as_target": []}})
    texts = [w.text() for w in detail.findChildren(QLabel)]
    assert "Created" in texts
    assert "Last Updated" in texts
    assert format_timestamp(_CREATED) in texts
    assert "—" in texts
