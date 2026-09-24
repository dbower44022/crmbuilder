"""Show, copy and save the handover sheet — PI-571 (REQ-652)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from crmbuilder_v2.segments.operate.ui.handover import render_handover_html
from crmbuilder_v2.ui.widgets.form_helpers import primary_button


def fit_to_screen(widget, fraction: float = 0.75, minimum: tuple[int, int] = (900, 640)) -> None:
    """Size ``widget`` to a share of the screen it opens on, never below ``minimum``."""
    screen = QGuiApplication.primaryScreen()
    width, height = minimum
    if screen is not None:
        geo = screen.availableGeometry()
        width = max(width, int(geo.width() * fraction))
        height = max(height, int(geo.height() * fraction))
        width, height = min(width, geo.width()), min(height, geo.height())
    widget.setMinimumSize(*minimum)
    widget.resize(width, height)


class HandoverDialog(QDialog):
    """The handover sheet for one deploy run, with Save and Copy password."""

    def __init__(self, run: dict[str, Any], *, admin_password: str | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self._run = run
        self._password = admin_password
        self.html = render_handover_html(run, admin_password=admin_password)
        self.setWindowTitle("Handover sheet")
        fit_to_screen(self, 0.7, (820, 640))
        layout = QVBoxLayout(self)
        self.view = QTextBrowser()
        self.view.setObjectName("handover_view")
        self.view.setOpenExternalLinks(True)
        self.view.setHtml(self.html)
        layout.addWidget(self.view, 1)
        row = QHBoxLayout()
        row.addStretch(1)
        self.copy_btn = QPushButton("Copy password")
        self.copy_btn.setObjectName("handover_copy_password")
        self.copy_btn.setVisible(bool(admin_password))
        self.copy_btn.clicked.connect(self._copy_password)
        self.save_btn = primary_button("Save…")
        self.save_btn.setObjectName("handover_save")
        self.save_btn.clicked.connect(self._save)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        for b in (self.copy_btn, self.save_btn, close_btn):
            row.addWidget(b)
        layout.addLayout(row)

    def _copy_password(self) -> None:
        QGuiApplication.clipboard().setText(self._password or "")
        self.copy_btn.setText("Copied")

    def save_to(self, path: str | Path) -> Path:
        """Write the sheet to ``path`` (``.html`` added when missing)."""
        target = Path(path)
        if target.suffix.lower() not in (".html", ".htm"):
            target = target.with_suffix(".html")
        target.write_text(self.html, encoding="utf-8")
        return target

    def _save(self) -> None:
        domain = (self._run.get("deploy_run_spec") or {}).get("domain") or "crm"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save the handover sheet", f"{domain}-handover.html", "Web page (*.html)"
        )
        if path:
            saved = self.save_to(path)
            self.save_btn.setText(f"Saved to {saved.name}")
