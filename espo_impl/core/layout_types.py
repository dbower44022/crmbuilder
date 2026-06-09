"""Registry of EspoCRM layout types and their structure classes.

The full set of layout types EspoCRM exposes via
``GET /Layout/action/getOriginal`` / ``PUT /{entity}/layout/{type}`` is grouped
into four **structure classes**. The class is the single dispatch key used by the
loader (parse + validate), the deploy path (``layout_manager``), and the audit
reverse-mapper (``audit_manager``), so adding a type is a one-line registry edit
plus, where the class is new, one builder/reverse-mapper.

Class shapes (confirmed against a live EspoCRM 9.x instance — see
``tests/fixtures/layouts/README.md``):

- **PANELS** — ``list[panel]``; each panel has rows of ``{"name": field}`` cells
  plus ``customLabel``/``style``/``tabBreak``/``tabLabel``/``hidden``/
  ``noteText``/``noteStyle``/``dynamicLogicVisible``.
- **COLUMNS** — ``list[column]``; each column has ``name`` plus optional
  ``link``/``width``/``notSortable``/``align``/``view``.
- **FIELD_LIST** — ``list[str]`` of field names (``filters``/``massUpdate``) or
  relationship link names (``relationships``).
- **PANEL_MAP** — ``{name: cfg}`` mapping with ``_delimiter_``/``_tabBreak_N``
  meta keys (the side/bottom relationship-panel placement layouts).

Portal variants are recognized but deploy-deferred (no defined portal layouts on
the captured instance). Layout Sets (per-team/role overrides) are out of scope.
"""

from __future__ import annotations

from enum import Enum


class LayoutClass(Enum):
    """Structure class of a layout type — the dispatch key everywhere."""

    PANELS = "panels"
    COLUMNS = "columns"
    FIELD_LIST = "field_list"
    PANEL_MAP = "panel_map"


PANEL_LAYOUTS: frozenset[str] = frozenset(
    {"detail", "edit", "detailSmall", "detailConvert"}
)
COLUMN_LAYOUTS: frozenset[str] = frozenset({"list", "listSmall", "kanban"})
FIELD_LIST_LAYOUTS: frozenset[str] = frozenset(
    {"filters", "massUpdate", "relationships"}
)
PANEL_MAP_LAYOUTS: frozenset[str] = frozenset(
    {
        "sidePanelsDetail",
        "sidePanelsEdit",
        "sidePanelsDetailSmall",
        "sidePanelsEditSmall",
        "bottomPanelsDetail",
        "bottomPanelsEdit",
        "bottomPanelsDetailSmall",
        "bottomPanelsEditSmall",
    }
)

#: Recognized but deploy-deferred (captured for presence; no write fidelity yet).
PORTAL_LAYOUTS: frozenset[str] = frozenset(
    {
        "listPortal",
        "detailPortal",
        "detailSmallPortal",
        "listSmallPortal",
        "relationshipsPortal",
    }
)

#: Layout types the engine deploys.
DEPLOYABLE_LAYOUT_TYPES: frozenset[str] = (
    PANEL_LAYOUTS | COLUMN_LAYOUTS | FIELD_LIST_LAYOUTS | PANEL_MAP_LAYOUTS
)

#: Every layout type the loader accepts without a hard-reject error.
KNOWN_LAYOUT_TYPES: frozenset[str] = DEPLOYABLE_LAYOUT_TYPES | PORTAL_LAYOUTS

_CLASS_BY_TYPE: dict[str, LayoutClass] = {}
for _t in PANEL_LAYOUTS:
    _CLASS_BY_TYPE[_t] = LayoutClass.PANELS
for _t in COLUMN_LAYOUTS:
    _CLASS_BY_TYPE[_t] = LayoutClass.COLUMNS
for _t in FIELD_LIST_LAYOUTS:
    _CLASS_BY_TYPE[_t] = LayoutClass.FIELD_LIST
for _t in PANEL_MAP_LAYOUTS:
    _CLASS_BY_TYPE[_t] = LayoutClass.PANEL_MAP
# Portal variants map to their base structure (used only by the audit
# passthrough; deploy short-circuits them as NOT_SUPPORTED).
for _t in ("listPortal", "listSmallPortal"):
    _CLASS_BY_TYPE[_t] = LayoutClass.COLUMNS
for _t in ("detailPortal", "detailSmallPortal"):
    _CLASS_BY_TYPE[_t] = LayoutClass.PANELS
_CLASS_BY_TYPE["relationshipsPortal"] = LayoutClass.FIELD_LIST


def is_known(layout_type: str) -> bool:
    """True if *layout_type* is a recognized EspoCRM layout type."""
    return layout_type in KNOWN_LAYOUT_TYPES


def is_deployable(layout_type: str) -> bool:
    """True if the engine deploys this layout type (portals are not)."""
    return layout_type in DEPLOYABLE_LAYOUT_TYPES


def is_deploy_deferred(layout_type: str) -> bool:
    """True for recognized-but-not-deployed types (portal variants)."""
    return layout_type in PORTAL_LAYOUTS


def structure_class(layout_type: str) -> LayoutClass | None:
    """Return the :class:`LayoutClass` for *layout_type*, or ``None``."""
    return _CLASS_BY_TYPE.get(layout_type)
