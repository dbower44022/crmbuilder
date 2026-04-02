# CRM Builder — Layout Management Implementation Reference

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Requirements:** PRDs/features/feat-layouts.md
**Maintained By:** Claude Code

---

## 1. Purpose

This document describes the implementation of layout management in
CRM Builder — the `LayoutManager` class, EspoCRM API endpoints,
panel payload construction, tab expansion, auto-row generation, and
dynamic logic translation.

---

## 2. File Location

```
espo_impl/core/layout_manager.py
```

---

## 3. API Endpoints

| Operation | Method | Endpoint | Notes |
|---|---|---|---|
| Read layout | GET | `/api/v1/Layout/action/getOriginal?scope={Entity}&name={type}` | Returns original (custom) layout |
| Save layout | PUT | `/api/v1/{Entity}/layout/{type}` | Replaces entire layout |

Note: GET and PUT use different URL patterns. Both use the
C-prefixed internal entity name.

Layout types: `detail`, `edit`, `list`

---

## 4. LayoutManager Class

```python
class LayoutManager:
    def __init__(self, client: EspoAdminClient, output_cb: Callable):
        self.client = client
        self.output = output_cb
```

### 4.1 Main Entry Point

```python
def process_layouts(
    self,
    entity_def: EntityDefinition,
    field_defs: list[FieldDefinition],
) -> list[LayoutResult]:
    """
    Process all layout types defined for the entity.
    Returns a list of LayoutResult (one per layout type).
    """
    if not entity_def.layout:
        return []

    results = []
    espo_name = get_espo_entity_name(entity_def.name)
    custom_field_names = {f.name for f in field_defs}

    for layout_type, layout_spec in entity_def.layout.items():
        result = self._process_layout(
            espo_name, entity_def.name, layout_type,
            layout_spec, field_defs, custom_field_names
        )
        results.append(result)
    return results
```

### 4.2 Layout Processing Cycle

```python
def _process_layout(
    self, espo_name, yaml_name, layout_type,
    layout_spec, field_defs, custom_field_names
) -> LayoutResult:

    self.output(f"[LAYOUT]  {yaml_name}.{layout_type} ... CHECKING", "white")
    status, current = self.client.get_layout(espo_name, layout_type)

    if status != 200:
        self.output(f"[LAYOUT]  {yaml_name}.{layout_type} "
                    f"... ERROR (HTTP {status})", "red")
        return LayoutResult(yaml_name, layout_type, LayoutStatus.ERROR)

    payload = self._build_payload(layout_type, layout_spec,
                                  field_defs, custom_field_names)

    if self._layouts_match(current, payload):
        self.output(f"[LAYOUT]  {yaml_name}.{layout_type} ... MATCHES", "gray")
        self.output(f"[LAYOUT]  {yaml_name}.{layout_type} "
                    f"... SKIPPED (no changes needed)", "gray")
        return LayoutResult(yaml_name, layout_type, LayoutStatus.SKIPPED)

    self.output(f"[LAYOUT]  {yaml_name}.{layout_type} ... DIFFERS", "white")
    status, body = self.client.save_layout(espo_name, layout_type, payload)

    if status == 200:
        self.output(f"[LAYOUT]  {yaml_name}.{layout_type} "
                    f"... UPDATED OK", "green")
        return LayoutResult(yaml_name, layout_type, LayoutStatus.UPDATED)

    self.output(f"[LAYOUT]  {yaml_name}.{layout_type} "
                f"... ERROR (HTTP {status})", "red")
    return LayoutResult(yaml_name, layout_type, LayoutStatus.ERROR,
                        error=f"HTTP {status}: {body}")
```

---

## 5. Payload Construction

### 5.1 Detail Layout

```python
def _build_detail_payload(
    self, panels_spec: list, field_defs: list, custom_field_names: set
) -> list[dict]:
    """
    Returns a list of panel dicts in EspoCRM API format.
    Expands tab-based panels into multiple panel objects.
    """
    result = []
    for panel_spec in panels_spec:
        if "tabs" in panel_spec:
            result.extend(
                self._expand_tabs(panel_spec, field_defs, custom_field_names)
            )
        else:
            result.append(
                self._build_panel(panel_spec, custom_field_names)
            )
    return result
```

### 5.2 Panel Object Structure

Each panel is translated to the EspoCRM API format:

```python
def _build_panel(self, panel_spec: dict, custom_field_names: set) -> dict:
    panel = {
        "customLabel": panel_spec["label"],
        "tabBreak": panel_spec.get("tabBreak", False),
        "tabLabel": panel_spec.get("tabLabel"),
        "style": panel_spec.get("style", "default"),
        "hidden": panel_spec.get("hidden", False),
        "noteText": None,
        "noteStyle": "info",
        "dynamicLogicVisible": self._translate_dynamic_logic(
            panel_spec.get("dynamicLogicVisible"),
            custom_field_names,
        ),
        "dynamicLogicStyled": None,
        "rows": self._build_rows(
            panel_spec.get("rows", []), custom_field_names
        ),
    }
    return panel
```

### 5.3 Row and Cell Construction

```python
def _build_rows(
    self, rows_spec: list, custom_field_names: set
) -> list[list]:
    rows = []
    for row in rows_spec:
        cells = []
        for cell in row:
            if cell is None:
                cells.append(False)          # null → false in API
            else:
                cells.append({
                    "name": self._resolve_field_name(cell, custom_field_names)
                })
        rows.append(cells)
    return rows
```

```python
def _resolve_field_name(self, name: str, custom_field_names: set) -> str:
    """Apply c-prefix to custom fields; pass native fields through."""
    if name in custom_field_names:
        return f"c{name[0].upper()}{name[1:]}"
    return name
```

---

## 6. Tab Expansion

When a panel has `tabs` instead of `rows`, it expands into multiple
API panel objects:

```python
def _expand_tabs(
    self, panel_spec: dict, field_defs: list, custom_field_names: set
) -> list[dict]:
    """
    Expands a panel with tabs into multiple API panel objects.

    First tab:
      - inherits parent tabBreak and tabLabel
      - inherits parent dynamicLogicVisible

    Subsequent tabs:
      - tabBreak: False
      - tabLabel: None
      - inherit parent dynamicLogicVisible
    """
    tabs = panel_spec["tabs"]
    dynamic_logic = self._translate_dynamic_logic(
        panel_spec.get("dynamicLogicVisible"),
        custom_field_names,
    )
    result = []

    for i, tab in enumerate(tabs):
        is_first = (i == 0)
        rows = self._auto_rows(tab["category"], field_defs, custom_field_names)

        panel = {
            "customLabel": tab["label"],
            "tabBreak": panel_spec.get("tabBreak", False) if is_first else False,
            "tabLabel": panel_spec.get("tabLabel") if is_first else None,
            "style": panel_spec.get("style", "default"),
            "hidden": panel_spec.get("hidden", False),
            "noteText": None,
            "noteStyle": "info",
            "dynamicLogicVisible": dynamic_logic,
            "dynamicLogicStyled": None,
            "rows": rows,
        }
        result.append(panel)

    return result
```

---

## 7. Auto-Row Generation

```python
def _auto_rows(
    self, category: str, field_defs: list, custom_field_names: set
) -> list[list]:
    """
    Collect fields matching category, arrange into rows of 2.
    Full-width types (wysiwyg, text, address) get their own row.
    """
    FULL_WIDTH_TYPES = {"wysiwyg", "text", "address"}

    category_fields = [
        f for f in field_defs if f.category == category
    ]

    rows = []
    i = 0
    while i < len(category_fields):
        field = category_fields[i]
        resolved = self._resolve_field_name(field.name, custom_field_names)
        cell = {"name": resolved}

        if field.type in FULL_WIDTH_TYPES:
            rows.append([cell, False])
            i += 1
        else:
            if i + 1 < len(category_fields) and \
               category_fields[i + 1].type not in FULL_WIDTH_TYPES:
                next_field = category_fields[i + 1]
                next_resolved = self._resolve_field_name(
                    next_field.name, custom_field_names
                )
                rows.append([cell, {"name": next_resolved}])
                i += 2
            else:
                rows.append([cell, False])
                i += 1

    return rows
```

---

## 8. Dynamic Logic Translation

The YAML shorthand is translated to the EspoCRM API format:

```python
def _translate_dynamic_logic(
    self, spec: dict | None, custom_field_names: set
) -> dict | None:
    """
    YAML:  {"attribute": "contactType", "value": "Mentor"}

    API:   {"conditionGroup": [
              {"type": "equals", "attribute": "cContactType", "value": "Mentor"}
            ]}
    """
    if not spec:
        return None

    attribute = self._resolve_field_name(
        spec["attribute"], custom_field_names
    )
    return {
        "conditionGroup": [{
            "type": "equals",
            "attribute": attribute,
            "value": spec["value"],
        }]
    }
```

---

## 9. List Layout

List layouts use a simpler structure — an array of column objects:

```python
def _build_list_payload(
    self, columns_spec: list, custom_field_names: set
) -> list[dict]:
    return [
        {
            "name": self._resolve_field_name(col["field"], custom_field_names),
            "width": col.get("width"),
        }
        for col in columns_spec
    ]
```

---

## 10. Data Models

```python
class LayoutStatus(Enum):
    UPDATED = "updated"
    SKIPPED = "skipped"
    ERROR = "error"

@dataclass
class LayoutResult:
    entity: str
    layout_type: str
    status: LayoutStatus
    error: str | None = None
```

---

## 11. API Client Methods

```python
def get_layout(
    self, entity: str, layout_type: str
) -> tuple[int, list | None]:
    return self._request("GET",
        f"Layout/action/getOriginal?scope={entity}&name={layout_type}")

def save_layout(
    self, entity: str, layout_type: str, payload: list
) -> tuple[int, dict | None]:
    return self._request("PUT",
        f"{entity}/layout/{layout_type}", json=payload)
```

---

## 12. Layout Comparison

Layouts are compared by serializing both the current and desired
payloads to JSON and doing a string comparison. This is simpler and
more reliable than deep-comparing nested panel structures:

```python
def _layouts_match(self, current: list, desired: list) -> bool:
    import json
    return json.dumps(current, sort_keys=True) == \
           json.dumps(desired, sort_keys=True)
```

---

## 13. Error Handling

| Error | Behavior |
|---|---|
| HTTP 401 | Raises `LayoutManagerError` — aborts entire run |
| HTTP 403 | Logs error, marks as ERROR, continues to next layout |
| HTTP 4xx/5xx on PUT | Logs error and response body, marks as ERROR, continues |
| Category not found | Caught during validation, prevents run |
| Network error | Logs error, marks as ERROR, continues |

```python
class LayoutManagerError(Exception):
    """Raised on HTTP 401 to abort the entire run."""
```

---

## 14. Testing

`layout_manager.py` is covered by `tests/test_layout_manager.py`:

| Test Area | Cases |
|---|---|
| Detail layout — explicit rows | Rows translated correctly, null→false, c-prefix applied |
| Detail layout — tab expansion | First tab gets tabBreak/tabLabel, subsequent do not |
| Auto-row generation | Two per row, full-width types get own row |
| Dynamic logic translation | Attribute gets c-prefix, conditionGroup format |
| List layout | Columns translated correctly |
| Layout matches — skip | PUT not called |
| Layout differs — update | PUT called with correct payload |
| HTTP 401 | `LayoutManagerError` raised |
| HTTP 5xx | ERROR result, continues |

Mocking pattern:

```python
def test_tab_expansion_first_tab_inherits_tab_break():
    client = MagicMock()
    client.get_layout.return_value = (200, [])
    client.save_layout.return_value = (200, {})

    field_defs = [
        FieldDefinition("firstName", "varchar", "First Name",
                        category="Identity"),
        FieldDefinition("lastName", "varchar", "Last Name",
                        category="Identity"),
    ]
    panel_spec = {
        "label": "Mentor Details",
        "tabBreak": True,
        "tabLabel": "Mentor",
        "tabs": [{"label": "Identity", "category": "Identity"}],
    }

    mgr = LayoutManager(client, lambda m, c: None)
    panels = mgr._expand_tabs(panel_spec, field_defs, {"firstName", "lastName"})

    assert len(panels) == 1
    assert panels[0]["tabBreak"] is True
    assert panels[0]["tabLabel"] == "Mentor"
    assert panels[0]["customLabel"] == "Identity"
```
