"""WCAG AA contrast verification for the v0.6 design token system.

Per DEC-107, this is a build gate. Failures are not tolerated.
Each text-on-background combination listed in
``styling-design-pass.md`` §4.4 (A9) is checked against the WCAG AA
threshold for its target text size.

WCAG AA thresholds:
- 4.5:1 minimum for normal-size text (<18pt or <14pt bold).
- 3.0:1 minimum for large-size text (>=18pt or >=14pt bold).

The implementation uses a hand-rolled WCAG 2.x contrast formula
(``wcag-contrast-ratio`` is not bundled). Numerically equivalent to
that library's ``rgb()`` helper.
"""

from __future__ import annotations

import pytest

from crmbuilder_v2.ui.styling import TOKENS

_LIGHT = TOKENS["light"]


def _luminance(hex_color: str) -> float:
    """Relative luminance per WCAG 2.x."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def _contrast(hex1: str, hex2: str) -> float:
    """WCAG 2.x contrast ratio between two hex colors."""
    l1, l2 = _luminance(hex1), _luminance(hex2)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


# (text_token, background_token, threshold, description)
_COMBINATIONS = [
    ("color.neutral.800", "color.neutral.0", 4.5, "body text on white"),
    ("color.neutral.500", "color.neutral.0", 4.5, "secondary text on white"),
    (
        "color.neutral.700",
        "color.neutral.100",
        4.5,
        "read-only field text on disabled bg",
    ),
    (
        "color.accent.default",
        "color.neutral.0",
        4.5,
        "accent text on white (text-link buttons)",
    ),
    (
        "color.danger.text",
        "color.neutral.0",
        4.5,
        "danger text on white",
    ),
    (
        "color.warning.default",
        "color.neutral.0",
        4.5,
        "warning text on white",
    ),
    (
        "color.neutral.0",
        "color.accent.default",
        4.5,
        "white on accent (primary button text)",
    ),
    (
        "color.neutral.0",
        "color.danger.default",
        4.5,
        "white on danger (destructive button text, crash banner)",
    ),
]


@pytest.mark.parametrize(
    "text_token,bg_token,threshold,description", _COMBINATIONS
)
def test_wcag_aa_contrast(text_token, bg_token, threshold, description):
    text_color = _LIGHT[text_token]
    bg_color = _LIGHT[bg_token]
    ratio = _contrast(text_color, bg_color)
    assert ratio >= threshold, (
        f"WCAG AA failure: {description} "
        f"({text_token}={text_color} on {bg_token}={bg_color}) "
        f"ratio={ratio:.2f}; required>={threshold}"
    )


def test_contrast_helper_known_values():
    """Sanity check on the contrast formula itself.

    Pure black on pure white is 21:1; an identical color on itself
    is 1:1. If either of these drifts the WCAG checks above are
    unreliable.
    """
    assert _contrast("#000000", "#FFFFFF") == pytest.approx(21.0, abs=0.01)
    assert _contrast("#FFFFFF", "#FFFFFF") == pytest.approx(1.0, abs=0.001)
