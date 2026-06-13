"""Acceptance verification for PI-124 / WTK-146.

Independent of the helper unit tests Develop wrote
(``test_selectable_text.py``), this module verifies the PI-124
*acceptance criterion* — "from every popup an operator can select the
full message and copy it" — end-to-end across the named crmbuilder_v2
message surfaces, exercising each surface the way the operator hits it
rather than the helper in isolation.

Surfaces (per the WTK-146 scope):

* **(a) activation overlay — REMOVED.** ``ui/widgets/activation_overlay.py``
  (the "Switching failed at step {step}" case that *surfaced* the
  requirement) no longer exists: PI-β replaced the subprocess-swap
  engagement switch with a client-side context change, so that popup is
  gone by construction. ``test_activation_overlay_surface_is_removed``
  pins that — if the surface ever returns it must come back with the
  shared selectable helper, not as a fresh raw popup.
* **(b) ``ui/dialogs/error.py``** — header, message, *and* the
  collapsible detail pane are selectable/copyable.
* **(c) MainWindow auto-reconnect / connection-loss banner** — driven
  through the real ``MainWindow`` recovery path: the banner shown to the
  operator has selectable text and an explicit Copy button that copies
  the displayed diagnostic verbatim.
* **(d) the swept QMessageBox popups** — the representative
  ``app._show_spawn_failure_dialog`` (body + detailed stderr) and the
  ``CopyableMessageBox.warning`` static path both yield fully selectable
  text, and the sweep is structurally complete (no raw popup remains).

Scope is verification only — no UI code is modified here.
"""

from __future__ import annotations

import httpx
import pytest
from crmbuilder_v2.ui import app as ui_app
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.main_window import _MAX_RECONNECT_ATTEMPTS, MainWindow
from crmbuilder_v2.ui.widgets.selectable_text import (
    SELECTABLE_TEXT_FLAGS,
    CopyableMessageBox,
)
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QMessageBox, QPlainTextEdit


def _has_selectable_flags(flags: Qt.TextInteractionFlags) -> bool:
    """True when both selectable-text flags are present on ``flags``."""
    return (flags & SELECTABLE_TEXT_FLAGS) == SELECTABLE_TEXT_FLAGS


# ---------------------------------------------------------------------------
# (a) activation overlay — removed by PI-β
# ---------------------------------------------------------------------------


def test_activation_overlay_surface_is_removed():
    """The originating "Switching failed at step N" popup no longer exists.

    PI-β made engagement switching a client-side context change, so the
    subprocess-swap overlay was deleted. This guards against the surface
    quietly returning as a raw, non-copyable popup.
    """
    with pytest.raises(ModuleNotFoundError):
        __import__("crmbuilder_v2.ui.widgets.activation_overlay")


def test_engagement_switch_failure_pops_no_raw_dialog(qapp, tmp_path):
    """The replacement switch path is best-effort: it logs, never popping.

    A failed ``switch_engagement`` returns ``False`` and leaves the prior
    engagement active — there is no popup here to make copyable, which is
    why surface (a) is moot rather than re-implemented.
    """
    win = _make_window(tmp_path)
    # No active context → the guarded early return; exercises the path
    # without a network call.
    assert win.switch_engagement("ENG-999") is False


# ---------------------------------------------------------------------------
# (b) ui/dialogs/error.py — body + detail
# ---------------------------------------------------------------------------


def test_error_dialog_body_and_detail_fully_copyable(qtbot):
    """Header, message, and the revealed detail pane are all selectable.

    Develop's unit test covers the header + message labels; this adds the
    detail pane — a read-only ``QPlainTextEdit`` whose full traceback an
    operator must be able to drag-select and Ctrl+C.
    """
    detail = "Traceback (most recent call last):\n  File ...\nValueError: boom"
    dialog = ErrorDialog(
        title="Could not save",
        message="Something went wrong.",
        detail=detail,
    )
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)

    labels = {label.text(): label for label in dialog.findChildren(QLabel)}
    for text in ("Could not save", "Something went wrong."):
        assert _has_selectable_flags(labels[text].textInteractionFlags())

    pane = dialog.findChild(QPlainTextEdit, "error_detail_text")
    assert pane is not None
    assert pane.isReadOnly()
    # A read-only QPlainTextEdit is drag-selectable by mouse — the
    # operative copy affordance (mouse select + Ctrl+C) for the pane.
    flags = pane.textInteractionFlags()
    assert flags & Qt.TextInteractionFlag.TextSelectableByMouse
    # The full diagnostic is present to be copied (reveal it first).
    dialog.findChild(object, "error_detail_toggle").toggle()
    assert pane.toPlainText() == detail


# ---------------------------------------------------------------------------
# (c) MainWindow auto-reconnect / connection-loss banner
# ---------------------------------------------------------------------------


class _FakeLifecycle(QObject):
    """ServerLifecycle stand-in: records start() calls, no real subprocess."""

    ready = Signal()
    crashed = Signal(str)
    spawn_failed = Signal(str)
    terminated = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.start_calls = 0
        self.ownership = "owned"

    def start(self) -> None:
        self.start_calls += 1

    def terminate(self) -> None:
        pass


def _empty_client() -> StorageClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": [], "meta": {}, "errors": None}
            )
        return httpx.Response(
            404, json={"data": None, "meta": {}, "errors": [{"message": "x"}]}
        )

    transport = httpx.MockTransport(handler)
    httpx_client = httpx.Client(
        base_url="http://test.invalid", transport=transport
    )
    return StorageClient(base_url="http://test.invalid", client=httpx_client)


def _make_window(tmp_path) -> MainWindow:
    for name in (
        "charter.json",
        "status.json",
        "decisions.json",
        "sessions.json",
        "risks.json",
        "planning_items.json",
        "topics.json",
        "references.json",
    ):
        (tmp_path / name).write_text("{}", encoding="utf-8")
    return MainWindow(
        lifecycle=_FakeLifecycle(),
        client=_empty_client(),
        snapshot_dir=tmp_path,
    )


def test_connection_loss_banner_text_is_selectable_and_copyable(qapp, tmp_path):
    """The banner the operator sees on a dropped API is fully copyable.

    Drives the real ``MainWindow`` recovery path (not ``CrashBanner`` in
    isolation): on a panel ``connection_lost`` the banner appears with
    selectable text, and its explicit Copy button copies the displayed
    message — which names the API URL the operator needs in a report.
    """
    win = _make_window(tmp_path)
    win._on_lifecycle_ready()  # first-ready so the recovery path is armed

    win._on_panel_connection_lost("Connection refused")

    banner = win._crash_banner
    assert not banner.isHidden()
    assert _has_selectable_flags(banner._label.textInteractionFlags())

    shown_text = banner._label.text()
    assert win._base_url in shown_text  # the diagnostic URL is in the text

    copy_button = banner.findChild(object, "crashBannerCopy")
    assert copy_button is not None
    copy_button.click()
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == shown_text
    # Copy is non-destructive — the banner stays up to re-read/re-copy.
    assert not banner.isHidden()


def test_exhausted_reconnect_banner_carries_copyable_log_path(qapp, tmp_path):
    """After retries are exhausted the actionable banner names the log path.

    The operator copies a message that includes the api.log location to
    diagnose why reconnection failed.
    """
    win = _make_window(tmp_path)
    win._on_lifecycle_ready()
    win._on_panel_connection_lost("boom")  # attempt 1
    for _ in range(_MAX_RECONNECT_ATTEMPTS):
        win.handle_reconnect_failed("spawn err")

    banner = win._crash_banner
    shown_text = banner._label.text()
    assert str(win._log_path) in shown_text
    assert _has_selectable_flags(banner._label.textInteractionFlags())

    banner.findChild(object, "crashBannerCopy").click()
    clipboard = QGuiApplication.clipboard()
    assert clipboard is not None
    assert clipboard.text() == shown_text


# ---------------------------------------------------------------------------
# (d) swept QMessageBox popups → CopyableMessageBox
# ---------------------------------------------------------------------------


def test_spawn_failure_dialog_body_and_detail_selectable(
    qapp, qtbot, monkeypatch
):
    """app._show_spawn_failure_dialog (a swept site) is fully copyable.

    Representative real sweep target: a startup popup that carries the
    API stderr as detailed text. Both the main message label and the
    detailed-text pane must be selectable so the operator can copy the
    failure into a report. ``exec`` is stubbed so no modal loop blocks.
    """
    captured: list[CopyableMessageBox] = []

    def fake_exec(self):
        captured.append(self)
        return 0

    monkeypatch.setattr(CopyableMessageBox, "exec", fake_exec)
    ui_app._show_spawn_failure_dialog(None, "boot stderr: port already in use")

    assert len(captured) == 1
    box = captured[0]
    qtbot.addWidget(box)

    # Main message label is selectable.
    main_labels = [
        lbl
        for lbl in box.findChildren(QLabel)
        if lbl.text() and lbl.text() == box.text()
    ]
    assert main_labels
    assert _has_selectable_flags(main_labels[0].textInteractionFlags())

    # Detailed-text pane carries the stderr and is selectable.
    panes = box.findChildren(QPlainTextEdit)
    from PySide6.QtWidgets import QTextEdit

    detail_panes = panes or box.findChildren(QTextEdit)
    assert detail_panes
    pane = detail_panes[0]
    assert "boot stderr" in pane.toPlainText()
    assert pane.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse


def test_copyable_message_box_static_warning_path_is_selectable(
    qapp, qtbot, monkeypatch
):
    """The ``CopyableMessageBox.warning`` static path (e.g. chat export) selects.

    Several swept sites call the static helpers rather than constructing
    the box; this checks that path yields a selectable body + informative.
    """
    captured: list[CopyableMessageBox] = []

    def fake_exec(self):
        captured.append(self)
        # mimic an Ok click so the classmethod returns cleanly
        ok = self.button(QMessageBox.StandardButton.Ok)
        if ok is not None:
            ok.click()
        return 0

    monkeypatch.setattr(CopyableMessageBox, "exec", fake_exec)
    CopyableMessageBox.warning(None, "Export failed", "disk full")

    assert len(captured) == 1
    box = captured[0]
    qtbot.addWidget(box)
    box.setInformativeText("retry after freeing space")

    labels = {lbl.text(): lbl for lbl in box.findChildren(QLabel)}
    assert _has_selectable_flags(labels["disk full"].textInteractionFlags())
    assert _has_selectable_flags(
        labels["retry after freeing space"].textInteractionFlags()
    )


def test_no_raw_qmessagebox_remains_in_v2_ui():
    """Acceptance backstop: the sweep left no raw, non-copyable popup.

    Mirrors Develop's source guard from the surface-acceptance angle — a
    single raw ``QMessageBox`` would defeat the criterion regardless of
    the helper's correctness.
    """
    import re
    from pathlib import Path

    import crmbuilder_v2.ui as ui_pkg

    raw_instantiation = re.compile(r"QMessageBox\(")
    raw_static = re.compile(
        r"QMessageBox\.(information|warning|critical|question)\("
    )
    ui_root = Path(ui_pkg.__file__).parent
    offenders: list[str] = []
    for path in ui_root.rglob("*.py"):
        if path.name == "selectable_text.py":
            continue
        source = path.read_text(encoding="utf-8")
        if raw_instantiation.search(source) or raw_static.search(source):
            offenders.append(str(path.relative_to(ui_root)))
    assert not offenders, f"raw QMessageBox popups remain: {offenders}"
