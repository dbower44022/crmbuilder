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

import pytest  # noqa: E402
from crmbuilder_v2.ui.server_lifecycle import ServerLifecycle  # noqa: E402


@pytest.fixture
def lifecycle_stub(qapp):
    """A real ``ServerLifecycle`` aimed at an unreachable URL.

    Slice-B tests that don't exercise lifecycle behavior directly (the
    main-window construction smoke test, panel construction in later
    slices) need a real lifecycle for type compatibility but never
    call ``start()`` on it. Pointing it at port 1 guarantees no
    accidental network call resolves.
    """
    return ServerLifecycle(base_url="http://127.0.0.1:1")
