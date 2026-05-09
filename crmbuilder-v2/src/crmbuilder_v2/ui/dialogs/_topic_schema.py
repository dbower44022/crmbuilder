"""Field schema for the topics CRUD dialogs.

v0.2 slice D introduces the Topics write surface as the fourth user of
the schema-driven ``EntityCrudDialog`` base — and the first user of the
``tree_picker`` widget kind. Four fields map onto the access-layer
Topic model: identifier, name, description, parent_topic.

The ``parent_topic`` field is a tree picker. On Create, every existing
topic is selectable. On Edit, the topic being edited and all its
descendants are non-selectable so the user cannot create a cycle by
re-parenting. The cycle filter is built by ``topic_fields_edit`` from
the live topic list at picker-open time.

The ``record_field_for_edit`` mapping reads the parent identifier off
the record under the API's ``parent_topic_identifier`` key, since the
API returns ``parent_topic_identifier`` on read but accepts
``parent_topic`` on write.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy

from crmbuilder_v2.ui.base.crud_dialog import FieldSchema
from crmbuilder_v2.ui.client import StorageClient
from crmbuilder_v2.ui.widgets.hierarchical_picker import HierarchicalEntityPicker

IDENTIFIER_RE = re.compile(r"^TOP-\d{3,}$")
IDENTIFIER_HINT = "Identifier must be in the format TOP-NNN (e.g., TOP-001)."


def _fetch_topic_nodes(client: StorageClient) -> list[HierarchicalEntityPicker.Node]:
    """Build the tree-picker node list from all topics."""
    topics = client.list_topics()
    return [
        HierarchicalEntityPicker.Node(
            id=t["identifier"],
            label=f"{t['identifier']} — {t.get('name') or ''}",
            parent_id=t.get("parent_topic_identifier"),
        )
        for t in topics
        if t.get("identifier")
    ]


def _no_filter(
    _client: StorageClient, _record: dict | None
) -> Callable[[HierarchicalEntityPicker.Node], bool]:
    """Create-mode predicate factory: every node is selectable."""

    def predicate(_node: HierarchicalEntityPicker.Node) -> bool:
        return True

    return predicate


def _exclude_self_and_descendants(
    client: StorageClient, record: dict | None
) -> Callable[[HierarchicalEntityPicker.Node], bool]:
    """Edit-mode predicate factory: returns False for the topic being
    edited and any of its descendants. Walks the parent → children map
    built from a fresh ``list_topics()`` call so reparents made by
    other writers since the dialog opened are reflected.
    """
    edited_id = (record or {}).get("identifier")
    if not edited_id:
        return _no_filter(client, record)

    topics = client.list_topics()
    children: dict[str, list[str]] = {}
    for t in topics:
        parent = t.get("parent_topic_identifier")
        ident = t.get("identifier")
        if parent and ident:
            children.setdefault(parent, []).append(ident)

    excluded: set[str] = set()
    stack = [edited_id]
    while stack:
        node_id = stack.pop()
        if node_id in excluded:
            continue
        excluded.add(node_id)
        stack.extend(children.get(node_id, []))

    def predicate(node: HierarchicalEntityPicker.Node) -> bool:
        return node.id not in excluded

    return predicate


_TOPIC_FIELDS_TEMPLATE: list[FieldSchema] = [
    FieldSchema(
        key="identifier",
        label="Identifier",
        widget="line",
        required=True,
        placeholder="TOP-NNN",
        regex=IDENTIFIER_RE,
        regex_hint=IDENTIFIER_HINT,
        read_only_on_edit=True,
    ),
    FieldSchema(key="name", label="Name", widget="line", required=True),
    FieldSchema(key="description", label="Description", widget="text"),
    FieldSchema(
        key="parent_topic",
        label="Parent Topic",
        widget="tree_picker",
        record_field_for_edit="parent_topic_identifier",
        omit_when_empty_in_create=True,
        tree_picker_data=_fetch_topic_nodes,
        tree_picker_filter=_no_filter,
        tree_picker_title="Select Parent Topic",
    ),
]


def topic_fields_create() -> list[FieldSchema]:
    """Return a fresh copy of the topic field schema for Create mode.

    Every existing topic is selectable in the parent picker.
    """
    return deepcopy(_TOPIC_FIELDS_TEMPLATE)


def topic_fields_edit() -> list[FieldSchema]:
    """Return a fresh copy of the topic field schema for Edit mode.

    The parent picker excludes the topic being edited and all its
    descendants (cycle prevention).
    """
    fields = deepcopy(_TOPIC_FIELDS_TEMPLATE)
    parent_field = next(f for f in fields if f.key == "parent_topic")
    parent_field.tree_picker_filter = _exclude_self_and_descendants
    return fields
