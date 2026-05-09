"""Topic edit dialog. Per ui-PRD-v0.2.md §4.4.

Thin subclass of ``EntityCrudDialog``. The base handles widget
pre-population from the record (the parent picker reads
``parent_topic_identifier`` via ``record_field_for_edit``), the
read-only identifier treatment, partial PATCH diff computation, and
error envelope routing. Cycle prevention is provided by the schema's
``tree_picker_filter`` callback, which excludes the topic being edited
and all of its descendants from being selectable.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.dialogs._topic_schema import topic_fields_edit


class TopicEditDialog(EntityCrudDialog):
    """Modal edit-topic dialog."""

    def __init__(
        self,
        client: StorageClient,
        record: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        identifier = str(record.get("identifier") or "")
        title = f"Edit {identifier}" if identifier else "Edit topic"
        super().__init__(
            client,
            topic_fields_edit(),
            mode="edit",
            title=title,
            update_method=client.update_topic,
            record=record,
            parent=parent,
        )
