"""Entry point for CRM Builder."""

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from espo_impl.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def _run_instance_migration(base: Path) -> list[str]:
    """Run the legacy JSON instance migration and return any warnings.

    :param base: Application base directory.
    :returns: List of warning strings (empty if none).
    """
    master_db = base / "automation" / "data" / "master.db"
    instances_dir = base / "data" / "instances"

    if not master_db.exists():
        return []

    try:
        from automation.migrations.instance_json_migration import (
            _log_report,
            run_migration,
        )

        report = run_migration(str(master_db), instances_dir)
        _log_report(report)
        return [w.reason for w in report.warnings]
    except Exception as exc:
        logger.warning("Instance migration failed: %s", exc)
        return [f"Instance migration error: {exc}"]


def main() -> None:
    """Launch the application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    base = Path(__file__).resolve().parent.parent
    (base / "data" / "instances").mkdir(parents=True, exist_ok=True)
    (base / "data" / "programs").mkdir(parents=True, exist_ok=True)
    (base / "reports").mkdir(parents=True, exist_ok=True)

    # Run legacy instance migration before showing the main window
    migration_warnings = _run_instance_migration(base)

    app = QApplication(sys.argv)
    app.setApplicationName("CRM Builder")
    window = MainWindow(base_dir=base)
    window.show()

    # Surface migration warnings after main window is visible
    if migration_warnings:
        QMessageBox.warning(
            window,
            "Instance Migration Warnings",
            "The following issues were encountered during legacy instance "
            "migration:\n\n" + "\n".join(f"  \u2022 {w}" for w in migration_warnings),
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
