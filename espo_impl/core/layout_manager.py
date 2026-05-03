"""Layout management — build, apply, and verify EspoCRM layouts.

Confirmed API endpoints:
  Read:  GET  /api/v1/Layout/action/getOriginal?scope={entity}&name={type}
  Save:  PUT  /api/v1/{entity}/layout/{type}

Both use the EspoCRM internal entity name (C-prefixed for custom entities).
"""

import logging
from collections.abc import Callable
from typing import Any

from espo_impl.core.api_client import EspoAdminClient, _format_error_detail
from espo_impl.core.condition_expression import render_condition
from espo_impl.core.models import (
    EntityDefinition,
    EntityLayoutStatus,
    FieldDefinition,
    LayoutResult,
    LayoutSpec,
    PanelSpec,
)
from espo_impl.ui.confirm_delete_dialog import (
    NATIVE_ENTITIES,
    get_espo_entity_name,
)

logger = logging.getLogger(__name__)

OutputCallback = Callable[[str, str], None]

# Field types that get their own full-width row in auto-generated layouts
FULL_WIDTH_TYPES: set[str] = {"wysiwyg", "text", "address"}


class LayoutManagerError(Exception):
    """Raised when the API returns 401 Unauthorized."""


class LayoutManager:
    """Orchestrates layout check/apply/verify operations.

    :param client: EspoCRM admin API client.
    :param output_fn: Callback for emitting output messages (message, color).
    """

    def __init__(
        self,
        client: EspoAdminClient,
        output_fn: OutputCallback,
    ) -> None:
        self.client = client
        self.output_fn = output_fn

    def process_layouts(
        self,
        entity_def: EntityDefinition,
        field_definitions: list[FieldDefinition],
    ) -> list[LayoutResult]:
        """Process all layouts defined for an entity.

        :param entity_def: Entity definition with layouts.
        :param field_definitions: Field definitions for c-prefix resolution.
        :returns: List of layout results.
        """
        results: list[LayoutResult] = []
        espo_name = get_espo_entity_name(entity_def.name)

        # EspoCRM auto-applies the 'c' prefix to custom fields only
        # when their parent entity is native (Contact, Account, Lead,
        # etc.). On custom entities — already C-prefixed at the entity
        # level (CEngagement, CContribution, ...) — custom fields are
        # stored with their natural names, no per-field prefix.
        # Build the c-prefix candidate set accordingly: populated for
        # native parents, empty for custom parents. With an empty set,
        # `_resolve_field_name` short-circuits on every cell and the
        # layout references the actual stored field names.
        if entity_def.name in NATIVE_ENTITIES:
            custom_field_names = {f.name for f in field_definitions}
        else:
            custom_field_names = set()

        # Default True. Entity-level setting can opt out (e.g. when
        # `name` is supplied by a formula or workflow).
        auto_place_name = True
        if entity_def.settings is not None:
            if entity_def.settings.autoPlaceName is False:
                auto_place_name = False

        for layout_type, layout_spec in entity_def.layouts.items():
            try:
                result = self._process_one_layout(
                    entity_def.name,
                    espo_name,
                    layout_type,
                    layout_spec,
                    field_definitions,
                    custom_field_names,
                    auto_place_name=auto_place_name,
                )
            except LayoutManagerError:
                self.output_fn(
                    "[ERROR]   Authentication failed (HTTP 401) — aborting",
                    "red",
                )
                results.append(LayoutResult(
                    entity=entity_def.name,
                    layout_type=layout_type,
                    status=EntityLayoutStatus.ERROR,
                    error="Authentication failed (HTTP 401)",
                ))
                return results
            else:
                results.append(result)

        return results

    def _process_one_layout(
        self,
        yaml_name: str,
        espo_name: str,
        layout_type: str,
        layout_spec: LayoutSpec,
        field_definitions: list[FieldDefinition],
        custom_field_names: set[str],
        auto_place_name: bool,
    ) -> LayoutResult:
        """Process a single layout: check → apply → verify.

        :param yaml_name: YAML entity name (for display).
        :param espo_name: EspoCRM entity name (for API calls).
        :param layout_type: Layout type (detail, edit, list).
        :param layout_spec: Layout specification.
        :param field_definitions: Field definitions for auto-row generation.
        :param custom_field_names: Set of custom field names (need c-prefix).
        :param auto_place_name: Whether to auto-prepend `name` to
            detail/edit layouts that do not place it explicitly.
        :returns: LayoutResult.
        :raises LayoutManagerError: If 401 received.
        """
        prefix = f"{yaml_name}.{layout_type}"
        self.output_fn(f"[LAYOUT]  {prefix} ... CHECKING", "white")

        # Build the desired payload
        payload = self._build_payload(
            layout_spec, field_definitions, custom_field_names,
            auto_place_name=auto_place_name,
        )

        # Fetch current layout
        status_code, current = self.client.get_layout(espo_name, layout_type)

        if status_code == 401:
            raise LayoutManagerError()

        if status_code < 0 or (status_code >= 400 and status_code != 404):
            self.output_fn(
                f"[LAYOUT]  {prefix} ... ERROR (HTTP {status_code})", "red"
            )
            self.output_fn(
                f"          {_format_error_detail(current)}", "red"
            )
            return LayoutResult(
                entity=yaml_name,
                layout_type=layout_type,
                status=EntityLayoutStatus.ERROR,
                error=f"HTTP {status_code}",
            )

        # Compare
        if self._layouts_match(payload, current):
            self.output_fn(f"[LAYOUT]  {prefix} ... MATCHES", "gray")
            self.output_fn(
                f"[LAYOUT]  {prefix} ... NO CHANGES NEEDED", "gray"
            )
            return LayoutResult(
                entity=yaml_name,
                layout_type=layout_type,
                status=EntityLayoutStatus.SKIPPED,
            )

        # Apply
        self.output_fn(f"[LAYOUT]  {prefix} ... APPLYING", "white")
        put_status, put_body = self.client.save_layout(
            espo_name, layout_type, payload
        )

        if put_status == 401:
            raise LayoutManagerError()

        if put_status < 0 or put_status >= 400:
            self.output_fn(
                f"[LAYOUT]  {prefix} ... ERROR (HTTP {put_status})", "red"
            )
            self.output_fn(
                f"          {_format_error_detail(put_body)}", "red"
            )
            return LayoutResult(
                entity=yaml_name,
                layout_type=layout_type,
                status=EntityLayoutStatus.ERROR,
                error=f"HTTP {put_status}",
            )

        self.output_fn(f"[LAYOUT]  {prefix} ... UPDATED OK", "green")
        return LayoutResult(
            entity=yaml_name,
            layout_type=layout_type,
            status=EntityLayoutStatus.UPDATED,
            verified=True,
        )

    def _build_payload(
        self,
        layout_spec: LayoutSpec,
        field_definitions: list[FieldDefinition],
        custom_field_names: set[str],
        auto_place_name: bool,
    ) -> list[dict[str, Any]] | list[Any]:
        """Convert a LayoutSpec to the EspoCRM API payload.

        :param layout_spec: Layout specification.
        :param field_definitions: Field definitions for auto-row generation.
        :param custom_field_names: Set of custom field names (need c-prefix).
        :param auto_place_name: Whether to auto-prepend `name` to
            detail/edit layouts that do not place it explicitly.
            Ignored for list layouts (list columns declare `name`
            explicitly in YAML).
        :returns: API payload (list of panels for detail/edit, list of columns for list).
        """
        if layout_spec.layout_type == "list":
            return self._build_list_payload(
                layout_spec, custom_field_names
            )
        return self._build_detail_payload(
            layout_spec, field_definitions, custom_field_names,
            auto_place_name=auto_place_name,
        )

    def _build_list_payload(
        self,
        layout_spec: LayoutSpec,
        custom_field_names: set[str],
    ) -> list[dict[str, Any]]:
        """Build a list layout payload.

        :param layout_spec: Layout specification with columns.
        :param custom_field_names: Set of custom field names.
        :returns: List of column dicts.
        """
        result: list[dict[str, Any]] = []
        for col in layout_spec.columns or []:
            api_name = self._resolve_field_name(
                col.field, custom_field_names
            )
            entry: dict[str, Any] = {"name": api_name}
            if col.width is not None:
                entry["width"] = col.width
            result.append(entry)
        return result

    def _build_detail_payload(
        self,
        layout_spec: LayoutSpec,
        field_definitions: list[FieldDefinition],
        custom_field_names: set[str],
        auto_place_name: bool,
    ) -> list[dict[str, Any]]:
        """Build a detail/edit layout payload.

        Expands tab-based panels into multiple API panel objects.

        :param layout_spec: Layout specification with panels.
        :param field_definitions: Field definitions for auto-row generation.
        :param custom_field_names: Set of custom field names.
        :param auto_place_name: Whether to auto-prepend `name` when
            it is not explicitly placed anywhere in the panels.
        :returns: List of panel dicts.
        """
        result: list[dict[str, Any]] = []

        for panel in layout_spec.panels or []:
            if panel.tabs:
                expanded = self._expand_tabs(
                    panel, field_definitions, custom_field_names
                )
                result.extend(expanded)
            else:
                result.append(
                    self._build_panel_dict(
                        panel, custom_field_names
                    )
                )

        if auto_place_name:
            self._ensure_name_placed(result, custom_field_names)

        return result

    def _build_panel_dict(
        self,
        panel: PanelSpec,
        custom_field_names: set[str],
        rows_override: list | None = None,
    ) -> dict[str, Any]:
        """Build a single panel dict for the API payload.

        :param panel: Panel specification.
        :param custom_field_names: Set of custom field names.
        :param rows_override: Override rows (for tab expansion).
        :returns: Panel dict.
        """
        rows = rows_override if rows_override is not None else panel.rows
        api_rows = self._build_rows(rows or [], custom_field_names)

        # Determine dynamic-logic visibility:
        # visibleWhen (v1.1) takes precedence over dynamicLogicVisible (deprecated)
        if panel.visible_when is not None:
            dynamic_vis = self._build_visible_when(
                panel.visible_when, custom_field_names
            )
        else:
            dynamic_vis = self._build_dynamic_logic(
                panel.dynamicLogicVisible, custom_field_names
            )

        panel_dict: dict[str, Any] = {
            "customLabel": panel.label,
            "tabBreak": panel.tabBreak,
            "tabLabel": panel.tabLabel,
            "style": panel.style,
            "hidden": panel.hidden,
            "noteText": None,
            "noteStyle": "info",
            "dynamicLogicVisible": dynamic_vis,
            "dynamicLogicStyled": None,
            "rows": api_rows,
        }
        return panel_dict

    def _expand_tabs(
        self,
        panel: PanelSpec,
        field_definitions: list[FieldDefinition],
        custom_field_names: set[str],
    ) -> list[dict[str, Any]]:
        """Expand a panel with tabs into multiple API panel objects.

        :param panel: Panel with tabs.
        :param field_definitions: Field definitions for auto-row generation.
        :param custom_field_names: Set of custom field names.
        :returns: List of expanded panel dicts.
        """
        result: list[dict[str, Any]] = []

        for i, tab in enumerate(panel.tabs or []):
            if tab.rows is not None:
                rows = tab.rows
            else:
                rows = self._auto_generate_rows(
                    tab.category, field_definitions, custom_field_names
                )

            # visibleWhen (v1.1) takes precedence
            if panel.visible_when is not None:
                dynamic_vis = self._build_visible_when(
                    panel.visible_when, custom_field_names
                )
            else:
                dynamic_vis = self._build_dynamic_logic(
                    panel.dynamicLogicVisible, custom_field_names
                )

            is_first = i == 0
            tab_panel = {
                "customLabel": tab.label,
                "tabBreak": panel.tabBreak if is_first else False,
                "tabLabel": panel.tabLabel if is_first else None,
                "style": panel.style,
                "hidden": panel.hidden,
                "noteText": None,
                "noteStyle": "info",
                "dynamicLogicVisible": dynamic_vis,
                "dynamicLogicStyled": None,
                "rows": self._build_rows(rows, custom_field_names),
            }
            result.append(tab_panel)

        return result

    def _auto_generate_rows(
        self,
        category: str,
        field_definitions: list[FieldDefinition],
        custom_field_names: set[str],
    ) -> list[list]:
        """Generate rows from fields matching a category.

        Rules:
        - 2 fields per row for normal fields
        - wysiwyg/text/address fields get their own full-width row
        - Last row padded with None if odd number of normal fields

        :param category: Category to filter fields by.
        :param field_definitions: All field definitions.
        :param custom_field_names: Set of custom field names.
        :returns: List of rows (each row is a list of field names or None).
        """
        fields = [
            f for f in field_definitions if f.category == category
        ]

        rows: list[list] = []
        normal_buffer: list[str] = []

        for f in fields:
            if f.type in FULL_WIDTH_TYPES:
                # Flush normal buffer first
                if normal_buffer:
                    rows.extend(self._pair_fields(normal_buffer))
                    normal_buffer = []
                rows.append([f.name])
            else:
                normal_buffer.append(f.name)

        # Flush remaining normal fields
        if normal_buffer:
            rows.extend(self._pair_fields(normal_buffer))

        return rows

    @staticmethod
    def _pair_fields(names: list[str]) -> list[list]:
        """Pair field names into rows of 2, padding the last if odd.

        :param names: List of field names.
        :returns: List of rows.
        """
        rows: list[list] = []
        for i in range(0, len(names), 2):
            pair = names[i:i + 2]
            if len(pair) == 1:
                pair.append(None)
            rows.append(pair)
        return rows

    def _build_rows(
        self,
        rows: list,
        custom_field_names: set[str],
    ) -> list[list]:
        """Convert row definitions to API format.

        :param rows: List of rows from YAML or auto-generation.
        :param custom_field_names: Set of custom field names.
        :returns: API-formatted rows.
        """
        api_rows: list[list] = []
        for row in rows:
            if not isinstance(row, list):
                continue
            api_row: list = []
            for cell in row:
                if cell is None or cell is False:
                    api_row.append(False)
                elif isinstance(cell, str):
                    api_name = self._resolve_field_name(
                        cell, custom_field_names
                    )
                    api_row.append({"name": api_name})
                elif isinstance(cell, dict):
                    api_row.append(cell)
                else:
                    api_row.append(False)
            api_rows.append(api_row)
        return api_rows

    def _build_visible_when(
        self,
        condition_node: Any,
        custom_field_names: set[str],
    ) -> dict:
        """Translate a parsed visibleWhen condition to API format.

        Renders the condition expression and resolves field names to
        c-prefixed API names.

        :param condition_node: Parsed condition AST.
        :param custom_field_names: Set of custom field names.
        :returns: API-formatted dynamic logic dict.
        """
        rendered = render_condition(condition_node)
        return self._resolve_condition_fields(rendered, custom_field_names)

    def _resolve_condition_fields(
        self,
        rendered: Any,
        custom_field_names: set[str],
    ) -> Any:
        """Recursively resolve field names in a rendered condition to API names.

        :param rendered: Rendered condition (dict or list).
        :param custom_field_names: Set of custom field names.
        :returns: Condition with resolved field names.
        """
        if isinstance(rendered, dict):
            result = {}
            for key, val in rendered.items():
                if key == "field":
                    result[key] = self._resolve_field_name(
                        val, custom_field_names
                    )
                elif key in ("all", "any"):
                    result[key] = [
                        self._resolve_condition_fields(item, custom_field_names)
                        for item in val
                    ]
                else:
                    result[key] = val
            return result
        if isinstance(rendered, list):
            return [
                self._resolve_condition_fields(item, custom_field_names)
                for item in rendered
            ]
        return rendered

    def _build_dynamic_logic(
        self,
        spec: dict | None,
        custom_field_names: set[str],
    ) -> dict | None:
        """Translate YAML dynamic logic shorthand to API format.

        YAML: {attribute: "contactType", value: "Mentor"}
        API:  {conditionGroup: [{type: "equals", attribute: "cContactType", value: "Mentor"}]}

        :param spec: Dynamic logic from YAML (or None).
        :param custom_field_names: Set of custom field names.
        :returns: API-formatted dynamic logic (or None).
        """
        if not spec:
            return None

        attribute = spec.get("attribute", "")
        api_attribute = self._resolve_field_name(
            attribute, custom_field_names
        )

        return {
            "conditionGroup": [
                {
                    "type": spec.get("type", "equals"),
                    "attribute": api_attribute,
                    "value": spec.get("value"),
                }
            ]
        }

    @staticmethod
    def _resolve_field_name(
        name: str, custom_field_names: set[str]
    ) -> str:
        """Apply c-prefix to custom field names, pass other names through.

        :param name: Field name from YAML.
        :param custom_field_names: Names that should be c-prefixed.
            Callers must populate this set only when the parent entity
            is native (Contact, Account, etc.). For custom entities,
            pass an empty set — EspoCRM stores custom fields on
            custom entities under their natural names, with no
            per-field prefix.
        :returns: API field name.
        """
        if name in custom_field_names:
            return f"c{name[0].upper()}{name[1:]}"
        return name

    def _ensure_name_placed(
        self,
        panels: list[dict[str, Any]],
        custom_field_names: set[str],
    ) -> None:
        """Prepend a `name` row to the first always-visible panel
        if `name` is not already placed somewhere in the layout.

        EspoCRM treats `name` as required on every entity. YAMLs
        that express their detail layout via category-driven `tabs:`
        blocks routinely fail to place `name` (it has no category),
        producing a create form on which the user cannot enter the
        required value. This helper guarantees `name` lands on the
        layout.

        Mutates `panels` in place. No-op when:
            - `panels` is empty (YAML-shape problem, not ours);
            - any cell anywhere in `panels` already resolves to
              `name`.

        :param panels: Built detail-layout panel list.
        :param custom_field_names: Set of custom field names (for
            symmetry with the rest of the layout code; `name` is
            always native and resolves to itself).
        """
        if not panels:
            return

        target_name = self._resolve_field_name("name", custom_field_names)

        # Detect existing placement.
        for panel in panels:
            for row in panel.get("rows") or []:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    cell_name = (
                        cell.get("name")
                        if isinstance(cell, dict)
                        else cell
                    )
                    if cell_name == target_name:
                        return

        # Pick insertion target: first panel without
        # `dynamicLogicVisible`. Fall back to first panel.
        target = next(
            (p for p in panels if not p.get("dynamicLogicVisible")),
            panels[0],
        )
        existing_rows = target.get("rows") or []
        target["rows"] = [[{"name": target_name}], *existing_rows]

    @staticmethod
    def _layouts_match(
        desired: list, current: Any
    ) -> bool:
        """Compare desired layout payload to current API response.

        :param desired: Built payload.
        :param current: Current layout from API.
        :returns: True if they match structurally.
        """
        if not isinstance(current, list):
            return False
        if len(desired) != len(current):
            return False

        for d_item, c_item in zip(desired, current, strict=True):
            if isinstance(d_item, dict) and isinstance(c_item, dict):
                # List-layout columns are flat dicts shaped like
                # {"name": "amount", "width": 20} with no rows or
                # customLabel — they must be compared on `name` and
                # `width` directly. Detail-layout panel dicts do not
                # carry these keys at the top level, so for those
                # items both sides return None and these checks are
                # no-ops.
                if d_item.get("name") != c_item.get("name"):
                    return False
                if d_item.get("width") != c_item.get("width"):
                    return False
                # Compare panel: check customLabel and rows
                if d_item.get("customLabel") != c_item.get("customLabel"):
                    return False
                d_rows = d_item.get("rows", [])
                c_rows = c_item.get("rows", [])
                if len(d_rows) != len(c_rows):
                    return False
                for d_row, c_row in zip(d_rows, c_rows, strict=True):
                    if not isinstance(d_row, list) or not isinstance(c_row, list):
                        if d_row != c_row:
                            return False
                        continue
                    if len(d_row) != len(c_row):
                        return False
                    for d_cell, c_cell in zip(d_row, c_row, strict=True):
                        d_name = (
                            d_cell.get("name")
                            if isinstance(d_cell, dict)
                            else d_cell
                        )
                        c_name = (
                            c_cell.get("name")
                            if isinstance(c_cell, dict)
                            else c_cell
                        )
                        if d_name != c_name:
                            return False
                # Check tabBreak/tabLabel
                if d_item.get("tabBreak") != c_item.get("tabBreak"):
                    return False
                if d_item.get("tabLabel") != c_item.get("tabLabel"):
                    return False
            elif d_item != c_item:
                return False

        return True
