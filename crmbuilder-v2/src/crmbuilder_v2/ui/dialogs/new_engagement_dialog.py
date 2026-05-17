"""Single-gesture create+activate engagement dialog (v0.5 slice D).

Extends slice C's :class:`EngagementCreateDialog`. Where the slice C
dialog creates only the meta DB row, the slice D variant chains three
sequential operations behind one user click per PRD §5.3:

1. POST ``/engagements`` to create the meta DB row.
2. Create the per-engagement DB file at ``engagements/{code}.db`` and
   run Alembic to head against it via
   :func:`run_engagement_migrations`.
3. Activate via :class:`ActivationWorker`.

A three-label progress indicator displays the running operation. On
failure the dialog presents the standard retry / stay affordances and,
in the file-creation failure case, rolls back the meta DB row.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.access.engagement_models import (
    Engagement,
    EngagementStatus,
)
from crmbuilder_v2.migration.lazy_migration import (
    MigrationError,
    engagement_db_path,
)
from crmbuilder_v2.ui.activation_worker import (
    ActivationWorker,
    SubprocessManagers,
    run_activation_in_thread,
)
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs.engagement_crud import EngagementCreateDialog

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.new_engagement_dialog")


class NewEngagementDialog(EngagementCreateDialog):
    """Slice D single-gesture creation + activation dialog.

    Constructor parameters beyond :class:`EngagementCreateDialog`:

    * ``active_context`` — the desktop's :class:`ActiveEngagementContext`.
    * ``managers`` — :class:`SubprocessManagers` for the activation worker.
    """

    activation_completed = Signal(object)  # Engagement
    activation_failed = Signal(object, str)  # Engagement | None, message

    def __init__(
        self,
        client: StorageClient,
        active_context,
        managers: SubprocessManagers,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(client, parent)
        self._active_context = active_context
        self._managers = managers
        self.setWindowTitle("New engagement (create + activate)")

        self._created_engagement: Engagement | None = None
        self._activation_thread = None
        self._activation_worker: ActivationWorker | None = None

        self._progress_widget = self._build_progress_widget()
        self._progress_widget.setVisible(False)
        outer = self.layout()
        if isinstance(outer, QVBoxLayout):
            outer.addWidget(self._progress_widget)

    # ------------------------------------------------------------------
    # Progress widget
    # ------------------------------------------------------------------

    def _build_progress_widget(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("new_engagement_progress")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(4)

        self._step1_label = self._make_step_label("Creating engagement record…")
        self._step2_label = self._make_step_label("Initializing database…")
        self._step3_label = self._make_step_label("Switching to engagement…")
        layout.addWidget(self._step1_label)
        layout.addWidget(self._step2_label)
        layout.addWidget(self._step3_label)

        # Action row hidden until activation failure.
        action_row = QHBoxLayout()
        action_row.addStretch(1)
        self._retry_btn = QPushButton("Try switching now")
        self._retry_btn.setObjectName("retry_activation_button")
        self._retry_btn.clicked.connect(self._on_retry_activation)
        action_row.addWidget(self._retry_btn)
        self._stay_btn = QPushButton("Stay in current engagement")
        self._stay_btn.setObjectName("stay_in_previous_button")
        self._stay_btn.clicked.connect(self._on_stay_in_previous)
        action_row.addWidget(self._stay_btn)
        self._retry_btn.setVisible(False)
        self._stay_btn.setVisible(False)
        layout.addLayout(action_row)

        return wrapper

    def _make_step_label(self, text: str) -> QLabel:
        label = QLabel(f"○ {text}")
        label.setObjectName(f"step_{text.split()[0].lower()}")
        return label

    def _mark_step(
        self, label: QLabel, status: str
    ) -> None:
        """Update a step label's leading glyph (``○`` / ``✓`` / ``✗``)."""
        text = label.text()
        # Strip prior glyph (single character + space).
        if text[:2] in ("○ ", "✓ ", "✗ "):
            text = text[2:]
        glyph = {"pending": "○ ", "success": "✓ ", "failure": "✗ "}.get(
            status, "○ "
        )
        label.setText(f"{glyph}{text}")

    # ------------------------------------------------------------------
    # Submit overrides — chain create → migrate → activate
    # ------------------------------------------------------------------

    def _on_save_clicked(self) -> None:
        # Reuse parent class validation + worker for the POST step.
        # The parent's success callback will run our chained flow.
        self._progress_widget.setVisible(True)
        self._mark_step(self._step1_label, "pending")
        super()._on_save_clicked()

    def _on_save_success(self, result: Any) -> None:
        # Operation 1 succeeded: capture the returned engagement record.
        if isinstance(result, dict):
            self._created_engagement = _engagement_from_dict(result)
            self._saved_identifier = result.get("engagement_identifier")
        self._mark_step(self._step1_label, "success")

        # Operation 2: create the per-engagement DB file + run Alembic.
        self._mark_step(self._step2_label, "pending")
        if self._created_engagement is None:
            self._mark_step(self._step2_label, "failure")
            self._show_inline_failure(
                "Engagement record was created but the returned payload was "
                "malformed; cannot proceed with database initialization."
            )
            return
        try:
            self._create_engagement_db(self._created_engagement.engagement_code)
        except Exception as exc:  # noqa: BLE001 — see rollback below
            self._mark_step(self._step2_label, "failure")
            self._rollback_meta_row(self._created_engagement)
            self._show_inline_failure(f"Database initialization failed: {exc}")
            return
        self._mark_step(self._step2_label, "success")

        # Operation 3: activate via ActivationWorker.
        self._mark_step(self._step3_label, "pending")
        self._start_activation()

    # ------------------------------------------------------------------
    # File creation + meta-row rollback
    # ------------------------------------------------------------------

    def _create_engagement_db(self, engagement_code: str) -> None:
        """Create the per-engagement DB file and materialise the schema.

        Uses :func:`bootstrap_database` (the v0.1-shipped ``create_all``
        helper) to seed the schema, then stamps Alembic's
        ``alembic_version`` table at head so subsequent activation
        no-op upgrades match the dogfood-migrated CRMBUILDER engagement's
        on-disk shape. Going via Alembic directly fails today because
        the ``0004_catalog_seed`` migration depends on the decommissioned
        ``PRDs/product/crmbuilder-v2/research/base-entity-catalog/``
        YAML directory (commit ``eb02943``); when that migration is
        replaced with a data-only seeder, this helper can route through
        ``run_engagement_migrations`` instead.
        """
        import os

        from alembic import command

        from crmbuilder_v2.access.db import bootstrap_database, reset_engine_cache
        from crmbuilder_v2.config import reset_settings_cache
        from crmbuilder_v2.migration.lazy_migration import (
            make_engagement_alembic_config,
        )

        db_path = engagement_db_path(engagement_code)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # Touch the file so subsequent reachability checks succeed.
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("SELECT 1")
        finally:
            conn.close()

        prior = os.environ.get("CRMBUILDER_V2_DB_PATH")
        os.environ["CRMBUILDER_V2_DB_PATH"] = str(db_path)
        reset_settings_cache()
        reset_engine_cache()
        try:
            bootstrap_database()
            cfg = make_engagement_alembic_config(engagement_code)
            command.stamp(cfg, "head")
        finally:
            if prior is None:
                os.environ.pop("CRMBUILDER_V2_DB_PATH", None)
            else:
                os.environ["CRMBUILDER_V2_DB_PATH"] = prior
            reset_settings_cache()
            reset_engine_cache()

    def _rollback_meta_row(self, engagement: Engagement) -> None:
        """Best-effort DELETE of the meta DB row created in step 1."""
        try:
            self._client.delete_engagement(engagement.engagement_identifier)
        except Exception:  # noqa: BLE001 — diagnostic only
            _log.exception(
                "Rollback DELETE for %s failed; meta row left in place",
                engagement.engagement_identifier,
            )

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------

    def _start_activation(self) -> None:
        if self._created_engagement is None:
            return
        previous = (
            self._active_context.engagement()
            if self._active_context is not None
            else None
        )
        worker = ActivationWorker(
            target_engagement=self._created_engagement,
            previous_engagement=previous,
            client=self._client,
            active_context=self._active_context,
            managers=self._managers,
        )
        worker.completed.connect(self._on_activation_completed)
        worker.failed.connect(self._on_activation_failed)
        self._activation_worker = worker
        self._activation_thread = run_activation_in_thread(worker, parent=self)

    def _on_activation_completed(self, engagement) -> None:
        self._mark_step(self._step3_label, "success")
        self.activation_completed.emit(engagement)
        self.accept()

    def _on_activation_failed(self, _previous, error_message: str) -> None:
        self._mark_step(self._step3_label, "failure")
        self._show_inline_failure(error_message)
        self.activation_failed.emit(self._created_engagement, error_message)

    def _show_inline_failure(self, message: str) -> None:
        _log.warning("NewEngagementDialog failure: %s", message)
        self._retry_btn.setVisible(True)
        self._stay_btn.setVisible(True)
        self._save_btn.setEnabled(True)
        # Surface the error message visually under the step labels.
        if not hasattr(self, "_inline_error"):
            self._inline_error = QLabel("")
            self._inline_error.setObjectName("new_engagement_inline_error")
            self._inline_error.setStyleSheet("color: #c1272d;")
            self._inline_error.setWordWrap(True)
            self._inline_error.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            )
            layout = self._progress_widget.layout()
            if isinstance(layout, QVBoxLayout):
                layout.addWidget(self._inline_error)
        self._inline_error.setText(message)

    def _on_retry_activation(self) -> None:
        if self._created_engagement is None:
            return
        self._mark_step(self._step3_label, "pending")
        self._retry_btn.setVisible(False)
        self._stay_btn.setVisible(False)
        if hasattr(self, "_inline_error"):
            self._inline_error.setText("")
        self._start_activation()

    def _on_stay_in_previous(self) -> None:
        # The engagement record + DB file persist on disk; the user can
        # try activation again later from the picker. Close the dialog.
        self.reject()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _engagement_from_dict(payload: dict[str, Any]) -> Engagement | None:
    """Build an :class:`Engagement` from a REST envelope payload."""
    try:
        status_raw = payload.get("engagement_status") or "active"
        status = (
            status_raw
            if isinstance(status_raw, EngagementStatus)
            else EngagementStatus(status_raw)
        )
        return Engagement(
            engagement_identifier=payload["engagement_identifier"],
            engagement_code=payload["engagement_code"],
            engagement_name=payload.get("engagement_name") or "",
            engagement_purpose=payload.get("engagement_purpose") or "",
            engagement_status=status,
            engagement_last_opened_at=None,
            engagement_export_dir=payload.get("engagement_export_dir"),
            engagement_created_at=_parse_dt(payload.get("engagement_created_at")),
            engagement_updated_at=_parse_dt(payload.get("engagement_updated_at")),
            engagement_deleted_at=None,
        )
    except Exception:  # noqa: BLE001 — defensive
        return None


def _parse_dt(value):
    from datetime import UTC, datetime

    if value is None:
        return datetime.now(UTC)
    if isinstance(value, datetime):
        return value
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt
    except ValueError:
        return datetime.now(UTC)
