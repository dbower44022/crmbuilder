"""Modal-only elevation per design pass §1.5 (DEC-091).

The rest of the app stays flat on one z-plane; modals are meant to get
exactly one elevation treatment. The ``shadow.dialog`` token in
:mod:`crmbuilder_v2.ui.styling` documents the intended effect parameters.

Implementation note: the original implementation called
``dialog.setGraphicsEffect(QGraphicsDropShadowEffect(...))`` on the
top-level dialog. ``QGraphicsEffect`` cannot be used on a top-level
window — Qt rasterizes the effect through an offscreen pixmap and the
window's surrounding surface fills opaque black, so the dialog renders
with a black background and the (dark) stylesheet text becomes
unreadable. This reproduces reliably on X11/Linux. The drop shadow for
an OS-level modal window is the window manager's job, not Qt's graphics
effect framework, so we no longer apply a graphics effect here and let
the native WM draw the modal's shadow.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget


def apply_dialog_shadow(dialog: QWidget) -> None:  # noqa: ARG001
    """No-op: native window-manager shadow is used for top-level modals.

    Kept as a stable hook so call sites need not change. Applying a
    ``QGraphicsDropShadowEffect`` to a top-level dialog paints the whole
    window black on X11/Linux, so no graphics effect is set here.
    """
    return
