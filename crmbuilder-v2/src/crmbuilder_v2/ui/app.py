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
    QProgressDialog,
)

from crmbuilder_v2.access.db import reset_engine_cache
from crmbuilder_v2.config import get_settings, reset_settings_cache
from crmbuilder_v2.migration.dogfood_v0_5 import (
    needs_migration,
    run_dogfood_migration,
)
from crmbuilder_v2.migration.lazy_migration import engagement_db_path
from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.main_window import MainWindow
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle
from crmbuilder_v2.ui.splash import Splash
from crmbuilder_v2.ui.styling import TOKENS, apply_stylesheet

_APP_NAME = "CRMBuilder v2"
_LOG_DIR = Path("~/.crmbuilder-v2").expanduser()
_LOG_FILE = _LOG_DIR / "ui.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
_LOG_BACKUPS = 3
_SPAWN_FAILED_EXIT_CODE = 1
_MIGRATION_FAILED_EXIT_CODE = 1

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


def _route_api_at_active_engagement(
    active: ActiveEngagementContext, log: logging.Logger
) -> None:
    """Point ``CRMBUILDER_V2_DB_PATH`` at the active engagement's DB.

    No-op when ``current_engagement.json`` did not resolve to an
    engagement (fresh install with no prior CRMBUILDER row, or empty
    after a deactivation flow). The env var feeds ``Settings.db_path``,
    which the spawned API process reads at startup and which
    ``meta_db_path`` / ``engagement_db_path`` normalise back to the
    canonical ``data/`` dir via :func:`crmbuilder_v2.access.meta_db.data_dir`.
    """
    code = active.engagement_code()
    if not code:
        log.debug(
            "no active engagement on load; leaving CRMBUILDER_V2_DB_PATH unset"
        )
        return
    db_path = engagement_db_path(code)
    os.environ["CRMBUILDER_V2_DB_PATH"] = str(db_path)
    reset_settings_cache()
    reset_engine_cache()
    log.info(
        "routing API at engagement %s (CRMBUILDER_V2_DB_PATH=%s)",
        code,
        db_path,
    )


def _run_dogfood_migration_if_needed(log: logging.Logger) -> bool:
    """Run the v0.5 dogfood migration if the engine is on a v0.4 state.

    Returns ``True`` if no migration was needed or the migration
    succeeded; ``False`` if the migration failed (caller exits the
    process). Wraps the synchronous migration call in an indeterminate
    :class:`QProgressDialog` per PRD §5.4 so the user sees an
    "Upgrading to v0.5: migrating engagement..." indicator. No cancel
    affordance: the migration is atomic and must complete or fail.
    """
    if not needs_migration():
        return True

    log.info("v0.5 dogfood migration required; starting")
    progress = QProgressDialog(
        "Upgrading to v0.5: migrating engagement...",
        None,
        0,
        0,
        None,
    )
    progress.setWindowTitle("CRMBuilder v2 — Upgrading")
    progress.setMinimumDuration(0)
    progress.setCancelButton(None)
    progress.show()
    QApplication.processEvents()

    try:
        result = run_dogfood_migration()
    finally:
        progress.close()

    if not result.success:
        failed_step = (
            result.steps_completed[-1]
            if result.steps_completed
            else "pre-flight"
        )
        log.error(
            "v0.5 dogfood migration failed at step %s: %s",
            failed_step,
            result.error,
        )
        box = QMessageBox(None)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("Migration failed")
        box.setText(
            f"v0.5 migration failed at step: {failed_step}\n\n"
            f"Error: {result.error}\n\n"
            "Your v0.4 data is preserved at "
            "crmbuilder-v2/data/v2.db.pre-v0.5-backup. "
            "Please revert to the prior v2 release and contact support."
        )
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
        return False

    log.info(
        "v0.5 dogfood migration completed (%d steps)",
        len(result.steps_completed),
    )
    return True


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

    # v0.5 slice A follow-up: if the engine boots from a v0.4-state
    # ``v2.db`` (no meta DB yet), run the one-shot dogfood migration
    # before the splash and lifecycle start. Hard-fail UX per PRD §5.4:
    # on migration failure show a critical dialog naming the recovery
    # path and exit non-zero — the app must not continue half-migrated.
    if not _run_dogfood_migration_if_needed(log):
        return _MIGRATION_FAILED_EXIT_CODE

    splash = Splash()
    splash.show()
    app.processEvents()

    settings = get_settings()
    lifecycle = ServerLifecycle(base_url=settings.api_base_url)
    client = StorageClient(base_url=settings.api_base_url)
    # v0.5 slice A: ActiveEngagementContext loads from
    # ``current_engagement.json`` after the QApplication is built.
    # Slice D wires a resolver against the meta DB; slice A uses the
    # synthesised stub so panels can read identifier/code immediately.
    active_engagement = ActiveEngagementContext()
    active_engagement.load_from_disk()
    # v0.5 slice D follow-up: route the API spawn at the active
    # engagement's per-engagement DB before lifecycle.start(). The
    # activation worker handles env-var injection on every subsequent
    # engagement switch (activation_worker.build_lifecycle_managers
    # ._launch_api); on first launch there is no activation, so we set
    # it here. ``load_from_disk`` runs first because
    # ``current_engagement.json`` lives next to ``v2.db`` and we read
    # it before mutating the path. Settings + engine caches are reset
    # so any get_settings() in this process picks up the new value;
    # the QProcess spawn in ServerLifecycle inherits the env directly.
    _route_api_at_active_engagement(active_engagement, log)
    # v0.5 slice D: build the subprocess managers bundle from the
    # lifecycle so the engagement-switching activation worker can drive
    # kill/relaunch through the same lifecycle the rest of the UI uses.
    from crmbuilder_v2.ui.activation_worker import build_lifecycle_managers

    managers = build_lifecycle_managers(lifecycle)
    window = MainWindow(
        lifecycle=lifecycle,
        client=client,
        active_context=active_engagement,
        managers=managers,
    )
    window.active_engagement = active_engagement

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
