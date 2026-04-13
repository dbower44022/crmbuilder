"""Reusable row styling for status-aware list items.

Provides left-edge status stripe, status-tinted background, and hover
highlight for any row widget that displays a status. Derives colors
from the existing STATUS_COLORS palette.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

# Work-item status → (stripe color, row background, hover background)
# Stripe uses the badge foreground; background is a very light tint;
# hover is slightly darker than the background.
_WORK_ITEM_ROW_COLORS: dict[str, dict[str, str]] = {
    "not_started": {"stripe": "#9E9E9E", "bg": "#FAFAFA", "hover": "#F0F0F0"},
    "ready": {"stripe": "#1565C0", "bg": "#F5F9FF", "hover": "#E3F0FF"},
    "in_progress": {"stripe": "#E65100", "bg": "#FFFAF5", "hover": "#FFF0E0"},
    "complete": {"stripe": "#2E7D32", "bg": "#F5FAF5", "hover": "#E5F2E5"},
    "blocked": {"stripe": "#C62828", "bg": "#FFF8F8", "hover": "#FFE8E8"},
}

# Document status → (stripe color, row background, hover background)
_DOCUMENT_ROW_COLORS: dict[str, dict[str, str]] = {
    "stale": {"stripe": "#E65100", "bg": "#FFFAF5", "hover": "#FFF0E0"},
    "current": {"stripe": "#2E7D32", "bg": "#F5FAF5", "hover": "#E5F2E5"},
    "draft_only": {"stripe": "#1565C0", "bg": "#F5F9FF", "hover": "#E3F0FF"},
    "not_generated": {"stripe": "#9E9E9E", "bg": "#FAFAFA", "hover": "#F0F0F0"},
}

# Session import_status → (stripe color, row background, hover background)
_SESSION_ROW_COLORS: dict[str, dict[str, str]] = {
    "pending": {"stripe": "#E65100", "bg": "#FFFAF5", "hover": "#FFF0E0"},
    "imported": {"stripe": "#2E7D32", "bg": "#F5FAF5", "hover": "#E5F2E5"},
    "partial": {"stripe": "#F9A825", "bg": "#FFFDF5", "hover": "#FFF8E1"},
    "rejected": {"stripe": "#C62828", "bg": "#FFF8F8", "hover": "#FFE8E8"},
}

# Impact review status → (stripe color, row background, hover background)
_IMPACT_ROW_COLORS: dict[str, dict[str, str]] = {
    "unreviewed": {"stripe": "#E65100", "bg": "#FFFAF5", "hover": "#FFF0E0"},
    "reviewed": {"stripe": "#2E7D32", "bg": "#F5FAF5", "hover": "#E5F2E5"},
    "flagged": {"stripe": "#C62828", "bg": "#FFF8F8", "hover": "#FFE8E8"},
    "informational": {"stripe": "#9E9E9E", "bg": "#FAFAFA", "hover": "#F0F0F0"},
}


def apply_work_item_row_style(widget: QWidget, status: str) -> None:
    """Apply status row styling to a work-item row widget.

    Sets left-edge stripe, tinted background, hover highlight, and
    bottom border. Enables ``WA_StyledBackground`` so the background
    renders on plain QWidget subclasses.

    :param widget: The row widget to style.
    :param status: Work item status string (not_started, ready, etc.).
    """
    colors = _WORK_ITEM_ROW_COLORS.get(
        status, _WORK_ITEM_ROW_COLORS["not_started"]
    )
    _apply(widget, colors)


def apply_document_row_style(widget: QWidget, document_status: str) -> None:
    """Apply status row styling to a document row widget.

    :param widget: The row widget to style.
    :param document_status: Document status string (stale, current, etc.).
    """
    colors = _DOCUMENT_ROW_COLORS.get(
        document_status, _DOCUMENT_ROW_COLORS["not_generated"]
    )
    _apply(widget, colors)


def apply_session_row_style(widget: QWidget, import_status: str) -> None:
    """Apply status row styling to a session card widget.

    :param widget: The row widget to style.
    :param import_status: Session import status (pending, imported, partial, rejected).
    """
    colors = _SESSION_ROW_COLORS.get(
        import_status, _SESSION_ROW_COLORS["pending"]
    )
    _apply(widget, colors)


def apply_impact_row_style(widget: QWidget, review_key: str) -> None:
    """Apply status row styling to an impact row widget.

    :param widget: The row widget to style.
    :param review_key: One of unreviewed, reviewed, flagged, informational.
    """
    colors = _IMPACT_ROW_COLORS.get(
        review_key, _IMPACT_ROW_COLORS["unreviewed"]
    )
    _apply(widget, colors)


def _apply(widget: QWidget, colors: dict[str, str]) -> None:
    """Apply the common stylesheet to a widget.

    :param widget: Target widget.
    :param colors: Dict with stripe, bg, and hover keys.
    """
    widget.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    cls = type(widget).__name__
    widget.setStyleSheet(
        f"{cls} {{ "
        f"  border-left: 4px solid {colors['stripe']}; "
        f"  background-color: {colors['bg']}; "
        f"  border-bottom: 1px solid #E0E0E0; "
        f"}} "
        f"{cls}:hover {{ "
        f"  background-color: {colors['hover']}; "
        f"}}"
    )
