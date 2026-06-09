"""Apply accepted field differences to a :class:`YamlDocument`.

Phase 1 covers the "changed-in-both" case for fields: replace an existing scalar
property of an existing field. The patcher navigates the ruamel document to the
owning node and delegates the surgical splice to :meth:`YamlDocument.set_scalar`.

CRM-only field insertion and YAML-only deletion are later phases; per the design,
deletions are report-only in v1.
"""
from __future__ import annotations

from espo_impl.core.reconcile.document import YamlDocument


def _find_entity(doc: YamlDocument, entity: str):
    entities = doc.data.get("entities")
    if not entities or entity not in entities:
        raise KeyError(f"entity {entity!r} not found under 'entities:'")
    return entities[entity]


def _find_field(entity_node, field_name: str):
    fields = entity_node.get("fields")
    if not fields:
        raise KeyError("entity has no 'fields:' block")
    for item in fields:
        if item.get("name") == field_name:
            return item
    raise KeyError(f"field {field_name!r} not found")


def set_field_property(
    doc: YamlDocument, entity: str, field_name: str, prop: str, new_value
) -> None:
    """Replace the value of ``prop`` on ``entity.field_name`` in ``doc``.

    The property must already exist on the field (the changed-in-both case);
    adding a previously-absent property is a separate key-insertion operation
    handled in a later phase. Raises :class:`KeyError` if the entity, field, or
    property is missing.
    """
    entity_node = _find_entity(doc, entity)
    field_node = _find_field(entity_node, field_name)
    if prop not in field_node:
        raise KeyError(
            f"property {prop!r} is not present on field {field_name!r}; "
            "adding an absent property is not supported in this phase"
        )
    doc.set_scalar(field_node, prop, new_value)


def insert_field(
    doc: YamlDocument, entity: str, field_block: dict, *, blank_line_before: bool = True
) -> None:
    """Append a new field to ``entity``'s ``fields:`` list (the CRM-only case).

    ``field_block`` is a YAML-shaped field mapping (``{name, type, label, ...}``)
    — the caller reconstructs it from live CRM state via the Audit reverse-mapper,
    so it already uses YAML field names, not raw API meta. The new block is
    rendered fresh (no comments to preserve) and spliced at the end of the
    sequence; everything else in the file is untouched.
    """
    entity_node = _find_entity(doc, entity)
    if "fields" not in entity_node:
        raise KeyError(f"entity {entity!r} has no 'fields:' block to append to")
    name = field_block.get("name")
    if not name:
        raise ValueError("field_block must include a 'name'")
    if _field_exists(entity_node, name):
        raise ValueError(f"field {name!r} already exists on {entity!r}")
    doc.insert_sequence_item(
        entity_node, "fields", field_block, blank_line_before=blank_line_before
    )


def _field_exists(entity_node, field_name: str) -> bool:
    fields = entity_node.get("fields") or []
    return any(item.get("name") == field_name for item in fields)
