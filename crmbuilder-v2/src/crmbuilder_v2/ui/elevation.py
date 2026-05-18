"""Modal-only elevation per design pass §1.5 (DEC-091).

The rest of the app stays flat on one z-plane; modals get exactly one
elevation treatment via Qt's built-in ``QGraphicsDropShadowEffect``.

The ``shadow.dialog`` token in :mod:`crmbuilder_v2.ui.styling` documents
the effect parameters (offset, blur, color, alpha); this module reads
them as concrete values rather than re-parsing the token string so the
effect parameters remain authoritative in one place.
"""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QWidget

_SHADOW_OFFSET_X = 0
_SHADOW_OFFSET_Y = 4
_SHADOW_BLUR_RADIUS = 16
# color.neutral.900 at 25% alpha — token shadow.dialog
_SHADOW_COLOR = QColor(15, 19, 24, 64)


def apply_dialog_shadow(dialog: QWidget) -> None:
    """Apply the design system's modal drop shadow to ``dialog``."""
    effect = QGraphicsDropShadowEffect(dialog)
    effect.setOffset(_SHADOW_OFFSET_X, _SHADOW_OFFSET_Y)
    effect.setBlurRadius(_SHADOW_BLUR_RADIUS)
    effect.setColor(_SHADOW_COLOR)
    dialog.setGraphicsEffect(effect)
