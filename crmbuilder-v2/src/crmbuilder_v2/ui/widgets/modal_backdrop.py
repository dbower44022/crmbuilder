"""Full-window backdrop overlay for active modals per DEC-091.

When any registered ``QDialog`` is open, a translucent overlay covers
the main window's central widget so the modal foreground is
disambiguated from the underlying panel. Alpha is the
``overlay.modal_backdrop`` token (``color.neutral.900`` at 8%) per
design pass §1.5.

Public surface is three names:

* :class:`ModalBackdropOverlay` — the widget itself. Subclasses
  ``QWidget`` and tracks the central widget's size so the overlay
  remains full-window across main-window resizes.
* :func:`attach` — register a dialog as active; show the overlay if
  it isn't already visible. Fade-in is 150ms via
  ``QPropertyAnimation`` on ``windowOpacity``.
* :func:`detach` — deregister; hide the overlay (with a fade-out)
  when the last active dialog closes.

The overlay is event-transparent (``WA_TransparentForMouseEvents``)
so clicks pass through to the dialog's modal-blocking mechanism, not
the overlay itself.
"""

from __future__ import annotations

import logging
from weakref import WeakSet

from PySide6.QtCore import QEvent, QObject, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QApplication, QDialog, QWidget

_log = logging.getLogger("crmbuilder_v2.ui.widgets.modal_backdrop")

_OVERLAY_COLOR = QColor(15, 19, 24, 20)  # color.neutral.900 at 8% alpha
_FADE_DURATION_MS = 150
_FADE_IN_OPACITY = 1.0
_FADE_OUT_OPACITY = 0.0

_active_dialogs: WeakSet[QDialog] = WeakSet()
_overlay: ModalBackdropOverlay | None = None


class ModalBackdropOverlay(QWidget):
    """Translucent full-window overlay shown while a modal is active."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        # Overlay sits above the panel content but below dialogs (dialogs
        # are top-level windows, so window stacking handles that already).
        self.setWindowOpacity(_FADE_OUT_OPACITY)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(_FADE_DURATION_MS)
        self._fade.finished.connect(self._on_fade_finished)
        self._parent_filter = _ParentResizeFilter(self)
        parent.installEventFilter(self._parent_filter)
        self.resize(parent.size())
        self.hide()

    def paintEvent(self, event) -> None:  # noqa: N802 — Qt naming
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), _OVERLAY_COLOR)
        finally:
            painter.end()

    def fade_in(self) -> None:
        self.raise_()
        self.show()
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(_FADE_IN_OPACITY)
        self._fade.start()

    def fade_out(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(self.windowOpacity())
        self._fade.setEndValue(_FADE_OUT_OPACITY)
        self._fade.start()

    def _on_fade_finished(self) -> None:
        if self.windowOpacity() <= _FADE_OUT_OPACITY:
            self.hide()


class _ParentResizeFilter(QObject):
    """Match the overlay's size to its parent on every parent resize."""

    def __init__(self, overlay: ModalBackdropOverlay) -> None:
        super().__init__(overlay)
        self._overlay = overlay

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 — Qt naming
        if event.type() == QEvent.Type.Resize:
            self._overlay.resize(obj.size())
        return False


def _resolve_overlay_parent() -> QWidget | None:
    """Return the widget the overlay should be parented to.

    Prefers the main window's central widget so the overlay does not
    cover the menu bar or status bar; falls back to the active window
    when the central widget cannot be resolved.
    """
    app = QApplication.instance()
    if app is None:
        return None
    main = app.activeWindow()
    if main is None:
        for widget in app.topLevelWidgets():
            if widget.isVisible():
                main = widget
                break
    if main is None:
        return None
    central = main.centralWidget() if hasattr(main, "centralWidget") else None
    return central or main


def _ensure_overlay() -> ModalBackdropOverlay | None:
    global _overlay
    if _overlay is not None:
        try:
            # If the prior parent has been destroyed (e.g., main window
            # closed during a test teardown) the overlay is also stale.
            _overlay.parent()
            return _overlay
        except RuntimeError:
            _overlay = None
    parent = _resolve_overlay_parent()
    if parent is None:
        _log.debug("modal_backdrop: no resolvable parent; overlay skipped")
        return None
    _overlay = ModalBackdropOverlay(parent)
    return _overlay


def attach(dialog: QDialog) -> None:
    """Register ``dialog`` and show the overlay if not yet visible."""
    _active_dialogs.add(dialog)
    overlay = _ensure_overlay()
    if overlay is None:
        return
    overlay.fade_in()


def detach(dialog: QDialog) -> None:
    """Deregister ``dialog`` and fade the overlay out if no modals remain."""
    _active_dialogs.discard(dialog)
    if _active_dialogs:
        return
    overlay = _overlay
    if overlay is None:
        return
    overlay.fade_out()
