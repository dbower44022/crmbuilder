"""Typed addresses into a YAML program file.

A locator names *where* a difference lives in semantic terms (entity, field,
property). The diff engine emits locators; :mod:`document` / :mod:`patcher`
resolve a locator to a concrete node position and splice the edit. Keeping the
address typed and separate from the diff payload lets the comparators stay
unaware of ruamel and the writer stay unaware of comparison.

``prop is None`` denotes the whole item (a field/relationship add or remove)
rather than a single property change.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldLocator:
    """A field, or one property of a field, on an entity.

    :param entity: entity name as it appears under ``entities:``.
    :param field_name: the field's ``name:`` value.
    :param prop: the field property key (e.g. ``"label"``); ``None`` for the
        whole field.
    """

    entity: str
    field_name: str
    prop: str | None = None


@dataclass(frozen=True)
class RelationshipLocator:
    """A relationship, or one of its properties, on an entity."""

    entity: str
    rel_name: str
    prop: str | None = None


@dataclass(frozen=True)
class LayoutLocator:
    """A position within a layout. Layouts are positional (list-of-lists), so a
    cell is addressed by panel + row + column rather than by a stable name.

    Reconciliation granularity is per-layout-type block (e.g. the whole
    ``detail`` layout), so ``panel``/``row``/``col`` default to ``None`` and
    address the layout-type block as a unit; they are reserved for finer
    targeting if cell-level reconciliation is added later.
    """

    entity: str
    layout_type: str
    panel: str | int | None = None
    row: int | None = None
    col: int | None = None


@dataclass(frozen=True)
class EntityOptionLocator:
    """One entity-level option on an entity (PI-312 / REQ-346).

    Entity options are single scalar values living in the entity's ``settings:``
    block (icon, color, multiple-assigned-users, optimistic-concurrency,
    list-count, kanban), so a difference is addressed by entity + option key.

    :param entity: entity name as it appears under ``entities:``.
    :param option: the canonical option key (e.g. ``"iconClass"``).
    """

    entity: str
    option: str


@dataclass(frozen=True)
class RoleLocator:
    """A role, or one property within it, in the top-level ``roles:`` list.

    The role is matched by ``role`` (its ``name``). ``part`` selects the section:
    ``"description"`` (the role-level scalar), ``"scope_access"`` (then ``entity``
    + ``key`` name the per-entity access dimension, e.g. entity=Contact key=read),
    or ``"system_permissions"`` (then ``key`` names the permission, e.g. export).
    ``part is None`` / all-None addresses the whole role (add/remove).
    """

    role: str
    part: str | None = None
    entity: str | None = None
    key: str | None = None


@dataclass(frozen=True)
class TeamLocator:
    """A team, or one property of it, in the top-level ``teams:`` list.

    Matched by ``team`` (its ``name``); ``part`` is ``"description"`` or ``None``
    for the whole team.
    """

    team: str
    part: str | None = None
