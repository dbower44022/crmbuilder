"""ReferencesSection — uniform inbound/outbound references rendering.

Pure rendering widget; takes a pre-fetched references payload (the
shape returned by ``StorageClient.list_references_touching``) and lays
out grouped sections. Click any reference link, the widget emits
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

v0.6 slice C rewrite (DEC-107). The previous two-level (direction →
relationship type) grouping is replaced with per-(direction, type)
kind-labeled sub-sections per the design pass §2.4. ``_KIND_LABELS``
maps ``(direction, relationship)`` tuples to title-case headers like
"Decided in", "Supersedes", "Superseded by", "Hands off to". Unmapped
kinds fall through to a humanized fallback derived from the
relationship token.

Constructor parameters ``inbound_label`` and ``outbound_label`` are
**vestigial** in the new model — the direction sub-headings they
previously customized are gone — but the args remain on the
constructor for back-compat so existing panels (notably ``processes``)
import without change. Added in v2-ui-v0.2-A per DEC-031. v0.3 slice C
added the ``Add reference`` button + per-row right-click menu.
"""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.styling import t
from crmbuilder_v2.ui.widgets.form_helpers import text_link_button


# (direction, relationship) → human-readable sub-section header.
# Direction is "inbound" (the record is the target) or "outbound" (the
# record is the source). Unmapped kinds fall through to
# :func:`_default_kind_label` so future vocab additions still render.
_KIND_LABELS: dict[tuple[str, str], str] = {
    # Generic kinds — directional human labels per design pass §2.4.
    ("outbound", "is_about"): "Is about",
    ("inbound", "is_about"): "Cited by",
    ("outbound", "references"): "References",
    ("inbound", "references"): "Referenced by",
    # Decisions — the most-used set.
    ("inbound", "decided_in"): "Decided in",
    ("outbound", "decided_in"): "Decides",
    ("outbound", "supersedes"): "Supersedes",
    ("inbound", "supersedes"): "Superseded by",
    # Risks / planning_items.
    ("outbound", "affects"): "Affects",
    ("inbound", "affects"): "Affected by",
    # v0.8: legacy ``blocks`` kind retired; replaced by directed
    # ``blocked_by`` (planning_item → planning_item) per methodology §3.4.
    ("outbound", "blocked_by"): "Blocked by",
    ("inbound", "blocked_by"): "Blocks",
    # Charter / status coverage.
    ("outbound", "covers"): "Covers",
    ("inbound", "covers"): "Covered by",
    # Methodology entities (v0.4).
    ("outbound", "entity_scopes_to_domain"): "Scopes to",
    ("inbound", "entity_scopes_to_domain"): "Scoped by",
    ("outbound", "process_hands_off_to_process"): "Hands off to",
    ("inbound", "process_hands_off_to_process"): "Receives from",
    # v0.8 Code Change Lifecycle additions (methodology §3.2–§3.3).
    ("outbound", "resolves"): "Resolves",
    ("inbound", "resolves"): "Resolved by",
    ("outbound", "addresses"): "Addresses",
    ("inbound", "addresses"): "Addressed by",
}


def _default_kind_label(direction: str, relationship: str) -> str:
    """Fallback label for an unmapped (direction, relationship) pair."""
    pretty = relationship.replace("_", " ")
    if direction == "outbound":
        return pretty[:1].upper() + pretty[1:]
    return f"{pretty.title()} (inbound)"


def _pretty_entity_type(entity_type: str) -> str:
    return entity_type.replace("_", " ").title()


class ReferencesSection(QWidget):
    """Renders inbound and outbound references for an entity record.

    The widget is a pure renderer: it takes a pre-fetched payload and
    lays out the section. Reference fetching itself happens on the
    panel level via ``fetch_detail_extras`` (consistent with v0.1's
    threading pattern).

    v0.6 slice C: the rendering switches to a flat sequence of
    kind-labeled sub-sections (one per (direction, relationship)
    bucket). The two top-level direction sections are removed; the
    ``inbound_label`` / ``outbound_label`` constructor args are kept
    but ignored at render time — they remain to preserve the v0.4
    constructor signature for the processes panel.
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
        inbound_label: str = "Inbound",  # noqa: ARG002 — vestigial; kept for back-compat
        outbound_label: str = "Outbound",  # noqa: ARG002 — vestigial; kept for back-compat
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._entity_type = entity_type
        self._identifier = identifier
        self._exclude = set(exclude_relationships or set())
        self._client = client
        # ``inbound_label`` / ``outbound_label`` are accepted to preserve
        # the v0.4 constructor signature but are not consumed by the
        # v0.6 sub-sectioned renderer. The two former direction headers
        # they customized no longer exist.
        self._build(references_payload or {})

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build(self, payload: dict[str, Any]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(t("space.2").rstrip("px")))

        layout.addWidget(self._heading("References"))

        # Flatten (direction, relationship, ref) tuples, honoring the
        # exclude filter and dropping unknown directions defensively.
        flat: list[tuple[str, str, dict[str, Any]]] = []
        for ref in payload.get("as_target") or []:
            rel = ref.get("relationship") or "?"
            if rel in self._exclude:
                continue
            flat.append(("inbound", rel, ref))
        for ref in payload.get("as_source") or []:
            rel = ref.get("relationship") or "?"
            if rel in self._exclude:
                continue
            flat.append(("outbound", rel, ref))

        if not flat:
            layout.addWidget(self._dim_label("(none)"))
            self._add_button_row(layout)
            return

        # Bucket by (direction, relationship); insertion order drives
        # display order so inbound buckets render before outbound ones
        # for a given relationship token, matching the v0.5 visual flow.
        buckets: "OrderedDict[tuple[str, str], list[dict[str, Any]]]" = (
            OrderedDict()
        )
        for direction, rel, ref in flat:
            key = (direction, rel)
            buckets.setdefault(key, []).append(ref)

        section_gap = int(t("space.4").rstrip("px"))
        for index, ((direction, rel), rows) in enumerate(buckets.items()):
            if index > 0:
                layout.addSpacing(section_gap)
            header_text = _KIND_LABELS.get(
                (direction, rel), _default_kind_label(direction, rel)
            )
            layout.addWidget(self._kind_header(header_text))
            for ref in rows:
                if direction == "inbound":
                    other_type = ref.get("source_type") or ""
                    other_id = ref.get("source_id") or ""
                else:
                    other_type = ref.get("target_type") or ""
                    other_id = ref.get("target_id") or ""
                layout.addWidget(
                    self._entry_row(other_type, other_id, ref)
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
        layout.addSpacing(int(t("space.3").rstrip("px")))
        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(int(t("space.2").rstrip("px")))
        # v0.6 slice D: Text/Link category per design pass §2.5. The
        # slice-C inline ``setStyleSheet`` block is gone — all chrome
        # is now in ``build_app_stylesheet`` keyed off
        # ``buttonCategory="text"``.
        self._add_button = text_link_button("Add reference", icon_name="plus")
        self._add_button.setObjectName("references_section_add_button")
        self._add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add_button.clicked.connect(self._on_add_clicked)
        button_row.addWidget(self._add_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)

    def _heading(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("references_section_heading")
        label.setStyleSheet(
            f"font-size: {t('font.size.body_large')};"
            f" font-weight: {t('font.weight.semibold')};"
            f" color: {t('color.neutral.800')};"
        )
        return label

    def _kind_header(self, text: str) -> QLabel:
        """Sub-section header for one (direction, relationship) bucket.

        Tagged with ``role="references-kind-header"`` so the global QSS
        rule in :func:`build_app_stylesheet` styles it without
        per-widget setStyleSheet calls.
        """
        label = QLabel(text)
        label.setProperty("role", "references-kind-header")
        # Set inline styling too — Qt's QSS property-selector lookup
        # can lag in some build environments, and the inline values
        # below match the QSS rule character-for-character so there's
        # no visual difference if both apply.
        label.setStyleSheet(
            f"font-size: {t('font.size.small')};"
            f" font-weight: {t('font.weight.semibold')};"
            f" color: {t('color.neutral.700')};"
        )
        return label

    def _entry_row(
        self, entity_type: str, identifier: str, ref: dict[str, Any]
    ) -> QLabel:
        """Render one reference entry — identifier (mono) + entity type.

        Design pass §2.4: identifier rendered in mono font at
        ``font.size.small`` ``color.neutral.700``, then ``space.3`` of
        horizontal gap, then the pretty type label in ``font.size.body``
        ``color.neutral.800``. Both pieces sit inside the same rich-text
        QLabel so the entire row carries a single ``<a href>`` for
        click-to-navigate.

        Hover tint is delivered via inline QSS — Qt has no
        ``:hover`` rule that applies inside a single label, so the
        whole label background lifts to ``color.neutral.50`` on hover.
        """
        href = f"{entity_type}:{identifier}"
        pretty_type = _pretty_entity_type(entity_type)
        # Outer link spans the whole row; inner spans set the per-piece
        # font. Identifier first (mono), then a gap, then the pretty
        # type label.
        html = (
            f'<a href="{href}" style="text-decoration: none;">'
            f'<span style="font-family: {t("font.family.mono")};'
            f' font-size: {t("font.size.small")};'
            f' color: {t("color.neutral.700")};">{identifier}</span>'
            f'&nbsp;&nbsp;'
            f'<span style="font-size: {t("font.size.body")};'
            f' color: {t("color.neutral.800")};">{pretty_type}</span>'
            f'</a>'
        )
        label = QLabel(html)
        label.setProperty("role", "references-entry")
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        label.setOpenExternalLinks(False)
        # Hover tint on the row background; inline styling so it
        # doesn't fight QSS specificity.
        label.setStyleSheet(
            f"QLabel {{ padding: {t('space.1')} {t('space.2')}; }}"
            f" QLabel:hover {{ background: {t('color.neutral.50')}; }}"
        )
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
        label.setStyleSheet(f"color: {t('color.neutral.500')};")
        return label

    def _on_link_activated(self, href: str) -> None:
        if ":" not in href:
            return
        entity_type, _, identifier = href.partition(":")
        if not entity_type or not identifier:
            return
        self.navigate_requested.emit(entity_type, identifier)
