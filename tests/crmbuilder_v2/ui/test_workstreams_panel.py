"""WTK-004: Workstreams panel — read-only browse + detail, attention flag."""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.workstreams import WorkstreamsPanel
from crmbuilder_v2.ui.widgets.references_section import WorkTaskGridSection
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from .conftest import build_client, envelope_ok


def _workstream(
    ident: str,
    *,
    phase: str = "Development",
    status: str = "In Progress",
    needs_attention: bool = False,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "workstream_identifier": ident,
        "workstream_phase_type": phase,
        "workstream_title": f"{phase} — {ident}",
        "workstream_description": f"description of {ident}",
        "workstream_status": status,
        "workstream_notes": None,
        "workstream_needs_attention": needs_attention,
        "workstream_needs_attention_reason": reason,
        "workstream_created_at": "2026-05-31T14:56:11.023414",
        "workstream_updated_at": "2026-05-31T14:56:11.024743",
        "workstream_deleted_at": None,
        "workstream_started_at": "2026-05-31T14:56:11.023959",
        "workstream_completed_at": None,
    }


_WORKSTREAMS = [
    _workstream("WSK-001"),
    _workstream(
        "WSK-002",
        phase="Testing",
        status="Blocked",
        needs_attention=True,
        reason="Awaiting a human review of the migration plan",
    ),
]

# A WSK-001 touching response: parent PI edge (as_source) + two Work Task
# membership edges (as_target).
_TOUCHING_WSK001 = {
    "as_source": [
        {
            "source_type": "workstream",
            "source_id": "WSK-001",
            "target_type": "planning_item",
            "target_id": "PI-114",
            "relationship": "workstream_belongs_to_planning_item",
        }
    ],
    "as_target": [
        {
            "source_type": "work_task",
            "source_id": "WTK-002",
            "target_type": "workstream",
            "target_id": "WSK-001",
            "relationship": "work_task_belongs_to_workstream",
        },
        {
            "source_type": "work_task",
            "source_id": "WTK-001",
            "target_type": "workstream",
            "target_id": "WSK-001",
            "relationship": "work_task_belongs_to_workstream",
        },
    ],
}


# Child Work Task records for WSK-001 (carry area + claim state, the two
# fields the edge summary omits). WTK-001 is claimed; WTK-002 is unclaimed.
_CHILD_WORK_TASKS = [
    {
        "work_task_identifier": "WTK-001",
        "work_task_title": "Storage layer migration",
        "work_task_area": "storage",
        "work_task_status": "Complete",
        "work_task_claimed_by": "AGP-dev-storage",
    },
    {
        "work_task_identifier": "WTK-002",
        "work_task_title": "API endpoints",
        "work_task_area": "api",
        "work_task_status": "Ready",
        "work_task_claimed_by": None,
    },
]


def _handler(
    workstreams=_WORKSTREAMS, *, touching=_TOUCHING_WSK001, work_tasks=_CHILD_WORK_TASKS
):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if req.method == "GET" and path == "/workstreams":
            return httpx.Response(200, json=envelope_ok(workstreams))
        if req.method == "GET" and path == "/work-tasks":
            return httpx.Response(200, json=envelope_ok(work_tasks))
        if req.method == "GET" and path.startswith(
            "/references/touching/workstream/"
        ):
            return httpx.Response(200, json=envelope_ok(touching))
        if req.method == "GET" and path.startswith("/workstreams/"):
            ident = path.rsplit("/", 1)[-1]
            for w in workstreams:
                if w["workstream_identifier"] == ident:
                    return httpx.Response(200, json=envelope_ok(w))
            return httpx.Response(
                404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]}
            )
        return httpx.Response(
            404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]}
        )

    return handler


def test_columns_and_no_new_button(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    assert titles == [
        "Identifier",
        "Phase",
        "Title",
        "Status",
        "Attention",
        "Updated",
    ]
    # Read-only: no New button.
    assert panel.findChild(QPushButton, "new_workstream_button") is None


def test_records_load_and_attention_column(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=3000)
    processed = panel._post_process_records([dict(w) for w in _WORKSTREAMS])
    assert processed[0]["needs_attention_display"] == "—"
    assert processed[1]["needs_attention_display"].startswith("⚠")
    # Updated synthetic column is formatted, not the raw ISO string.
    assert processed[0]["updated_at_display"] != _WORKSTREAMS[0]["workstream_updated_at"]


def _detail_extras(touching=_TOUCHING_WSK001, children=_CHILD_WORK_TASKS):
    return {"references": touching, "child_work_tasks": children}


def _work_task_grid(detail):
    grids = detail.findChildren(WorkTaskGridSection)
    assert len(grids) == 1
    return grids[0]


def _grid_headers(grid):
    model = grid._model
    return [
        model.headerData(c, Qt.Orientation.Horizontal)
        for c in range(model.columnCount())
    ]


def test_detail_pane_renders_parent_pi_and_work_tasks(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_WORKSTREAMS[0], _detail_extras())
    labels = [w.text() for w in detail.findChildren(QLabel)]
    # Parent PI link still rendered as a navigable label.
    assert any('href="planning_item:PI-114"' in t for t in labels)
    # The Work Tasks section is now a grid, not href labels.
    grid = _work_task_grid(detail)
    identifiers = {r["identifier"] for r in grid._model._rows}
    assert identifiers == {"WTK-001", "WTK-002"}
    # Key scalar fields surfaced.
    line_edits = [w.text() for w in detail.findChildren(QLineEdit)]
    assert "WSK-001" in line_edits
    assert "Development" in line_edits


def test_work_task_grid_renders_all_five_fields(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_WORKSTREAMS[0], _detail_extras())
    grid = _work_task_grid(detail)
    # Column model: identifier, title, area, status, claim state.
    assert _grid_headers(grid) == [
        "Identifier",
        "Title",
        "Area",
        "Status",
        "Claim state",
    ]
    by_id = {r["identifier"]: r for r in grid._model._rows}
    claimed = by_id["WTK-001"]
    assert claimed["title"] == "Storage layer migration"
    assert claimed["area"] == "storage"
    assert claimed["status"] == "Complete"
    assert claimed["claim_state"] == "Claimed · AGP-dev-storage"
    unclaimed = by_id["WTK-002"]
    assert unclaimed["area"] == "api"
    assert unclaimed["status"] == "Ready"
    assert unclaimed["claim_state"] == "Unclaimed"
    # Read-only: no Add affordance on the Work Task grid.
    add_btn = grid.findChild(QPushButton, "references_section_add_button")
    assert add_btn is None


def test_work_task_grid_empty_case_preserved(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _WORKSTREAMS[0],
        {"references": {"as_source": [], "as_target": []}, "child_work_tasks": []},
    )
    assert not detail.findChildren(WorkTaskGridSection)
    labels = [w.text() for w in detail.findChildren(QLabel)]
    assert "No Work Tasks recorded." in labels


def test_fetch_detail_extras_joins_edges_with_records(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    extras = panel.fetch_detail_extras(_WORKSTREAMS[0])
    children = {c["work_task_identifier"]: c for c in extras["child_work_tasks"]}
    # Both membership edges resolved to their full records (area + claim state).
    assert set(children) == {"WTK-001", "WTK-002"}
    assert children["WTK-001"]["work_task_area"] == "storage"
    assert children["WTK-002"]["work_task_claimed_by"] is None


def test_fetch_detail_extras_degrades_when_record_missing(qtbot):
    # WSK-001's edges name WTK-001/002, but the record list omits them.
    panel = WorkstreamsPanel(build_client(_handler(work_tasks=[])))
    qtbot.addWidget(panel)
    extras = panel.fetch_detail_extras(_WORKSTREAMS[0])
    children = extras["child_work_tasks"]
    # The membership edge set still defines the rows; missing records degrade
    # to an identifier-only fallback (area/claim state render as the dash).
    assert {c["work_task_identifier"] for c in children} == {"WTK-001", "WTK-002"}
    assert all("work_task_area" not in c for c in children)


def test_detail_pane_attention_banner_when_flagged(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _WORKSTREAMS[1], {"references": {"as_source": [], "as_target": []}}
    )
    banner = detail.findChild(QLabel, "workstream_needs_attention_banner")
    assert banner is not None
    assert "Awaiting a human review" in banner.text()


def test_detail_pane_no_attention_banner_when_clear(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _WORKSTREAMS[0], {"references": _TOUCHING_WSK001}
    )
    assert detail.findChild(QLabel, "workstream_needs_attention_banner") is None


def test_detail_pane_references_add_affordance_disabled(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _WORKSTREAMS[0], {"references": {"as_source": [], "as_target": []}}
    )
    add_btn = detail.findChild(QPushButton, "references_section_add_button")
    # Read-only monitoring panel: the Add affordance is suppressed.
    assert add_btn is not None
    assert add_btn.isHidden()
