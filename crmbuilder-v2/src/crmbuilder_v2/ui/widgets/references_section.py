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

Added in v2-ui-v0.2-A per DEC-031.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

_SECTION_HEADER_POINT_BUMP = 1


class ReferencesSection(QWidget):
    """Renders inbound and outbound references for an entity record.

    The widget is a pure renderer: it takes a pre-fetched payload and
    lays out the section. Reference fetching itself happens on the
    panel level via ``fetch_detail_extras`` (consistent with v0.1's
    threading pattern).
    """

    navigate_requested = Signal(str, str)

    def __init__(
        self,
        entity_type: str,
        identifier: str,
        references_payload: dict[str, Any] | None,
        *,
        exclude_relationships: set[str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entity_type = entity_type
        self._identifier = identifier
        self._exclude = set(exclude_relationships or set())
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
            return

        layout.addSpacing(4)
        layout.addWidget(self._sub_heading(f"Inbound ({inbound_count})"))
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
        layout.addWidget(self._sub_heading(f"Outbound ({outbound_count})"))
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
        return label

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
