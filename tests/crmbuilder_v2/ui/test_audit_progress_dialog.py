"""AuditProgressDialog tests — live per-area audit progress (PI-274)."""

from __future__ import annotations

from crmbuilder_v2.ui.dialogs.audit_progress_dialog import (
    AuditProgressDialog,
    _summary_line,
)
from crmbuilder_v2.ui.exceptions import StorageConnectionError

_AREAS = [
    {"area": "entities", "label": "Entities"},
    {"area": "fields", "label": "Fields"},
    {"area": "associations", "label": "Relationships"},
]

_RECORD = {"instance_identifier": "INST-001", "instance_name": "CBM sandbox"}


class _FakeClient:
    def __init__(self, *, per_area=None, fail_on=None, log_for=None):
        self._per_area = per_area or {}
        self._fail_on = fail_on
        self._log_for = log_for or {}
        self.area_calls: list[str] = []

    def list_audit_areas(self):
        return list(_AREAS)

    def audit_instance_area(self, identifier, area):
        self.area_calls.append(area)
        if self._fail_on == area:
            raise RuntimeError(f"{area} blew up")
        summary = self._per_area.get(
            area, {"seen": 1, "created": 1, "present": 1, "drifted": 0, "absent": 0}
        )
        label = next(a["label"] for a in _AREAS if a["area"] == area)
        return {
            "area": area,
            "label": label,
            "summary": summary,
            "log": self._log_for.get(area, []),
        }


def _log_text(dlg) -> str:
    return dlg._log.toPlainText()


# -- pure helper -------------------------------------------------------------


def test_summary_line():
    line = _summary_line(
        "Fields",
        {"seen": 5, "created": 2, "present": 3, "drifted": 1, "absent": 0},
    )
    assert "Fields" in line
    assert "5 seen" in line and "2 created" in line and "1 drifted" in line


# -- dialog behaviour --------------------------------------------------------


def test_drives_all_areas_and_completes(qtbot):
    client = _FakeClient()
    dlg = AuditProgressDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._finished, timeout=4000)
    # Every area was driven, in order.
    assert client.area_calls == ["entities", "fields", "associations"]
    assert "Audit complete" in dlg._status.text()
    assert dlg._progress.value() == len(_AREAS)
    text = _log_text(dlg)
    assert "Entities" in text and "Relationships" in text
    # Cancel hidden after completion; Close shown.
    assert not dlg._cancel_btn.isVisibleTo(dlg)
    assert dlg._close_btn.isVisibleTo(dlg)


def test_warning_lines_rendered(qtbot):
    client = _FakeClient(
        log_for={"fields": [["Contact: could not read fields (HTTP 500)", "warning"]]}
    )
    dlg = AuditProgressDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._finished, timeout=4000)
    assert "could not read fields" in _log_text(dlg)


def test_area_error_stops_the_run(qtbot):
    client = _FakeClient(fail_on="fields")
    dlg = AuditProgressDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    qtbot.waitUntil(lambda: dlg._finished, timeout=4000)
    # entities + the failing fields ran; associations never reached.
    assert client.area_calls == ["entities", "fields"]
    assert "stopped" in dlg._status.text().lower()
    assert "failed" in _log_text(dlg).lower()


def test_connection_lost_relayed(qtbot):
    class _DropClient(_FakeClient):
        def audit_instance_area(self, identifier, area):
            self.area_calls.append(area)
            raise StorageConnectionError(message="dropped")

    client = _DropClient()
    dlg = AuditProgressDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    relayed: list[str] = []
    dlg.connection_lost.connect(relayed.append)
    qtbot.waitUntil(lambda: dlg._finished, timeout=4000)
    assert relayed  # the dialog re-emitted connection_lost for the panel
    assert "Connection lost" in _log_text(dlg)


def test_cancel_stops_before_any_area(qtbot):
    client = _FakeClient()
    dlg = AuditProgressDialog(client, _RECORD)
    qtbot.addWidget(dlg)
    # Cancel synchronously, before the queued areas-loaded callback runs.
    dlg._on_cancel()
    qtbot.waitUntil(lambda: dlg._finished, timeout=4000)
    assert client.area_calls == []  # cancelled before the first area
    assert "cancel" in dlg._status.text().lower()
