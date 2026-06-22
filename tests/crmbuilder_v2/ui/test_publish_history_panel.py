"""Publish History panel + client tests — PI-266 (PRJ-042 / REQ-293)."""

from __future__ import annotations

import httpx
from crmbuilder_v2.ui.panels.publish_history import (
    PublishHistoryPanel,
    _scope_display,
    _verification_line,
)
from PySide6.QtWidgets import QPushButton

from .conftest import build_client, envelope_ok


def _run(ident, instance="INST-001", status="succeeded", **kw):
    return {
        "publish_run_identifier": ident,
        "instance_identifier": instance,
        "publish_run_status": status,
        "publish_run_scope": kw.get("scope"),
        "publish_run_backup": kw.get("backup"),
        "publish_run_summary": kw.get("summary"),
        "publish_run_started_at": "2026-06-22T10:00:00",
        "publish_run_ended_at": "2026-06-22T10:01:00",
        "created_at": "2026-06-22T10:01:00",
        "updated_at": "2026-06-22T10:01:00",
    }


_RUNS = [
    _run(
        "PUB-002",
        status="succeeded_with_issues",
        scope=["Contact.yaml"],
        backup={"entities": {"Contact": {"fields": {}}}},
        summary={
            "deployed": ["Contact.yaml"],
            "verification": {
                "ran": True,
                "conclusive": True,
                "all_present": False,
                "entities": [{"entity": "Contact"}],
            },
        },
    ),
    _run("PUB-001"),
]


def _handler(runs=_RUNS):
    def handler(req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if req.method == "GET" and path == "/publish-runs":
            return httpx.Response(200, json=envelope_ok(runs))
        if req.method == "GET" and path.startswith("/publish-runs/"):
            ident = path.rsplit("/", 1)[-1]
            for r in runs:
                if r["publish_run_identifier"] == ident:
                    return httpx.Response(200, json=envelope_ok(r))
        return httpx.Response(
            404, json={"data": None, "meta": {}, "errors": [{"code": "x"}]}
        )

    return handler


# -- pure helpers ------------------------------------------------------------


def test_scope_display():
    assert _scope_display(None) == "whole design"
    assert _scope_display([]) == "whole design"
    assert _scope_display(["a.yaml", "b.yaml"]) == "2 program(s)"


def test_verification_line():
    assert _verification_line(None) == "—"
    assert _verification_line({"verification": {"ran": False}}) == "not run"
    assert (
        _verification_line({"verification": {"ran": True, "conclusive": False}})
        == "inconclusive"
    )
    assert (
        _verification_line(
            {
                "verification": {
                    "ran": True,
                    "conclusive": True,
                    "all_present": False,
                }
            }
        )
        == "gaps found"
    )


# -- panel -------------------------------------------------------------------


def test_columns_and_read_only(qtbot):
    panel = PublishHistoryPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    titles = [c.title for c in panel.list_columns()]
    assert titles == ["Identifier", "Target", "Status", "Scope", "Finished"]
    # Read-only: no New button.
    assert panel.findChild(QPushButton, "new_publish_run_button") is None


def test_records_load_newest_first_and_display_fields(qtbot):
    panel = PublishHistoryPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    panel.refresh()
    qtbot.waitUntil(lambda: panel._model.rowCount() == 2, timeout=3000)
    processed = panel._post_process_records([dict(r) for r in _RUNS])
    assert processed[0]["status_display"].startswith("⚠")
    assert processed[0]["scope_display"] == "1 program(s)"
    assert processed[1]["scope_display"] == "whole design"
    # The Finished column is formatted, not the raw ISO string.
    assert processed[0]["ended_display"] != _RUNS[0]["publish_run_ended_at"]


def test_detail_pane_renders_backup_and_summary(qtbot):
    panel = PublishHistoryPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RUNS[0], {})
    qtbot.addWidget(detail)
    text = _all_text(detail)
    assert "PUB-002" in text
    assert "Contact.yaml" in text  # published programs list
    assert "entity(ies) captured" in text  # backup heading
    assert "gaps found" in text  # verification line


def test_detail_pane_no_backup(qtbot):
    panel = PublishHistoryPanel(build_client(_handler()))
    qtbot.addWidget(panel)
    detail = panel.render_detail(_RUNS[1], {})
    qtbot.addWidget(detail)
    assert "No backup was captured" in _all_text(detail)


def _all_text(widget) -> str:
    from PySide6.QtWidgets import (
        QLabel,
        QLineEdit,
        QPlainTextEdit,
        QTextEdit,
    )

    bits: list[str] = []
    for lab in widget.findChildren(QLabel):
        bits.append(lab.text())
    for le in widget.findChildren(QLineEdit):
        bits.append(le.text())
    for te in widget.findChildren(QTextEdit):
        bits.append(te.toPlainText())
    for pe in widget.findChildren(QPlainTextEdit):
        bits.append(pe.toPlainText())
    return "\n".join(bits)


# -- client ------------------------------------------------------------------


def test_client_list_and_get(qtbot):
    client = build_client(_handler())
    runs = client.list_publish_runs()
    assert [r["publish_run_identifier"] for r in runs] == ["PUB-002", "PUB-001"]
    one = client.get_publish_run("PUB-001")
    assert one["instance_identifier"] == "INST-001"


def test_client_list_filtered_path():
    from crmbuilder_v2.ui.client import StorageClient

    calls: list[str] = []
    sc = StorageClient.__new__(StorageClient)

    def _req(method, path, *, json_body=None):
        calls.append(path)
        return []

    sc._request = _req
    sc.list_publish_runs("INST-009", limit=5)
    assert any("instance=INST-009" in p and "limit=5" in p for p in calls)
