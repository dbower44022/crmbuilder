"""Turning a checked declaration into something the appliers can apply
(PI-532 / REQ-618).

The declaration is the contract between the design and the instance: the file
a person can read, and — because the publish path parses back what it emitted
— provably the thing that gets applied. This module is the join between that
file and the appliers, and it is deliberately thin. It renames, it drops what
the platform must never receive, and it decides nothing.

**Three keys are documentation and never reach the instance.** A field's
description, the mark that says its choices are set on the instance rather
than by the design, and the mark that says something outside the system fills
it in. Version 1 was careful about these because sending them creates a field
the platform will not let an administrator edit afterwards.

**A layout is translated by its shape.** The declaration writes a record view
as a named list of panels, a list view as a named list of columns naming the
field each shows, and a filter list as bare names; the platform wants the
list itself, and it calls a column's field its name. Getting this wrong is
quiet: a column whose field did not survive the translation is a column with
no heading and nothing in it. And on an object type the platform ships, a
field this design adds carries the platform's prefix — a cell naming it
unprefixed shows nothing at all.

**The name field is placed if the design did not place it.** The platform
treats a record's name as required, and a design that arranges its screens by
grouping fields has no reason to mention a field with no group — so the
record view comes out with no place to type the one value the platform
insists on, and the form cannot be saved. The design can say it means it, by
turning the automatic placement off.

**A panel is given the shape the platform stores.** The declaration writes a
panel as a title and some rows; the platform keeps a title under a different
key and expects every other property to be present, so a panel is filled out
to that shape before it is sent. Sending the declaration's own spelling
would quietly lose the panel's title.

**Two keys are renamed, not translated.** A rule about when a field is
required or visible is written in the declaration under a readable name and
sent under the platform's. The rule's own shape is the platform's already:
the emitter compiled it on the way out, which is why nothing here has to
understand conditions.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from crmbuilder_v2.publish.declaration import Declaration
from crmbuilder_v2.publish.entities import (
    CREATE,
    REMOVE,
    REMOVE_AND_CREATE,
    EntityIntent,
)
from crmbuilder_v2.publish.entity_settings import SETTINGS, SettingsIntent
from crmbuilder_v2.publish.fields import FieldIntent
from crmbuilder_v2.publish.filtered_tabs import TabIntent
from crmbuilder_v2.publish.layouts import LayoutIntent
from crmbuilder_v2.publish.links import LinkIntent
from crmbuilder_v2.publish.message_templates import TemplateIntent
from crmbuilder_v2.publish.run import ApplyPlan, EntityPlan
from crmbuilder_v2.publish.security import FieldPermission, RoleIntent, TeamIntent

#: Field keys that describe the design and must never be sent to the platform.
DOCUMENTATION_ONLY = frozenset(
    {"description", "optionsDeferred", "externallyPopulated"}
)

#: Field keys the declaration and the platform spell differently.
RENAMED: dict[str, str] = {
    "requiredWhen": "dynamicLogicRequired",
    "visibleWhen": "dynamicLogicVisible",
}

#: How the declaration wraps each layout shape, and what the platform wants.
_LAYOUT_WRAPPERS = ("panels", "columns")

#: What the declaration calls the field a column shows, and what the platform
#: calls it.
_COLUMN_FIELD = ("field", "name")

#: The layouts a record is typed into, where the name field must have a place.
_RECORD_VIEWS = frozenset({"detail", "edit", "detailSmall", "detailConvert"})

#: The setting a design uses to say it left the name field out on purpose.
AUTO_PLACE_NAME = "autoPlaceName"

#: What the platform calls a record's name.
NAME_FIELD = "name"

#: A panel as the platform stores one: the title under its own key, and every
#: other property present rather than assumed.
_PANEL_DEFAULTS: dict[str, Any] = {
    "customLabel": None,
    "tabBreak": False,
    "tabLabel": None,
    "style": "default",
    "hidden": False,
    "noteText": None,
    "noteStyle": "info",
    "dynamicLogicVisible": None,
    "dynamicLogicStyled": None,
    "rows": [],
}

#: What the declaration calls a panel's title, and what the platform calls it.
_PANEL_TITLE = ("label", "customLabel")

#: What a declaration may ask for an object type, in the appliers' words.
ACTIONS: dict[str, str] = {
    "create": CREATE,
    "delete": REMOVE,
    "delete_and_create": REMOVE_AND_CREATE,
}


def field_payload(declared: Mapping[str, Any]) -> dict[str, Any]:
    """One declared field, as the platform should receive it."""
    payload: dict[str, Any] = {}
    for key, value in declared.items():
        if key in DOCUMENTATION_ONLY:
            continue
        payload[RENAMED.get(key, key)] = value
    return payload


def _entity_intent(name: str, block: Mapping[str, Any]) -> EntityIntent | None:
    """The object type itself, when the declaration asks for one."""
    action = ACTIONS.get(str(block.get("action") or "").lower())
    if action is None:
        return None
    settings = block.get("settings") or {}
    return EntityIntent(
        name=name,
        action=action,
        kind=str(block.get("type") or "Base"),
        label_singular=settings.get("labelSingular"),
        label_plural=settings.get("labelPlural"),
        stream=bool(settings.get("stream", False)),
        disabled=bool(settings.get("disabled", False)),
    )


def _settings_intent(name: str, block: Mapping[str, Any]) -> SettingsIntent | None:
    """The object type's own settings, keeping only what this system applies.

    A declaration's settings block carries keys the applier does not manage —
    the automatic placement of the name field is the layout emitter's
    business, not a setting to write — so it is filtered rather than passed
    through whole.
    """
    declared = block.get("settings") or {}
    values = {
        key: value for key, value in declared.items() if key in SETTINGS
    }
    if not values:
        return None
    return SettingsIntent(entity=name, values=values)


def _prefixed(name: str) -> str:
    return f"c{name[0].upper()}{name[1:]}" if name else name


def layout_body(
    body: Any,
    *,
    layout_type: str = "",
    entity_is_native: bool = False,
    declared_fields: frozenset[str] = frozenset(),
) -> Any:
    """One layout as the platform wants it.

    :param body: The layout as the declaration writes it.
    :param layout_type: Which layout it is, which decides its shape.
    :param entity_is_native: Whether the platform ships this object type, in
        which case a field this design adds to it carries the prefix.
    :param declared_fields: The fields this design declares on that object
        type. A cell naming anything else is a field the platform ships, and
        its name is already its own.
    """
    from crmbuilder_v2.adapters.espocrm.layout_types import LayoutClass, structure_class

    unwrapped = body
    if isinstance(body, Mapping):
        for wrapper in _LAYOUT_WRAPPERS:
            if wrapper in body:
                unwrapped = body[wrapper]
                break

    def on_platform(name: str) -> str:
        if entity_is_native and name in declared_fields:
            return _prefixed(name)
        return name

    shape = structure_class(layout_type) if layout_type else None

    if shape is LayoutClass.COLUMNS and isinstance(unwrapped, list):
        declared_key, platform_key = _COLUMN_FIELD
        columns: list[Any] = []
        for column in unwrapped:
            if not isinstance(column, Mapping):
                columns.append(column)
                continue
            translated = {
                platform_key if key == declared_key else key: value
                for key, value in column.items()
            }
            if isinstance(translated.get(platform_key), str):
                translated[platform_key] = on_platform(translated[platform_key])
            columns.append(translated)
        return columns

    if shape is LayoutClass.FIELD_LIST and isinstance(unwrapped, list):
        return [
            on_platform(name) if isinstance(name, str) else name
            for name in unwrapped
        ]

    if shape is LayoutClass.PANEL_MAP:
        return unwrapped

    if not entity_is_native:
        return unwrapped
    return _rename_cells(unwrapped, declared_fields)


def _rename_cells(body: Any, declared_fields: frozenset[str]) -> Any:
    """Give every cell naming a declared field the platform's prefix."""
    if isinstance(body, Mapping):
        renamed: dict[str, Any] = {}
        for key, value in body.items():
            if key == "name" and isinstance(value, str) and value in declared_fields:
                renamed[key] = _prefixed(value)
            else:
                renamed[key] = _rename_cells(value, declared_fields)
        return renamed
    if isinstance(body, list):
        return [
            _prefixed(item)
            if isinstance(item, str) and item in declared_fields
            else _rename_cells(item, declared_fields)
            for item in body
        ]
    return body


def panel_payload(panel: Mapping[str, Any]) -> dict[str, Any]:
    """One panel as the platform stores one.

    The declaration's title key becomes the platform's, every property the
    platform expects is present, and anything else the panel carries — the
    attributes an audit read back and the design kept — passes through
    untouched.
    """
    declared_title, platform_title = _PANEL_TITLE
    payload: dict[str, Any] = dict(_PANEL_DEFAULTS)
    for key, value in panel.items():
        payload[platform_title if key == declared_title else key] = value
    return payload


def _panelled(body: Any) -> Any:
    """Every panel in a record view, as the platform stores them."""
    if not isinstance(body, list):
        return body
    return [
        panel_payload(panel) if isinstance(panel, Mapping) else panel
        for panel in body
    ]


def place_name_field(body: Any) -> Any:
    """Put the name field on a record view that does not already carry it.

    The platform requires a record's name, so a view without it is a form
    nobody can save. It goes at the top of the first panel that is always
    shown — never one that appears only under a condition, where it would be
    just as absent when the condition is false.
    """
    if not isinstance(body, list) or not body:
        return body
    for panel in body:
        if not isinstance(panel, Mapping):
            continue
        for row in panel.get("rows") or []:
            if not isinstance(row, list):
                continue
            for cell in row:
                cell_name = cell.get("name") if isinstance(cell, Mapping) else cell
                if cell_name == NAME_FIELD:
                    return body

    placed = [dict(panel) if isinstance(panel, Mapping) else panel for panel in body]
    target = next(
        (
            panel
            for panel in placed
            if isinstance(panel, Mapping) and not panel.get("dynamicLogicVisible")
        ),
        placed[0],
    )
    if isinstance(target, Mapping):
        target["rows"] = [[{"name": NAME_FIELD}], *(target.get("rows") or [])]
    return placed


def _layout_intents(
    block: Mapping[str, Any],
    *,
    entity_is_native: bool,
    declared_fields: frozenset[str],
) -> list[LayoutIntent]:
    layouts = block.get("layout") or {}
    if not isinstance(layouts, Mapping):
        return []
    settings = block.get("settings") or {}
    place_name = settings.get(AUTO_PLACE_NAME, True)

    intents: list[LayoutIntent] = []
    for layout_type, body in layouts.items():
        kind = str(layout_type)
        translated = layout_body(
            body,
            layout_type=kind,
            entity_is_native=entity_is_native,
            declared_fields=declared_fields,
        )
        if kind in _RECORD_VIEWS:
            if place_name:
                translated = place_name_field(translated)
            translated = _panelled(translated)
        intents.append(LayoutIntent(layout_type=kind, body=translated))
    return intents


def _template_intents(
    entity_wire_name: str, block: Mapping[str, Any]
) -> list[TemplateIntent]:
    return [
        TemplateIntent(
            name=str(template.get("name") or ""),
            entity=entity_wire_name,
            subject=str(template.get("subject") or ""),
            body=str(template.get("body") or ""),
        )
        for template in block.get("emailTemplates") or []
        if isinstance(template, Mapping) and template.get("name")
    ]


def _tab_intents(
    entity_wire_name: str, block: Mapping[str, Any]
) -> list[TabIntent]:
    return [
        TabIntent(
            label=str(tab.get("label") or tab.get("name") or ""),
            entity=entity_wire_name,
            where=tab.get("where") or (tab.get("filter") or {}).get("where") or [],
        )
        for tab in block.get("filteredTabs") or []
        if isinstance(tab, Mapping) and (tab.get("label") or tab.get("name"))
    ]


def _link_intent(declared: Mapping[str, Any]) -> LinkIntent | None:
    entity = declared.get("entity")
    foreign = declared.get("entityForeign")
    link = declared.get("link")
    kind = declared.get("linkType")
    if not (entity and foreign and link and kind):
        return None
    return LinkIntent(
        entity=str(entity),
        entity_foreign=str(foreign),
        link=str(link),
        link_foreign=str(declared.get("linkForeign") or link),
        kind=str(kind),
        label=declared.get("label"),
        label_foreign=declared.get("labelForeign"),
        relation_name=declared.get("relationName"),
        audited=bool(declared.get("audited", False)),
        audited_foreign=bool(declared.get("auditedForeign", False)),
    )


def _role_intents(
    declarations: Sequence[Declaration],
) -> list[RoleIntent]:
    """Every declared role, with the field permissions gathered onto it.

    Field permissions are declared separately from roles — one entry per
    field — so they are grouped here rather than by each applier in turn.
    """
    permissions: dict[str, list[FieldPermission]] = {}
    for declaration in declarations:
        for entry in declaration.content.get("fieldPermissions") or []:
            if not isinstance(entry, Mapping):
                continue
            role = str(entry.get("role") or "")
            if not role:
                continue
            permissions.setdefault(role, []).append(
                FieldPermission(
                    entity=str(entry.get("entity") or ""),
                    field=str(entry.get("field") or ""),
                    level=str(entry.get("level") or "no"),
                )
            )

    roles: list[RoleIntent] = []
    for declaration in declarations:
        for declared in declaration.content.get("roles") or []:
            if not isinstance(declared, Mapping) or not declared.get("name"):
                continue
            name = str(declared["name"])
            roles.append(
                RoleIntent(
                    name=name,
                    scope_access=declared.get("scope_access")
                    or declared.get("scopeAccess")
                    or {},
                    system_permissions=declared.get("system_permissions")
                    or declared.get("systemPermissions")
                    or {},
                    field_permissions=permissions.get(name, []),
                )
            )
    return roles


def plan_for(
    declarations: Sequence[Declaration],
    *,
    wire_name: Any = None,
) -> ApplyPlan:
    """Turn checked declarations into one plan the appliers can carry out.

    :param declarations: Every declaration in the publish, already parsed and
        checked.
    :param wire_name: How an object type's design name becomes its name on
        the platform. Injected so a caller can supply another engine's rule;
        the CRM's own is the default.
    :returns: The plan, with the object types in the order they were
        declared.
    """
    if wire_name is None:
        from crmbuilder_v2.introspect.utilization import wire_entity_name

        wire_name = wire_entity_name
    from crmbuilder_v2.adapters.espocrm.layouts import is_native_entity

    entities: list[EntityPlan] = []
    tabs: list[TabIntent] = []
    links: list[LinkIntent] = []
    teams: list[TeamIntent] = []

    for declaration in declarations:
        for entity_name, block in declaration.entities.items():
            if not isinstance(block, Mapping):
                continue
            name = str(entity_name)
            on_platform = wire_name(name)
            declared_fields = frozenset(
                str(declared.get("name"))
                for declared in block.get("fields") or []
                if isinstance(declared, Mapping) and declared.get("name")
            )
            entities.append(
                EntityPlan(
                    name=name,
                    entity=_entity_intent(name, block),
                    settings=_settings_intent(name, block),
                    templates=_template_intents(on_platform, block),
                    fields=[
                        FieldIntent(
                            name=str(declared.get("name") or ""),
                            payload=field_payload(declared),
                        )
                        for declared in block.get("fields") or []
                        if isinstance(declared, Mapping) and declared.get("name")
                    ],
                    layouts=_layout_intents(
                        block,
                        entity_is_native=is_native_entity(name),
                        declared_fields=declared_fields,
                    ),
                )
            )
            tabs.extend(_tab_intents(on_platform, block))

        for declared in declaration.relationships:
            link = _link_intent(declared)
            if link is not None:
                links.append(link)

        for declared in declaration.content.get("teams") or []:
            if isinstance(declared, Mapping) and declared.get("name"):
                teams.append(
                    TeamIntent(
                        name=str(declared["name"]),
                        description=declared.get("description"),
                    )
                )

    return ApplyPlan(
        entities=entities,
        links=links,
        teams=teams,
        roles=_role_intents(declarations),
        tabs=tabs,
    )
