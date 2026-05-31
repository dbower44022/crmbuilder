"""WTK-004: Work Tasks panel — read-only browse + detail, area + claim state."""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.work_tasks import WorkTasksPanel
from PySide6.QtWidgets import QLabel, QLineEdit, QPushButton

from .conftest import build_client, envelope_ok


def _work_task(
    ident: str,
    *,
    area: str = "storage",
    status: str = "Complete",
    claimed_by: str | None = "CNV-039",
) -> dict[str, Any]:
    return {
        "work_task_identifier": ident,
        "work_task_title": f"Task {ident}",
        "work_task_description": f"description of {ident}",
        "work_task_status": status,
        "work_task_area": area,
        "work_task_claimed_by": claimed_by,
        "work_task_claimed_at": "2026-05-31T14:56:32.063944" if claimed_by else None,
        "work_task_notes": None,
        "work_task_created_at": "2026-05-31T14:56:31.690470",
        "work_task_updated_at": "2026-05-31T15:49:25.966811",
        "work_task_deleted_at": None,
        "work_task_started_at": "2026-05-31T14:57:17.643048",
        "work_task_completed_at": "2026-05-31T15:49:25.966436",
    }


_WORK_TASKS = [
    _work_task("WTK-001", area="storage", claimed_by="CNV-039"),
    _work_task("WTK-004", area="ui", status="Planned", claimed_by=None),
]

# A WTK-001 touching response: parent Workstream edge (as_source).
_TOUCHING_WTK001 = {
    "as_source": [
        {
            "source_type": "work_task",
            "source_id": "WTK-001",
            "target_type": "workstream",
            "target_id": "WSK-001",
            "relationship": "work_task_belongs_to_workstream",
        }
    ],
    "as_target": [],
}


def _handler(work_tasks=_WORK_TASKS, *, touching=_TOUCHING_WTK001):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if req.method == "GET" and path == "/work-tasks":
            return httpx.Response(200, json=envelope_ok(work_tasks))
        if req.method == "GET" and path.startswith(
            "/references/touching/work_task/"
        ):
            return httpx.Response(200, json=envelope_ok(touching))
        if req.method == "GET" and path.startswith("/work-tasks/"):
            ident = path.rsplit("/", 1)[-1]
            for w in work_tasks:
                if w["work_task_identifier"] == ident:
                    return httpx.Response(200, json=envelope_ok(w))
            return httpx.Response(
                404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]}
            )
        return httpx.Response(
            404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]}
        )

    return handler


def test_columns_and_no_new_button(qtbot):
    panel = WorkTasksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    assert titles == [
        "Identifier",
        "Title",
        "Area",
        "Status",
        "Claimed by",
        "Updated",
    ]
    # Read-only: no New button.
    assert panel.findChild(QPushButton, "new_work_task_button") is None


def test_records_load_and_claim_column(qtbot):
    panel = WorkTasksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=3000)
    processed = panel._post_process_records([dict(w) for w in _WORK_TASKS])
    assert processed[0]["claimed_by_display"] == "CNV-039"
    # Unclaimed task renders the em-dash placeholder.
    assert processed[1]["claimed_by_display"] == "—"
    assert processed[0]["updated_at_display"] != _WORK_TASKS[0]["work_task_updated_at"]


def test_detail_pane_renders_area_claim_and_parent_workstream(qtbot):
    panel = WorkTasksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _WORK_TASKS[0], {"references": _TOUCHING_WTK001}
    )
    labels = [w.text() for w in detail.findChildren(QLabel)]
    # Parent Workstream link.
    assert any('href="workstream:WSK-001"' in t for t in labels)
    # Area + claim surfaced as scalar fields.
    line_edits = [w.text() for w in detail.findChildren(QLineEdit)]
    assert "storage" in line_edits
    assert "CNV-039" in line_edits
    assert "WTK-001" in line_edits


def test_detail_pane_no_parent_workstream_shows_placeholder(qtbot):
    panel = WorkTasksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _WORK_TASKS[1], {"references": {"as_source": [], "as_target": []}}
    )
    labels = [w.text() for w in detail.findChildren(QLabel)]
    assert any("No parent recorded" in t for t in labels)
    # No spurious workstream link.
    assert not any('href="workstream:' in t for t in labels)


def test_detail_pane_references_add_affordance_disabled(qtbot):
    panel = WorkTasksPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _WORK_TASKS[0], {"references": {"as_source": [], "as_target": []}}
    )
    add_btn = detail.findChild(QPushButton, "references_section_add_button")
    # Read-only monitoring panel: the Add affordance is suppressed.
    assert add_btn is not None
    assert add_btn.isHidden()
