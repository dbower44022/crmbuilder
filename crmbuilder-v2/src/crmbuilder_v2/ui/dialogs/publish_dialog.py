"""Publish dialog — push the canonical design to a target instance (PRJ-042).

A two-phase modal: it first **validates** the generated design against the live
target (``POST /publish-validate``) and renders a per-program report; the
**Publish** button stays disabled until every program is valid (REQ-288). On
confirm it **deploys** (``POST /publish``) and renders the per-program result
with summary counts. Both phases run off the UI thread via
:func:`run_in_thread`; the render helpers are pure so they are unit-tested
directly.
"""

from __future__ import annotations

import html
import logging
from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import StorageConnectionError
from crmbuilder_v2.ui.widgets.form_helpers import primary_button
from crmbuilder_v2.ui.widgets.selectable_text import CopyableMessageBox
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.publish_dialog")

_GREEN = "#1e8449"
_RED = "#c0392b"
_AMBER = "#b9770e"
_MUTE = "#888"


def _esc(value: object) -> str:
    return html.escape(str(value))


def _summary_counts(summary: dict | None) -> str:
    """A compact human summary of the deploy counts for one program."""
    s = summary or {}
    bits: list[str] = []
    for key, label in (
        ("created", "created"),
        ("updated", "updated"),
        ("skipped", "skipped"),
        ("relationships_created", "rel(s)"),
        ("layouts_updated", "layout(s)"),
        ("errors", "error(s)"),
    ):
        if s.get(key):
            bits.append(f"{s[key]} {label}")
    return ", ".join(bits)


def _header(phase: str, result: dict) -> str:
    target = _esc(result.get("target_instance", "?"))
    engine = _esc(result.get("engine", "?"))
    return (
        f"<h3 style='margin:0 0 4px 0'>{phase} &middot; {target} "
        f"<span style='color:{_MUTE}'>({engine})</span></h3>"
    )


def _deferral_note(result: dict) -> str:
    defs = result.get("deferrals") or []
    if not defs:
        return ""
    return (
        f"<p style='color:{_AMBER}'>&#9888; {len(defs)} item(s) need manual "
        f"configuration (deferred — see the MANUAL-CONFIG checklist).</p>"
    )


def render_validate_html(result: dict) -> str:
    """Render the validate-phase report as rich text."""
    programs = result.get("programs", [])
    parts = [_header("Validate", result)]
    parts.append(
        f"<p style='color:#555'>{len(programs)} program(s) generated.</p>"
    )
    parts.append("<ul style='margin:0;padding-left:18px'>")
    for p in programs:
        fn = _esc(p.get("filename", "?"))
        errs = p.get("validation_errors") or []
        if errs:
            parts.append(
                f"<li><span style='color:{_RED}'>&#10007; {fn}</span> — "
                f"{len(errs)} error(s):<ul>"
            )
            parts.extend(
                f"<li style='color:{_RED}'>{_esc(e)}</li>" for e in errs
            )
            parts.append("</ul></li>")
        else:
            parts.append(
                f"<li><span style='color:{_GREEN}'>&#10003; {fn}</span> — "
                f"valid</li>"
            )
    parts.append("</ul>")
    parts.append(_deferral_note(result))
    if result.get("validation_failed"):
        parts.append(
            f"<p style='color:{_RED};font-weight:bold'>Fix the errors above "
            f"before publishing.</p>"
        )
    else:
        parts.append(
            f"<p style='color:{_GREEN};font-weight:bold'>All programs valid "
            f"— ready to publish.</p>"
        )
    return "".join(parts)


def render_publish_html(result: dict) -> str:
    """Render the publish-phase report as rich text."""
    programs = result.get("programs", [])
    parts = [_header("Publish", result)]
    parts.append("<ul style='margin:0;padding-left:18px'>")
    for p in programs:
        fn = _esc(p.get("filename", "?"))
        if p.get("deployed"):
            counts = _summary_counts(p.get("summary"))
            suffix = f" ({counts})" if counts else ""
            parts.append(
                f"<li><span style='color:{_GREEN}'>&#10003; {fn}</span> — "
                f"deployed{suffix}</li>"
            )
        else:
            errs = p.get("validation_errors") or []
            reason = (
                f"{len(errs)} validation error(s)" if errs else "not deployed"
            )
            parts.append(
                f"<li><span style='color:{_RED}'>&#10007; {fn}</span> — "
                f"{_esc(reason)}</li>"
            )
    parts.append("</ul>")
    parts.append(_deferral_note(result))
    if result.get("manual_config"):
        parts.append(
            f"<p style='color:{_AMBER}'>Some items must be configured by hand "
            f"— see the MANUAL-CONFIG checklist.</p>"
        )
    return "".join(parts)


def _preview_counts(summary: dict | None) -> str:
    """The actions a program WOULD take, from its dry-run report summary."""
    s = summary or {}
    bits: list[str] = []
    for key, label in (
        ("created", "create"),
        ("updated", "update"),
        ("relationships_created", "relationship(s)"),
        ("layouts_updated", "layout(s)"),
    ):
        if s.get(key):
            bits.append(f"{s[key]} {label}")
    unchanged = (
        (s.get("skipped") or 0)
        + (s.get("layouts_skipped") or 0)
        + (s.get("relationships_skipped") or 0)
    )
    if unchanged:
        bits.append(f"{unchanged} unchanged")
    return ", ".join(bits) or "no changes"


def render_preview_html(result: dict) -> str:
    """Render the preview (dry-run) plan as rich text."""
    programs = result.get("programs", [])
    parts = [_header("Preview", result)]
    parts.append(
        f"<p style='color:{_GREEN}'>Non-destructive — nothing was written "
        f"to the target.</p>"
    )
    parts.append("<ul style='margin:0;padding-left:18px'>")
    for p in programs:
        fn = _esc(p.get("filename", "?"))
        errs = p.get("validation_errors") or []
        if errs:
            parts.append(
                f"<li><span style='color:{_RED}'>&#10007; {fn}</span> — "
                f"{len(errs)} validation error(s)</li>"
            )
        else:
            parts.append(
                f"<li><span style='color:{_AMBER}'>&#9656; {fn}</span> — "
                f"would: {_esc(_preview_counts(p.get('summary')))}</li>"
            )
    parts.append("</ul>")
    parts.append(_deferral_note(result))
    return "".join(parts)


def _publish_failed(result: dict) -> bool:
    return bool(result.get("validation_failed")) or any(
        not p.get("deployed") for p in result.get("programs", [])
    )


class PublishDialog(QDialog):
    """Two-phase validate-then-deploy dialog for a target instance."""

    def __init__(self, client, instance_record: dict, parent=None) -> None:
        super().__init__(parent)
        self._client = client
        self._record = instance_record
        self._identifier = instance_record.get("instance_identifier")
        self._target_name = (
            instance_record.get("instance_name") or self._identifier
        )
        self._can_publish = False
        self._worker = None

        self.setWindowTitle(f"Publish design → {self._target_name}")
        self.resize(680, 500)

        layout = QVBoxLayout(self)
        self._status = QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._results = QTextEdit()
        self._results.setReadOnly(True)
        self._results.setObjectName("publish_results")
        layout.addWidget(self._results, 1)

        row = QHBoxLayout()
        self._revalidate_btn = QPushButton("Re-validate")
        self._revalidate_btn.setObjectName("revalidate_button")
        self._revalidate_btn.clicked.connect(self._start_validate)
        self._preview_btn = QPushButton("Preview")
        self._preview_btn.setObjectName("preview_button")
        self._preview_btn.setToolTip(
            "Show what publishing would change — without writing anything."
        )
        self._preview_btn.clicked.connect(self._start_preview)
        self._publish_btn = primary_button("Publish ▶")
        self._publish_btn.setObjectName("publish_button")
        self._publish_btn.clicked.connect(self._on_publish_clicked)
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        row.addWidget(self._revalidate_btn)
        row.addWidget(self._preview_btn)
        row.addStretch(1)
        row.addWidget(self._publish_btn)
        row.addWidget(close_btn)
        layout.addLayout(row)

        self._set_busy(False, can_publish=False)
        self._start_validate()

    # -- state -----------------------------------------------------------

    def _set_busy(self, busy: bool, *, can_publish: bool | None = None) -> None:
        if can_publish is not None:
            self._can_publish = can_publish
        self._revalidate_btn.setEnabled(not busy)
        self._preview_btn.setEnabled(not busy)
        self._publish_btn.setEnabled(not busy and self._can_publish)

    # -- validate phase --------------------------------------------------

    def _start_validate(self) -> None:
        self._status.setText("Validating the design against the target…")
        self._set_busy(True)
        self._worker = run_in_thread(
            lambda: self._client.publish_validate_instance(self._identifier),
            on_success=self._on_validated,
            on_error=self._on_error,
            parent=self,
        )

    def _on_validated(self, result: dict[str, Any]) -> None:
        self._results.setHtml(render_validate_html(result))
        ok = not result.get("validation_failed", True)
        self._status.setText(
            "Validation passed — ready to publish."
            if ok
            else "Validation failed — fix the errors before publishing."
        )
        self._set_busy(False, can_publish=ok)

    # -- preview phase (non-destructive dry-run) -------------------------

    def _start_preview(self) -> None:
        self._status.setText("Previewing — building the plan (no writes)…")
        self._set_busy(True)
        self._worker = run_in_thread(
            lambda: self._client.publish_preview_instance(self._identifier),
            on_success=self._on_previewed,
            on_error=self._on_error,
            parent=self,
        )

    def _on_previewed(self, result: dict[str, Any]) -> None:
        if result.get("validation_failed"):
            self._results.setHtml(render_validate_html(result))
            self._status.setText(
                "Validation failed — fix the errors before publishing."
            )
            self._set_busy(False, can_publish=False)
            return
        self._results.setHtml(render_preview_html(result))
        self._status.setText(
            "Preview complete — nothing was written. Ready to publish."
        )
        self._set_busy(False, can_publish=True)

    # -- publish phase ---------------------------------------------------

    def _on_publish_clicked(self) -> None:
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Confirm publish")
        confirm.setText(
            f"Deploy the canonical design to {self._target_name}?\n\n"
            "This writes configuration to the live instance."
        )
        confirm.setStandardButtons(
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )
        confirm.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if confirm.exec() != QMessageBox.StandardButton.Ok:
            return
        self._status.setText(f"Publishing to {self._target_name}…")
        self._set_busy(True)
        self._worker = run_in_thread(
            lambda: self._client.publish_instance(self._identifier),
            on_success=self._on_published,
            on_error=self._on_error,
            parent=self,
        )

    def _on_published(self, result: dict[str, Any]) -> None:
        self._results.setHtml(render_publish_html(result))
        self._status.setText(
            "Publish finished with issues — see the report."
            if _publish_failed(result)
            else "Publish complete."
        )
        # A fresh validate is required before another publish.
        self._set_busy(False, can_publish=False)

    # -- errors ----------------------------------------------------------

    def _on_error(self, exc: Exception) -> None:
        _log.warning("Publish operation failed: %s", exc)
        title = (
            "Connection lost"
            if isinstance(exc, StorageConnectionError)
            else "Operation failed"
        )
        ErrorDialog(
            title=title,
            message="The publish operation could not complete.",
            detail=str(exc),
            parent=self,
        ).exec()
        self._status.setText("Operation failed.")
        self._set_busy(False)
