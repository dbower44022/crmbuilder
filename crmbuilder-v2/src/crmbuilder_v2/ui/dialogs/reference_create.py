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
        list_method = self._list_method_for(entity_type)
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
            identifier, title = _identifier_and_title(record, entity_type)
            if identifier:
                out.append((identifier, title))
        self._entity_list_cache[entity_type] = out
        return out

    def _list_method_for(
        self, entity_type: str
    ) -> Callable[[], list[dict[str, Any]]] | None:
        """Resolve the client list call that backs ``entity_type``'s picker.

        Every record type the reference vocabulary allows and the client
        can list without arguments is covered (REQ-562 / PI-463); before
        that only the seven governance types were, so a process, entity,
        persona, field or domain picker opened empty and the operator had
        to type the identifier from memory. Charter and status are
        version-keyed and go through the labelled wrapper. A type with no
        list call resolves to ``None`` and the picker stays free-text.
        """
        if entity_type in ("charter", "status"):
            return self._list_versioned_with_label(entity_type)
        method_name = _LIST_METHOD_NAMES.get(entity_type)
        if method_name is None:
            return None
        return getattr(self._client, method_name, None)

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


# Client list call per record type (REQ-562 / PI-463). Keys are
# ``ENTITY_TYPES`` members; values are ``StorageClient`` method names
# that take no required arguments. A type absent here has no list call
# the picker can use and stays free-text.
_LIST_METHOD_NAMES: dict[str, str] = {
    "agent_profile": "list_agent_profiles",
    "association": "list_associations",
    "association_mapping": "list_association_mappings",
    "close_out_payload": "list_close_out_payloads",
    "commit": "list_commits",
    "conversation": "list_conversations",
    "crm_candidate": "list_crm_candidates",
    "decision": "list_decisions",
    "deposit_event": "list_deposit_events",
    "domain": "list_domains",
    "entity": "list_entities",
    "field": "list_fields",
    "field_mapping": "list_field_mappings",
    "governance_rule": "list_governance_rules",
    "instance": "list_instances",
    "learning": "list_learnings",
    "lesson": "list_lessons",
    "manual_config": "list_manual_configs",
    "mapping_candidate": "list_mapping_candidates",
    "participant": "list_participants",
    "persona": "list_personas",
    "planning_item": "list_planning_items",
    "preference": "list_preferences",
    "process": "list_processes",
    "project": "list_projects",
    "reference_book": "list_reference_books",
    "reference_entry": "list_reference_entries",
    "reference_pointer": "list_reference_pointers",
    "release": "list_releases",
    "requirement": "list_requirements",
    "risk": "list_risks",
    "session": "list_sessions",
    "skill": "list_skills",
    "source_mapping": "list_source_mappings",
    "term": "list_terms",
    "test_spec": "list_test_specs",
    "topic": "list_topics",
    "work_task": "list_work_tasks",
    "work_ticket": "list_work_tickets",
    "workstream": "list_workstreams",
}


def _identifier_and_title(record: dict[str, Any], entity_type: str) -> tuple[str, str]:
    """Return ``(identifier, title)`` for any list-row shape the API emits.

    Governance rows carry bare ``identifier`` / ``title``; methodology and
    later rows prefix them with the type name (``process_identifier``,
    ``process_name``, ``workstream_title``), so the type-prefixed key is
    tried first and the bare key second. Charter and status rows have no
    identifier at all and are keyed by ``version``, surfaced as ``vN``.
    Title falls back to empty, never to the identifier, so the picker's
    display stays ``identifier — title`` shaped.
    """
    identifier = (
        record.get(f"{entity_type}_identifier") or record.get("identifier") or ""
    )
    if not identifier:
        version = record.get("version")
        if version is not None:
            identifier = f"v{version}"
    title = ""
    for key in (
        f"{entity_type}_title",
        f"{entity_type}_name",
        "title",
        "name",
    ):
        if record.get(key):
            title = str(record[key])
            break
    return str(identifier), title


# Sanity-check: keep RELATIONSHIP_RULES import live so the module
# doesn't lose its dialog-open-time vocab read pattern under linting.
_ = RELATIONSHIP_RULES
