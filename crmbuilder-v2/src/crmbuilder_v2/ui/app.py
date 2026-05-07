"""Qt application factory and main entry function.

Per DEC-024 the v2 UI uses native Qt widget rendering with a minimal
QSS accent stub applied at startup. Per DEC-018 this is a standalone
PySide6 application installed as the ``crmbuilder-v2-ui`` console
script.

In slice A the splash is shown briefly as a smoke check that it
renders; full lifecycle integration (probe + spawn + dismiss-on-ready)
lands in slice B.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.splash import Splash
from crmbuilder_v2.ui.styling import apply_stylesheet

_APP_NAME = "CRMBuilder v2"
_LOG_DIR = Path("~/.crmbuilder-v2").expanduser()
_LOG_FILE = _LOG_DIR / "ui.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_LOG_BACKUPS = 3
_SPLASH_SMOKE_TEST_MS = 500


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

    window = MainWindow()

    # Slice A: dismiss the splash after a short delay as a smoke check.
    # Slice B will replace this with lifecycle-driven dismissal.
    def _show_window():
        window.show()
        splash.finish(window)

    QTimer.singleShot(_SPLASH_SMOKE_TEST_MS, _show_window)

    exit_code = app.exec()
    log.info("Exiting %s with code %d", _APP_NAME, exit_code)
    return exit_code
