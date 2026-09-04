"""Layout records → the YAML ``layout:`` body — PI-427 (REQ-519, DEC-951).

The audit stores a layout exactly as the CRM returned it: ``layout_content``
is the ``GET /Layout/action/getOriginal`` body, verbatim, spelled in the
platform's own field names (``cMentorStatus`` on a native entity). The deploy
engine reads the YAML shape instead (schema §7.1): ``{panels: [...]}`` for
the record views, ``{columns: [...]}`` for the list views, a bare name list
for filters / mass update / relationships, and a ``{name: cfg}`` map for the
side- and bottom-panel placements — with *natural* field names, because the
engine re-applies the ``c`` prefix on a native entity at deploy time.

The reverse translation here is the V1 audit's (``AuditManager._reverse_*``
in ``espo_impl.core.reconcile.capture``, kept lossless by the layout fixtures
under ``tests/fixtures/layouts``), ported rather than imported: nothing under
``crmbuilder_v2`` imports the V1 audit (REQ-549's structural guard).

This module also answers the one question the mapper cannot: whether every
field the layout places is a field the generated program will carry.
``validate_program`` deliberately lets an unknown cell name through (a native
field the YAML never declares is legitimate), so a layout naming a field the
design does not emit — a candidate field, a deferred one — would reach the
instance as a cell that shows nothing. The rule is the one the filtered-tab
block uses: a construct that references what is not emitted defers by name
rather than emitting a reference the engine cannot honour.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from crmbuilder_v2.introspect.audit_utils import (
    SYSTEM_FIELDS,
    get_native_fields_for_type,
    strip_field_c_prefix,
)
from crmbuilder_v2.introspect.native_entity_types import NATIVE_ENTITY_BASE_TYPE
from espo_impl.core.layout_types import LayoutClass, structure_class

#: Neutral ``layout_type`` (the store's vocabulary) → the EspoCRM layout name
#: the engine reads under ``layout:`` and the audit fetches by. The eighteen
#: ordinary types the deploy engine writes; the audit iterates this same map
#: (``introspect.reconcile``), so the two stay one list.
LAYOUT_TYPE_TO_ESPO: dict[str, str] = {
    "detail": "detail",
    "edit": "edit",
    "detail_small": "detailSmall",
    "detail_convert": "detailConvert",
    "list": "list",
    "list_small": "listSmall",
    "kanban": "kanban",
    "filters": "filters",
    "mass_update": "massUpdate",
    "relationships": "relationships",
    "side_panels_detail": "sidePanelsDetail",
    "side_panels_edit": "sidePanelsEdit",
    "side_panels_detail_small": "sidePanelsDetailSmall",
    "side_panels_edit_small": "sidePanelsEditSmall",
    "bottom_panels_detail": "bottomPanelsDetail",
    "bottom_panels_edit": "bottomPanelsEdit",
    "bottom_panels_detail_small": "bottomPanelsDetailSmall",
    "bottom_panels_edit_small": "bottomPanelsEditSmall",
}

#: The five portal variants (PI-418 / DEC-1029): read by the audit so they can
#: be shown as differences, never rendered — the deploy engine has no write
#: path for them (``layout_types.PORTAL_LAYOUTS`` is deploy-deferred) and the
#: platform offers none apart from the portal's own Layout Manager (REQ-520).
PORTAL_LAYOUT_TYPE_TO_ESPO: dict[str, str] = {
    "list_portal": "listPortal",
    "detail_portal": "detailPortal",
    "list_small_portal": "listSmallPortal",
    "detail_small_portal": "detailSmallPortal",
    "relationships_portal": "relationshipsPortal",
}

#: Everything the audit fetches per entity: the writable eighteen and the
#: portal five. The emitter renders only :data:`LAYOUT_TYPE_TO_ESPO`.
AUDITED_LAYOUT_TYPE_TO_ESPO: dict[str, str] = {
    **LAYOUT_TYPE_TO_ESPO,
    **PORTAL_LAYOUT_TYPE_TO_ESPO,
}

#: Why a portal variant is not rendered — the same fact the reconcile surface
#: states on the row (``reconcile_compare.capability_reason``), said for the
#: MANUAL-CONFIG reader.
PORTAL_LAYOUT_DEFERRAL = (
    "a portal layout variant: the platform offers no write path for it apart "
    "from the portal's own Layout Manager, so it is not published (REQ-520) — "
    "set it there by hand"
)

#: The field-list layouts whose entries are field names. ``relationships`` is
#: the third field-list type and its entries are link names, which are not
#: fields and are not resolved.
_FIELD_NAME_LISTS = frozenset({"filters", "massUpdate"})

#: The record-view field EspoCRM requires on every entity. The deploy engine
#: prepends it to any panel layout that does not place it unless the entity's
#: ``settings.autoPlaceName`` says otherwise (``LayoutManager._ensure_name_placed``).
NAME_FIELD = "name"


class LayoutRenderError(ValueError):
    """The layout cannot be rendered into the program; ``str(exc)`` names why."""


@dataclass
class LayoutRender:
    """One layout's YAML body under its EspoCRM ``layout:`` key."""

    espo_type: str
    body: Any
    #: Field names the body places (natural spelling), for the callers that
    #: reason about placement — the ``name`` auto-placement rule above.
    field_names: list[str] = field(default_factory=list)

    @property
    def places_name(self) -> bool:
        return NAME_FIELD in self.field_names


def is_native_entity(entity_name: str) -> bool:
    """Whether the engine treats ``entity_name`` as a platform entity — the
    case where custom fields carry the ``c`` prefix on the instance."""
    return entity_name in NATIVE_ENTITY_BASE_TYPE


# ---------------------------------------------------------------------------
# CRM payload → YAML body (the V1 audit's reverse mappers, ported)
# ---------------------------------------------------------------------------


def _natural(api_name: str, custom_names: set[str]) -> str:
    """A custom field's natural name; anything else passes through."""
    if api_name in custom_names:
        return strip_field_c_prefix(api_name, entity_is_native=True)
    return api_name


def _reverse_cell(cell: Any, custom_names: set[str]) -> Any:
    """One record-view cell. A plain ``{"name": f}`` collapses to the bare
    name; a cell carrying other attributes (``fullWidth``, ``noLabel``,
    ``view`` …) keeps them with the name reversed; an empty cell is ``None``."""
    if cell is False or cell is None:
        return None
    if isinstance(cell, str):
        return _natural(cell, custom_names)
    if isinstance(cell, dict) and "name" in cell:
        name = _natural(cell["name"], custom_names)
        if len(cell) == 1:
            return name
        out = dict(cell)
        out["name"] = name
        return out
    return None


def _reverse_dynamic_logic(dlv: dict[str, Any], custom_names: set[str]) -> dict[str, Any]:
    """A panel's ``dynamicLogicVisible``: the single-condition form becomes the
    YAML shorthand ``{attribute, value}``; anything more complex is kept as is."""
    group = dlv.get("conditionGroup", [])
    if isinstance(group, list) and len(group) == 1 and isinstance(group[0], dict):
        cond = group[0]
        attr = cond.get("attribute", "")
        if attr:
            return {"attribute": _natural(attr, custom_names), "value": cond.get("value")}
    return dlv


_PANEL_KEYS_HANDLED = frozenset({
    "customLabel", "label", "tabBreak", "tabLabel", "style", "hidden",
    "dynamicLogicVisible", "rows", "tabs",
})


def _reverse_panels(content: Any, custom_names: set[str]) -> list[dict[str, Any]]:
    """PANELS class: the CRM's panel list → the YAML ``panels:`` list."""
    if not isinstance(content, list):
        return []
    panels: list[dict[str, Any]] = []
    for raw in content:
        if not isinstance(raw, dict):
            continue
        panel: dict[str, Any] = {}
        label = raw.get("customLabel") or raw.get("label", "")
        if label:
            panel["label"] = label
        if raw.get("tabBreak"):
            panel["tabBreak"] = True
        if raw.get("tabLabel"):
            panel["tabLabel"] = raw["tabLabel"]
        style = raw.get("style", "default")
        if style and style != "default":
            panel["style"] = style
        if raw.get("hidden"):
            panel["hidden"] = True
        dlv = raw.get("dynamicLogicVisible")
        if dlv:
            panel["dynamicLogicVisible"] = _reverse_dynamic_logic(dlv, custom_names)
        rows_out: list[list[Any]] = []
        for row in raw.get("rows", []) if isinstance(raw.get("rows"), list) else []:
            if isinstance(row, list):
                rows_out.append([_reverse_cell(cell, custom_names) for cell in row])
        if rows_out:
            panel["rows"] = rows_out
        # Any other panel key (noteText, noteStyle, dynamicLogicStyled …) is
        # kept verbatim: the loader stores it in PanelSpec.attrs and the
        # builder re-emits it, so the round trip stays lossless.
        for key, val in raw.items():
            if key not in _PANEL_KEYS_HANDLED:
                panel[key] = val
        panels.append(panel)
    return panels


def _reverse_columns(content: Any, custom_names: set[str]) -> list[dict[str, Any]]:
    """COLUMNS class: the CRM's column list → the YAML ``columns:`` list."""
    if not isinstance(content, list):
        return []
    columns: list[dict[str, Any]] = []
    for raw in content:
        if not isinstance(raw, dict) or not raw.get("name"):
            continue
        column: dict[str, Any] = {"field": _natural(raw["name"], custom_names)}
        if raw.get("width") is not None:
            column["width"] = raw["width"]
        for key, val in raw.items():
            if key not in ("name", "width"):
                column[key] = val
        columns.append(column)
    return columns


def _reverse_field_list(content: Any, custom_names: set[str]) -> list[str]:
    """FIELD_LIST class: field names reversed; link names pass through."""
    if not isinstance(content, list):
        return []
    return [_natural(n, custom_names) for n in content if isinstance(n, str)]


def _reverse_panel_map(content: Any) -> dict[str, Any]:
    """PANEL_MAP class: link names plus ``_delimiter_`` / ``_tabBreak_N`` meta
    keys, all deterministic from the configuration — kept verbatim."""
    return dict(content) if isinstance(content, dict) else {}


def reverse_layout_payload(espo_type: str, content: Any, custom_names: set[str]) -> Any:
    """The YAML body for ``content`` under a ``layout: <espo_type>:`` key.

    :param custom_names: the entity's custom-field API names as the CRM
        spells them (``c``-prefixed on a native entity), reversed to natural
        names; every other name passes through.
    """
    cls = structure_class(espo_type)
    if cls is LayoutClass.PANELS:
        return {"panels": _reverse_panels(content, custom_names)}
    if cls is LayoutClass.COLUMNS:
        return {"columns": _reverse_columns(content, custom_names)}
    if cls is LayoutClass.FIELD_LIST:
        return _reverse_field_list(content, custom_names)
    if cls is LayoutClass.PANEL_MAP:
        return _reverse_panel_map(content)
    return content


# ---------------------------------------------------------------------------
# Field resolution against the emitted program
# ---------------------------------------------------------------------------


def _cell_name(cell: Any) -> str | None:
    if isinstance(cell, str):
        return cell
    if isinstance(cell, dict):
        name = cell.get("name")
        return name if isinstance(name, str) else None
    return None


def _raw_field_names(cls: LayoutClass, espo_type: str, content: Any) -> list[str]:
    """Field names as the CRM spelled them, in the verbatim payload."""
    names: list[str] = []
    if cls is LayoutClass.PANELS and isinstance(content, list):
        for panel in content:
            if not isinstance(panel, dict):
                continue
            for row in panel.get("rows") or []:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    name = _cell_name(cell)
                    if name:
                        names.append(name)
    elif cls is LayoutClass.COLUMNS and isinstance(content, list):
        for column in content:
            name = _cell_name(column)
            if name:
                names.append(name)
    elif (
        cls is LayoutClass.FIELD_LIST
        and espo_type in _FIELD_NAME_LISTS
        and isinstance(content, list)
    ):
        names.extend(n for n in content if isinstance(n, str))
    return names


def _body_field_names(cls: LayoutClass, espo_type: str, body: Any) -> list[str]:
    """Field names in the reversed (YAML) body, natural spelling."""
    names: list[str] = []
    if cls is LayoutClass.PANELS and isinstance(body, dict):
        for panel in body.get("panels") or []:
            for row in panel.get("rows") or []:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    name = _cell_name(cell)
                    if name:
                        names.append(name)
    elif cls is LayoutClass.COLUMNS and isinstance(body, dict):
        for column in body.get("columns") or []:
            if isinstance(column, dict) and isinstance(column.get("field"), str):
                names.append(column["field"])
    elif cls is LayoutClass.FIELD_LIST and espo_type in _FIELD_NAME_LISTS:
        names.extend(n for n in (body or []) if isinstance(n, str))
    return names


def _duplicate_panel_labels(body: Any) -> list[str]:
    """Labels two or more panels share. The deploy validator hard-rejects a
    duplicate panel label, and it counts a missing label as the empty one, so
    two unlabelled panels collide too."""
    seen: dict[str, int] = {}
    for panel in (body or {}).get("panels") or []:
        label = str(panel.get("label", "")) if isinstance(panel, dict) else ""
        seen[label] = seen.get(label, 0) + 1
    return sorted(label for label, count in seen.items() if count > 1)


def _base_type(entity_espo_type: str) -> str:
    """``BasePlus`` carries the ``Base`` platform fields; the rest are their
    own catalogue key."""
    return "Base" if entity_espo_type == "BasePlus" else entity_espo_type


def render_layout(
    layout_type: str,
    content: Any,
    *,
    entity_name: str,
    entity_espo_type: str,
    emitted_field_names: set[str],
    link_names: set[str],
) -> LayoutRender:
    """Translate one design layout into its YAML body, or refuse by name.

    :param layout_type: The neutral store type (``detail_small``).
    :param content: The verbatim CRM payload the design holds.
    :param entity_name: The owning entity's design name — ``Contact`` is a
        platform entity whose custom fields the CRM prefixes; ``Mentor
        Application`` is not.
    :param entity_espo_type: The ``type:`` the program emits for the entity
        (``Person`` / ``Company`` / ``Event`` / ``Base`` / ``BasePlus``), which
        decides the platform fields it carries without declaring them.
    :param emitted_field_names: Internal names of every field the program
        emits on this entity (the natural, un-prefixed spelling).
    :param link_names: Link names the program's ``relationships:`` blocks
        give this entity, on either side; a record view routinely places one.
    :raises LayoutRenderError: with the operator-facing reason.
    """
    espo_type = LAYOUT_TYPE_TO_ESPO.get(layout_type)
    if espo_type is None:
        if layout_type in PORTAL_LAYOUT_TYPE_TO_ESPO:
            raise LayoutRenderError(PORTAL_LAYOUT_DEFERRAL)
        raise LayoutRenderError(
            f"layout type {layout_type!r} has no deployable EspoCRM layout"
        )
    cls = structure_class(espo_type)
    if cls is None:  # pragma: no cover — every mapped type has a class
        raise LayoutRenderError(f"layout type {espo_type!r} has no structure class")
    if content in (None, False, [], {}, ""):
        raise LayoutRenderError(
            "the design holds no content for this layout — nothing to publish"
        )
    native = is_native_entity(entity_name)

    # On a platform entity the CRM prefixes the design's custom fields, so the
    # names that strip back to an emitted field are the ones to reverse. On a
    # custom entity fields keep their natural names and nothing is stripped —
    # a name that merely begins with ``c`` + capital is its own identity there
    # (REQ-342), which is the ``entity_is_native`` switch on the stripper.
    raw_names = _raw_field_names(cls, espo_type, content)
    custom_names: set[str] = set()
    if native:
        for raw in raw_names:
            natural = strip_field_c_prefix(raw, entity_is_native=True)
            if natural != raw and natural in emitted_field_names:
                custom_names.add(raw)
    body = reverse_layout_payload(espo_type, content, custom_names)

    names = _body_field_names(cls, espo_type, body)
    known = set(emitted_field_names) | set(link_names) | set(SYSTEM_FIELDS)
    known |= get_native_fields_for_type(_base_type(entity_espo_type))
    unresolved: list[str] = []
    for name in names:
        if name in known:
            continue
        if native:
            # A platform entity carries fields the program never declares
            # (its own built-ins and links): those pass through as the CRM
            # spelled them. A name still wearing the platform's custom-field
            # prefix is the exception — it is a custom field the design does
            # not emit, and the engine would recreate nothing for it.
            if strip_field_c_prefix(name, entity_is_native=True) != name:
                unresolved.append(name)
            continue
        unresolved.append(name)
    if unresolved:
        listed = ", ".join(sorted(set(unresolved)))
        raise LayoutRenderError(
            f"places field(s) the program does not emit on {entity_name}: "
            f"{listed} — confirm the field(s) in the design, or remove them "
            "from the layout"
        )
    if cls is LayoutClass.PANELS:
        duplicates = _duplicate_panel_labels(body)
        if duplicates:
            shown = ", ".join(repr(d) for d in duplicates)
            raise LayoutRenderError(
                f"two or more panels share the label {shown}; the deploy "
                "validator rejects a duplicate panel label — give each panel "
                "its own label in the design"
            )
    return LayoutRender(espo_type=espo_type, body=body, field_names=names)
