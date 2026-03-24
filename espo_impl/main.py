"""Entry point for CRM Builder."""

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from espo_impl.ui.main_window import MainWindow


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

    app = QApplication(sys.argv)
    app.setApplicationName("CRM Builder")
    window = MainWindow(base_dir=base)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
