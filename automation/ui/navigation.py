"""Drill-down navigation stack and breadcrumb logic.

Pure Python — no PySide6 imports. The Qt widget layer consumes
these data structures to render breadcrumbs and manage view history.
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class NavEntry:
    """A single entry in the navigation stack.

    :param label: Human-readable label shown in the breadcrumb.
    :param view_type: Identifier for the view to display (e.g. "dashboard", "work_item").
    :param view_data: Arbitrary data passed to the view constructor (e.g. work_item_id).
    """

    label: str
    view_type: str
    view_data: dict | None = None


class NavigationStack:
    """Manages a drill-down stack of views with breadcrumb support.

    The stack always has at least one entry (the root). Push adds
    a new level, pop removes the top, pop_to_level truncates to
    a specific depth.
    """

    def __init__(self, root: NavEntry) -> None:
        """Initialize with a root entry that cannot be popped.

        :param root: The root navigation entry (e.g. Requirements Dashboard).
        """
        self._stack: list[NavEntry] = [root]

    @property
    def depth(self) -> int:
        """Return the current stack depth."""
        return len(self._stack)

    @property
    def current(self) -> NavEntry:
        """Return the topmost entry."""
        return self._stack[-1]

    @property
    def breadcrumbs(self) -> list[NavEntry]:
        """Return all entries for breadcrumb display."""
        return list(self._stack)

    @property
    def show_breadcrumbs(self) -> bool:
        """Return True if breadcrumbs should be visible (depth > 1)."""
        return len(self._stack) > 1

    def push(self, entry: NavEntry) -> None:
        """Push a new entry onto the stack.

        :param entry: The navigation entry to add.
        """
        self._stack.append(entry)

    def pop(self) -> NavEntry | None:
        """Pop the topmost entry. Returns None if at root.

        :returns: The popped entry, or None if already at root.
        """
        if len(self._stack) <= 1:
            return None
        return self._stack.pop()

    def pop_to_level(self, level: int) -> None:
        """Truncate the stack to the given level (1-based).

        Level 1 means the root only. Level 2 means root + one child.

        :param level: The target depth (must be >= 1 and <= current depth).
        :raises ValueError: If level is out of range.
        """
        if level < 1 or level > len(self._stack):
            raise ValueError(
                f"Level {level} out of range [1, {len(self._stack)}]"
            )
        self._stack = self._stack[:level]

    def reset(self) -> None:
        """Reset to root only, discarding all drill-down state."""
        self._stack = self._stack[:1]


def build_breadcrumb_text(stack: NavigationStack, separator: str = " > ") -> str:
    """Build a breadcrumb string from the navigation stack.

    :param stack: The navigation stack.
    :param separator: Separator between breadcrumb segments.
    :returns: A string like "Requirements Dashboard > Work Item: Contact PRD".
    """
    return separator.join(entry.label for entry in stack.breadcrumbs)
