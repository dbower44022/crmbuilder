"""Enable an entity's Activities / History / Tasks bottom panels.

EspoCRM shows the Activities, History, and Tasks bottom panels on an entity's
detail view only when two conditions hold:

1. The entity is registered as a possible *parent* of ``Meeting`` / ``Call`` /
   ``Task`` — it appears in ``entityDefs.{Holder}.fields.parent.entityList``.
2. The entity's ``bottomPanelsDetail`` layout does not mark the panels
   ``disabled`` (the ``BasePlus`` template default ships them disabled).

This module holds the pure, deterministic transforms behind both conditions:

* :func:`build_bottom_panels_detail_layout` — the layout payload that un-disables
  the panels (Path 1, applied over REST via ``api_client.save_layout``).
* :func:`merge_parent_entity_list` — add an entity to a holder's
  ``parent.entityList`` idempotently (Path 2, the SSH metadata patch that repairs
  an entity not registered at creation; see
  ``automation/core/deployment/activity_metadata_ssh.py``).

The functions take and return plain dicts so they unit-test without any live
instance. See ``PRDs/product/crmbuilder-automation-PRD/entity-activity-panel-enablement-design.md``.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

#: The three activity bottom panels, in their conventional render order.
ACTIVITY_PANELS: tuple[str, ...] = ("activities", "history", "tasks")

#: The EspoCRM entities that carry a ``parent`` field whose ``entityList`` must
#: include an entity for it to act as an activity parent. ``Email`` is included
#: because EspoCRM's BasePlus template wires it alongside the calendar holders;
#: it drives the History panel's email rows.
PARENT_HOLDERS: tuple[str, ...] = ("Meeting", "Call", "Task", "Email")

#: Holders that drive the visible Activities/History/Tasks panels. ``Email`` is
#: registered for completeness but is not required for the three panels to show.
PANEL_HOLDERS: tuple[str, ...] = ("Meeting", "Call", "Task")

#: Default starting index for the enabled panels in the ``bottomPanelsDetail``
#: layout. Placed after the typical stream panel (index 8 in audited layouts) is
#: avoided; activity panels conventionally sit ahead of relationship panels.
_DEFAULT_START_INDEX = 4


def build_bottom_panels_detail_layout(
    panels: tuple[str, ...] = ACTIVITY_PANELS,
    start_index: int = _DEFAULT_START_INDEX,
) -> dict[str, dict[str, Any]]:
    """Build a ``bottomPanelsDetail`` layout that enables the activity panels.

    The PANEL_MAP layout is a dict keyed by panel name. Setting ``disabled``
    to ``False`` overrides the ``BasePlus`` template's disabled default so the
    panel renders. ``index`` preserves a stable order.

    :param panels: Panel names to enable, in render order.
    :param start_index: Index assigned to the first panel; each subsequent
        panel increments by one.
    :returns: Layout payload suitable for ``PUT /{Entity}/layout/bottomPanelsDetail``.
    """
    return {
        name: {"disabled": False, "index": start_index + offset}
        for offset, name in enumerate(panels)
    }


def merge_parent_entity_list(
    holder_def: dict[str, Any], entity: str
) -> dict[str, Any]:
    """Add ``entity`` to a holder's ``parent`` field entity list, idempotently.

    Operates on a single holder's ``entityDefs`` fragment (the JSON read from
    ``custom/Espo/Custom/Resources/metadata/entityDefs/{Holder}.json``). Both
    ``entityList`` and ``entityTypeList`` are updated when present — EspoCRM
    versions differ on which key drives the parent selector, so both are kept in
    sync. Missing structure is created. The input is not mutated; a new dict is
    returned.

    :param holder_def: The holder's ``entityDefs`` fragment (may be ``{}``).
    :param entity: EspoCRM entity name to register (e.g. ``"CEngagement"``).
    :returns: A new fragment with ``entity`` present in the parent lists.
    """
    result = deepcopy(holder_def) if holder_def else {}
    fields = result.setdefault("fields", {})
    parent = fields.setdefault("parent", {})

    for key in ("entityList", "entityTypeList"):
        current = parent.get(key)
        if current is None:
            # Only seed entityList by default; entityTypeList is created only if
            # the platform already uses it (handled by the caller passing real
            # metadata). For a fresh field, entityList is the canonical key.
            if key == "entityList":
                parent[key] = [entity]
            continue
        if not isinstance(current, list):
            continue
        if entity not in current:
            parent[key] = [*current, entity]

    return result


def parent_list_contains(holder_def: dict[str, Any], entity: str) -> bool:
    """Return whether ``entity`` is already registered in the holder's parent list.

    :param holder_def: The holder's ``entityDefs`` fragment.
    :param entity: EspoCRM entity name.
    :returns: True if present in ``entityList`` (or ``entityTypeList``).
    """
    parent = (holder_def or {}).get("fields", {}).get("parent", {})
    for key in ("entityList", "entityTypeList"):
        values = parent.get(key)
        if isinstance(values, list) and entity in values:
            return True
    return False
