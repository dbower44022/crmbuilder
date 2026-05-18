"""Lucide icon loader with runtime token-driven color tinting.

Per DEC-092 the v2 desktop UI bundles Lucide SVGs as the icon system.
Lucide SVGs render their strokes via ``stroke="currentColor"``; this
loader substitutes the resolved hex from a design token before
rasterizing through ``QSvgRenderer``. The resulting ``QIcon`` is
cached by ``(name, size, color_token)`` since SVG asset files don't
change at runtime.

Public surface is the single ``lucide()`` helper. ``FileNotFoundError``
is raised for unknown icon names so a typo at a call site surfaces
loudly rather than rendering an empty icon.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from crmbuilder_v2.ui.styling import t

_ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons" / "lucide"
_DEFAULT_SIZE = 16
_DEFAULT_COLOR_TOKEN = "color.neutral.700"

_cache: dict[tuple[str, int, str], QIcon] = {}

_CURRENT_COLOR_PATTERN = re.compile(r'currentColor', flags=re.IGNORECASE)


def lucide(
    name: str,
    *,
    size: int = _DEFAULT_SIZE,
    color_token: str = _DEFAULT_COLOR_TOKEN,
) -> QIcon:
    """Return a Lucide icon at ``size`` tinted with the resolved token color.

    ``name`` is the kebab-case Lucide icon name (e.g. ``"trash-2"``,
    ``"chevron-down"``). ``color_token`` is a design-token key
    resolvable via :func:`crmbuilder_v2.ui.styling.t` whose value must
    be a hex color string (``"#RRGGBB"``).
    """
    cache_key = (name, size, color_token)
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached

    svg_path = _ICON_DIR / f"{name}.svg"
    if not svg_path.is_file():
        raise FileNotFoundError(
            f"Lucide icon not bundled: {name!r} "
            f"(looked for {svg_path})"
        )

    color = t(color_token)
    svg_text = svg_path.read_text(encoding="utf-8")
    tinted = _CURRENT_COLOR_PATTERN.sub(color, svg_text)

    renderer = QSvgRenderer(QByteArray(tinted.encode("utf-8")))
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()

    pixmap = QPixmap.fromImage(image)
    icon = QIcon(pixmap)
    _cache[cache_key] = icon
    return icon
