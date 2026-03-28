"""Deploy section for the main window — switches content based on instance state."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from espo_impl.core.deploy_manager import load_deploy_config
from espo_impl.core.models import DeployConfig, InstanceProfile
from espo_impl.ui.deploy_dashboard import DeployDashboard

logger = logging.getLogger(__name__)


class DeployPanel(QWidget):
    """Deploy section whose content switches based on instance selection.

    Three states:
    - No instance selected
    - Instance selected, no deploy config
    - Instance selected, deploy config exists (shows dashboard)

    :param instances_dir: Path to instances directory.
    :param parent: Parent widget.
    """

    def __init__(
        self,
        instances_dir: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._instances_dir = instances_dir
        self._profile: InstanceProfile | None = None
        self._config: DeployConfig | None = None
        self._dashboard: DeployDashboard | None = None
        self._cert_worker = None
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack)

        # State 0: No instance selected
        no_instance = QWidget()
        no_layout = QVBoxLayout(no_instance)
        no_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_label = QLabel("Select an instance to manage its deployment.")
        no_label.setStyleSheet("color: gray;")
        no_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_layout.addWidget(no_label)
        self._stack.addWidget(no_instance)

        # State 1: Instance selected, no deploy config
        no_config = QWidget()
        nc_layout = QVBoxLayout(no_config)
        nc_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nc_label = QLabel("No deployment configured for this instance.")
        nc_label.setStyleSheet("color: gray;")
        nc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        nc_layout.addWidget(nc_label)
        self._setup_btn = QPushButton("Set Up Deployment")
        self._setup_btn.clicked.connect(self._on_setup_deployment)
        nc_layout.addWidget(
            self._setup_btn, alignment=Qt.AlignmentFlag.AlignCenter
        )
        self._stack.addWidget(no_config)

        # State 2: Dashboard (added dynamically)
        self._dashboard_placeholder = QWidget()
        self._stack.addWidget(self._dashboard_placeholder)

        self._stack.setCurrentIndex(0)

    def set_instance(self, profile: InstanceProfile | None) -> None:
        """Update the panel for a new instance selection.

        :param profile: Selected instance profile, or None.
        """
        self._profile = profile
        self._config = None
        self._dashboard = None

        if profile is None:
            self._stack.setCurrentIndex(0)
            return

        # Try to load deploy config
        self._config = load_deploy_config(
            self._instances_dir, profile.slug
        )

        if self._config is None:
            self._stack.setCurrentIndex(1)
            return

        # Show dashboard
        self._show_dashboard()

        # Background cert check
        self._start_cert_check()

    def get_dashboard(self) -> DeployDashboard | None:
        """Return the current dashboard widget, if any."""
        return self._dashboard

    def _show_dashboard(self) -> None:
        """Create and display the dashboard for the current config."""
        dashboard = DeployDashboard(
            self._profile, self._config, self._instances_dir, self
        )
        self._dashboard = dashboard

        # Replace the placeholder widget at index 2
        old = self._stack.widget(2)
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.addWidget(dashboard)
        self._stack.setCurrentIndex(2)

    def _on_setup_deployment(self) -> None:
        """Open the deploy wizard for first-time setup."""
        if not self._profile:
            return

        from espo_impl.ui.deploy_wizard import DeployWizard

        wizard = DeployWizard(
            self._profile, self._instances_dir, parent=self
        )
        wizard.config_saved.connect(self._on_config_saved)
        wizard.exec()

    def _on_config_saved(self, config: DeployConfig) -> None:
        """Handle config saved from wizard."""
        self._config = config
        self._show_dashboard()

    def _start_cert_check(self) -> None:
        """Start a background certificate expiry check."""
        if not self._config or not self._dashboard:
            return

        from espo_impl.workers.deploy_worker import CertCheckWorker

        self._cert_worker = CertCheckWorker(
            self._config.full_domain, parent=self
        )
        self._cert_worker.cert_expiry_result.connect(
            self._on_cert_expiry_result
        )
        self._cert_worker.start()

    def _on_cert_expiry_result(self, expiry_date: str) -> None:
        """Handle background cert check result."""
        self._cert_worker = None
        if self._config:
            self._config.cert_expiry_date = expiry_date
        if self._dashboard:
            self._dashboard.update_cert_badge(expiry_date)
