"""UI test fixtures.

Forces the offscreen Qt platform plugin so headless test runs (CI,
plain shells with no display) don't hang on a missing X server. Set
before any pytest-qt fixture imports a QApplication. ``qapp`` and
``qtbot`` themselves come from pytest-qt and are picked up
automatically without re-export.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
