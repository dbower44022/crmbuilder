"""Engagements panel (UI v0.5 slice C).

``ListDetailPanel`` subclass registered as the single entry in the
Engagements sidebar group introduced empty by slice A. Master pane
shows the five PRD §5.1 columns; detail pane shows the read-only form
per ``engagement.md`` §3.6.3 / PRD §5.1; right-click menu offers the
four standard actions plus Restore on soft-deleted rows; an empty-state
banner with a "Create Engagement" CTA renders when there are no
engagements.

The active engagement (per ``ActiveEngagementContext``) is marked with
a left-accent stripe on its row plus a leading "✓ " glyph in the
Identifier column. Soft-deleted rows render with strikethrough and a
leading "🗑 " glyph in the Identifier column; they appear only when the
"Show soft-deleted" toggle is on.

The accent color was migrated from the legacy ``ACCENT_COLOR`` navy
to the design-tokens ``color.accent.default`` (cool blue ``#1F5FBF``)
in v0.6 slice A; the public ``ACTIVE_ACCENT_COLOR`` export keeps the
same name so downstream consumers (the soft-delete strikethrough
delegate, the legacy-pinned color tests) continue to import it.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.active_engagement_context import ActiveEngagementContext
from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.dialogs.engagement_crud import (
    EngagementCreateDialog,
    EngagementEditDialog,
)
from crmbuilder_v2.ui.dialogs.engagement_delete import EngagementDeleteDialog
from crmbuilder_v2.ui.dialogs.error import ErrorDialog
from crmbuilder_v2.ui.exceptions import (
    NotFoundError,
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import created_updated_section
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import (
    destructive_button,
    primary_button,
    required_label,
)

_log = logging.getLogger("crmbuilder_v2.ui.panels.engagements")

_ACTIVE_ACCENT_COLOR = t("color.accent.default")
_STATUS_PAUSED_COLOR = t("color.warning.default")
_STATUS_ARCHIVED_COLOR = t("color.neutral.500")
_SOFT_DELETED_COLOR = t("color.neutral.500")

# Glyphs prepended to the Identifier column. Plain Unicode rather than
# Lucide icons because v0.4 panels render their list cells via the
# default ``_RecordTableModel`` and don't carry an icon-paint hook. The
# styling tokens module (when it ships) may replace these with Lucide
# SVGs.
_ACTIVE_GLYPH = "✓ "
_SOFT_DELETED_GLYPH = "🗑 "

_READ_ONLY_STYLE = "color: #444; background: #f4f4f4;"
_LONG_TEXT_MIN_HEIGHT = 80


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def format_relative_date(dt: datetime | None, *, now: datetime | None = None) -> str:
    """Render a datetime as a relative-date string per PRD §5.1.

    Null → ``"—"``. Within last 60 minutes → ``"N minutes ago"``.
    Within last 24 hours → ``"N hours ago"``. Within last 30 days →
    ``"N days ago"``. Older → ISO date ``"YYYY-MM-DD"`` (resolving PRD
    Open Question 3's "common alternative").
    """
    if dt is None:
        return "—"
    reference = now if now is not None else datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=UTC)
    delta = reference - dt
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return dt.date().isoformat()
    minutes = seconds // 60
    if minutes < 60:
        return f"{max(minutes, 0)} minutes ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours} hours ago"
    days = hours // 24
    if days < 30:
        return f"{days} days ago"
    return dt.date().isoformat()


def _heading_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    font = QFont(label.font())
    font.setBold(True)
    font.setPointSize(font.pointSize() + 2)
    label.setFont(font)
    return label


def _read_only_line(value: str, *, placeholder: str = "") -> QLineEdit:
    widget = QLineEdit()
    widget.setText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


def _read_only_text(value: str, *, placeholder: str = "") -> QPlainTextEdit:
    widget = QPlainTextEdit()
    widget.setPlainText(value or "")
    widget.setReadOnly(True)
    widget.setStyleSheet(_READ_ONLY_STYLE)
    widget.setMinimumHeight(_LONG_TEXT_MIN_HEIGHT)
    if placeholder:
        widget.setPlaceholderText(placeholder)
    return widget


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFrameShadow(QFrame.Shadow.Sunken)
    return line


# ---------------------------------------------------------------------------
# Export-dir warning band (multi-tenancy routing fix slice B — B4 / B5)
# ---------------------------------------------------------------------------

_WARN_STATE_HIDDEN = "hidden"
_WARN_STATE_NULL = "null"
_WARN_STATE_MISSING = "missing"

_WARN_NULL_TEXT = (
    "This engagement has no export directory configured. Reads will "
    "work; writes are disabled until you set one via Edit Engagement."
)
_WARN_NULL_BUTTON = "Set export directory…"
_WARN_MISSING_BUTTON = "Edit engagement…"


def _warn_missing_text(path: str) -> str:
    return (
        f"Configured export directory does not exist on disk: {path}. "
        "Either create the directory or update the engagement via Edit "
        "Engagement."
    )


class ExportDirWarningBand(QFrame):
    """Inline band warning that the active engagement's export_dir is unusable.

    Three states (B4 / B5):

    * ``null`` (yellow / warning tone) — the active engagement has no
      ``engagement_export_dir`` configured. Reads work; writes fail loud.
    * ``missing`` (red / danger tone) — a path is configured but does not
      exist on disk. Writes fail loud at the export gate.
    * ``hidden`` — export_dir is configured and present, or there is no
      assessable active engagement.

    The action button is never disabled (project convention); it is simply
    hidden along with the band when the state is ``hidden``. The button's
    label tracks the state; the panel connects it to a single handler that
    dispatches on :attr:`state`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("engagement_export_dir_warning_band")
        self.state = _WARN_STATE_HIDDEN

        layout = QHBoxLayout(self)
        pad = int(t("space.2").rstrip("px"))
        layout.setContentsMargins(pad, pad, pad, pad)
        layout.setSpacing(pad)

        self._text_label = QLabel()
        self._text_label.setObjectName("engagement_export_dir_warning_text")
        self._text_label.setWordWrap(True)
        layout.addWidget(self._text_label, stretch=1)

        self._action_button = QPushButton()
        self._action_button.setObjectName(
            "engagement_export_dir_warning_action"
        )
        layout.addWidget(self._action_button)

        self.setVisible(False)

    @property
    def action_button(self) -> QPushButton:
        return self._action_button

    def show_null(self) -> None:
        self.state = _WARN_STATE_NULL
        self._text_label.setText(_WARN_NULL_TEXT)
        self._action_button.setText(_WARN_NULL_BUTTON)
        self._apply_tone(
            bg="color.warning.subtle",
            border="color.warning.default",
            fg="color.warning.default",
        )
        self.setVisible(True)

    def show_missing(self, path: str) -> None:
        self.state = _WARN_STATE_MISSING
        self._text_label.setText(_warn_missing_text(path))
        self._action_button.setText(_WARN_MISSING_BUTTON)
        self._apply_tone(
            bg="color.danger.subtle",
            border="color.danger.default",
            fg="color.danger.text",
        )
        self.setVisible(True)

    def hide_band(self) -> None:
        self.state = _WARN_STATE_HIDDEN
        self.setVisible(False)

    def _apply_tone(self, *, bg: str, border: str, fg: str) -> None:
        self.setStyleSheet(
            f"#engagement_export_dir_warning_band {{"
            f" background: {t(bg)};"
            f" border: 1px solid {t(border)};"
            f" border-radius: 4px;"
            f" }}"
            f" #engagement_export_dir_warning_text {{ color: {t(fg)}; }}"
        )


# ---------------------------------------------------------------------------
# Panel
# ---------------------------------------------------------------------------


class EngagementsPanel(ListDetailPanel):
    """Engagement management panel with read + write surfaces."""

    def __init__(
        self,
        client,
        active_context: ActiveEngagementContext | None = None,
        parent=None,
    ):
        self._include_deleted = False
        self._active_context = active_context
        self._now_provider = lambda: datetime.now(UTC)
        super().__init__(client, parent)

        self._show_deleted_check = QCheckBox("Show soft-deleted")
        self._show_deleted_check.setObjectName("show_soft_deleted_check")
        self._show_deleted_check.toggled.connect(self._on_show_deleted_toggled)
        self._action_layout.addWidget(self._show_deleted_check)

        self._new_button = primary_button("New Engagement")
        self._new_button.setObjectName("new_engagement_button")
        self._new_button.clicked.connect(self._on_new_engagement_clicked)
        self._action_layout.addWidget(self._new_button)

        # Export-dir warning band (B4 / B5): sits immediately under the
        # toolbar/header, above the master/detail splitter. Its state is
        # recomputed on every refresh (``_post_process_records``) and on
        # active-engagement switches (which trigger a refresh).
        self._warning_band = ExportDirWarningBand()
        self._warning_band.action_button.clicked.connect(
            self._on_warning_band_action
        )
        outer = self.layout()
        if isinstance(outer, QVBoxLayout):
            # Index 1: after the toolbar (index 0), before the splitter.
            outer.insertWidget(1, self._warning_band)

        # Empty-state overlay (toggled by ``_post_process_records``).
        self._empty_state = self._build_empty_state()
        self._empty_state.setVisible(False)
        if isinstance(outer, QVBoxLayout):
            outer.addWidget(self._empty_state)

        # Active-engagement signal: refresh so the marker repaints.
        if active_context is not None:
            active_context.active_engagement_changed.connect(
                lambda _eng: self.refresh()
            )

    # ------------------------------------------------------------------
    # ListDetailPanel hooks
    # ------------------------------------------------------------------

    def entity_title(self) -> str:
        return "Engagements"

    def fetch_records(self) -> list[dict[str, Any]]:
        return self._client.list_engagements(
            include_deleted=self._include_deleted
        )

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(
                field="_display_identifier", title="Identifier", width=110
            ),
            ColumnSpec(field="engagement_code", title="Code", width=100),
            ColumnSpec(field="engagement_name", title="Name"),
            ColumnSpec(
                field="engagement_status", title="Status", width=90
            ),
            ColumnSpec(
                field="_display_last_opened", title="Last Opened", width=130
            ),
            ColumnSpec(
                field="created_at_display", title="Created", width=140
            ),
        ]

    def _strikethrough_for_record(self, record: dict[str, Any]) -> bool:
        return record.get("engagement_deleted_at") is not None

    # ------------------------------------------------------------------
    # Post-process: sort and decorate identifier column
    # ------------------------------------------------------------------

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        active_identifier = (
            self._active_context.engagement_identifier()
            if self._active_context is not None
            else None
        )
        now = self._now_provider()

        decorated: list[dict[str, Any]] = []
        for r in records:
            identifier = r.get("engagement_identifier") or ""
            is_deleted = r.get("engagement_deleted_at") is not None
            is_active = identifier == active_identifier
            glyph = ""
            if is_active:
                glyph = _ACTIVE_GLYPH
            elif is_deleted:
                glyph = _SOFT_DELETED_GLYPH
            display_id = f"{glyph}{identifier}"
            last_opened = _parse_iso(r.get("engagement_last_opened_at"))
            display_last_opened = format_relative_date(last_opened, now=now)
            decorated.append(
                {
                    **r,
                    "_display_identifier": display_id,
                    "_display_last_opened": display_last_opened,
                    "_is_active_engagement": is_active,
                    "_last_opened_dt": last_opened,
                    # PI-108: formatted Created column for the master pane.
                    "created_at_display": format_timestamp(
                        r.get("engagement_created_at")
                    ),
                }
            )

        # Default sort: deleted to the bottom; otherwise Last Opened
        # descending (most recent first; nulls last).
        epoch = datetime.fromtimestamp(0, UTC)

        def _sort_key(r: dict[str, Any]):
            deleted = r.get("engagement_deleted_at") is not None
            last_opened = r.get("_last_opened_dt")
            # Negate timestamp for descending order; missing → epoch
            # (sorts last among the live group).
            score = -(last_opened or epoch).timestamp()
            return (1 if deleted else 0, score, r.get("engagement_identifier") or "")

        decorated.sort(key=_sort_key)

        # Toggle empty-state visibility.
        self._empty_state.setVisible(len(decorated) == 0)
        self._master_view.setVisible(len(decorated) > 0)

        # Recompute the export-dir warning band against the freshly-fetched
        # records (which carry the real engagement_export_dir from the meta
        # DB). Runs on the UI thread per the base-class contract.
        self._update_export_dir_warning(decorated)
        return decorated

    def _on_show_deleted_toggled(self, checked: bool) -> None:
        self._include_deleted = checked
        self.refresh()

    # ------------------------------------------------------------------
    # Export-dir warning band (B4 / B5)
    # ------------------------------------------------------------------

    def _update_export_dir_warning(
        self, records: list[dict[str, Any]]
    ) -> None:
        """Set the warning band state from the active engagement's export_dir.

        Reads ``engagement_export_dir`` from the active engagement's record
        in ``records`` (the authoritative meta-DB value), not from the
        in-memory ``ActiveEngagementContext`` stub which may carry ``None``.
        Null/empty → yellow band; set-but-absent-on-disk → red band;
        present → hidden. Hidden also when there is no active engagement or
        its record is not in the current list (e.g. filtered out).
        """
        active_identifier = (
            self._active_context.engagement_identifier()
            if self._active_context is not None
            else None
        )
        if not active_identifier:
            self._warning_band.hide_band()
            return
        record = next(
            (
                r
                for r in records
                if r.get("engagement_identifier") == active_identifier
            ),
            None,
        )
        if record is None:
            self._warning_band.hide_band()
            return
        export_dir = record.get("engagement_export_dir")
        if not export_dir:
            self._warning_band.show_null()
            return
        if not Path(export_dir).is_dir():
            self._warning_band.show_missing(export_dir)
            return
        self._warning_band.hide_band()

    def _on_warning_band_action(self) -> None:
        """Open Edit Engagement for the active engagement from the band.

        Null state focuses the export-dir field (so the operator lands on
        the field to set); missing state opens the dialog normally.
        """
        focus = self._warning_band.state == _WARN_STATE_NULL
        self._open_edit_for_active(focus_export_dir=focus)

    def _open_edit_for_active(self, *, focus_export_dir: bool) -> None:
        identifier = (
            self._active_context.engagement_identifier()
            if self._active_context is not None
            else None
        )
        if not identifier:
            return
        try:
            fresh = self._client.get_engagement(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning(
                "Connection lost loading active %s for edit: %s",
                identifier,
                exc,
            )
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning(
                "Engagement error loading active %s for edit: %s",
                identifier,
                exc,
            )
            ErrorDialog(
                title="Could not load engagement",
                message="Could not load the latest version of this engagement.",
                detail=str(exc),
                parent=self,
            ).exec()
            return
        dialog = EngagementEditDialog(self._client, fresh, self)
        if focus_export_dir:
            dialog.focus_export_dir_field()
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    # ------------------------------------------------------------------
    # Detail pane
    # ------------------------------------------------------------------

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("engagement_identifier") or ""
        is_deleted = record.get("engagement_deleted_at") is not None
        is_active = bool(record.get("_is_active_engagement"))

        # Edit / Delete (or Restore / Edit) strip.
        strip = QWidget()
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(6)
        if is_deleted:
            restore_btn = QPushButton("Restore")
            restore_btn.setObjectName("restore_engagement_button")
            restore_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
            strip_layout.addWidget(restore_btn)
        edit_btn = QPushButton("Edit")
        edit_btn.setObjectName("edit_engagement_button")
        edit_btn.clicked.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        strip_layout.addWidget(edit_btn)
        if not is_deleted:
            delete_btn = destructive_button("Delete")
            delete_btn.setObjectName("delete_engagement_button")
            delete_btn.clicked.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
            strip_layout.addWidget(delete_btn)
        strip_layout.addStretch(1)
        outer.addWidget(strip)

        name = record.get("engagement_name") or "(unnamed)"
        title_text = f"{_ACTIVE_GLYPH}{name}" if is_active else name
        outer.addWidget(_heading_label(title_text))

        form = QFormLayout()
        # v0.6 slice C: label-above form layout per design pass §2.4.
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        identifier_label = QLabel(identifier or "—")
        identifier_label.setObjectName("engagement_identifier_value")
        mono = QFont("Monospace")
        mono.setStyleHint(QFont.StyleHint.TypeWriter)
        identifier_label.setFont(mono)
        identifier_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        form.addRow(required_label("Identifier"), identifier_label)

        code_value = _read_only_line(record.get("engagement_code") or "")
        code_value.setObjectName("engagement_code_value")
        code_value.setFont(mono)
        form.addRow(required_label("Code"), code_value)

        name_value = _read_only_line(record.get("engagement_name") or "")
        name_value.setObjectName("engagement_name_value")
        form.addRow(required_label("Name"), name_value)

        purpose_value = _read_only_text(
            record.get("engagement_purpose") or "",
            placeholder="What this engagement covers",
        )
        purpose_value.setObjectName("engagement_purpose_value")
        form.addRow(required_label("Purpose"), purpose_value)

        status_value = _read_only_line(record.get("engagement_status") or "")
        status_value.setObjectName("engagement_status_value")
        status_value.setStyleSheet(
            _read_only_status_stylesheet(record.get("engagement_status"))
        )
        form.addRow(required_label("Status"), status_value)

        export_dir_value = _read_only_line(
            record.get("engagement_export_dir") or "",
            placeholder="Optional — leave blank to disable auto-export.",
        )
        export_dir_value.setObjectName("engagement_export_dir_value")
        form.addRow("Export dir", export_dir_value)

        created_value = _read_only_line(
            format_relative_date(
                _parse_iso(record.get("engagement_created_at")),
                now=self._now_provider(),
            )
        )
        created_value.setObjectName("engagement_created_at_value")
        form.addRow("Created at", created_value)

        updated_value = _read_only_line(
            format_relative_date(
                _parse_iso(record.get("engagement_updated_at")),
                now=self._now_provider(),
            )
        )
        updated_value.setObjectName("engagement_updated_at_value")
        form.addRow("Updated at", updated_value)

        if is_deleted:
            deleted_value = _read_only_line(
                format_relative_date(
                    _parse_iso(record.get("engagement_deleted_at")),
                    now=self._now_provider(),
                )
            )
            deleted_value.setObjectName("engagement_deleted_at_value")
            form.addRow("Deleted at", deleted_value)

        outer.addLayout(form)

        # PI-108: created / last-edited audit timestamps (absolute local
        # time, in addition to the relative "Created at" / "Updated at"
        # rows above).
        outer.addWidget(_separator())
        outer.addWidget(
            created_updated_section(
                record, "engagement_created_at", "engagement_updated_at"
            )
        )

        outer.addWidget(_separator())
        # No References section: engagement has no relationships in v0.5
        # per engagement.md §3.8.
        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Identifier addressing (engagement uses ``engagement_identifier``)
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("engagement_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def _currently_selected_identifier(self) -> str | None:
        master = getattr(self, "_master_view", None)
        if master is None:
            return None
        sel_model = master.selectionModel()
        if sel_model is None:
            return None
        index = sel_model.currentIndex()
        if not index.isValid():
            return None
        row = index.row()
        if 0 <= row < len(self._records):
            ident = self._records[row].get("engagement_identifier")
            if isinstance(ident, str):
                return ident
        return None

    # ------------------------------------------------------------------
    # Right-click context menu
    # ------------------------------------------------------------------

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            new_action = menu.addAction("New")
            new_action.triggered.connect(self._on_new_engagement_clicked)
            return menu

        record = self._record_at_index(index)
        if record is None:
            return menu

        new_action = menu.addAction("New")
        new_action.triggered.connect(self._on_new_engagement_clicked)
        edit_action = menu.addAction("Edit")
        edit_action.triggered.connect(
            lambda _checked=False, r=record: self._on_edit_clicked(r)
        )
        if record.get("engagement_deleted_at") is not None:
            restore_action = menu.addAction("Restore")
            restore_action.triggered.connect(
                lambda _checked=False, r=record: self._on_restore_clicked(r)
            )
        else:
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(
                lambda _checked=False, r=record: self._on_delete_clicked(r)
            )
        return menu

    # ------------------------------------------------------------------
    # Empty-state
    # ------------------------------------------------------------------

    def _build_empty_state(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setObjectName("engagements_empty_state")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(24, 32, 24, 32)
        layout.setSpacing(8)
        layout.addStretch(1)
        heading = QLabel("No engagements yet")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading_font = QFont(heading.font())
        heading_font.setBold(True)
        heading_font.setPointSize(heading_font.pointSize() + 2)
        heading.setFont(heading_font)
        layout.addWidget(heading)
        body = QLabel("Create your first engagement to begin")
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(body)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        create_btn = primary_button("Create Engagement")
        create_btn.setObjectName("empty_state_create_engagement_button")
        create_btn.clicked.connect(self._on_new_engagement_clicked)
        button_row.addWidget(create_btn)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        layout.addStretch(1)
        return wrapper

    # ------------------------------------------------------------------
    # Write-surface click handlers
    # ------------------------------------------------------------------

    def _on_new_engagement_clicked(self) -> None:
        # PI-β: prefer the create-and-select NewEngagementDialog when the panel
        # has an active-engagement context (the desktop). Fall back to the
        # plain Create dialog for scripted / fixture paths without a context.
        if self._active_context is not None:
            from crmbuilder_v2.ui.dialogs.new_engagement_dialog import (
                NewEngagementDialog,
            )

            dialog = NewEngagementDialog(
                self._client,
                self._active_context,
                self,
            )
        else:
            dialog = EngagementCreateDialog(self._client, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_id = dialog.created_identifier()
            if new_id:
                self.select_record_by_identifier(new_id)
            else:
                self.refresh()

    def _on_edit_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("engagement_identifier")
        if not identifier:
            return
        try:
            fresh = self._client.get_engagement(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost loading %s for edit: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Engagement error loading %s for edit: %s", identifier, exc)
            ErrorDialog(
                title="Could not load engagement",
                message="Could not load the latest version of this engagement.",
                detail=str(exc),
                parent=self,
            ).exec()
            return

        dialog = EngagementEditDialog(self._client, fresh, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_delete_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("engagement_identifier") or ""
        name = record.get("engagement_name") or ""
        if not identifier:
            return
        dialog = EngagementDeleteDialog(
            self._client,
            identifier,
            name,
            active_context=self._active_context,
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _on_restore_clicked(self, record: dict[str, Any]) -> None:
        identifier = record.get("engagement_identifier") or ""
        if not identifier:
            return
        try:
            self._client.restore_engagement(identifier)
        except NotFoundError:
            self.refresh()
            return
        except StorageConnectionError as exc:
            _log.warning("Connection lost restoring %s: %s", identifier, exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            _log.warning("Engagement error restoring %s: %s", identifier, exc)
            ErrorDialog(
                title="Could not restore engagement",
                message=(
                    "An error occurred while restoring the engagement. "
                    "Please try again."
                ),
                detail=str(exc),
                parent=self,
            ).exec()
            return
        self.refresh()


# ---------------------------------------------------------------------------
# Status colour stylesheet helper
# ---------------------------------------------------------------------------


def _read_only_status_stylesheet(status: Any) -> str:
    """Return a QSS string with the status-aware color overlay."""
    base = _READ_ONLY_STYLE
    if status == "paused":
        return base + f" color: {_STATUS_PAUSED_COLOR};"
    if status == "archived":
        return base + f" color: {_STATUS_ARCHIVED_COLOR};"
    return base


# Re-export for tests / future styling integration.
ACTIVE_ACCENT_COLOR = _ACTIVE_ACCENT_COLOR
ACTIVE_GLYPH = _ACTIVE_GLYPH
SOFT_DELETED_GLYPH = _SOFT_DELETED_GLYPH

__all__ = (
    "EngagementsPanel",
    "format_relative_date",
    "ACTIVE_ACCENT_COLOR",
    "ACTIVE_GLYPH",
    "SOFT_DELETED_GLYPH",
)

# QBrush/QColor are imported for the styling tokens module retrofit path
# (e.g., painting active-row backgrounds via a custom delegate); the
# slice-C tokens are inlined as constants per the prompt's coordination
# note when the tokens module has not shipped.
_ = (QBrush, QColor)
