"""WTK-004: Workstreams panel — read-only browse + detail, attention flag."""

from __future__ import annotations

from typing import Any

import httpx
from crmbuilder_v2.ui.panels.workstreams import WorkstreamsPanel
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


def _handler(workstreams=_WORKSTREAMS, *, touching=_TOUCHING_WSK001):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if req.method == "GET" and path == "/workstreams":
            return httpx.Response(200, json=envelope_ok(workstreams))
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


def test_detail_pane_renders_parent_pi_and_work_tasks(qtbot):
    panel = WorkstreamsPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(
        _WORKSTREAMS[0], {"references": _TOUCHING_WSK001}
    )
    labels = [w.text() for w in detail.findChildren(QLabel)]
    # Parent PI link.
    assert any('href="planning_item:PI-114"' in t for t in labels)
    # Both Work Task links present.
    assert any('href="work_task:WTK-001"' in t for t in labels)
    assert any('href="work_task:WTK-002"' in t for t in labels)
    # Key scalar fields surfaced.
    line_edits = [w.text() for w in detail.findChildren(QLineEdit)]
    assert "WSK-001" in line_edits
    assert "Development" in line_edits


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
