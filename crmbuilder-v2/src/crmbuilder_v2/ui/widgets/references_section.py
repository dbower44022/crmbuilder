"""ReferencesSection — uniform inbound/outbound references rendering.

Pure rendering widget; takes a pre-fetched references payload (the
shape returned by ``StorageClient.list_references_touching``) and lays
out two grouped sections (Inbound, Outbound), each grouped by
relationship type with a count header. Empty sections render
``(none)``. Click any reference link, the widget emits
``navigate_requested(entity_type, identifier)``.

Why pre-fetched data instead of widget-side fetching: v0.1's panel
architecture already fetches references in ``fetch_detail_extras`` on a
worker thread; threading that result through ``render_detail`` keeps
the existing master/detail data flow intact and avoids a second async
fetch per detail-pane render.

Constructor parameter ``exclude_relationships`` filters out specific
relationship types from the rendered output. The DecisionsPanel passes
``{"supersedes"}`` to suppress the outbound supersedes reference, which
is already shown as a top-level Supersedes/Superseded By field on the
detail pane.

Constructor parameters ``inbound_label`` and ``outbound_label`` rename
the two direction sub-headings. They default to ``"Inbound"`` /
``"Outbound"`` (every v0.2/v0.3 caller's behavior is unchanged); the
v0.4 Processes panel passes ``"Receives from"`` / ``"Hands off to"`` so
the directional ``process_hands_off_to_process`` edges read in the
methodology's own language.

Added in v2-ui-v0.2-A per DEC-031. v0.3 slice C extends with an
``Add reference`` button (visible when a ``StorageClient`` is supplied)
and a per-row right-click context menu offering ``Delete reference``
and ``Go to [other side]``. Successful writes emit
``references_changed`` so the host panel can refresh.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient

_SECTION_HEADER_POINT_BUMP = 1


class ReferencesSection(QWidget):
    """Renders inbound and outbound references for an entity record.

    The widget is a pure renderer: it takes a pre-fetched payload and
    lays out the section. Reference fetching itself happens on the
    panel level via ``fetch_detail_extras`` (consistent with v0.1's
    threading pattern).
    """

    navigate_requested = Signal(str, str)
    # Emitted after a successful add or delete inside the section so
    # the host panel can ``refresh()`` the master view (which re-runs
    # ``fetch_detail_extras`` and re-renders this section). v0.3
    # slice C — DEC-033.
    references_changed = Signal()

    def __init__(
        self,
        entity_type: str,
        identifier: str,
        references_payload: dict[str, Any] | None,
        *,
        exclude_relationships: set[str] | None = None,
        client: StorageClient | None = None,
        inbound_label: str = "Inbound",
        outbound_label: str = "Outbound",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entity_type = entity_type
        self._identifier = identifier
        self._exclude = set(exclude_relationships or set())
        self._client = client
        self._inbound_label = inbound_label
        self._outbound_label = outbound_label
        self._build(references_payload or {})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build(self, payload: dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._heading("References"))

        as_target = list(payload.get("as_target") or [])
        as_source = list(payload.get("as_source") or [])

        inbound = self._group(as_target, key="source")
        outbound = self._group(as_source, key="target")

        inbound_count = sum(len(rows) for rows in inbound.values())
        outbound_count = sum(len(rows) for rows in outbound.values())

        if inbound_count == 0 and outbound_count == 0:
            layout.addWidget(self._dim_label("(none)"))
            self._add_button_row(layout)
            return

        layout.addSpacing(4)
        layout.addWidget(
            self._sub_heading(f"{self._inbound_label} ({inbound_count})")
        )
        if inbound_count == 0:
            layout.addWidget(self._dim_label("(none)"))
        else:
            for relationship in sorted(inbound):
                rows = inbound[relationship]
                layout.addWidget(self._relationship_label(relationship, len(rows)))
                for ref in rows:
                    layout.addWidget(
                        self._link_label(
                            ref["source_type"], ref["source_id"], ref
                        )
                    )

        layout.addSpacing(4)
        layout.addWidget(
            self._sub_heading(f"{self._outbound_label} ({outbound_count})")
        )
        if outbound_count == 0:
            layout.addWidget(self._dim_label("(none)"))
        else:
            for relationship in sorted(outbound):
                rows = outbound[relationship]
                layout.addWidget(self._relationship_label(relationship, len(rows)))
                for ref in rows:
                    layout.addWidget(
                        self._link_label(
                            ref["target_type"], ref["target_id"], ref
                        )
                    )

        self._add_button_row(layout)

    def _add_button_row(self, layout: QVBoxLayout) -> None:
        """Append the ``Add reference`` button row at the section bottom.

        Only rendered when a ``StorageClient`` was supplied to the
        constructor (otherwise the section is read-only, preserving
        v0.2 callers that pre-date the v0.3 write surface).
        """
        if self._client is None:
            return
        layout.addSpacing(6)
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        self._add_button = QPushButton("Add reference")
        self._add_button.setObjectName("references_section_add_button")
        self._add_button.clicked.connect(self._on_add_clicked)
        button_row.addWidget(self._add_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

    def _group(
        self, refs: list[dict[str, Any]], *, key: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Group references by relationship, applying the exclude filter."""
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        _ = key  # parameter retained for future use; grouping is by relationship.
        for ref in refs:
            relationship = ref.get("relationship") or "?"
            if relationship in self._exclude:
                continue
            groups[relationship].append(ref)
        return groups

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        font.setPointSize(font.pointSize() + _SECTION_HEADER_POINT_BUMP)
        label.setFont(font)
        return label

    def _sub_heading(self, text: str) -> QLabel:
        label = QLabel(text)
        font = QFont(label.font())
        font.setBold(True)
        label.setFont(font)
        return label

    def _relationship_label(self, relationship: str, count: int) -> QLabel:
        label = QLabel(f"  {relationship} ({count})")
        font = QFont(label.font())
        font.setItalic(True)
        label.setFont(font)
        return label

    def _link_label(
        self, entity_type: str, identifier: str, ref: dict[str, Any]
    ) -> QLabel:
        href = f"{entity_type}:{identifier}"
        pretty_type = entity_type.replace("_", " ").title()
        label = QLabel(f'    <a href="{href}">{pretty_type} {identifier}</a>')
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        label.setOpenExternalLinks(False)
        label.linkActivated.connect(self._on_link_activated)
        # v0.3 slice C — right-click each rendered row for delete + go-to.
        # Only wire the menu when a client is available (i.e. write
        # surfaces are reachable). Without a client, rows stay read-only
        # and respond only to left-click navigation.
        if self._client is not None:
            label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            label.customContextMenuRequested.connect(
                lambda position, lbl=label, r=ref, et=entity_type, ident=identifier:
                self._on_row_context_menu(lbl, position, r, et, ident)
            )
        return label

    # ------------------------------------------------------------------
    # Per-row right-click menu (v0.3 slice C — DEC-033)
    # ------------------------------------------------------------------

    def _on_row_context_menu(
        self,
        row_widget: QLabel,
        position: QPoint,
        reference: dict[str, Any],
        other_side_type: str,
        other_side_id: str,
    ) -> None:
        menu = QMenu(row_widget)
        delete_action = menu.addAction("Delete reference")
        delete_action.triggered.connect(
            lambda _checked=False, r=reference: self._on_delete_clicked(r)
        )
        go_label = f"Go to {other_side_id}"
        go_action = menu.addAction(go_label)
        go_action.triggered.connect(
            lambda _checked=False, et=other_side_type, ident=other_side_id:
            self.navigate_requested.emit(et, ident)
        )
        menu.exec(row_widget.mapToGlobal(position))

    # ------------------------------------------------------------------
    # Add / Delete click handlers
    # ------------------------------------------------------------------

    def _on_add_clicked(self) -> None:
        if self._client is None:
            return
        # Local import keeps the module-level import graph free of a
        # widgets ↔ dialogs cycle.
        from crmbuilder_v2.ui.dialogs.reference_create import (
            ReferenceCreateDialog,
        )

        dialog = ReferenceCreateDialog(
            self._client,
            pre_populated_source=(self._entity_type, self._identifier),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.references_changed.emit()

    def _on_delete_clicked(self, reference: dict[str, Any]) -> None:
        if self._client is None:
            return
        ref_id = reference.get("id")
        if ref_id is None:
            return
        from crmbuilder_v2.ui.dialogs.reference_delete import (
            ReferenceDeleteDialog,
            edge_text,
        )

        dialog = ReferenceDeleteDialog(
            self._client,
            reference_id=int(ref_id),
            edge=edge_text(reference),
            parent=self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.references_changed.emit()

    def _dim_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("color: #888;")
        return label

    def _on_link_activated(self, href: str) -> None:
        if ":" not in href:
            return
        entity_type, _, identifier = href.partition(":")
        if not entity_type or not identifier:
            return
        self.navigate_requested.emit(entity_type, identifier)
