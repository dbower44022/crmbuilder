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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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


# Friendly headings for the deferral ``kind`` groups, so the checklist names
# the EspoCRM construct an operator configures by hand rather than the raw
# internal kind token. Unknown kinds fall back to a title-cased label.
_DEFERRAL_KIND_LABELS = {
    "view": "Saved views",
    "workflow_action": "Workflows",
    "automation": "Automations / workflows",
    "dedup_rule": "Duplicate-check rules",
    "dedup_normalize": "Duplicate-check rules",
    "message_template": "Message templates",
    "entity_rule": "Dynamic-logic rules",
    "field_rule": "Dynamic-logic rules",
    "derived_field": "Derived (formula) fields",
    "reference_field": "Reference fields",
    "field_attribute": "Field attributes",
    "unmapped_field": "Unmapped fields",
    "entity_default_sort": "Default sort order",
}


def _kind_label(kind: str) -> str:
    return _DEFERRAL_KIND_LABELS.get(
        kind, str(kind).replace("_", " ").capitalize()
    )


def _deferral_line(item: dict) -> str:
    """One checklist row: ``☐ name (parent) — reason``."""
    name = _esc(item.get("name") or item.get("identifier") or "?")
    parent = item.get("parent")
    where = f" <span style='color:{_MUTE}'>({_esc(parent)})</span>" if parent else ""
    detail = item.get("detail")
    why = f" — {_esc(detail)}" if detail else ""
    return f"<li>&#9744; <b>{name}</b>{where}{why}</li>"


def render_manual_config_html(result: dict) -> str:
    """Render the manual-config checklist from the publish result (REQ-294).

    The publish/preview/validate result already carries structured
    ``deferrals`` — the design constructs EspoCRM cannot apply over the REST
    API (saved views, workflows, duplicate-check rules, message templates,
    dynamic-logic rules, derived/reference fields, …) — plus the adapter's
    ``MANUAL-CONFIG.md`` companion text. This turns them into a readable,
    grouped post-publish checklist so an operator knows exactly what is left
    to configure by hand. Returns ``""`` when there is nothing deferred.
    """
    defs = result.get("deferrals") or []
    if not defs:
        # No structured deferrals; note the companion only if it exists.
        if result.get("manual_config"):
            return (
                f"<p style='color:{_AMBER}'>A MANUAL-CONFIG.md companion was "
                f"generated for this design.</p>"
            )
        return ""

    groups: dict[str, list[dict]] = {}
    for item in defs:
        groups.setdefault(item.get("kind") or "other", []).append(item)

    parts = [
        f"<h4 style='margin:12px 0 4px 0;color:{_AMBER}'>&#9888; Manual "
        f"configuration required ({len(defs)} item(s))</h4>",
        "<p style='color:#555;margin:0 0 6px 0'>These are not applied "
        "automatically — configure them by hand in the target's admin UI:"
        "</p>",
    ]
    # Stable, human order: group by friendly label.
    for kind in sorted(groups, key=_kind_label):
        items = groups[kind]
        parts.append(
            f"<p style='margin:6px 0 2px 0'><b>{_esc(_kind_label(kind))}</b> "
            f"<span style='color:{_MUTE}'>({len(items)})</span></p>"
        )
        parts.append("<ul style='margin:0;padding-left:18px'>")
        parts.extend(_deferral_line(i) for i in items)
        parts.append("</ul>")
    return "".join(parts)


_VERIFY_GLYPH = {
    "matching": (_GREEN, "&#10003;"),  # ✓
    "partial": (_AMBER, "&#9656;"),  # ▸
    "missing": (_RED, "&#10007;"),  # ✗
    "unverified": (_MUTE, "?"),
}


def render_verification_html(result: dict) -> str:
    """Render the post-publish verification section (REQ-291).

    After a real publish the service re-reads the live target and confirms each
    declared entity + field landed; this renders that per-object result. Returns
    ``""`` when no verification ran (preview / validate-only).
    """
    verify = result.get("verification")
    if not verify or not verify.get("ran"):
        return ""
    entities = verify.get("entities") or []
    if verify.get("all_present"):
        head = (
            f"<h4 style='margin:12px 0 4px 0;color:{_GREEN}'>&#10003; "
            f"Verified on target — all {len(entities)} object(s) present.</h4>"
        )
    elif not verify.get("conclusive"):
        head = (
            f"<h4 style='margin:12px 0 4px 0;color:{_AMBER}'>&#9888; "
            f"Verification inconclusive — could not read the target's live "
            f"state.</h4>"
        )
    else:
        head = (
            f"<h4 style='margin:12px 0 4px 0;color:{_RED}'>&#10007; "
            f"Verification found gaps — some objects did not land.</h4>"
        )
    parts = [head, "<ul style='margin:0;padding-left:18px'>"]
    for ent in entities:
        status = ent.get("status", "unverified")
        color, glyph = _VERIFY_GLYPH.get(status, (_MUTE, "?"))
        name = _esc(ent.get("entity", "?"))
        missing = ent.get("fields_missing") or []
        if status == "missing":
            detail = "entity not found on target"
        elif missing:
            detail = f"missing field(s): {_esc(', '.join(missing))}"
        elif status == "unverified":
            detail = "not checked"
        else:
            n = len(ent.get("fields_present") or [])
            detail = f"{n} field(s) present"
        parts.append(
            f"<li><span style='color:{color}'>{glyph} {name}</span> — "
            f"{detail}</li>"
        )
    parts.append("</ul>")
    for w in verify.get("warnings") or []:
        parts.append(f"<p style='color:{_MUTE};margin:2px 0'>{_esc(w)}</p>")
    return "".join(parts)


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
    parts.append(render_manual_config_html(result))
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
    parts.append(render_verification_html(result))
    parts.append(render_manual_config_html(result))
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
    parts.append(render_manual_config_html(result))
    return "".join(parts)


def _publish_failed(result: dict) -> bool:
    if bool(result.get("validation_failed")) or any(
        not p.get("deployed") for p in result.get("programs", [])
    ):
        return True
    # A conclusive post-publish verify that found missing objects is an issue
    # even when every program reported "deployed" (REQ-291).
    verify = result.get("verification") or {}
    if verify.get("ran") and verify.get("conclusive") and not verify.get(
        "all_present"
    ):
        return True
    return False


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

        # Scope selector (REQ-290): the operator can uncheck programs to
        # publish only a subset. Populated from the validate result.
        self._scope_label = QLabel("Publish scope (uncheck to exclude):")
        layout.addWidget(self._scope_label)
        self._scope_list = QListWidget()
        self._scope_list.setObjectName("publish_scope_list")
        self._scope_list.setMaximumHeight(110)
        self._scope_list.itemChanged.connect(self._on_scope_changed)
        layout.addWidget(self._scope_list)

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
        self._busy = busy
        self._revalidate_btn.setEnabled(not busy)
        self._preview_btn.setEnabled(not busy)
        self._publish_btn.setEnabled(
            not busy and self._can_publish and self._has_selection()
        )

    # -- scope selection (REQ-290) ---------------------------------------

    def _populate_scope(self, programs: list[dict]) -> None:
        """Fill the scope list from the validate result, preserving any prior
        unchecked selections (a re-validate keeps the operator's choices)."""
        prev_unchecked = {
            self._scope_list.item(i).text()
            for i in range(self._scope_list.count())
            if self._scope_list.item(i).checkState() != Qt.CheckState.Checked
        }
        self._scope_list.blockSignals(True)
        self._scope_list.clear()
        for p in programs:
            fn = p.get("filename", "?")
            item = QListWidgetItem(fn)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Unchecked
                if fn in prev_unchecked
                else Qt.CheckState.Checked
            )
            self._scope_list.addItem(item)
        self._scope_list.blockSignals(False)

    def _has_selection(self) -> bool:
        return any(
            self._scope_list.item(i).checkState() == Qt.CheckState.Checked
            for i in range(self._scope_list.count())
        )

    def _selected_scope(self) -> list[str] | None:
        """The checked filenames, or ``None`` when everything is selected
        (publish the whole design — the default, sends no scope)."""
        total = self._scope_list.count()
        checked = [
            self._scope_list.item(i).text()
            for i in range(total)
            if self._scope_list.item(i).checkState() == Qt.CheckState.Checked
        ]
        if total == 0 or len(checked) == total:
            return None
        return checked

    def _on_scope_changed(self, _item) -> None:
        # Re-evaluate the Publish button (needs at least one selected program).
        self._publish_btn.setEnabled(
            not getattr(self, "_busy", False)
            and self._can_publish
            and self._has_selection()
        )

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
        # The full program list drives the scope selector (validate is always
        # run full-scope so every program is selectable).
        self._populate_scope(result.get("programs", []))
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
        scope = self._selected_scope()
        self._worker = run_in_thread(
            lambda: self._client.publish_preview_instance(
                self._identifier, scope
            ),
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
        scope = self._selected_scope()
        what = (
            "the canonical design"
            if scope is None
            else f"{len(scope)} selected program(s)"
        )
        confirm = CopyableMessageBox(self)
        confirm.setWindowTitle("Confirm publish")
        confirm.setText(
            f"Deploy {what} to {self._target_name}?\n\n"
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
            lambda: self._client.publish_instance(self._identifier, scope),
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
