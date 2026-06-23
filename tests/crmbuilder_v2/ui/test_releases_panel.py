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
# References touching REL-001: the one project_belongs_to_release edge (PRJ-031).
_EDGES = {
    "as_source": [],
    "as_target": [
        {
            "id": 501,
            "source_type": "project",
            "source_id": "PRJ-031",
            "target_type": "release",
            "target_id": "REL-001",
            "relationship": "project_belongs_to_release",
        }
    ],
}
# Project catalog for the Add-to-scope picker.
_PROJECTS = [
    {"project_identifier": "PRJ-031", "project_name": "Release Pipeline"},
    {"project_identifier": "PRJ-040", "project_name": "Unassigned Project"},
]


_HISTORY = {
    "release_identifier": "REL-001",
    "status": "development",
    "events": [
        {"event_kind": "transition", "outcome": None,
         "summary": "ready -> development", "work_task": None, "area": None,
         "pipeline_event_created_at": "2026-06-22T10:00:00+00:00"},
        {"event_kind": "dispatch", "outcome": None, "summary": "dispatch WTK-9",
         "work_task": "WTK-9", "area": "storage",
         "pipeline_event_created_at": "2026-06-22T10:01:00+00:00"},
        {"event_kind": "agent_outcome", "outcome": "delivered",
         "summary": "verified + merged", "work_task": "WTK-9", "area": "storage",
         "pipeline_event_created_at": "2026-06-22T10:05:00+00:00"},
    ],
}


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
        "edges": _EDGES,
        "history": _HISTORY,
    }
    extras.update(overrides)
    return extras


def _handler(releases=_RELEASES, *, captured: list | None = None):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        method = req.method
        if captured is not None and method in ("POST", "PATCH", "DELETE"):
            captured.append((method, path, req.content.decode()))
        if method == "DELETE" and path.startswith("/references/"):
            return httpx.Response(200, json=envelope_ok({"deleted": True}))
        if method == "PATCH" and path.startswith("/releases/"):
            return httpx.Response(200, json=envelope_ok(_release()))
        if method == "POST" and path == "/releases":
            return httpx.Response(201, json=envelope_ok(_release("REL-009")))
        if method == "POST" and path == "/references":
            return httpx.Response(201, json=envelope_ok({"id": 777}))
        if method == "GET" and path == "/releases":
            return httpx.Response(200, json=envelope_ok(releases))
        if method == "GET" and path == "/releases/lane-holder":
            return httpx.Response(200, json=envelope_ok(_LANE_HOLDER))
        if method == "GET" and path.startswith("/references/touching/release/"):
            return httpx.Response(200, json=envelope_ok(_EDGES))
        if method == "GET" and path == "/projects":
            return httpx.Response(200, json=envelope_ok(_PROJECTS))
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
        if method == "GET" and path.endswith("/history"):
            return httpx.Response(200, json=envelope_ok(_HISTORY))
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


def test_detail_has_five_tabs(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    tabs = detail.findChild(QTabWidget)
    assert tabs is not None
    assert [tabs.tabText(i) for i in range(tabs.count())] == [
        "Overview", "Composition", "Conflicts", "Reopens", "History",
    ]


def test_history_tab_shows_position_and_events(qtbot):
    # REQ-315: the History tab surfaces the pipeline position + ordered events.
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    text = " ".join(
        lbl.text() for lbl in detail.findChildren(QLabel) if lbl.text()
    )
    assert "Pipeline position:" in text
    assert "ready -> development" in text          # a transition event
    assert "agent_outcome" in text and "[delivered]" in text  # an agent outcome
    assert "WTK-9" in text                          # correlation tag


def test_history_tab_degrades_when_unavailable(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    extras = _full_extras(history=None, errors={"history": "boom"})
    detail = panel.render_detail(_RELEASES[0], extras)
    text = " ".join(lbl.text() for lbl in detail.findChildren(QLabel) if lbl.text())
    assert "History unavailable: boom" in text


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
    qtbot.waitUntil(lambda: any(c[1] == "/releases/REL-001/qa-pass" for c in captured), timeout=3000)


def test_transition_release_client_request_shape(qtbot):
    captured: list = []
    client = build_client(_handler(captured=captured))
    client.transition_release("REL-001", "reconciliation", actor="claude")
    assert captured
    _method, path, body = captured[0]
    assert path == "/releases/REL-001/transition"
    assert '"to_status":"reconciliation"' in body
    assert '"actor":"claude"' in body


def test_resolve_conflict_client_request_shape(qtbot):
    captured: list = []
    client = build_client(_handler(captured=captured))
    client.resolve_reconciliation_conflict(
        7, decision_identifier="DEC-9", resolved_value={"value": True}
    )
    _method, path, body = captured[0]
    assert path == "/reconciliation-conflicts/7/resolve"
    assert '"decision_identifier":"DEC-9"' in body
    assert '"value":true' in body


# --- PI-226: human planning workbench --------------------------------------


def test_new_release_button_present(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    assert panel.findChild(QPushButton, "new_release_button") is not None


def test_action_row_has_edit(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    assert "Edit…" in {b.text() for b in detail.findChildren(QPushButton)}


def test_composition_scope_actions_when_open(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    # Default extras have freeze_band == "open" (development_planning).
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    assert detail.findChild(QPushButton, "add_project_button") is not None
    assert "Remove" in {b.text() for b in detail.findChildren(QPushButton)}


def test_composition_scope_closed_when_frozen(qtbot):
    panel = ReleasesPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    frozen = _full_extras(freeze={"freeze_band": "locked"})
    detail = panel.render_detail(_RELEASES[0], frozen)
    assert detail.findChild(QPushButton, "add_project_button") is None
    labels = [w.text() for w in detail.findChildren(QLabel)]
    assert any("Scope is closed" in t for t in labels)


def test_create_release_client_shape(qtbot):
    captured: list = []
    client = build_client(_handler(captured=captured))
    client.create_release({"release_title": "R", "release_description": "d", "release_lane_order": 2})
    method, path, body = captured[0]
    assert (method, path) == ("POST", "/releases")
    assert '"release_title":"R"' in body and '"release_lane_order":2' in body


def test_patch_release_client_shape(qtbot):
    captured: list = []
    client = build_client(_handler(captured=captured))
    client.patch_release("REL-001", {"release_title": "New"})
    method, path, body = captured[0]
    assert (method, path) == ("PATCH", "/releases/REL-001")
    assert '"release_title":"New"' in body


def test_release_create_dialog_validates_and_returns_values(qtbot):
    from crmbuilder_v2.ui.panels.releases import _ReleaseCreateDialog

    dlg = _ReleaseCreateDialog()
    qtbot.addWidget(dlg)
    dlg._title.setText("My release")
    dlg._description.setPlainText("Scope of this release")
    dlg._order.setValue(3)
    assert dlg.values() == ("My release", "Scope of this release", 3)


def test_add_project_excludes_in_scope_and_posts_edge(qtbot, monkeypatch):
    captured: list = []
    panel = ReleasesPanel(build_client(_handler(captured=captured)))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    qtbot.addWidget(detail)
    # Auto-accept the picker; it should offer PRJ-040 (PRJ-031 is already scoped).
    monkeypatch.setattr(panel, "_exec_dialog", lambda dlg, cb: cb())
    panel._do_add_project("REL-001", _full_extras())
    qtbot.waitUntil(
        lambda: any(c[1] == "/references" for c in captured), timeout=3000
    )
    _m, _p, body = next(c for c in captured if c[1] == "/references")
    assert '"relationship":"project_belongs_to_release"' in body
    assert '"source_id":"PRJ-040"' in body  # the unassigned one, not PRJ-031


def test_remove_project_deletes_scope_edge(qtbot, monkeypatch):
    captured: list = []
    panel = ReleasesPanel(build_client(_handler(captured=captured)))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RELEASES[0], _full_extras())
    qtbot.addWidget(detail)
    monkeypatch.setattr(panel, "_confirm", lambda *a, **k: True)
    panel._do_remove_project("REL-001", "PRJ-031", _full_extras())
    # _EDGES maps PRJ-031 -> edge id 501.
    qtbot.waitUntil(
        lambda: any(c[1] == "/references/501" for c in captured), timeout=3000
    )
    assert captured[-1][0] == "DELETE"
