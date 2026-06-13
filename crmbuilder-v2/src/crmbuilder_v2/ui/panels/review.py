"""Requirements Review panel (requirements-provenance Phase 6b).

The Qt rendering of the topic-first review process (anchor §"How a review
works"): pick a topic → read its requirement tree top-down → open a requirement
and trace it to the conversation that defined it → read the read-back document →
sign off; plus the three review queues (approval / drift / coverage gaps).

The panel is read-only over the review surface (``/review/...``,
``/coverage/...``) with one exception — recording a sign-off, which is a
conforming API write (``POST /review/signoffs``). Record *creation* is otherwise
the API/MCP's job; this panel is for review.

It subclasses :class:`ListDetailPanel` purely to inherit the main-window wiring
(``connection_lost`` / ``navigate_requested`` signals, refresh-on-select,
refresh-on-lifecycle-ready, worker-drain teardown) — the layout is fully custom
(a topic picker driving a tree + tabs), so ``_build_ui`` and ``refresh`` are
overridden wholesale rather than reusing the master/detail scaffolding. Fetches
run on the shared worker-thread helper; transient sub-dialogs are
``deleteLater``-d to avoid the worker-thread GC crash
(``project_qt_worker_widget_gc_hazard``).
"""

from __future__ import annotations

import logging
from functools import partial
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.base.list_detail_panel import ColumnSpec, ListDetailPanel
from crmbuilder_v2.ui.exceptions import (
    StorageClientError,
    StorageConnectionError,
)
from crmbuilder_v2.ui.panels._governance_helpers import (
    heading_label,
    read_only_line,
    read_only_text,
    separator,
)
from crmbuilder_v2.ui.widgets.datetime_format import format_timestamp
from crmbuilder_v2.ui.widgets.form_helpers import icon_button
from crmbuilder_v2.ui.workers import run_in_thread

_log = logging.getLogger("crmbuilder_v2.ui.panels.review")

_NODE_ROLE = Qt.ItemDataRole.UserRole

_NEEDS_REVIEW_STYLE = (
    "color: #842029; background: #f8d7da; border: 1px solid #f5c2c7;"
    " border-radius: 4px; padding: 2px 6px;"
)
_FLAG_STYLE = "color: #b76e00;"

# The provenance spine (anchor §"How a review works"). Two stages have a
# concrete flag on the node; the other four are "present/unknown for now"
# per the Phase 6b prompt.
_SPINE_STAGES = ("defined", "decided", "specified", "planned", "developed", "verified")


class ReviewPanel(ListDetailPanel):
    """Topic-first requirements review surface (read-only + sign-off write)."""

    def __init__(self, client, parent=None):
        # Custom state, set before super().__init__ runs _build_ui.
        self._topic_index: dict[str, dict[str, Any]] = {}
        self._current_topic_id: str | None = None
        self._populating_combo = False
        self._dialogs: list[QWidget] = []
        super().__init__(client, parent)

    # -- ListDetailPanel abstract hooks (unused; layout is fully custom) ----

    def entity_title(self) -> str:
        return "Requirements Review"

    def fetch_records(self) -> list[dict[str, Any]]:  # pragma: no cover - unused
        return []

    def list_columns(self) -> list[ColumnSpec]:  # pragma: no cover - unused
        return []

    def render_detail(self, record, extras) -> QWidget:  # pragma: no cover - unused
        return QWidget()

    # -- Layout --------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(8)

        # Toolbar: title · refresh · topic picker · status.
        bar = QHBoxLayout()
        bar.setSpacing(8)
        bar.addWidget(heading_label("Requirements Review"))
        self._refresh_button = icon_button("rotate-ccw", tooltip="Refresh")
        self._refresh_button.clicked.connect(self.refresh)
        bar.addWidget(self._refresh_button)
        bar.addWidget(QLabel("Topic:"))
        self._topic_combo = QComboBox()
        self._topic_combo.setMinimumWidth(360)
        self._topic_combo.currentIndexChanged.connect(self._on_topic_changed)
        bar.addWidget(self._topic_combo, stretch=1)
        self._status_label = QLabel("")
        bar.addWidget(self._status_label)
        outer.addLayout(bar)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_review_tab(), "Topic Review")
        self._tabs.addTab(self._build_document_tab(), "Read-back")
        self._tabs.addTab(self._build_approval_tab(), "Approval")
        self._tabs.addTab(self._build_drift_tab(), "Drift")
        self._tabs.addTab(self._build_coverage_tab(), "Coverage gaps")
        outer.addWidget(self._tabs, stretch=1)

    def _build_review_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self._req_tree = QTreeWidget()
        self._req_tree.setHeaderLabels(["Requirement", "Status", "Flags"])
        self._req_tree.setColumnWidth(0, 320)
        self._req_tree.setColumnWidth(1, 90)
        self._req_tree.setAlternatingRowColors(True)
        self._req_tree.currentItemChanged.connect(self._on_req_selected)
        splitter.addWidget(self._req_tree)

        self._detail_scroll = QScrollArea()
        self._detail_scroll.setWidgetResizable(True)
        self._detail_scroll.setWidget(
            self._placeholder("Select a requirement to see its detail.")
        )
        splitter.addWidget(self._detail_scroll)
        splitter.setSizes([450, 550])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        layout.addWidget(self._build_signoff_section())
        return page

    def _build_signoff_section(self) -> QWidget:
        box = QGroupBox("Sign-off")
        v = QVBoxLayout(box)
        self._signoff_topic_label = QLabel("No topic selected.")
        self._signoff_topic_label.setWordWrap(True)
        v.addWidget(self._signoff_topic_label)
        row = QHBoxLayout()
        self._signoff_button = QPushButton("Record sign-off…")
        self._signoff_button.clicked.connect(self._on_record_signoff)
        row.addWidget(self._signoff_button)
        row.addStretch(1)
        v.addLayout(row)
        v.addWidget(QLabel("Prior sign-offs:"))
        self._signoff_list = QListWidget()
        self._signoff_list.setMaximumHeight(120)
        v.addWidget(self._signoff_list)
        return box

    def _build_document_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self._doc_view = QTextBrowser()
        self._doc_view.setOpenExternalLinks(False)
        layout.addWidget(self._doc_view)
        return page

    def _build_approval_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(
            QLabel(
                "Candidate requirements awaiting activation — each row shows "
                "what it still needs before it can be approved."
            )
        )
        self._approval_tree = QTreeWidget()
        self._approval_tree.setHeaderLabels(
            ["Identifier", "Name", "Origin", "Has provenance", "Has topic"]
        )
        self._approval_tree.setColumnWidth(0, 110)
        self._approval_tree.setColumnWidth(1, 300)
        self._approval_tree.setAlternatingRowColors(True)
        layout.addWidget(self._approval_tree)
        return page

    def _build_drift_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(
            QLabel("Requirements flagged NEEDS REVIEW by living drift.")
        )
        self._drift_tree = QTreeWidget()
        self._drift_tree.setHeaderLabels(["Identifier", "Name", "Status", "Origin"])
        self._drift_tree.setColumnWidth(0, 110)
        self._drift_tree.setColumnWidth(1, 320)
        self._drift_tree.setAlternatingRowColors(True)
        layout.addWidget(self._drift_tree)
        return page

    def _build_coverage_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        self._coverage_summary = QLabel("")
        self._coverage_summary.setWordWrap(True)
        layout.addWidget(self._coverage_summary)
        layout.addWidget(
            QLabel(
                "Coverage gaps — work without a requirement above it, "
                "requirements without planned work below them, and completed "
                "conversations that produced no requirement."
            )
        )
        self._coverage_tree = QTreeWidget()
        self._coverage_tree.setHeaderLabels(["Identifier", "Detail"])
        self._coverage_tree.setColumnWidth(0, 200)
        self._coverage_tree.setAlternatingRowColors(True)
        layout.addWidget(self._coverage_tree)
        return page

    @staticmethod
    def _placeholder(text: str) -> QWidget:
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #888;")
        return label

    # -- Refresh (overview: topics + the three global queues) ----------------

    def refresh(self) -> None:
        self._status_label.setText("Loading…")
        self._run(
            self._fetch_overview,
            on_success=self._on_overview,
            on_error=self._on_error,
        )

    def _fetch_overview(self) -> dict[str, Any]:
        return {
            "topics": self._client.list_topics(),
            "approval": self._client.review_approval_queue(),
            "drift": self._client.review_drift_queue(),
            "coverage": self._client.capability_coverage(),
        }

    def _on_overview(self, result: Any) -> None:
        if not isinstance(result, dict):
            return
        topics = result.get("topics") or []
        self._topic_index = {
            t["identifier"]: t for t in topics if t.get("identifier")
        }
        self._populate_topic_combo(topics)
        self._fill_approval(result.get("approval") or [])
        self._fill_drift(result.get("drift") or [])
        self._fill_coverage(result.get("coverage") or {})
        self._status_label.setText(f"{len(topics)} topics")
        # Drive the topic-scoped panes off the (possibly newly-restored)
        # selection.
        if self._current_topic_id:
            self._load_topic(self._current_topic_id)

    def _populate_topic_combo(self, topics: list[dict[str, Any]]) -> None:
        # Preserve the prior selection across refreshes.
        prior = self._current_topic_id
        ordered = sorted(topics, key=lambda t: t.get("identifier") or "")
        self._populating_combo = True
        try:
            self._topic_combo.clear()
            for t in ordered:
                ident = t.get("identifier") or ""
                name = t.get("name") or ""
                self._topic_combo.addItem(f"{ident} — {name}", ident)
            if prior is not None:
                idx = self._topic_combo.findData(prior)
                if idx >= 0:
                    self._topic_combo.setCurrentIndex(idx)
        finally:
            self._populating_combo = False
        # Settle the current selection (the guard suppressed the signal).
        data = self._topic_combo.currentData()
        self._current_topic_id = data if isinstance(data, str) else None
        self._signoff_topic_label.setText(
            self._signoff_topic_text(self._current_topic_id)
        )

    def _on_topic_changed(self, _index: int) -> None:
        if self._populating_combo:
            return
        data = self._topic_combo.currentData()
        self._current_topic_id = data if isinstance(data, str) else None
        self._signoff_topic_label.setText(
            self._signoff_topic_text(self._current_topic_id)
        )
        if self._current_topic_id:
            self._load_topic(self._current_topic_id)

    def _signoff_topic_text(self, topic_id: str | None) -> str:
        if not topic_id:
            return "No topic selected."
        topic = self._topic_index.get(topic_id, {})
        return f"Topic {topic_id} — {topic.get('name') or ''}"

    # -- Topic-scoped load (tree + read-back document + sign-offs) -----------

    def _load_topic(self, topic_id: str) -> None:
        def _fetch() -> dict[str, Any]:
            return {
                "topic_id": topic_id,
                "review": self._client.topic_review(topic_id),
                "document": self._client.topic_review_document(topic_id),
                "signoffs": self._client.list_signoffs(topic_id),
            }

        self._run(_fetch, on_success=self._on_topic_loaded, on_error=self._on_error)

    def _on_topic_loaded(self, result: Any) -> None:
        if not isinstance(result, dict):
            return
        # Ignore a stale result if the user moved on to another topic.
        if result.get("topic_id") != self._current_topic_id:
            return
        review = result.get("review") or {}
        self._fill_req_tree(review.get("requirements") or [])
        document = (result.get("document") or {}).get("document") or ""
        self._doc_view.setMarkdown(document)
        self._fill_signoffs(result.get("signoffs") or [])

    # -- Requirement tree ----------------------------------------------------

    def _fill_req_tree(self, roots: list[dict[str, Any]]) -> None:
        self._req_tree.clear()
        for node in roots:
            self._req_tree.addTopLevelItem(self._make_req_item(node))
        self._req_tree.expandAll()
        self._detail_scroll.setWidget(
            self._placeholder("Select a requirement to see its detail.")
        )

    def _make_req_item(self, node: dict[str, Any]) -> QTreeWidgetItem:
        ident = node.get("identifier") or ""
        name = node.get("name") or ""
        item = QTreeWidgetItem(
            [f"{ident} · {name}", node.get("status") or "", self._flags_text(node)]
        )
        item.setData(0, _NODE_ROLE, node)
        for child in node.get("children") or []:
            item.addChild(self._make_req_item(child))
        return item

    @staticmethod
    def _flags_text(node: dict[str, Any]) -> str:
        flags = []
        if node.get("review_state") == "needs_review":
            flags.append("NEEDS REVIEW")
        confirmed = node.get("status") == "confirmed"
        if confirmed and not node.get("planned"):
            flags.append("unbuilt")
        if confirmed and not node.get("verified"):
            flags.append("unverified")
        return " · ".join(flags)

    def _on_req_selected(self, current: QTreeWidgetItem, _previous) -> None:
        if current is None:
            self._detail_scroll.setWidget(
                self._placeholder("Select a requirement to see its detail.")
            )
            return
        node = current.data(0, _NODE_ROLE)
        if not isinstance(node, dict):
            return
        self._detail_scroll.setWidget(self._render_req_detail(node))

    def _render_req_detail(self, node: dict[str, Any]) -> QWidget:
        host = QWidget()
        v = QVBoxLayout(host)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        ident = node.get("identifier") or ""
        v.addWidget(heading_label(f"{ident} — {node.get('name') or ''}"))

        if node.get("review_state") == "needs_review":
            badge = QLabel("⚠ NEEDS REVIEW")
            badge.setStyleSheet(_NEEDS_REVIEW_STYLE)
            v.addWidget(badge)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Status", read_only_line(str(node.get("status") or "")))
        form.addRow("Origin", read_only_line(str(node.get("origin") or "—")))
        form.addRow("Priority", read_only_line(str(node.get("priority") or "—")))
        v.addLayout(form)

        v.addWidget(separator())
        v.addWidget(QLabel("<b>Acceptance</b>"))
        v.addWidget(read_only_text(str(node.get("acceptance_summary") or "")))

        v.addWidget(separator())
        v.addWidget(QLabel("<b>Provenance spine</b>"))
        v.addWidget(self._spine_widget(node))

        v.addWidget(separator())
        v.addWidget(QLabel("<b>Defined in conversations</b>"))
        v.addWidget(self._provenance_widget(node))

        v.addStretch(1)
        return host

    def _spine_widget(self, node: dict[str, Any]) -> QWidget:
        # defined: present (the requirement exists). planned/verified: from
        # the node flags. decided/specified/developed: unknown for now.
        marks = {
            "defined": "✓",
            "decided": "?",
            "specified": "?",
            "planned": "✓" if node.get("planned") else "✗",
            "developed": "?",
            "verified": "✓" if node.get("verified") else "✗",
        }
        text = "  →  ".join(f"{stage} {marks[stage]}" for stage in _SPINE_STAGES)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setStyleSheet(_FLAG_STYLE)
        return label

    def _provenance_widget(self, node: dict[str, Any]) -> QWidget:
        container = QWidget()
        v = QVBoxLayout(container)
        v.setContentsMargins(0, 0, 0, 0)
        convs = node.get("defined_in_conversations") or []
        if not convs:
            empty = QLabel("No defining conversation recorded.")
            empty.setStyleSheet("color: #888;")
            v.addWidget(empty)
            return container
        for cid in convs:
            btn = QPushButton(f"Trace → {cid}")
            btn.setToolTip("Fetch and show the conversation that defined this requirement")
            btn.clicked.connect(partial(self._open_conversation, cid))
            v.addWidget(btn)
        return container

    # -- Queues --------------------------------------------------------------

    def _fill_approval(self, rows: list[dict[str, Any]]) -> None:
        self._approval_tree.clear()
        for r in rows:
            QTreeWidgetItem(
                self._approval_tree,
                [
                    r.get("identifier") or "",
                    r.get("name") or "",
                    str(r.get("origin") or "—"),
                    "yes" if r.get("has_provenance") else "MISSING",
                    "yes" if r.get("has_topic") else "MISSING",
                ],
            )
        self._tab_count("Approval", len(rows))

    def _fill_drift(self, rows: list[dict[str, Any]]) -> None:
        self._drift_tree.clear()
        for r in rows:
            QTreeWidgetItem(
                self._drift_tree,
                [
                    r.get("identifier") or "",
                    r.get("name") or "",
                    str(r.get("status") or ""),
                    str(r.get("origin") or "—"),
                ],
            )
        self._tab_count("Drift", len(rows))

    def _fill_coverage(self, coverage: dict[str, Any]) -> None:
        self._coverage_tree.clear()
        summary = coverage.get("summary") or {}
        self._coverage_summary.setText(
            f"Orphan planning items: {summary.get('orphan_planning_items', 0)}  ·  "
            f"Unbuilt requirements: {summary.get('unbuilt_requirements', 0)}  ·  "
            f"Conversations without a requirement: "
            f"{summary.get('conversations_without_requirement', 0)}"
        )

        def _group(title: str, rows: list[dict[str, Any]], id_key: str, detail_keys):
            parent = QTreeWidgetItem(self._coverage_tree, [f"{title} ({len(rows)})", ""])
            parent.setExpanded(True)
            for r in rows:
                detail = " · ".join(
                    str(r.get(k)) for k in detail_keys if r.get(k) is not None
                )
                QTreeWidgetItem(parent, [str(r.get(id_key) or ""), detail])

        _group(
            "Orphan planning items",
            coverage.get("orphan_planning_items") or [],
            "identifier",
            ("title", "item_type", "status"),
        )
        _group(
            "Unbuilt requirements",
            coverage.get("unbuilt_requirements") or [],
            "requirement_identifier",
            ("requirement_name", "requirement_status"),
        )
        _group(
            "Conversations without a requirement",
            coverage.get("conversations_without_requirement") or [],
            "conversation_identifier",
            ("conversation_title", "conversation_status"),
        )
        total = sum(summary.values()) if summary else 0
        self._tab_count("Coverage gaps", total)

    def _tab_count(self, base_label: str, count: int) -> None:
        """Annotate a queue tab's title with its row count."""
        for i in range(self._tabs.count()):
            if self._tabs.tabText(i).split(" (")[0] == base_label:
                self._tabs.setTabText(i, f"{base_label} ({count})")
                return

    # -- Sign-off ------------------------------------------------------------

    def _fill_signoffs(self, rows: list[dict[str, Any]]) -> None:
        self._signoff_list.clear()
        if not rows:
            self._signoff_list.addItem("No sign-offs recorded for this topic.")
            return
        for r in rows:
            when = format_timestamp(r.get("signoff_created_at"))
            reviewer = r.get("signoff_reviewer") or "?"
            attestation = r.get("signoff_attestation") or ""
            self._signoff_list.addItem(f"{when} · {reviewer} — {attestation}")

    def _on_record_signoff(self) -> None:
        if not self._current_topic_id:
            self._status_label.setText("Select a topic before signing off.")
            return
        dialog = _SignoffDialog(self._current_topic_id, parent=self)
        self._dialogs.append(dialog)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                reviewer, attestation = dialog.values()
                self._submit_signoff(self._current_topic_id, reviewer, attestation)
        finally:
            self._dialogs.remove(dialog)
            dialog.deleteLater()

    def _submit_signoff(self, topic_id: str, reviewer: str, attestation: str) -> None:
        body = {
            "signoff_topic_identifier": topic_id,
            "signoff_reviewer": reviewer,
            "signoff_attestation": attestation,
        }

        def _on_done(_result: Any) -> None:
            self._status_label.setText("Sign-off recorded.")
            if self._current_topic_id:
                self._load_topic(self._current_topic_id)

        self._run(
            lambda: self._client.create_signoff(body),
            on_success=_on_done,
            on_error=self._on_error,
        )

    # -- Provenance conversation dialog --------------------------------------

    def _open_conversation(self, conv_id: str) -> None:
        self._status_label.setText(f"Loading {conv_id}…")
        self._run(
            lambda cid=conv_id: self._client.get_conversation(cid),
            on_success=self._show_conversation,
            on_error=self._on_error,
        )

    def _show_conversation(self, conv: Any) -> None:
        if not isinstance(conv, dict):
            return
        self._status_label.setText("")
        dialog = _ConversationDialog(conv, parent=self)
        dialog.open_in_panel.connect(self._on_open_conversation_in_panel)
        self._dialogs.append(dialog)
        try:
            dialog.exec()
        finally:
            self._dialogs.remove(dialog)
            dialog.deleteLater()

    def _on_open_conversation_in_panel(self, conv_id: str) -> None:
        # Route to the Conversations panel via the main window's nav router.
        self.navigate_requested.emit("conversation", conv_id)

    # -- Worker plumbing -----------------------------------------------------

    def _run(self, fn, *, on_success, on_error) -> None:
        worker = run_in_thread(fn, on_success=on_success, on_error=on_error, parent=self)
        # Reuse the base class's in-flight list so ``drain_workers`` waits on
        # these on teardown; drop each from the list when it finishes.
        self._in_flight_workers.append(worker)
        worker.finished.connect(lambda w=worker: self._drop_worker(w))

    def _drop_worker(self, worker) -> None:
        try:
            self._in_flight_workers.remove(worker)
        except ValueError:
            pass

    def _on_error(self, exc: Exception) -> None:
        if isinstance(exc, StorageConnectionError):
            _log.warning("Connection lost during review fetch: %s", exc)
            self._status_label.setText("Connection lost")
            self.connection_lost.emit(str(exc))
            return
        if isinstance(exc, StorageClientError):
            _log.warning("Domain error during review fetch: %s", exc)
            self._status_label.setText(f"Error: {exc.message}")
            return
        _log.exception("Unexpected error during review fetch", exc_info=exc)
        self._status_label.setText(f"Error: {exc!s}")


class _SignoffDialog(QDialog):
    """Modal capturing reviewer + attestation for a topic sign-off."""

    def __init__(self, topic_id: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Sign off — {topic_id}")
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"Recording a review sign-off for topic <b>{topic_id}</b>.<br>"
                "The server snapshots the topic's current requirement set."
            )
        )
        form = QFormLayout()
        self._reviewer = QLineEdit()
        self._reviewer.setPlaceholderText("Your name")
        form.addRow("Reviewer", self._reviewer)
        self._attestation = QPlainTextEdit()
        self._attestation.setPlaceholderText(
            "What you reviewed and what you are attesting to."
        )
        self._attestation.setMinimumHeight(100)
        form.addRow("Attestation", self._attestation)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setText("Record sign-off")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._refresh_ok_state()
        self._reviewer.textChanged.connect(self._refresh_ok_state)
        self._attestation.textChanged.connect(self._refresh_ok_state)

    def _refresh_ok_state(self) -> None:
        # Never disable the button (house rule); validate on accept instead.
        pass

    def _on_accept(self) -> None:
        reviewer, attestation = self.values()
        if not reviewer or not attestation:
            # Both fields are required server-side; nudge inline rather than
            # round-tripping a 422.
            self.setWindowTitle("Reviewer and attestation are both required")
            return
        self.accept()

    def values(self) -> tuple[str, str]:
        return (
            self._reviewer.text().strip(),
            self._attestation.toPlainText().strip(),
        )


class _ConversationDialog(QDialog):
    """Read-only view of the conversation that defined a requirement."""

    open_in_panel = Signal(str)

    def __init__(self, conv: dict[str, Any], parent=None):
        super().__init__(parent)
        ident = conv.get("conversation_identifier") or "conversation"
        self.setWindowTitle(f"Defining conversation — {ident}")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)

        layout.addWidget(heading_label(conv.get("conversation_title") or ident))
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Identifier", read_only_line(ident))
        form.addRow("Status", read_only_line(str(conv.get("conversation_status") or "")))
        layout.addLayout(form)

        summary = conv.get("conversation_summary") or conv.get("conversation_description")
        layout.addWidget(QLabel("<b>Summary</b>"))
        layout.addWidget(read_only_text(str(summary or "")))

        buttons = QDialogButtonBox()
        open_btn = QPushButton("Open in Conversations panel")
        open_btn.clicked.connect(lambda: self._emit_open(ident))
        buttons.addButton(open_btn, QDialogButtonBox.ButtonRole.ActionRole)
        close_btn = buttons.addButton(QDialogButtonBox.StandardButton.Close)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)

    def _emit_open(self, ident: str) -> None:
        self.open_in_panel.emit(ident)
        self.accept()
