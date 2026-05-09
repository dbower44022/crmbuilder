"""Reference create dialog — v0.3 slice C (DEC-033).

Source-first cascading dialog for creating a reference. Strict
``RELATIONSHIP_RULES`` vocab compliance: every dropdown shows only
valid choices for the partially-filled state, so invalid combinations
are unrepresentable in the dialog.

Field cascade:

1. Source type (combo, vocab from ``ENTITY_TYPES``).
2. Source identifier (``EntityIdentifierPicker``, depends on source
   type — fetches that entity type's records).
3. Relationship (combo, depends on source type — kinds whose source
   constraint matches).
4. Target type (combo, depends on source type and relationship —
   target types valid for the (source, kind) pair).
5. Target identifier (``EntityIdentifierPicker``, depends on target
   type).

When opened with ``pre_populated_source=(source_type, source_id)``,
the source fields are filled and disabled; the cascade starts from
relationship.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QWidget

from crmbuilder_v2.access.vocab import (
    ENTITY_TYPES,
    RELATIONSHIP_RULES,
    kinds_for_source,
    target_types_for,
)
from crmbuilder_v2.ui.base.crud_dialog import EntityCrudDialog, FieldSchema
from crmbuilder_v2.ui.client import StorageClient


class ReferenceCreateDialog(EntityCrudDialog):
    """Modal create-reference dialog with cascading filters."""

    def __init__(
        self,
        client: StorageClient,
        *,
        pre_populated_source: tuple[str, str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._pre_populated_source = pre_populated_source
        self._entity_list_cache: dict[str, list[tuple[str, str]]] = {}
        # The base ``EntityCrudDialog`` builds widgets from the schema in
        # __init__; the schema's compute_options closures capture
        # ``self`` to reach the cached entity lists. Build the schema
        # before calling super so the closures are bound.
        schema = self._build_schema(client)
        super().__init__(
            client,
            schema,
            mode="create",
            title="New Reference",
            create_method=client.create_reference,
            parent=parent,
        )
        if pre_populated_source is None:
            # Source-first cascade UX: open with the source-type combo
            # unselected so the user explicitly picks. Without this, Qt
            # defaults the combo to the first vocab item, which would
            # auto-cascade source_id to that type's records before the
            # user has chosen anything.
            source_type_widget = self._field_widgets.get("source_type")
            if source_type_widget is not None:
                source_type_widget.setCurrentIndex(-1)
            self._refresh_dependent_fields()
        else:
            source_type, source_id = pre_populated_source
            source_type_widget = self._field_widgets.get("source_type")
            if source_type_widget is not None:
                idx = source_type_widget.findText(source_type)
                if idx >= 0:
                    source_type_widget.setCurrentIndex(idx)
            self._refresh_dependent_fields()
            source_id_schema = self._fields_by_key["source_id"]
            self._set_widget_value(source_id_schema, source_id)
            # Lock source fields *after* the cascade has populated them
            # so the user can only fill the downstream side. The base's
            # _refresh_dependent_fields ran in __init__ before this
            # branch, populating relationship from the just-set
            # source_type; no further refresh is needed here because
            # source_id is a leaf (nothing depends on it).
            self.set_field_enabled("source_type", False)
            self.set_field_enabled("source_id", False)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _build_schema(self, client: StorageClient) -> list[FieldSchema]:
        return [
            FieldSchema(
                key="source_type",
                label="Source type",
                widget="combo",
                required=True,
                vocab=frozenset(ENTITY_TYPES),
            ),
            FieldSchema(
                key="source_id",
                label="Source identifier",
                widget="identifier_picker",
                required=True,
                depends_on=["source_type"],
                compute_options=self._compute_source_identifiers,
            ),
            FieldSchema(
                key="relationship",
                label="Relationship",
                widget="combo",
                required=True,
                depends_on=["source_type"],
                compute_options=self._compute_kinds,
            ),
            FieldSchema(
                key="target_type",
                label="Target type",
                widget="combo",
                required=True,
                depends_on=["source_type", "relationship"],
                compute_options=self._compute_target_types,
            ),
            FieldSchema(
                key="target_id",
                label="Target identifier",
                widget="identifier_picker",
                required=True,
                depends_on=["target_type"],
                compute_options=self._compute_target_identifiers,
            ),
        ]

    # ------------------------------------------------------------------
    # compute_options callables (read RELATIONSHIP_RULES at dialog-open
    # time — see DEC-033)
    # ------------------------------------------------------------------

    def _compute_source_identifiers(
        self, state: dict[str, str]
    ) -> list[tuple[str, str]]:
        source_type = state.get("source_type", "").strip()
        if not source_type:
            return []
        return self._fetch_entity_list(source_type)

    def _compute_kinds(self, state: dict[str, str]) -> list[str]:
        source_type = state.get("source_type", "").strip()
        if not source_type:
            return []
        return sorted(kinds_for_source(source_type))

    def _compute_target_types(self, state: dict[str, str]) -> list[str]:
        source_type = state.get("source_type", "").strip()
        kind = state.get("relationship", "").strip()
        if not source_type or not kind:
            return []
        return sorted(target_types_for(source_type, kind))

    def _compute_target_identifiers(
        self, state: dict[str, str]
    ) -> list[tuple[str, str]]:
        target_type = state.get("target_type", "").strip()
        if not target_type:
            return []
        return self._fetch_entity_list(target_type)

    # ------------------------------------------------------------------
    # Entity list fetching (cached per dialog-open)
    # ------------------------------------------------------------------

    def _fetch_entity_list(self, entity_type: str) -> list[tuple[str, str]]:
        """Return ``[(identifier, title), ...]`` for the given entity type.

        Cached per dialog-open so repeated cascade passes don't re-hit
        the API. Lists are small (< 1000 entries per type today) so a
        synchronous fetch is acceptable inside the cascade.
        """
        cached = self._entity_list_cache.get(entity_type)
        if cached is not None:
            return cached
        method_map: dict[str, Callable[[], list[dict[str, Any]]]] = {
            "decision": self._client.list_decisions,
            "session": self._client.list_sessions,
            "risk": self._client.list_risks,
            "planning_item": self._client.list_planning_items,
            "topic": self._client.list_topics,
            "charter": self._list_versioned_with_label("charter"),
            "status": self._list_versioned_with_label("status"),
        }
        list_method = method_map.get(entity_type)
        if list_method is None:
            self._entity_list_cache[entity_type] = []
            return []
        try:
            records = list_method()
        except Exception:
            # Best effort — empty list lets the user know the cascade
            # blocked, even though the picker accepts free text. The
            # base's error pipeline catches save failures.
            self._entity_list_cache[entity_type] = []
            return []
        out: list[tuple[str, str]] = []
        for record in records:
            identifier = record.get("identifier") or ""
            if not identifier:
                # Charter / status records use ``version`` for identity;
                # surface a synthetic label.
                version = record.get("version")
                if version is not None:
                    identifier = f"v{version}"
            title = record.get("title") or ""
            out.append((identifier, title))
        self._entity_list_cache[entity_type] = out
        return out

    def _list_versioned_with_label(
        self, entity_type: str
    ) -> Callable[[], list[dict[str, Any]]]:
        """Wrap charter/status list calls so cached results survive
        the version-keyed shape (no per-row title field on those rows)."""
        if entity_type == "charter":
            return self._client.list_charter_versions
        return self._client.list_status_versions

    def created_identifier(self) -> str | None:
        """Identifier of the newly created record (mirrors other dialogs).

        References don't have a single string identifier; the returned
        value is the integer ``id`` rendered as a string. Callers that
        only need to refresh on success can continue to ignore this.
        """
        return self.saved_identifier()


# Sanity-check: keep RELATIONSHIP_RULES import live so the module
# doesn't lose its dialog-open-time vocab read pattern under linting.
_ = RELATIONSHIP_RULES
