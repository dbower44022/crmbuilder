"""Qt application factory and main entry function.

Per DEC-024 the v2 UI uses native Qt widget rendering with a minimal
QSS accent stub applied at startup. Per DEC-018 this is a standalone
PySide6 application installed as the ``crmbuilder-v2-ui`` console
script.

Slice B wires the storage-server lifecycle (per DEC-023): on launch
the splash is shown, the lifecycle probes ``GET /health`` and
spawns ``crmbuilder-v2-api`` as a managed subprocess if no API
responds. The splash is dismissed when the lifecycle emits ``ready``;
spawn failures show a modal error dialog and exit with code 1.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from crmbuilder_v2.config import get_settings
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle
from crmbuilder_v2.ui.splash import Splash
from crmbuilder_v2.ui.styling import apply_stylesheet

_APP_NAME = "CRMBuilder v2"
_LOG_DIR = Path("~/.crmbuilder-v2").expanduser()
_LOG_FILE = _LOG_DIR / "ui.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_LOG_BACKUPS = 3
_SPAWN_FAILED_EXIT_CODE = 1


def build_application(argv: list[str] | None = None) -> QApplication:
    """Construct (or reuse) the QApplication and apply the styling stub."""
    existing = QApplication.instance()
    if existing is not None:
        apply_stylesheet(existing)
        return existing
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(_APP_NAME)
    apply_stylesheet(app)
    return app


def _configure_logging(verbose: bool) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    level = logging.DEBUG if verbose else logging.INFO

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s — %(message)s"
    )

    file_handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=_LOG_MAX_BYTES, backupCount=_LOG_BACKUPS
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    # Avoid duplicate handlers on repeat invocations (e.g., test runs).
    for existing_handler in list(root.handlers):
        root.removeHandler(existing_handler)
    root.addHandler(file_handler)
    root.addHandler(console_handler)


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="crmbuilder-v2-ui")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level logging.",
    )
    return parser.parse_args(argv[1:])


def _show_spawn_failure_dialog(
    parent: MainWindow | None, stderr_text: str
) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("Storage server failed to start")
    box.setText(
        "crmbuilder-v2-ui could not start the storage API and "
        "no API was already running."
    )
    if stderr_text:
        box.setDetailedText(stderr_text)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.exec()


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv
    args = _parse_args(argv)
    _configure_logging(verbose=args.verbose)

    log = logging.getLogger("crmbuilder_v2.ui")
    log.info("Starting %s", _APP_NAME)

    # Headless test/CI runs may set this themselves; we don't override it.
    if "QT_QPA_PLATFORM" in os.environ:
        log.debug("QT_QPA_PLATFORM=%s", os.environ["QT_QPA_PLATFORM"])

    app = build_application(argv)

    splash = Splash()
    splash.show()
    app.processEvents()

    settings = get_settings()
    lifecycle = ServerLifecycle(base_url=settings.api_base_url)
    client = StorageClient(base_url=settings.api_base_url)
    window = MainWindow(lifecycle=lifecycle, client=client)

    def on_ready() -> None:
        if not window.isVisible():
            window.show()
            splash.finish(window)

    def on_spawn_failed(stderr_text: str) -> None:
        log.error("Spawn failed; showing failure dialog and exiting")
        if splash.isVisible():
            splash.hide()
        parent = window if window.isVisible() else None
        _show_spawn_failure_dialog(parent, stderr_text)
        app.exit(_SPAWN_FAILED_EXIT_CODE)

    lifecycle.ready.connect(on_ready)
    lifecycle.spawn_failed.connect(on_spawn_failed)
    lifecycle.crashed.connect(window.handle_crash)

    lifecycle.start()

    exit_code = app.exec()
    log.info("Exiting %s with code %d", _APP_NAME, exit_code)
    return exit_code
