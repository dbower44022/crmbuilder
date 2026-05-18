"""Form-construction helpers shared across panels and dialogs.

Slice C (v0.6) introduces two widgets that the panel detail-pane
builders and the ``EntityCrudDialog`` base both consume:

* :func:`required_label` — builds a composite QWidget pairing a small
  Lucide ``asterisk`` icon in ``color.danger.text`` with the field
  label text. Use as the first arg to ``QFormLayout.addRow`` for any
  required field; the asterisk marks the requirement per design pass
  §2.4.
* :class:`CollapsibleSection` — a chevron + label toggle row plus the
  hidden/visible content widget beneath. Used by the Domains, Entities,
  Processes, and CRM Candidates panels to render the "Internal notes"
  collapsible field per design pass §2.4. Replaces a flat
  ``QToolButton`` with the new tokenized chevron + label treatment.

Both helpers depend on the Lucide icon loader and the design tokens; the
icons are tinted to the right hex color at lookup time.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from crmbuilder_v2.ui.icons import lucide
from crmbuilder_v2.ui.styling import t

_ASTERISK_SIZE = 10
_CHEVRON_SIZE = 14


def required_label(text: str) -> QWidget:
    """Build a form-row label widget prefixed with a required-field asterisk.

    Returns a composite ``QWidget`` containing a 10px Lucide
    ``asterisk`` icon in ``color.danger.text`` followed by the label
    text. The widget is suitable as the first argument to
    ``QFormLayout.addRow`` — ``QFormLayout`` accepts a ``QWidget`` in
    place of the auto-created label.

    Per design pass §2.4 the asterisk is small, danger-toned, and sits
    immediately to the left of the field label. Tag the inner text
    QLabel with ``role="form-label"`` so the global QSS in
    :func:`build_app_stylesheet` can pick up the design-pass treatment
    (small, medium-weight, neutral.700) without per-widget styling.
    """
    container = QWidget()
    container.setObjectName("requiredFieldLabel")
    container.setSizePolicy(
        QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
    )
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(int(t("space.1").rstrip("px")))

    asterisk = QLabel()
    asterisk.setObjectName("requiredFieldAsterisk")
    asterisk.setPixmap(
        lucide(
            "asterisk",
            size=_ASTERISK_SIZE,
            color_token="color.danger.text",
        ).pixmap(QSize(_ASTERISK_SIZE, _ASTERISK_SIZE))
    )
    asterisk.setAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    asterisk.setFixedSize(_ASTERISK_SIZE, _ASTERISK_SIZE + 2)
    layout.addWidget(asterisk)

    text_label = QLabel(text)
    text_label.setObjectName("requiredFieldText")
    text_label.setProperty("role", "form-label")
    text_label.setAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    layout.addWidget(text_label, stretch=1)

    return container


class _CollapsibleHeader(QWidget):
    """Clickable header row for :class:`CollapsibleSection`.

    A small composite widget with a chevron icon and a label. Clicking
    anywhere in the row toggles the parent section. Built as a
    standalone QWidget so the parent section can install an event
    filter on the same widget to subscribe to mouse-press events.
    """

    def __init__(
        self,
        title: str,
        *,
        on_clicked,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_clicked = on_clicked
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(int(t("space.2").rstrip("px")))

        self._chevron = QLabel()
        self._chevron.setObjectName("collapsibleChevron")
        self._chevron.setFixedSize(_CHEVRON_SIZE, _CHEVRON_SIZE + 2)
        self._chevron.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        layout.addWidget(self._chevron)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("collapsibleTitle")
        self._title_label.setStyleSheet(
            f"font-size: {t('font.size.small')};"
            f" font-weight: {t('font.weight.medium')};"
            f" color: {t('color.neutral.700')};"
        )
        layout.addWidget(self._title_label, stretch=1)

    def set_expanded(self, expanded: bool) -> None:
        name = "chevron-down" if expanded else "chevron-right"
        self._chevron.setPixmap(
            lucide(name, size=_CHEVRON_SIZE, color_token="color.neutral.700")
            .pixmap(QSize(_CHEVRON_SIZE, _CHEVRON_SIZE))
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_clicked()
            event.accept()
            return
        super().mousePressEvent(event)


class CollapsibleSection(QWidget):
    """Chevron-toggled section per design pass §2.4.

    Replaces the v0.5 flat ``QToolButton`` notes toggle. The header row
    shows a Lucide chevron (right when collapsed, down when expanded)
    plus the title label; clicking anywhere on the header expands or
    collapses the supplied content widget below it. The content sits
    8px below the header (``space.2``) when expanded.

    Construction:

    >>> section = CollapsibleSection("Internal notes", content_widget)
    >>> section.setObjectName("entity_notes_section")  # for tests

    The content widget is parented to this section. ``set_expanded``
    is exposed so panels can toggle externally if needed.
    """

    def __init__(
        self,
        title: str,
        content: QWidget,
        *,
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._expanded = expanded
        self._content = content

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(int(t("space.2").rstrip("px")))

        self._header = _CollapsibleHeader(title, on_clicked=self._toggle)
        outer.addWidget(self._header)

        content.setParent(self)
        outer.addWidget(content)

        self._apply_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        if expanded == self._expanded:
            return
        self._expanded = expanded
        self._apply_state()

    def content_widget(self) -> QWidget:
        return self._content

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def _apply_state(self) -> None:
        self._header.set_expanded(self._expanded)
        self._content.setVisible(self._expanded)
