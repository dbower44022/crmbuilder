"""Engagement delete dialog with forbid-active behaviour (UI v0.5 slice C).

Implements PRD §5.6: soft-deleting the currently-active engagement is
forbidden. The dialog probes ``ActiveEngagementContext`` at open time
and routes to one of three states:

* **Case A — target is not the active engagement.** Standard edge-text
  confirmation flow inherited from ``EntityCrudDeleteDialog``: type the
  identifier, click Delete, soft-delete via the REST API.

* **Case B — target IS the active engagement and another engagement
  exists.** Confirmation field replaced with a static "switch first"
  message; Delete button replaced with an inert "Switch engagement"
  button (slice D rewires it to open the picker).

* **Case B sub-case — target is the active engagement AND the only
  engagement on this install.** Message becomes "create another first";
  button becomes "Create engagement", wired in slice C to open the slice
  C ``EngagementCreateDialog`` directly (slice D rewires to the
  single-gesture ``NewEngagementDialog``).

The slice C placeholder wiring is deliberately explicit (printed
"[TODO slice D]" lines + ``_SLICE_D_TODO_*`` constants) so slice D's
prompt can locate and update them.
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDeleteDialog
from crmbuilder_v2.ui.client import StorageClient

_log = logging.getLogger("crmbuilder_v2.ui.dialogs.engagement_delete")

_SLICE_D_TODO_SWITCH = "[TODO slice D] open picker"
_SLICE_D_TODO_CREATE = "[TODO slice D] open NewEngagementDialog"


class EngagementDeleteDialog(EntityCrudDeleteDialog):
    """Delete-engagement dialog that forbids deleting the active engagement.

    ``active_context`` is the live ``ActiveEngagementContext`` (the same
    instance the rest of the UI shares). When omitted (typical for
    standalone tests of Case A), the dialog assumes no active engagement
    and falls through to standard delete behaviour.
    """

    def __init__(
        self,
        client: StorageClient,
        identifier: str,
        title: str,
        *,
        active_context: ActiveEngagementContext | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            client,
            identifier,
            title,
            client.delete_engagement,
            entity_label="engagement",
            parent=parent,
        )
        self._active_context = active_context
        self._confirm_edit: QLineEdit | None = None
        self._switch_btn: QPushButton | None = None
        self._create_btn: QPushButton | None = None
        self._on_switch_clicked = self._default_switch_handler
        self._on_create_clicked = self._default_create_handler

        active_identifier = (
            active_context.engagement_identifier() if active_context else None
        )
        if active_identifier != identifier:
            self._render_case_a()
            return

        # Case B: active engagement is the target. Count non-deleted
        # engagements to decide between "switch first" and
        # "create another first".
        try:
            other_engagements = [
                e
                for e in client.list_engagements()
                if e.get("engagement_identifier") != identifier
            ]
        except Exception:  # noqa: BLE001 — degrade to switch-first messaging
            _log.exception(
                "Failed to fetch engagements while evaluating last-engagement edge case"
            )
            other_engagements = []
        if other_engagements:
            self._render_case_b_switch(title)
        else:
            self._render_case_b_create(title)

    # ------------------------------------------------------------------
    # Case A — standard edge-text confirmation
    # ------------------------------------------------------------------

    def _render_case_a(self) -> None:
        self._body_label.setText(
            f"Delete {self._identifier} — {self._title or '(unnamed)'}?\n\n"
            "Type the identifier below to confirm. This soft-deletes the "
            "engagement; it can be restored from the Show soft-deleted view."
        )
        self._confirm_edit = QLineEdit()
        self._confirm_edit.setObjectName("delete_confirm_edit")
        self._confirm_edit.setPlaceholderText(self._identifier)
        self._confirm_edit.textChanged.connect(self._on_confirm_text_changed)
        layout = self.layout()
        if isinstance(layout, QVBoxLayout):
            layout.insertWidget(layout.count() - 1, self._confirm_edit)
        self._delete_btn.setEnabled(False)

    def _on_confirm_text_changed(self, text: str) -> None:
        self._delete_btn.setEnabled(text.strip() == self._identifier)

    # ------------------------------------------------------------------
    # Case B — switch-first / create-first messaging
    # ------------------------------------------------------------------

    def _render_case_b_switch(self, title: str) -> None:
        self._body_label.setText(
            f"{title or self._identifier} is currently active. "
            "Switch to a different engagement first, then soft-delete this one."
        )
        self._delete_btn.hide()
        self._switch_btn = QPushButton("Switch engagement")
        self._switch_btn.setObjectName("switch_engagement_button")
        self._switch_btn.setDefault(True)
        self._switch_btn.clicked.connect(self._invoke_switch_handler)
        self._add_action_button(self._switch_btn)

    def _render_case_b_create(self, title: str) -> None:
        self._body_label.setText(
            f"{title or self._identifier} is the only engagement on this "
            "install. Create another engagement before soft-deleting this one."
        )
        self._delete_btn.hide()
        self._create_btn = QPushButton("Create engagement")
        self._create_btn.setObjectName("create_engagement_button")
        self._create_btn.setDefault(True)
        self._create_btn.clicked.connect(self._invoke_create_handler)
        self._add_action_button(self._create_btn)

    def _add_action_button(self, btn: QPushButton) -> None:
        """Insert ``btn`` next to the existing Cancel button in the action row."""
        layout = self.layout()
        if not isinstance(layout, QVBoxLayout):
            return
        # The base inserts a button row as the last child layout in
        # ``__init__``. Walk children to find it.
        for i in range(layout.count() - 1, -1, -1):
            item = layout.itemAt(i)
            sub = item.layout() if item is not None else None
            if isinstance(sub, QHBoxLayout):
                sub.addWidget(btn)
                return
        # Fallback: append as a standalone widget.
        layout.addWidget(btn)

    # ------------------------------------------------------------------
    # Slice C inert handlers (slice D rewires)
    # ------------------------------------------------------------------

    def _default_switch_handler(self) -> None:
        # Slice D rewires this to open the engagement picker on the
        # main window. Slice C-only callers see a stdout trace as a
        # diagnostic hint; the production main window swaps the handler
        # in via :meth:`set_switch_handler`.
        print(_SLICE_D_TODO_SWITCH)
        main_window = _find_main_window(self)
        if main_window is not None and hasattr(
            main_window, "_on_top_strip_clicked"
        ):
            self.reject()
            main_window._on_top_strip_clicked()

    def _default_create_handler(self) -> None:
        # Opens the create-and-select NewEngagementDialog when the parent
        # exposes an active-engagement context; otherwise falls back to the
        # plain EngagementCreateDialog.
        print(_SLICE_D_TODO_CREATE)
        main_window = _find_main_window(self)
        active_ctx = (
            getattr(main_window, "_active_context", None)
            if main_window is not None
            else None
        )
        if active_ctx is not None:
            from crmbuilder_v2.ui.dialogs.new_engagement_dialog import (
                NewEngagementDialog,
            )

            dialog = NewEngagementDialog(self._client, active_ctx, self)
        else:
            from crmbuilder_v2.ui.dialogs.engagement_crud import (
                EngagementCreateDialog,
            )

            dialog = EngagementCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Closing the parent delete dialog lets the panel refresh;
            # the active engagement remains, and the user can re-attempt
            # the delete after switching.
            self.reject()

    def _invoke_switch_handler(self) -> None:
        self._on_switch_clicked()

    def _invoke_create_handler(self) -> None:
        self._on_create_clicked()

    # ------------------------------------------------------------------
    # Slice D rewiring hooks
    # ------------------------------------------------------------------

    def set_switch_handler(self, handler) -> None:
        """Hook for slice D to replace the inert switch-button behaviour."""
        self._on_switch_clicked = handler

    def set_create_handler(self, handler) -> None:
        """Hook for slice D to replace the create-button behaviour."""
        self._on_create_clicked = handler


def _find_main_window(widget: QWidget):
    """Walk up the parent chain looking for the application's MainWindow.

    Returns ``None`` if no MainWindow ancestor is found (test dialogs
    constructed without a window parent fall back to slice-C
    placeholder behavior).
    """
    parent = widget.parentWidget()
    while parent is not None:
        if parent.metaObject().className() == "MainWindow":
            return parent
        # Some Qt builds report the qualified class name; do a lenient
        # check too.
        cls_name = type(parent).__name__
        if cls_name == "MainWindow":
            return parent
        parent = parent.parentWidget()
    return None
