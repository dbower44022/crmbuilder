"""PI-031: planning_items resolution chain (adapted to session-grain schema)."""

from __future__ import annotations

import httpx
from crmbuilder_v2.ui.panels.planning_items import PlanningItemsPanel
from PySide6.QtWidgets import QLabel

from .conftest import build_client, envelope_ok


def _resolved_pi(ident: str = "PI-107") -> dict:
    return {
        "identifier": ident,
        "title": "Resolved item",
        "description": "desc",
        "item_type": "pending_work",
        "status": "Resolved",
        "resolution_reference": None,
        "executive_summary": "summary",
    }


def _traced_handler():
    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/references/touching/planning_item/PI-107":
            return httpx.Response(200, json=envelope_ok({
                "as_source": [],
                "as_target": [
                    {"relationship": "resolves", "source_type": "conversation", "source_id": "CNV-020"},
                ],
            }))
        if p == "/references/touching/conversation/CNV-020":
            return httpx.Response(200, json=envelope_ok({
                "as_source": [
                    {"relationship": "conversation_belongs_to_session", "target_type": "session", "target_id": "SES-118"},
                ],
                "as_target": [
                    {"relationship": "deposit_event_wrote_record", "source_type": "deposit_event", "source_id": "DEP-110"},
                ],
            }))
        if p == "/sessions/SES-118/commits":
            return httpx.Response(200, json=envelope_ok([
                {"commit_identifier": "CM-0052", "commit_message_first_line": "the fix"},
            ]))
        return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})

    return handler


def _untraced_handler():
    def handler(req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/references/touching/planning_item/PI-107":
            # No resolves edge — a legacy manual status flip.
            return httpx.Response(200, json=envelope_ok({"as_source": [], "as_target": []}))
        return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})

    return handler


def _hrefs(widget) -> list[str]:
    out = []
    for lbl in widget.findChildren(QLabel):
        t = lbl.text()
        if 'href="' in t:
            out.append(t)
    return out


def test_resolved_item_renders_full_chain(qtbot):
    panel = PlanningItemsPanel(build_client(_traced_handler()))
    qtbot.addWidget(panel)
    record = _resolved_pi()
    extras = panel.fetch_detail_extras(record)
    assert extras["resolution_chain"]["traced"] is True
    detail = panel.render_detail(record, extras)
    blob = " ".join(_hrefs(detail))
    assert 'href="conversation:CNV-020"' in blob
    assert 'href="deposit_event:DEP-110"' in blob
    assert 'href="session:SES-118"' in blob
    assert 'href="commit:CM-0052"' in blob


def test_chain_extras_absent_for_open_item(qtbot):
    panel = PlanningItemsPanel(build_client(_traced_handler()))
    qtbot.addWidget(panel)
    record = _resolved_pi()
    record["status"] = "Open"
    extras = panel.fetch_detail_extras(record)
    assert "resolution_chain" not in extras


def test_resolved_without_trace_renders_degraded(qtbot):
    panel = PlanningItemsPanel(build_client(_untraced_handler()))
    qtbot.addWidget(panel)
    record = _resolved_pi()
    extras = panel.fetch_detail_extras(record)
    assert extras["resolution_chain"]["traced"] is False
    detail = panel.render_detail(record, extras)
    texts = " ".join(lbl.text() for lbl in detail.findChildren(QLabel))
    assert "without a governance trace" in texts
    assert 'href="planning_item:PI-033"' in texts
