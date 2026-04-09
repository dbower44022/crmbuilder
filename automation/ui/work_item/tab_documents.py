"""Documents tab (Section 14.3.6).

Read-only display of document generation log entries.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from automation.ui.common.staleness_indicators import StalenessIndicator
from automation.ui.work_item.work_item_logic import DocumentRow


class DocumentCard(QWidget):
    """A card for a single document generation entry.

    :param doc: The document data.
    :param parent: Parent widget.
    """

    def __init__(self, doc: DocumentRow, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)

        type_label = QLabel(doc.document_type.replace("_", " ").title())
        type_label.setStyleSheet("font-size: 12px; font-weight: bold;")
        layout.addWidget(type_label)

        mode_label = QLabel(doc.generation_mode.title())
        mode_label.setStyleSheet("font-size: 11px; color: #757575;")
        layout.addWidget(mode_label)

        date_label = QLabel(doc.generated_at[:10] if doc.generated_at else "")
        date_label.setStyleSheet("font-size: 11px; color: #757575;")
        layout.addWidget(date_label)

        layout.addStretch()

        path_label = QLabel(doc.file_path)
        path_label.setStyleSheet("font-size: 11px; color: #757575;")
        layout.addWidget(path_label)

        if doc.git_commit_hash:
            commit_label = QLabel(f"#{doc.git_commit_hash[:7]}")
            commit_label.setStyleSheet("font-size: 10px; color: #9E9E9E;")
            layout.addWidget(commit_label)


class DocumentsTab(QWidget):
    """Tab showing document generation history.

    :param parent: Parent widget.
    """

    navigate_to_documents = Signal(int)  # work_item_id

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._work_item_id: int | None = None

        # Staleness indicator at top
        self._staleness = StalenessIndicator()
        self._layout.addWidget(self._staleness)

        # Generate Document action — navigates to Documents view
        self._gen_btn = QPushButton("Generate Document")
        self._gen_btn.setStyleSheet(
            "QPushButton { background-color: #FFA726; color: white; "
            "border-radius: 4px; padding: 6px 12px; font-size: 12px; } "
            "QPushButton:hover { background-color: #FB8C00; }"
        )
        self._gen_btn.clicked.connect(self._on_generate)
        self._layout.addWidget(self._gen_btn)

        self._docs_container = QWidget()
        self._docs_layout = QVBoxLayout(self._docs_container)
        self._docs_layout.setContentsMargins(0, 0, 0, 0)
        self._layout.addWidget(self._docs_container)

    def _on_generate(self) -> None:
        """Navigate to Documents view scoped to this work item."""
        if self._work_item_id is not None:
            self.navigate_to_documents.emit(self._work_item_id)

    def update_documents(self, docs: list[DocumentRow], is_stale: bool = False, work_item_id: int | None = None) -> None:
        """Refresh the tab with new document data.

        :param docs: Document rows, descending by date.
        :param is_stale: Whether the documents are stale.
        :param work_item_id: The current work item ID.
        """
        if work_item_id is not None:
            self._work_item_id = work_item_id
        self._staleness.set_stale(is_stale)

        while self._docs_layout.count():
            child = self._docs_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if docs:
            for doc in docs:
                card = DocumentCard(doc)
                self._docs_layout.addWidget(card)
        else:
            empty = QLabel("No documents generated")
            empty.setStyleSheet("color: #757575; padding: 12px;")
            self._docs_layout.addWidget(empty)

        self._docs_layout.addStretch()
