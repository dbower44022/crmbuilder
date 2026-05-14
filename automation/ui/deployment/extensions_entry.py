"""Extensions sidebar entry — install paid + free EspoCRM extensions.

Two sub-tabs:

* **Install** — pick a zip, see the parsed manifest, view slot usage,
  and launch ``ExtensionInstallDialog`` for the active instance.
* **Licenses** — manage registered extension license keys with their
  vendor slot caps. Re-uses ``ExtensionLicenseDialog`` for both add
  and edit.

Slot enforcement (e.g., Advanced Pack: 1 prod + 2 non-prod) is driven
by ``extension_repo.check_slot_availability``; the entry hands off the
final call to ``ExtensionInstallDialog`` which surfaces the blocking
message inline if the cap is hit.
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from automation.core.deployment.deploy_config_repo import load_deploy_config
from automation.core.deployment.extension_repo import (
    ExtensionLicense,
    get_slot_usage,
    list_installs_for_instance,
    list_licenses,
    load_license,
    save_license,
)
from automation.core.deployment.extension_ssh import parse_extension_manifest
from automation.ui.deployment.deployment_logic import InstanceRow
from automation.ui.deployment.extension_install_dialog import (
    ExtensionInstallDialog,
)

logger = logging.getLogger(__name__)


_PRIMARY_STYLE = (
    "QPushButton { background-color: #1565C0; color: white; "
    "border-radius: 4px; padding: 6px 14px; font-size: 12px; } "
    "QPushButton:hover { background-color: #0D47A1; }"
)


_EMPTY_NO_INSTANCES = (
    "No CRM instances available.\n\n"
    "Go to the Instances entry to create one, or run the Deploy Wizard."
)

_EMPTY_NO_INSTANCE = (
    "Select an instance from the picker above to manage its extensions."
)

_EMPTY_NO_DEPLOY_CONFIG = (
    "The selected instance has no deploy configuration.\n\n"
    "Run the Deploy Wizard to provision the instance before installing "
    "extensions."
)


# ── License edit dialog ───────────────────────────────────────────────


class ExtensionLicenseDialog(QDialog):
    """Modal for registering or editing a single license row.

    Used by the Licenses tab. Persists via ``extension_repo.save_license``
    when accepted; the keyring round-trip is opaque to this layer.
    """

    def __init__(
        self,
        db_path: str,
        license_id: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.db_path = db_path
        self.license_id = license_id
        self.setWindowTitle(
            "Edit License" if license_id else "Add License"
        )
        self.setModal(True)
        self.resize(560, 420)

        self._build_ui()
        if license_id is not None:
            self._load_existing(license_id)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Advanced Pack")
        form.addRow("Extension name:", self._name_edit)

        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText(
            "Optional — e.g. CBM core license"
        )
        form.addRow("Purchaser label:", self._label_edit)

        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText(
            "Paste license key — stored in the OS keyring"
        )
        form.addRow("License key:", self._key_edit)

        self._show_key_btn = QPushButton("Show")
        self._show_key_btn.setCheckable(True)
        self._show_key_btn.toggled.connect(self._on_toggle_show_key)
        form.addRow("", self._show_key_btn)

        self._max_prod_spin = QSpinBox()
        self._max_prod_spin.setRange(0, 99)
        self._max_prod_spin.setValue(1)
        form.addRow("Max production slots:", self._max_prod_spin)

        self._max_nonprod_spin = QSpinBox()
        self._max_nonprod_spin.setRange(0, 99)
        self._max_nonprod_spin.setValue(2)
        form.addRow("Max non-production slots:", self._max_nonprod_spin)

        self._notes_edit = QTextEdit()
        self._notes_edit.setPlaceholderText(
            "Optional — renewal date, vendor contact, etc."
        )
        self._notes_edit.setMaximumHeight(80)
        form.addRow("Notes:", self._notes_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_toggle_show_key(self, checked: bool) -> None:
        self._key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked
            else QLineEdit.EchoMode.Password
        )
        self._show_key_btn.setText("Hide" if checked else "Show")

    def _load_existing(self, license_id: int) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                lic = load_license(conn, license_id)
            finally:
                conn.close()
        except Exception as exc:
            QMessageBox.critical(
                self, "Load failed", f"Could not load license: {exc}",
            )
            self.reject()
            return
        if lic is None:
            QMessageBox.critical(
                self, "Not found", "License row no longer exists.",
            )
            self.reject()
            return

        self._name_edit.setText(lic.extension_name)
        self._name_edit.setEnabled(False)  # immutable after creation
        self._label_edit.setText(lic.purchaser_label or "")
        self._key_edit.setText(lic.license_key)
        self._max_prod_spin.setValue(lic.max_production)
        self._max_nonprod_spin.setValue(lic.max_nonproduction)
        self._notes_edit.setPlainText(lic.notes or "")

    def _on_save(self) -> None:
        name = self._name_edit.text().strip()
        key = self._key_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self, "Missing name", "Extension name is required.",
            )
            return
        if not key:
            QMessageBox.warning(
                self, "Missing key", "License key is required.",
            )
            return

        if self.license_id is not None:
            confirm = QMessageBox.question(
                self,
                "Confirm changes",
                "Save changes to this license? If the key was rotated, "
                "any existing installs continue to reference this license "
                "row but the next CRM-side license check will use the new "
                "key.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        license_obj = ExtensionLicense(
            id=self.license_id,
            extension_name=name,
            license_key=key,
            purchaser_label=self._label_edit.text().strip() or None,
            max_production=self._max_prod_spin.value(),
            max_nonproduction=self._max_nonprod_spin.value(),
            notes=self._notes_edit.toPlainText().strip() or None,
        )

        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("PRAGMA foreign_keys = ON")
                save_license(conn, license_obj)
            finally:
                conn.close()
        except sqlite3.IntegrityError as exc:
            QMessageBox.warning(
                self, "Duplicate license",
                f"A license for {name!r} with this purchaser label already "
                "exists. Edit it instead, or use a different label.",
            )
            return
        except Exception as exc:
            logger.exception("save_license failed")
            QMessageBox.critical(
                self, "Save failed", f"Could not save license: {exc}",
            )
            return

        self.accept()


# ── Main entry widget ─────────────────────────────────────────────────


class ExtensionsEntry(QWidget):
    """Sidebar entry containing the Install and Licenses tabs."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._conn: sqlite3.Connection | None = None
        self._instance: InstanceRow | None = None
        self._db_path: str | None = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._empty_label = QLabel()
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            "font-size: 14px; color: #757575; padding: 40px;"
        )
        layout.addWidget(self._empty_label)

        self._tabs = QTabWidget()
        layout.addWidget(self._tabs, stretch=1)
        self._build_install_tab()
        self._build_licenses_tab()

    def _build_install_tab(self) -> None:
        tab = QWidget()
        v = QVBoxLayout(tab)

        info_group = QGroupBox("Target instance")
        info_layout = QVBoxLayout(info_group)
        self._instance_label = QLabel("")
        info_layout.addWidget(self._instance_label)
        v.addWidget(info_group)

        installed_group = QGroupBox("Currently installed extensions")
        installed_layout = QVBoxLayout(installed_group)
        self._installed_table = QTableWidget(0, 4)
        self._installed_table.setHorizontalHeaderLabels(
            ["Extension", "Version", "License", "Installed at"]
        )
        self._installed_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._installed_table.horizontalHeader().setStretchLastSection(True)
        self._installed_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        installed_layout.addWidget(self._installed_table)
        v.addWidget(installed_group, stretch=1)

        btn_row = QHBoxLayout()
        self._install_btn = QPushButton("Install Extension…")
        self._install_btn.setStyleSheet(_PRIMARY_STYLE)
        self._install_btn.clicked.connect(self._on_install_clicked)
        btn_row.addWidget(self._install_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self._tabs.addTab(tab, "Install")

    def _build_licenses_tab(self) -> None:
        tab = QWidget()
        v = QVBoxLayout(tab)

        self._licenses_table = QTableWidget(0, 4)
        self._licenses_table.setHorizontalHeaderLabels(
            ["Extension", "Label", "Production", "Non-production"]
        )
        self._licenses_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self._licenses_table.horizontalHeader().setStretchLastSection(True)
        self._licenses_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self._licenses_table.cellDoubleClicked.connect(
            self._on_license_double_clicked
        )
        v.addWidget(self._licenses_table, stretch=1)

        btn_row = QHBoxLayout()
        self._add_license_btn = QPushButton("Add License…")
        self._add_license_btn.setStyleSheet(_PRIMARY_STYLE)
        self._add_license_btn.clicked.connect(self._on_add_license)
        btn_row.addWidget(self._add_license_btn)

        self._edit_license_btn = QPushButton("Edit Selected…")
        self._edit_license_btn.clicked.connect(self._on_edit_license)
        btn_row.addWidget(self._edit_license_btn)
        btn_row.addStretch()
        v.addLayout(btn_row)

        self._tabs.addTab(tab, "Licenses")

    # ── Public API ────────────────────────────────────────────────

    def refresh(
        self,
        conn: sqlite3.Connection,
        instance: InstanceRow | None,
        db_path: str | None,
        has_instances: bool,
    ) -> None:
        """Reload with current context."""
        self._conn = conn
        self._instance = instance
        self._db_path = db_path

        # Licenses tab is always populated when we have a conn; it's
        # not instance-scoped.
        self._refresh_licenses()

        if not has_instances:
            self._empty_label.setText(_EMPTY_NO_INSTANCES)
            self._empty_label.setVisible(True)
            self._tabs.setVisible(False)
            return
        if not instance:
            self._empty_label.setText(_EMPTY_NO_INSTANCE)
            self._empty_label.setVisible(True)
            self._tabs.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._tabs.setVisible(True)

        self._instance_label.setText(
            f"<b>{instance.name}</b> ({instance.code}) — "
            f"{instance.environment}"
        )
        self._refresh_installed()

    # ── Install tab ───────────────────────────────────────────────

    def _refresh_installed(self) -> None:
        self._installed_table.setRowCount(0)
        if self._conn is None or self._instance is None:
            return
        try:
            installs = list_installs_for_instance(
                self._conn, self._instance.id,
            )
        except sqlite3.OperationalError:
            # Schema may not yet include the extension tables (db pre-v13)
            installs = []

        for inst in installs:
            row = self._installed_table.rowCount()
            self._installed_table.insertRow(row)
            self._installed_table.setItem(
                row, 0, QTableWidgetItem(inst.extension_name),
            )
            self._installed_table.setItem(
                row, 1, QTableWidgetItem(inst.extension_version),
            )
            license_cell = (
                "Licensed" if inst.license_id is not None else "Unlicensed"
            )
            self._installed_table.setItem(
                row, 2, QTableWidgetItem(license_cell),
            )
            self._installed_table.setItem(
                row, 3, QTableWidgetItem(inst.installed_at or ""),
            )

    def _on_install_clicked(self) -> None:
        if self._conn is None or self._instance is None or not self._db_path:
            return

        zip_path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Select EspoCRM extension zip",
            "",
            "EspoCRM extensions (*.zip)",
        )
        if not zip_path_str:
            return
        zip_path = Path(zip_path_str)

        # Validate manifest before opening the heavyweight dialog
        try:
            manifest = parse_extension_manifest(zip_path)
        except (FileNotFoundError, ValueError) as exc:
            QMessageBox.critical(
                self, "Invalid extension zip",
                f"Could not read manifest:\n{exc}",
            )
            return

        try:
            config = load_deploy_config(self._conn, self._instance.id)
        except Exception as exc:
            QMessageBox.critical(
                self, "Deploy config error",
                f"Could not load deploy config: {exc}",
            )
            return
        if config is None:
            QMessageBox.warning(
                self, "Not deployed",
                _EMPTY_NO_DEPLOY_CONFIG,
            )
            return

        dlg = ExtensionInstallDialog(
            config=config,
            db_path=self._db_path,
            instance_name=self._instance.name,
            zip_path=zip_path,
            parent=self,
        )
        dlg.exec()
        self._refresh_installed()
        self._refresh_licenses()

    # ── Licenses tab ──────────────────────────────────────────────

    def _refresh_licenses(self) -> None:
        self._licenses_table.setRowCount(0)
        if self._conn is None:
            return
        try:
            licenses = list_licenses(self._conn)
        except sqlite3.OperationalError:
            return

        for lic in licenses:
            try:
                usage = get_slot_usage(self._conn, lic.id)
                prod_cell = (
                    f"{len(usage.production_installs)}/{usage.max_production}"
                )
                nonprod_cell = (
                    f"{len(usage.nonproduction_installs)}"
                    f"/{usage.max_nonproduction}"
                )
            except Exception:
                prod_cell = "?"
                nonprod_cell = "?"

            row = self._licenses_table.rowCount()
            self._licenses_table.insertRow(row)
            name_item = QTableWidgetItem(lic.extension_name)
            name_item.setData(Qt.ItemDataRole.UserRole, lic.id)
            self._licenses_table.setItem(row, 0, name_item)
            self._licenses_table.setItem(
                row, 1, QTableWidgetItem(lic.purchaser_label or ""),
            )
            self._licenses_table.setItem(row, 2, QTableWidgetItem(prod_cell))
            self._licenses_table.setItem(
                row, 3, QTableWidgetItem(nonprod_cell),
            )

    def _on_add_license(self) -> None:
        if not self._db_path:
            return
        dlg = ExtensionLicenseDialog(
            db_path=self._db_path, license_id=None, parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_licenses()

    def _on_edit_license(self) -> None:
        license_id = self._selected_license_id()
        if license_id is None:
            QMessageBox.information(
                self, "Select a license",
                "Pick a row first, then click Edit Selected.",
            )
            return
        self._open_edit_dialog(license_id)

    def _on_license_double_clicked(self, row: int, _col: int) -> None:
        item = self._licenses_table.item(row, 0)
        if item is None:
            return
        license_id = item.data(Qt.ItemDataRole.UserRole)
        if license_id is None:
            return
        self._open_edit_dialog(int(license_id))

    def _open_edit_dialog(self, license_id: int) -> None:
        if not self._db_path:
            return
        dlg = ExtensionLicenseDialog(
            db_path=self._db_path, license_id=license_id, parent=self,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._refresh_licenses()

    def _selected_license_id(self) -> int | None:
        rows = self._licenses_table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self._licenses_table.item(rows[0].row(), 0)
        if item is None:
            return None
        data = item.data(Qt.ItemDataRole.UserRole)
        return int(data) if data is not None else None
