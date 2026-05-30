"""Commits panel — code change lifecycle browse surface (PI-031).

Read-only master/detail over the ``/commits`` API. Commits are
documentary records ingested via close-out payload (DEC-185); the panel
exposes no Create/Edit/Delete affordance — only browse, filter, and a
natural-key by-SHA lookup.

Schema note (DEC reconciling PI-031 to post-PI-073): commits attribute
at *session* grain (``commit_session_id`` FK, ``/sessions/{id}/commits``)
rather than the conversation grain PI-031 originally assumed. The
producing session is therefore the identity-level link rendered
prominently outside the ``ReferencesSection`` (parallel to ``field``'s
parent-entity treatment per DEC-273). The repository and session filters
are the server-supported axes; the PI's conversation/planning-item
filters do not map to the current schema and are intentionally omitted.
"""

from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.exceptions import StorageClientError, StorageConnectionError
from crmbuilder_v2.ui.panels._governance_helpers import (
    heading_label,
    read_only_line,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.references_section import ReferencesSection

_log = logging.getLogger("crmbuilder_v2.ui.panels.commits")

_ALL = "All"
_SHA_MIN = 4


class CommitsPanel(ListDetailPanel):
    """Read-only browse panel for commits (PI-031)."""

    def __init__(self, client, parent=None):
        # Created in ``_filter_strip_widget`` (runs during super().__init__).
        self._repo_filter: QComboBox | None = None
        self._session_filter: QComboBox | None = None
        self._sha_input: QLineEdit | None = None
        self._sha_status: QLabel | None = None
        self._all_records: list[dict[str, Any]] = []
        super().__init__(client, parent)
        # No New button — commits are ingested via close-out only (DEC-185).

    def entity_title(self) -> str:
        return "Commits"

    def fetch_records(self) -> list[dict[str, Any]]:
        # API already sorts commit_committed_at descending (DEC-214).
        return self._client.list_commits()

    def list_columns(self) -> list[ColumnSpec]:
        return [
            ColumnSpec(field="commit_identifier", title="Identifier", width=90),
            ColumnSpec(field="commit_repository", title="Repository", width=120),
            ColumnSpec(field="commit_author_name", title="Author", width=130),
            ColumnSpec(field="commit_committed_display", title="Committed", width=140),
            ColumnSpec(field="commit_message_first_line", title="Message"),
        ]

    # ------------------------------------------------------------------
    # Filter strip — Repository + Session combos and by-SHA lookup
    # ------------------------------------------------------------------

    def _filter_strip_widget(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Repository:"))
        self._repo_filter = QComboBox()
        self._repo_filter.setObjectName("commit_repository_filter")
        self._repo_filter.addItem(_ALL)
        self._repo_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._repo_filter)

        layout.addSpacing(12)
        layout.addWidget(QLabel("Session:"))
        self._session_filter = QComboBox()
        self._session_filter.setObjectName("commit_session_filter")
        self._session_filter.addItem(_ALL)
        self._session_filter.currentIndexChanged.connect(self._on_filter_changed)
        layout.addWidget(self._session_filter)

        layout.addSpacing(16)
        layout.addWidget(QLabel("Find by SHA:"))
        self._sha_input = QLineEdit()
        self._sha_input.setObjectName("commit_sha_input")
        self._sha_input.setPlaceholderText("≥4 chars")
        self._sha_input.setMaximumWidth(180)
        self._sha_input.returnPressed.connect(self._on_sha_lookup)
        layout.addWidget(self._sha_input)
        find_btn = QPushButton("Find")
        find_btn.setObjectName("commit_sha_find_button")
        find_btn.clicked.connect(self._on_sha_lookup)
        layout.addWidget(find_btn)
        self._sha_status = QLabel("")
        self._sha_status.setObjectName("commit_sha_status")
        self._sha_status.setStyleSheet("color: #888;")
        layout.addWidget(self._sha_status)

        layout.addStretch(1)
        return container

    def _post_process_records(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        for r in records:
            r["commit_committed_display"] = format_timestamp(
                r.get("commit_committed_at")
            )
        self._all_records = list(records)
        self._refresh_filter_options(records)
        return self._apply_filter(records)

    def _refresh_filter_options(self, records: list[dict[str, Any]]) -> None:
        repos = sorted(
            {r.get("commit_repository") or "" for r in records if r.get("commit_repository")}
        )
        sessions = sorted(
            {r.get("commit_session_id") or "" for r in records if r.get("commit_session_id")}
        )
        self._set_combo_items(self._repo_filter, repos)
        self._set_combo_items(self._session_filter, sessions)

    def _set_combo_items(self, combo: QComboBox | None, values: list[str]) -> None:
        if combo is None:
            return
        previous = combo.currentText()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(_ALL)
        for v in values:
            combo.addItem(v)
        index = combo.findText(previous) if previous else -1
        combo.setCurrentIndex(index if index >= 0 else 0)
        combo.blockSignals(False)

    def _apply_filter(
        self, records: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        repo_value = self._repo_filter.currentText() if self._repo_filter else _ALL
        session_value = (
            self._session_filter.currentText() if self._session_filter else _ALL
        )

        def keep(r: dict[str, Any]) -> bool:
            if repo_value != _ALL and (r.get("commit_repository") or "") != repo_value:
                return False
            if (
                session_value != _ALL
                and (r.get("commit_session_id") or "") != session_value
            ):
                return False
            return True

        return [r for r in records if keep(r)]

    def _on_filter_changed(self, _index: int) -> None:
        filtered = self._apply_filter(self._all_records)
        self._records = filtered
        self._model.set_records(filtered)
        self._status_label.setText(f"{len(filtered)} records")

    # ------------------------------------------------------------------
    # By-SHA lookup (DEC-213 four-case behavior)
    # ------------------------------------------------------------------

    def _on_sha_lookup(self) -> None:
        if self._sha_input is None or self._sha_status is None:
            return
        sha = self._sha_input.text().strip()
        if len(sha) < _SHA_MIN:
            self._sha_status.setText(f"Enter at least {_SHA_MIN} characters.")
            return
        try:
            kind, payload = self._client.find_commit_by_sha(sha)
        except StorageConnectionError as exc:
            _log.warning("Connection lost during by-SHA lookup: %s", exc)
            self.connection_lost.emit(str(exc))
            return
        except StorageClientError as exc:
            self._sha_status.setText(f"Lookup failed: {exc}")
            return

        if kind == "found" and isinstance(payload, dict):
            ident = payload.get("commit_identifier") or ""
            self._reset_filters()
            if ident:
                self._sha_status.setText(f"→ {ident}")
                self.select_record_by_identifier(ident)
            return
        if kind == "ambiguous":
            candidates = payload or []
            preview = ", ".join(c[:10] for c in candidates[:5])
            extra = "" if len(candidates) <= 5 else f" (+{len(candidates) - 5} more)"
            self._sha_status.setText(
                f"Ambiguous prefix — {len(candidates)} matches: {preview}{extra}"
                if candidates
                else "Ambiguous prefix — enter more characters."
            )
            return
        self._sha_status.setText(f"No commit matches '{sha}'.")

    def _reset_filters(self) -> None:
        for combo in (self._repo_filter, self._session_filter):
            if combo is not None and combo.currentIndex() != 0:
                combo.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Detail pane
    # ------------------------------------------------------------------

    def fetch_detail_extras(self, record: dict[str, Any]) -> dict[str, Any]:
        identifier = record.get("commit_identifier")
        if not identifier:
            return {"references": {"as_source": [], "as_target": []}}
        return {
            "references": self._client.list_references_touching("commit", identifier)
        }

    def render_detail(
        self, record: dict[str, Any], extras: dict[str, Any]
    ) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        identifier = record.get("commit_identifier") or ""
        outer.addWidget(
            heading_label(record.get("commit_message_first_line") or identifier)
        )

        # Producing session rendered prominently (identity-level, DEC-273).
        session_id = record.get("commit_session_id") or ""
        if session_id:
            link = QLabel(
                f'Produced in session: <a href="session:{session_id}">{session_id}</a>'
            )
            link.setObjectName("commit_producing_session_link")
            link.setTextFormat(Qt.TextFormat.RichText)
            link.linkActivated.connect(self._emit_link_navigation)
            outer.addWidget(link)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form.addRow("Identifier", read_only_line(identifier))
        form.addRow("SHA", read_only_line(record.get("commit_sha") or ""))
        form.addRow("Repository", read_only_line(record.get("commit_repository") or ""))
        form.addRow("Branch", read_only_line(record.get("commit_branch") or ""))
        author = record.get("commit_author_name") or ""
        email = record.get("commit_author_email") or ""
        form.addRow(
            "Author",
            read_only_line(f"{author} <{email}>" if email else author),
        )
        form.addRow(
            "Committed",
            read_only_line(format_timestamp(record.get("commit_committed_at"))),
        )
        files_changed = record.get("commit_files_changed_count")
        form.addRow(
            "Files changed",
            read_only_line("" if files_changed is None else str(files_changed)),
        )
        parents = record.get("commit_parent_shas") or []
        if isinstance(parents, list) and parents:
            form.addRow(
                "Parent(s)",
                read_only_line(", ".join(p[:10] for p in parents)),
            )
        outer.addLayout(form)

        outer.addWidget(separator())
        outer.addWidget(QLabel("<b>Commit message</b>"))
        outer.addWidget(read_only_text(record.get("commit_message_full") or ""))

        outer.addWidget(separator())
        refs = ReferencesSection(
            "commit", identifier, extras.get("references") or {}, client=self._client
        )
        # Read-only: commits are ingested via close-out, not edited in the UI.
        if hasattr(refs, "set_add_enabled"):
            refs.set_add_enabled(False)
        refs.navigate_requested.connect(self.navigate_requested)
        outer.addWidget(refs)

        outer.addStretch(1)
        scroll.setWidget(container)
        return scroll

    # ------------------------------------------------------------------
    # Identifier-field overrides (commit_identifier, not "identifier")
    # ------------------------------------------------------------------

    def _select_by_identifier(self, identifier: str) -> bool:
        for row, record in enumerate(self._records):
            if record.get("commit_identifier") == identifier:
                self._select_row(row)
                return True
        return False

    def _build_context_menu(self, index: QModelIndex) -> QMenu:
        menu = QMenu(self)
        if not index.isValid():
            return menu
        record = self._record_at_index(index)
        if record is None:
            return menu
        copy_id = menu.addAction("Copy Identifier")
        copy_id.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("commit_identifier") or "")
        )
        copy_sha = menu.addAction("Copy SHA")
        copy_sha.triggered.connect(
            lambda _c=False, r=record: self._copy(r.get("commit_sha") or "")
        )
        return menu

    @staticmethod
    def _copy(text: str) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(text)
