"""Apply accepted field differences to a :class:`YamlDocument`.

Phase 1 covers the "changed-in-both" case for fields: replace an existing scalar
property of an existing field. The patcher navigates the ruamel document to the
owning node and delegates the surgical splice to :meth:`YamlDocument.set_scalar`.

CRM-only field insertion and YAML-only deletion are later phases; per the design,
deletions are report-only in v1.
"""
from __future__ import annotations

from espo_impl.core.reconcile.document import YamlDocument
from espo_impl.core.reconcile.locators import RoleLocator, TeamLocator


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


def _find_named(doc: YamlDocument, block: str, name: str):
    items = doc.data.get(block)
    if not items:
        raise KeyError(f"no top-level {block!r} block")
    for item in items:
        if item.get("name") == name:
            return item
    raise KeyError(f"{block[:-1]} {name!r} not found")


def _set_existing(owner, key: str, value, doc: YamlDocument, where: str) -> None:
    if key not in owner:
        raise KeyError(
            f"{where} has no {key!r} to change; adding an absent key is not "
            "supported in this phase"
        )
    doc.set_scalar(owner, key, value)


def apply_role_change(doc: YamlDocument, locator: RoleLocator, new_value) -> None:
    """Write an accepted role-property drift back into the YAML.

    Navigates ``roles:`` → role (by name) → the section the locator names, then
    surgically sets the scalar (booleans keep their yes/no vs true/false spelling
    via set_scalar). Only existing keys are changed (the changed-in-both case);
    adding an absent entity scope or permission is deferred.
    """
    role = _find_named(doc, "roles", locator.role)
    if locator.part == "description":
        _set_existing(role, "description", new_value, doc, f"role {locator.role!r}")
    elif locator.part == "scope_access":
        scope = role.get("scope_access")
        if not scope or locator.entity not in scope:
            raise KeyError(
                f"role {locator.role!r} has no scope_access for {locator.entity!r}"
            )
        _set_existing(
            scope[locator.entity], locator.key, new_value, doc,
            f"role {locator.role!r} scope_access.{locator.entity}",
        )
    elif locator.part == "system_permissions":
        perms = role.get("system_permissions")
        if not perms:
            raise KeyError(f"role {locator.role!r} has no system_permissions block")
        _set_existing(
            perms, locator.key, new_value, doc,
            f"role {locator.role!r} system_permissions",
        )
    else:
        raise ValueError(f"unsupported role locator part {locator.part!r}")


def apply_team_change(doc: YamlDocument, locator: TeamLocator, new_value) -> None:
    """Write an accepted team-property drift (description) back into the YAML."""
    team = _find_named(doc, "teams", locator.team)
    if locator.part == "description":
        _set_existing(team, "description", new_value, doc, f"team {locator.team!r}")
    else:
        raise ValueError(f"unsupported team locator part {locator.part!r}")
