"""Helpers for mode switching with context preservation (Section 14.9.2).

Pure Python — no PySide6 imports.
"""

from __future__ import annotations


def should_auto_select_on_mode_change(
    target_mode: str,
    has_current_selection: bool,
) -> bool:
    """Determine whether auto-selection should occur on mode change.

    Auto-selection only happens when there is a current selection in the
    source mode to match against.

    :param target_mode: The mode being switched to ('deployment' or 'requirements').
    :param has_current_selection: Whether something is currently selected in the source mode.
    :returns: True if auto-selection should be attempted.
    """
    return has_current_selection
