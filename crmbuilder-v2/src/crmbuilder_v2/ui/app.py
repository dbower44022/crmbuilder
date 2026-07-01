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

from PySide6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from crmbuilder_v2.config import get_settings
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle
from crmbuilder_v2.ui.splash import Splash
from crmbuilder_v2.ui.styling import TOKENS, apply_stylesheet
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox

_APP_NAME = "CRMBuilder v2"
_LOG_DIR = Path("~/.crmbuilder-v2").expanduser()
_LOG_FILE = _LOG_DIR / "ui.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_LOG_BACKUPS = 3
_SPAWN_FAILED_EXIT_CODE = 1
#: REQ-452 / PI-390: exit code when the desktop refuses to run against a local
#: backend without the explicit local opt-in.
_LOCAL_BLOCKED_EXIT_CODE = 2


def _should_block_local(settings) -> bool:
    """REQ-452: refuse a local backend unless local use is explicitly enabled.

    True when the desktop is pointed at a local (loopback) API and
    ``allow_local`` is not set — the accidental-local-connection case.
    """
    return not settings.is_remote_api() and not settings.allow_local

_FONT_ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
_BUNDLED_FONTS = (
    "Inter-VariableFont_opsz,wght.ttf",
    "JetBrainsMono-VariableFont_wght.ttf",
)


def _load_bundled_fonts() -> None:
    """Register bundled font families with Qt's font database.

    Per DEC-090 the desktop UI ships Inter Variable and JetBrains Mono
    Variable rather than relying on per-platform system fonts. Loading
    failure is logged but non-fatal — the application falls back to
    system defaults.

    The Inter v4.x variable font registers as ``"Inter Variable"``
    rather than ``"Inter"``; the design tokens reference the cleaner
    ``"Inter"`` name, so a Qt substitution maps ``Inter`` to the
    bundled ``Inter Variable`` family.
    """
    log = logging.getLogger("crmbuilder_v2.ui.fonts")
    for filename in _BUNDLED_FONTS:
        path = _FONT_ASSETS_DIR / filename
        try:
            font_id = QFontDatabase.addApplicationFont(str(path))
        except Exception:  # noqa: BLE001 — font loading is best-effort
            log.exception("Could not load bundled font %s", filename)
            continue
        if font_id < 0:
            log.warning(
                "Qt rejected bundled font %s (path=%s)", filename, path
            )
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        log.debug("Loaded bundled font %s — families=%s", filename, families)
    QFont.insertSubstitution("Inter", "Inter Variable")


def build_application(argv: list[str] | None = None) -> QApplication:
    """Construct (or reuse) the QApplication, load fonts, apply stylesheet."""
    existing = QApplication.instance()
    if existing is not None:
        existing.setStyle("Fusion")
        _apply_light_palette(existing)
        _load_bundled_fonts()
        apply_stylesheet(existing)
        return existing
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(_APP_NAME)
    # Force Fusion style + explicit light palette so OS theme (GTK on
    # Linux, native on macOS/Windows) cannot bleed through to widget
    # surfaces that the project QSS doesn't explicitly cover. The
    # palette colors mirror TOKENS["light"] so the application bootstrap
    # stays consistent with the styling design pass.
    app.setStyle("Fusion")
    _apply_light_palette(app)
    _load_bundled_fonts()
    apply_stylesheet(app)
    return app


def _apply_light_palette(app: QApplication) -> None:
    """Force an explicit light palette built from ``TOKENS["light"]``.

    Ensures widget surfaces that don't have explicit QSS rules still
    render against light-theme colors regardless of OS theme. Palette
    role-to-token mapping mirrors the design pass §1.2 color tokens
    and stays in sync with ``TOKENS`` without duplicating values.
    """
    light = TOKENS["light"]
    palette = QPalette()
    palette.setColor(
        QPalette.ColorRole.Window, QColor(light["color.neutral.0"])
    )
    palette.setColor(
        QPalette.ColorRole.WindowText, QColor(light["color.neutral.800"])
    )
    palette.setColor(
        QPalette.ColorRole.Base, QColor(light["color.neutral.0"])
    )
    palette.setColor(
        QPalette.ColorRole.AlternateBase, QColor(light["color.neutral.50"])
    )
    palette.setColor(
        QPalette.ColorRole.ToolTipBase, QColor(light["color.neutral.0"])
    )
    palette.setColor(
        QPalette.ColorRole.ToolTipText, QColor(light["color.neutral.800"])
    )
    palette.setColor(
        QPalette.ColorRole.Text, QColor(light["color.neutral.800"])
    )
    palette.setColor(
        QPalette.ColorRole.PlaceholderText, QColor(light["color.neutral.500"])
    )
    palette.setColor(
        QPalette.ColorRole.Button, QColor(light["color.neutral.0"])
    )
    palette.setColor(
        QPalette.ColorRole.ButtonText, QColor(light["color.neutral.700"])
    )
    palette.setColor(
        QPalette.ColorRole.BrightText, QColor(light["color.danger.default"])
    )
    palette.setColor(
        QPalette.ColorRole.Link, QColor(light["color.accent.default"])
    )
    palette.setColor(
        QPalette.ColorRole.LinkVisited, QColor(light["color.accent.pressed"])
    )
    palette.setColor(
        QPalette.ColorRole.Highlight, QColor(light["color.accent.subtle"])
    )
    palette.setColor(
        QPalette.ColorRole.HighlightedText, QColor(light["color.neutral.900"])
    )
    # Disabled-state roles for grayed-out widgets.
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText,
        QColor(light["color.neutral.300"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text,
        QColor(light["color.neutral.300"]),
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText,
        QColor(light["color.neutral.300"]),
    )
    app.setPalette(palette)


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


def _preselect_engagement(window: MainWindow, log: logging.Logger) -> None:
    """Best-effort: select the most-recently-opened engagement at startup.

    The API serves the unified DB and resolves the engagement per request
    from the ``X-Engagement`` header; on launch the desktop picks the first
    engagement the registry returns (ordered most-recently-opened first) and
    sets it active via :meth:`MainWindow.switch_engagement` (which mirrors
    onto the client header and refreshes the panels), so panels show one
    engagement's data instead of an unscoped span. The user can switch via
    the picker. A failure or empty registry leaves no active engagement.
    """
    try:
        engagements = window._client.list_engagements()
    except Exception:  # noqa: BLE001 — best-effort preselection
        log.debug("could not list engagements for preselection; leaving unset")
        return
    record = next(
        (e for e in engagements if not e.get("engagement_deleted_at")),
        None,
    )
    identifier = record.get("engagement_identifier") if record else None
    if not identifier:
        log.debug("no engagement to preselect")
        return
    log.info("preselecting engagement %s", identifier)
    window.switch_engagement(identifier)


def _show_spawn_failure_dialog(
    parent: MainWindow | None, stderr_text: str
) -> None:
    box = CopyableMessageBox(parent)
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


def _show_local_blocked_dialog(api_base_url: str) -> None:
    """REQ-452 / PI-390: explain why a local backend was refused."""
    box = CopyableMessageBox(None)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle("Cloud backend not configured")
    box.setText(
        "CRMBuilder connects to the shared cloud service, but it is currently "
        f"pointed at a local backend ({api_base_url}).\n\n"
        "Set these in crmbuilder-v2/data/crmbuilder.env (or as environment "
        "variables) and restart:\n"
        "  CRMBUILDER_V2_API_BASE_URL=https://api.crmbuilder.ai\n"
        "  CRMBUILDER_V2_API_TOKEN=<your token>\n\n"
        "For local development only, set CRMBUILDER_V2_ALLOW_LOCAL=true."
    )
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
    # REQ-452 / PI-390: the desktop targets the cloud by default. If it is
    # pointed at a local backend without the explicit local opt-in, refuse to
    # start (rather than silently connect to an empty/stale local database) and
    # explain how to configure the cloud.
    if _should_block_local(settings):
        splash.hide()
        _show_local_blocked_dialog(settings.api_base_url)
        return _LOCAL_BLOCKED_EXIT_CODE
    # REQ-448 / PI-386: in remote mode the client authenticates with a bearer
    # token and the lifecycle never spawns a local API.
    remote_api = settings.is_remote_api()
    lifecycle = ServerLifecycle(
        base_url=settings.api_base_url, remote=remote_api
    )
    client = StorageClient(
        base_url=settings.api_base_url, token=settings.api_token or None
    )
    # PI-β: the active engagement is purely client-side desktop state. It is
    # mirrored onto the client's ``X-Engagement`` header on every change, so
    # switching engagements is a context change (no API restart, no marker).
    active_engagement = ActiveEngagementContext()
    active_engagement.active_engagement_changed.connect(
        lambda e: client.set_active_engagement(
            e.engagement_identifier if e is not None else None
        )
    )
    window = MainWindow(
        lifecycle=lifecycle,
        client=client,
        active_context=active_engagement,
    )
    window.active_engagement = active_engagement

    def on_ready() -> None:
        if not window.isVisible():
            # First ready: pick an engagement so panels are scoped, then show.
            _preselect_engagement(window, log)
            window.show()
            splash.finish(window)

    def on_spawn_failed(stderr_text: str) -> None:
        # A spawn failure *before* the API was ever reachable is a fatal
        # startup failure — show the modal dialog and exit. Once the app
        # has been live, the same signal means a runtime auto-reconnect
        # attempt failed; route it to the in-window banner (which retries
        # up to its bound, then offers manual Reconnect) instead of
        # tearing down the running session.
        if window.had_first_ready():
            log.warning(
                "Runtime reconnect spawn failed; deferring to in-window banner"
            )
            window.handle_reconnect_failed(stderr_text)
            return
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
