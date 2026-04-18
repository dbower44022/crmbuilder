"""Research dialog for automated CRM platform profiling.

Three-step wizard: Input → Progress → Review & Save.
"""

import logging
from pathlib import Path
from urllib.parse import urlparse

import yaml

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from automation.config import preferences

logger = logging.getLogger(__name__)

_STEP_INPUT = 0
_STEP_PROGRESS = 1
_STEP_REVIEW = 2

# Output panel colors matching output_panel.py conventions
_COLOR_MAP = {
    "info": "#FFFFFF",
    "warn": "#FFC107",
    "error": "#F44336",
}


class ResearchDialog(QDialog):
    """Modal dialog for researching a CRM platform.

    :param base_dir: Project root directory.
    :param update_slug: If set, opens in update mode for this platform slug.
    :param parent: Parent widget.
    """

    platform_saved = Signal()

    def __init__(
        self,
        base_dir: Path,
        update_slug: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._base_dir = base_dir
        self._platforms_dir = base_dir / "docs" / "crm-platforms" / "platforms"
        self._update_slug = update_slug
        self._result = None
        self._worker = None
        self._build_ui()
        if update_slug:
            self._apply_update_mode(update_slug)

    def _build_ui(self) -> None:
        """Build the three-step wizard layout."""
        self.setWindowTitle("Research CRM Platform")
        self.setMinimumSize(700, 500)

        layout = QVBoxLayout(self)

        # Step indicator
        self._step_label = QLabel()
        self._step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._step_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self._step_label)

        # Stacked widget for steps
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_step_input())
        self._stack.addWidget(self._build_step_progress())
        self._stack.addWidget(self._build_step_review())
        layout.addWidget(self._stack, stretch=1)

        self._set_step(_STEP_INPUT)

    def _set_step(self, step: int) -> None:
        """Switch to a wizard step.

        :param step: Step index.
        """
        labels = {
            _STEP_INPUT: "Step 1 of 3 — Enter CRM URL",
            _STEP_PROGRESS: "Step 2 of 3 — Researching Platform",
            _STEP_REVIEW: "Step 3 of 3 — Review & Save",
        }
        self._step_label.setText(labels.get(step, ""))
        self._stack.setCurrentIndex(step)

    # ─── Step 1: Input ─────────────────────────────────────────────

    def _build_step_input(self) -> QWidget:
        """Build the input step with URL and API key fields."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        form = QFormLayout()

        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://www.example-crm.com")
        self._url_input.textChanged.connect(self._on_url_changed)
        form.addRow("Platform URL:", self._url_input)

        self._api_docs_input = QLineEdit()
        self._api_docs_input.setPlaceholderText(
            "https://developer.example-crm.com/docs/api (optional)"
        )
        form.addRow("API Docs URL:", self._api_docs_input)

        # API key with show/hide
        key_row = QHBoxLayout()
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("sk-ant-...")
        stored = preferences.get_anthropic_api_key()
        if stored:
            self._key_input.setText(stored)
        key_row.addWidget(self._key_input)

        self._key_toggle = QPushButton("Show")
        self._key_toggle.setFixedWidth(60)
        self._key_toggle.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self._key_toggle)

        form.addRow("Anthropic API Key:", key_row)

        self._remember_key = QCheckBox("Remember API key")
        self._remember_key.setChecked(True)
        form.addRow("", self._remember_key)

        layout.addLayout(form)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #757575; font-size: 12px;")
        layout.addWidget(self._status_label)

        layout.addStretch()

        # Button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        self._research_btn = QPushButton("Research")
        self._research_btn.setStyleSheet(
            "background-color: #FFA726; color: white; font-weight: bold; "
            "padding: 8px 20px; border-radius: 4px;"
        )
        self._research_btn.clicked.connect(self._on_research)
        btn_row.addWidget(self._research_btn)

        layout.addLayout(btn_row)
        return widget

    def _toggle_key_visibility(self) -> None:
        """Toggle API key visibility."""
        if self._key_input.echoMode() == QLineEdit.EchoMode.Password:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self._key_toggle.setText("Hide")
        else:
            self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self._key_toggle.setText("Show")

    def _on_url_changed(self, text: str) -> None:
        """Update status label based on URL input.

        :param text: Current URL text.
        """
        slug = self._slug_from_url(text)
        if not slug:
            self._status_label.setText("")
            return

        yaml_path = self._platforms_dir / f"{slug}.yaml"
        if yaml_path.exists():
            self._status_label.setText(f"Update existing platform: {slug}")
            self._status_label.setStyleSheet("color: #FFA726; font-size: 12px;")
        else:
            self._status_label.setText(f"New platform (slug: {slug})")
            self._status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")

    @staticmethod
    def _slug_from_url(url: str) -> str:
        """Extract a candidate slug from a URL.

        :param url: URL string.
        :returns: Slug string or empty.
        """
        try:
            parsed = urlparse(url if "://" in url else f"https://{url}")
            host = parsed.netloc.lower()
            if not host:
                return ""
            # Strip www. prefix and TLD
            host = host.split(":")[0]  # remove port
            if host.startswith("www."):
                host = host[4:]
            parts = host.split(".")
            if len(parts) >= 2:
                return parts[0]
            return host
        except Exception:
            return ""

    def _apply_update_mode(self, slug: str) -> None:
        """Pre-configure the dialog for updating an existing platform.

        :param slug: Platform slug to update.
        """
        yaml_path = self._platforms_dir / f"{slug}.yaml"
        if not yaml_path.exists():
            return
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        name = data.get("name", slug) if isinstance(data, dict) else slug
        self.setWindowTitle(f"Update Platform — {name}")
        self._status_label.setText(f"Updating: {name} ({slug})")
        self._status_label.setStyleSheet("color: #FFA726; font-size: 12px;")

    def _on_research(self) -> None:
        """Validate inputs and start the research worker."""
        url = self._url_input.text().strip()
        api_key = self._key_input.text().strip()

        if not url:
            QMessageBox.warning(self, "Missing URL", "Please enter a CRM platform URL.")
            return

        # Basic URL validation
        if "://" not in url:
            url = f"https://{url}"
            self._url_input.setText(url)

        parsed = urlparse(url)
        if not parsed.netloc:
            QMessageBox.warning(
                self, "Invalid URL",
                "Please enter a valid URL (e.g., https://www.example-crm.com)."
            )
            return

        if not api_key:
            QMessageBox.warning(
                self, "Missing API Key",
                "Please provide an Anthropic API key."
            )
            return

        # Save key if requested
        if self._remember_key.isChecked():
            preferences.set_anthropic_api_key(api_key)

        # Normalize optional API docs URL
        api_docs_url = self._api_docs_input.text().strip()
        if api_docs_url and "://" not in api_docs_url:
            api_docs_url = f"https://{api_docs_url}"

        # Check for existing YAML to pass as context
        existing_yaml = None
        slug = self._update_slug or self._slug_from_url(url)
        if slug:
            yaml_path = self._platforms_dir / f"{slug}.yaml"
            if yaml_path.exists():
                existing_yaml = yaml_path.read_text(encoding="utf-8")

        # Switch to progress step
        self._output_panel.clear()
        self._set_step(_STEP_PROGRESS)

        # Start worker
        from espo_impl.workers.research_worker import ResearchWorker

        self._worker = ResearchWorker(
            api_key=api_key,
            url=url,
            base_dir=self._base_dir,
            existing_yaml=existing_yaml,
            api_docs_url=api_docs_url or None,
            parent=self,
        )
        self._worker.output_line.connect(self._on_output_line)
        self._worker.finished_ok.connect(self._on_research_finished)
        self._worker.finished_error.connect(self._on_research_error)
        self._worker.start()

    def _on_output_line(self, message: str, level: str) -> None:
        """Append a line to the output panel.

        :param message: Log message.
        :param level: Level string (info, warn, error).
        """
        color = _COLOR_MAP.get(level, "#FFFFFF")
        self._output_panel.append(
            f'<span style="color: {color};">{message}</span>'
        )

    def _on_research_finished(self, result: object) -> None:
        """Handle successful research completion.

        :param result: PlatformResearchResult.
        """
        self._result = result
        self._yaml_preview.setPlainText(result.yaml_content)

        info_parts = [f"Platform: {result.name}", f"Slug: {result.slug}"]
        if result.is_update:
            info_parts.append("Mode: Update existing")
        else:
            info_parts.append("Mode: New platform")
        info_parts.append(f"Pages fetched: {result.pages_fetched}")
        self._review_info.setText("\n".join(info_parts))

        if result.validation_warnings:
            warnings_text = "\n".join(
                f"  \u2022 {w}" for w in result.validation_warnings
            )
            self._review_warnings.setText(f"Warnings:\n{warnings_text}")
            self._review_warnings.setVisible(True)
        else:
            self._review_warnings.setVisible(False)

        self._set_step(_STEP_REVIEW)

    def _on_research_error(self, error: str) -> None:
        """Handle research failure.

        :param error: Error message.
        """
        self._on_output_line(f"\nResearch failed: {error}", "error")
        self._on_output_line("\nClick 'Back' to try again.", "info")
        self._back_btn.setVisible(True)

    # ─── Step 3: Review & Save ─────────────────────────────────────

    def _build_step_review(self) -> QWidget:
        """Build the review step with YAML preview and save button."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Info section
        self._review_info = QLabel()
        self._review_info.setStyleSheet("font-size: 13px;")
        layout.addWidget(self._review_info)

        # Warnings
        self._review_warnings = QLabel()
        self._review_warnings.setStyleSheet(
            "color: #FFC107; font-size: 12px; padding: 4px;"
        )
        self._review_warnings.setWordWrap(True)
        self._review_warnings.setVisible(False)
        layout.addWidget(self._review_warnings)

        # YAML preview
        self._yaml_preview = QTextEdit()
        self._yaml_preview.setReadOnly(True)
        self._yaml_preview.setStyleSheet(
            "font-family: monospace; font-size: 12px; "
            "background-color: #FAFAFA; padding: 8px;"
        )
        layout.addWidget(self._yaml_preview, stretch=1)

        # Button row
        btn_row = QHBoxLayout()

        discard_btn = QPushButton("Discard")
        discard_btn.clicked.connect(self.reject)
        btn_row.addWidget(discard_btn)

        btn_row.addStretch()

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(
            "background-color: #4CAF50; color: white; font-weight: bold; "
            "padding: 8px 20px; border-radius: 4px;"
        )
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)
        return widget

    def _on_save(self) -> None:
        """Write the YAML file and emit the saved signal."""
        if not self._result or not self._result.yaml_data:
            QMessageBox.warning(
                self, "No Data", "No valid YAML data to save."
            )
            return

        slug = self._result.slug
        if not slug:
            QMessageBox.warning(
                self, "No Slug",
                "The generated profile has no slug. Cannot save."
            )
            return

        yaml_path = self._platforms_dir / f"{slug}.yaml"

        try:
            self._platforms_dir.mkdir(parents=True, exist_ok=True)
            yaml_path.write_text(
                self._result.yaml_content, encoding="utf-8"
            )
        except OSError as exc:
            QMessageBox.critical(
                self, "Save Failed",
                f"Could not write {yaml_path}:\n{exc}"
            )
            return

        logger.info("Saved platform profile: %s", yaml_path)
        self.platform_saved.emit()
        self.accept()

    # ─── Progress step back button ─────────────────────────────────

    def _build_step_progress(self) -> QWidget:
        """Build the progress step with output panel and back button."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self._output_panel = QTextEdit()
        self._output_panel.setReadOnly(True)
        self._output_panel.setStyleSheet(
            "background-color: #1E1E1E; color: #FFFFFF; "
            "font-family: monospace; font-size: 12px; padding: 8px;"
        )
        layout.addWidget(self._output_panel, stretch=1)

        btn_row = QHBoxLayout()
        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(lambda: self._set_step(_STEP_INPUT))
        self._back_btn.setVisible(False)
        btn_row.addWidget(self._back_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        return widget
