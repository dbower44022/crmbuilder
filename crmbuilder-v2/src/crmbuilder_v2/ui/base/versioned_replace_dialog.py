"""VersionedReplaceDialog skeleton — full implementation lands in slice E.

This module exists in slice A so the ``base/`` package layout is
complete and slice E (charter and status replace flows) imports cleanly.
The class skeleton raises ``NotImplementedError`` on construction. Slice
E replaces this body with the full JSON-payload-editor implementation.

Per DEC-029, the v0.2 replace flow uses a raw JSON editor with a
Validate button — sufficient for v2's loose payload schema and
infrequent-edit use case. Make Current is a separate panel-level
affordance (also slice E).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QDialog, QWidget


class VersionedReplaceDialog(QDialog):
    """Skeleton — slice E provides the full implementation.

    Constructor signature is provisional and will be confirmed during
    slice E's design. Calling the constructor before slice E lands
    raises ``NotImplementedError`` to make incomplete usage obvious.
    """

    def __init__(
        self,
        current_payload: dict,
        save_callback: Callable[[dict], dict],
        *,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._current_payload = current_payload
        self._save_callback = save_callback
        self._title = title
        raise NotImplementedError(
            "VersionedReplaceDialog is implemented in slice E "
            "(CLAUDE-CODE-PROMPT-v2-ui-v0.2-E-charter-status-replace.md)."
        )
