"""Searchable FK dropdown selector (Section 14.8.3).

Type-constrained input for foreign key fields in edit mode.
"""

from __future__ import annotations

import sqlite3

from PySide6.QtWidgets import QComboBox

from automation.ui.browser.browser_logic import get_fk_options


class FKSelector(QComboBox):
    """Searchable dropdown for selecting FK references.

    :param conn: Database connection.
    :param fk_table: The referenced table.
    :param current_value: Current FK value (ID).
    :param parent: Parent widget.
    """

    def __init__(
        self,
        conn: sqlite3.Connection,
        fk_table: str,
        current_value: int | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setEditable(True)
        self.setMaxVisibleItems(15)
        self.setStyleSheet("font-size: 11px;")

        # Add empty option
        self.addItem("— None —", None)

        # Populate with FK options
        options = get_fk_options(conn, fk_table)
        for fk_id, label in options:
            self.addItem(label, fk_id)

        # Set current selection
        if current_value is not None:
            for i in range(self.count()):
                if self.itemData(i) == current_value:
                    self.setCurrentIndex(i)
                    break

    def get_selected_id(self) -> int | None:
        """Get the selected FK ID.

        :returns: Selected record ID, or None.
        """
        return self.currentData()
