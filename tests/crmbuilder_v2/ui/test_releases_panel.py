"""PI-224: Releases hub panel — master/detail browse + lifecycle actions.

Covers the master columns and synthetic fields, the tabbed detail render
(badges, action row, Overview/Composition/Conflicts/Reopens), the
per-section degradation in ``fetch_detail_extras``, the legal-transition
gating, and the action client methods' request shapes.
"""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.releases import ReleasesPanel
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
)

from .conftest import build_client, envelope_ok


def _release(
    ident: str = "REL-001",
    *,
    status: str = "development_planning",
    lane_order: int | None = None,
) -> dict[str, Any]:
    return {
        "release_identifier": ident,
        "release_title": f"Release {ident}",
        "release_description": "A staged delivery container.",
        "release_notes": None,
        "release_status": status,
        "release_lane_order": lane_order,
        "release_frozen_at": None,
        "release_planned_completely_at": None,
        "release_qa_passed_at": None,
        "release_test_passed_at": None,
        "release_shipped_at": None,
        "release_cancelled_at": None,
        "release_superseded_at": None,
        "release_created_at": "2026-06-17T10:00:00",
        "release_updated_at": "2026-06-17T11:00:00",
        "release_deleted_at": None,
    }


_RELEASES = [
    _release("REL-001", status="development_planning"),
    _release("REL-002", status="development", lane_order=1),
]

_FREEZE = {"release_identifier": "REL-001", "status": "development_planning", "freeze_band": "open"}
_TEMPERATURE = {"release_identifier": "REL-001", "status": "development_planning", "temperature": "conceptual"}
_READINESS = {
    "release_identifier": "REL-001",
    "frozen": False,
    "in_scope_planning_items": ["PI-300"],
    "undecomposed_planning_items": ["PI-300"],
    "designs_authored": 0,
    "sequencing_ok": True,
    "ready": False,
    "missing": ["decompose PI-300"],
}
_COMPOSITION = {
    "release_identifier": "REL-001",
    "projects": [{"project_identifier": "PRJ-031", "planning_items": ["PI-300", "PI-301"]}],
}
_VERSIONS = [
    {"artifact_type": "entity", "artifact_identifier": "ENT-1", "version_number": 2},
]
_CONFLICTS = [
    {
        "id": 7,
        "artifact_type": "entity",
        "artifact_identifier": "ENT-1",
        "facet": "email.required",
        "conflict_type": "facet_value",
        "status": "open",
        "resolved_value": None,
        "resolving_decision_identifier": None,
    },
    {
        "id": 8,
        "artifact_type": "entity",
        "artifact_identifier": "ENT-2",
        "facet": "name.maxLength",
        "conflict_type": "facet_value",
        "status": "resolved",
        "resolved_value": {"value": 255},
        "resolving_decision_identifier": "DEC-9",
    },
]
_REOPENS = {
    "reopens": [
        {
            "id": 3,
            "area": "access",
            "reason": "API needs a wider column",
            "status": "open",
            "cascade_areas": ["api", "mcp", "ui"],
            "revalidated_areas": ["api"],
            "approval_tier": "lead",
            "approval_decision_identifier": "DEC-10",
        }
    ],
    "paused_areas": ["api", "mcp", "ui"],
}
_AREA_OWNERSHIP = {"access": "AGP-dev-access"}
_LANE_HOLDER = _release("REL-002", status="development", lane_order=1)


def _full_extras(**overrides: Any) -> dict[str, Any]:
    extras = {
        "errors": {},
        "freeze": _FREEZE,
        "temperature": _TEMPERATURE,
        "readiness": _READINESS,
        "composition": _COMPOSITION,
        "versions": _VERSIONS,
        "conflicts": _CONFLICTS,
        "reopens": _REOPENS,
        "area_ownership": _AREA_OWNERSHIP,
        "lane_holder": _LANE_HOLDER,
    }
    extras.update(overrides)
    return extras


def _handler(releases=_RELEASES, *, captured: list | None = None):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        method = req.method
        if captured is not None and method == "POST":
            captured.append((path, req.url.query.decode(), req.content.decode()))
        if method == "GET" and path == "/releases":
            return httpx.Response(200, json=envelope_ok(releases))
        if method == "GET" and path == "/releases/lane-holder":
            return httpx.Response(200, json=envelope_ok(_LANE_HOLDER))
        if method == "GET" and path.endswith("/freeze"):
            return httpx.Response(200, json=envelope_ok(_FREEZE))
        if method == "GET" and path.endswith("/temperature"):
            return httpx.Response(200, json=envelope_ok(_TEMPERATURE))
        if method == "GET" and path.endswith("/planning-readiness"):
            return httpx.Response(200, json=envelope_ok(_READINESS))
        if method == "GET" and path.endswith("/composition"):
            return httpx.Response(200, json=envelope_ok(_COMPOSITION))
        if method == "GET" and path.endswith("/versions"):
            return httpx.Response(200, json=envelope_ok(_VERSIONS))
        if method == "GET" and path.endswith("/reconciliation-conflicts"):
            return httpx.Response(200, json=envelope_ok(_CONFLICTS))
        if method == "GET" and path.endswith("/area-reopens"):
            return httpx.Response(200, json=envelope_ok(_REOPENS))
        if method == "GET" and path.endswith("/area-ownership"):
            return httpx.Response(200, json=envelope_ok(_AREA_OWNERSHIP))
        if method == "GET" and path.endswith("/reopen-impact"):
            return httpx.Response(
                200,
                json=envelope_ok(
                    {"downstream_areas": ["api", "mcp", "ui"], "tier": "lead", "is_repeat": False}
                ),
            )
        if method == "POST":
            return httpx.Response(200, json=envelope_ok({"ok": True}))
        return httpx.Response(404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]})

    return handler


# --- master list -----------------------------------------------------------


def test_columns(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    assert [c.title for c in panel.list_columns()] == [
        "Identifier", "Title", "Status", "Lane", "Updated",
    ]


def test_records_load_and_synthetic_fields(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=3000)
    processed = panel._post_process_records([dict(r) for r in _RELEASES])
    # Synthetic identifier mirrors release_identifier (drives base selection).
    assert processed[0]["identifier"] == "REL-001"
    assert processed[0]["lane_order_display"] == "—"
    assert processed[1]["lane_order_display"] == "1"
    assert processed[0]["updated_at_display"] != _RELEASES[0]["release_updated_at"]


# --- detail render ---------------------------------------------------------


def test_detail_badges_and_action_row(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    labels = [w.text() for w in detail.findChildren(QLabel)]
    assert any("Status: development_planning" in t for t in labels)
    assert any("Freeze: open" in t for t in labels)
    assert any("Temperature: conceptual" in t for t in labels)
    buttons = {b.text() for b in detail.findChildren(QPushButton)}
    assert {
        "Transition…", "QA Pass", "Test Pass", "Set Lane Order…",
        "Open Correction…", "Reopen Area…",
    } <= buttons


def test_detail_has_four_tabs(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    tabs = detail.findChild(QTabWidget)
    assert tabs is not None
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Overview", "Composition", "Conflicts", "Reopens",
    ]


def test_overview_readiness_and_area_ownership(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    # The readiness + ownership facts land in read-only multi-line text blocks.
    plain = " ".join(w.toPlainText() for w in detail.findChildren(QPlainTextEdit))
    assert "Ready: no" in plain
    assert "access: AGP-dev-access" in plain


def test_conflicts_tab_open_conflict_has_resolve(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    buttons = {b.text() for b in detail.findChildren(QPushButton)}
    assert "Resolve…" in buttons  # the one open conflict
    labels = [w.text() for w in detail.findChildren(QLabel)]
    # The resolved conflict shows its decision, not a button.
    assert any("by DEC-9" in t for t in labels)


def test_reopens_tab_paused_areas_and_refreeze(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    labels = [w.text() for w in detail.findChildren(QLabel)]
    assert any("Paused areas: api, mcp, ui" in t for t in labels)
    assert any("revalidated 1/3" in t for t in labels)
    assert "Refreeze" in {b.text() for b in detail.findChildren(QPushButton)}


def test_composition_tab_projects_and_versions(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    labels = [w.text() for w in detail.findChildren(QLabel)]
    assert any('href="project:PRJ-031"' in t for t in labels)
    assert any("PI-300, PI-301" in t for t in labels)
    plain = " ".join(w.toPlainText() for w in detail.findChildren(QPlainTextEdit))
    assert "entity:ENT-1 v2" in plain


# --- detail extras degradation --------------------------------------------


def test_fetch_detail_extras_aggregates(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    extras = panel.fetch_detail_extras(_RELEASES[0])
    assert extras["freeze"]["freeze_band"] == "open"
    assert extras["readiness"]["ready"] is False
    assert extras["reopens"]["paused_areas"] == ["api", "mcp", "ui"]
    assert extras["errors"] == {}


def test_fetch_detail_extras_degrades_per_section(qtbot):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/composition"):
            return httpx.Response(
                500, json={"data": None, "meta": {}, "errors": [{"message": "boom"}]}
            )
        return _handler()(req)

    panel = ReleasesPanel(build_client(handler))
    qtbot.addWidget(panel)
    extras = panel.fetch_detail_extras(_RELEASES[0])
    # One failing section is captured in errors; the rest still resolve.
    assert "composition" in extras["errors"]
    assert extras["freeze"]["freeze_band"] == "open"
    # And the Composition tab renders the inline note rather than blanking.
    detail = panel.render_detail(_RELEASES[0], extras)
    labels = [w.text() for w in detail.findChildren(QLabel)]
    assert any("Unavailable" in t for t in labels)


# --- transition gating + action requests -----------------------------------


def test_transition_terminal_status_shows_message(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    # Render to create the inline action-status label; retain it so the C++
    # object backing the label isn't reclaimed before the assertion.
    detail = panel.render_detail(_release("REL-001", status="shipped"), _full_extras())
    qtbot.addWidget(detail)
    panel._do_transition("REL-001", "shipped")
    assert "terminal" in panel._action_status.text()


def test_qa_pass_issues_post(qtbot):
    captured: list = []
    panel = ReleasesPanel(build_client(_handler(captured=captured)))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    qtbot.addWidget(detail)
    panel._do_simple(panel._client.release_qa_pass, "REL-001")
    qtbot.waitUntil(lambda: any("/qa-pass" in c[0] for c in captured), timeout=3000)


def test_transition_release_client_request_shape(qtbot):
    captured: list = []
    client = build_client(_handler(captured=captured))
    client.transition_release("REL-001", "reconciliation", actor="claude")
    assert captured
    path, _query, body = captured[0]
    assert path == "/releases/REL-001/transition"
    assert '"to_status":"reconciliation"' in body
    assert '"actor":"claude"' in body


def test_resolve_conflict_client_request_shape(qtbot):
    captured: list = []
    client = build_client(_handler(captured=captured))
    client.resolve_reconciliation_conflict(
        7, decision_identifier="DEC-9", resolved_value={"value": True}
    )
    path, _query, body = captured[0]
    assert path == "/reconciliation-conflicts/7/resolve"
    assert '"decision_identifier":"DEC-9"' in body
    assert '"value":true' in body
