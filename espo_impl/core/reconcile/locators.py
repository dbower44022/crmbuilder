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

    Phase 3 (deferred until the parallel layout-schema expansion lands).
    """

    entity: str
    layout_type: str
    panel: str | int
    row: int | None = None
    col: int | None = None
