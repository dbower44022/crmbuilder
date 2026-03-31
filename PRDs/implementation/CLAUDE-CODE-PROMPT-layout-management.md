# Claude Code Prompt — Layout Management Implementation

## Context

The CRM Builder currently handles entity creation/deletion and
field management. We are now adding Phase 2: layout management — the ability to
define and deploy detail view layouts and list view column definitions via YAML
program files.

The full technical specification is in two documents:
- `PRDs/crmbuilder-spec-espocrm-impl.md` — main tool spec (v1.4)
- `PRDs/crmbuilder-spec-layout-management.md` — layout management spec (read this first)

Read both documents carefully before writing any code.

---

## Overview of Changes

1. Add `category` property to `FieldDefinition` model
2. Add `PanelSpec`, `TabSpec`, `ColumnSpec`, `LayoutSpec` models
3. Add `layout` parsing to `EntityDefinition` in `config_loader.py`
4. Add validation for layout definitions
5. Create `core/layout_manager.py`
6. Update `workers/run_worker.py` to process layouts after fields
7. Update output panel messages for layout operations
8. Update spec and guides
9. Add tests

Implement in the order listed above. Confirm with me after each task before
proceeding to the next.

---

## Task 1 — Update `core/models.py`

### 1a — Add `category` to FieldDefinition

```python
category: str | None = None    # UI grouping / tab category
```

### 1b — Add layout models

```python
@dataclass
class TabSpec:
    """A sub-tab within a panel, populated by field category."""
    label: str
    category: str
    rows: list | None = None    # explicit rows override (optional)


@dataclass
class ColumnSpec:
    """A column in a list view layout."""
    field: str
    width: int | None = None


@dataclass
class PanelSpec:
    """A panel in a detail/edit layout."""
    label: str
    tabBreak: bool = False
    tabLabel: str | None = None
    style: str = "default"
    hidden: bool = False
    dynamicLogicVisible: dict | None = None
    rows: list | None = None      # explicit rows — list of lists of field names or None
    tabs: list[TabSpec] | None = None   # sub-tabs — mutually exclusive with rows


@dataclass
class LayoutSpec:
    """Layout definition for one layout type (detail, edit, or list)."""
    layout_type: str              # "detail", "edit", or "list"
    panels: list[PanelSpec] | None = None   # for detail/edit
    columns: list[ColumnSpec] | None = None  # for list


class EntityLayoutStatus(Enum):
    """Outcome status for a layout operation."""
    UPDATED = "updated"
    SKIPPED = "skipped"
    VERIFICATION_FAILED = "verification_failed"
    ERROR = "error"


@dataclass
class LayoutResult:
    """Result of processing a single layout."""
    entity: str
    layout_type: str
    status: EntityLayoutStatus
    verified: bool = False
    error: str | None = None
```

Also update `RunSummary` to include layout counts:
```python
layouts_updated: int = 0
layouts_skipped: int = 0
layouts_failed: int = 0
```

And update `RunReport` to include layout results:
```python
layout_results: list[LayoutResult] = field(default_factory=list)
```

---

## Task 2 — Update `core/config_loader.py`

### 2a — Parse `category` on fields

In `_parse_field()`, add:
```python
category=data.get("category"),
```

### 2b — Parse `layout` section on entity blocks

In `load_program()`, after parsing fields for each entity, parse the optional
`layout` block:

```python
layouts: dict[str, LayoutSpec] = {}
raw_layout = entity_data.get("layout", {})
for layout_type, layout_data in raw_layout.items():
    layouts[layout_type] = self._parse_layout(layout_type, layout_data)
entity_def.layouts = layouts
```

Add `_parse_layout()`, `_parse_panel()`, `_parse_tab()`, `_parse_column()`
helper methods.

### 2c — Add validation for layouts

In `validate_program()`, for each entity with layouts:

- Each panel must have either `rows` or `tabs`, not both
- Each panel with `tabBreak: true` must have a `tabLabel`
- Each `TabSpec.category` must match at least one field's `category` in that entity
- Field names in explicit `rows` must exist in the entity's field list
- No duplicate panel labels within a layout
- List layouts must have `columns`, not `panels`

Add `_validate_layout()` method.

### 2d — Update `EntityDefinition`

Add:
```python
layouts: dict[str, LayoutSpec] = field(default_factory=dict)
```

---

## Task 3 — Create `core/layout_manager.py`

This is the core new module. Implement the following:

### 3.1 API Endpoints (confirmed)

```python
# Read current layout
GET_URL = "{api_url}/Layout/action/getOriginal?scope={entity}&name={layout_type}"

# Save layout
PUT_URL = "{api_url}/{entity}/layout/{layout_type}"
```

Note: Both URLs use the EspoCRM internal entity name (C-prefixed for custom
entities). Use the same `get_espo_entity_name()` mapping as EntityManager.

### 3.2 Check

Fetch current layout via GET. Compare panel structure to spec:
- Same number of panels (after tab expansion)
- Same panel labels in same order
- Same field names in same row positions
- Same dynamicLogicVisible conditions
- Same tabBreak / tabLabel values

Return a ComparisonResult-style object indicating match or differences.

### 3.3 Build Payload

Convert a `LayoutSpec` to the EspoCRM API payload format.

**For detail/edit layouts:**

For each `PanelSpec`:

If panel has `rows` (explicit):
```python
{
    "customLabel": panel.label,
    "tabBreak": panel.tabBreak,
    "tabLabel": panel.tabLabel,
    "style": panel.style,
    "hidden": panel.hidden,
    "noteText": None,
    "noteStyle": "info",
    "dynamicLogicVisible": _build_dynamic_logic(panel.dynamicLogicVisible),
    "dynamicLogicStyled": None,
    "rows": _build_rows(panel.rows, field_definitions)
}
```

If panel has `tabs` (category-based), expand into multiple panel objects:
- First tab: takes parent panel's `tabBreak`, `tabLabel`, `dynamicLogicVisible`
- Subsequent tabs: `tabBreak: false`, `tabLabel: null`, inherit `dynamicLogicVisible`

**Auto-row generation from category:**
1. Collect fields where `field.category == tab.category`, in definition order
2. Group into rows of 2 fields each
3. `wysiwyg`, `text`, `address` type fields get their own full-width row
4. If last row has one non-full-width field, pad with `false`

**Row format:**
- Field cell: `{"name": "cFieldName"}` (apply c-prefix mapping)
- Empty cell: `false`

**Dynamic logic translation:**
```python
# YAML input:
# dynamicLogicVisible:
#   attribute: contactType
#   value: "Mentor"

# API output:
{
    "conditionGroup": [
        {
            "type": "equals",
            "attribute": "cContactType",   # apply c-prefix
            "value": "Mentor"
        }
    ]
}
```

**For list layouts:**
```python
[
    {"name": "cFieldName", "width": 20},
    ...
]
```
Apply c-prefix to field names. If `width` is None, omit it (EspoCRM distributes equally).

### 3.4 Apply

PUT the built payload to the save endpoint. Return success/failure.

### 3.5 Verify

After applying, re-fetch via GET and compare to the built payload.
Check field names and order in each panel's rows.

### 3.6 Process

Main entry point called by the run worker:

```python
def process_layouts(
    self,
    entity_def: EntityDefinition,
    field_definitions: list[FieldDefinition],
    dry_run: bool = False
) -> list[LayoutResult]:
    """Process all layouts defined for an entity."""
```

For each layout type in `entity_def.layouts`:
1. Check current state
2. If matches: log SKIP
3. If differs: apply (unless dry_run), then verify
4. Return LayoutResult for each

### 3.7 Error Handling

Follow the same pattern as `field_manager.py`:
- HTTP 401 → raise `LayoutManagerError` (aborts run)
- HTTP 403 → log error, mark as ERROR, continue
- HTTP 4xx/5xx → log error and response body, mark as ERROR, continue
- Network error → log error, mark as ERROR, continue

---

## Task 4 — Update `workers/run_worker.py`

After field operations complete for each entity, process layouts:

```python
# After field_mgr.run(program) completes:
for entity_def in program.entities:
    if entity_def.layouts:
        layout_results = layout_mgr.process_layouts(
            entity_def,
            entity_def.fields
        )
        all_layout_results.extend(layout_results)
```

Add layout results to the RunReport.

### Output messages

```
[LAYOUT]  Contact.detail ... CHECKING
[LAYOUT]  Contact.detail ... DIFFERS (panel count, field order)
[LAYOUT]  Contact.detail ... UPDATED OK
[LAYOUT]  Contact.detail ... VERIFIED

[LAYOUT]  Contact.list ... CHECKING
[LAYOUT]  Contact.list ... MATCHES
[LAYOUT]  Contact.list ... NO CHANGES NEEDED
```

### Summary block additions

```
===========================================
LAYOUT SUMMARY
===========================================
Total layouts processed : 4
  Updated              : 2
  Skipped (no change)  : 2
  Failed               : 0
===========================================
```

---

## Task 5 — Update `core/reporter.py`

Include layout results in both `.log` and `.json` report outputs.

JSON schema addition:
```json
{
  "layout_results": [
    {
      "entity": "Contact",
      "layout_type": "detail",
      "status": "updated",
      "verified": true,
      "error": null
    }
  ]
}
```

---

## Task 6 — Update Spec and Guides

### 6a — Update `PRDs/crmbuilder-spec-espocrm-impl.md`

- Bump version to 1.5
- Add layout management to the Phase 1 scope description
- Add `category` to the field definition schema table (Section 5.2)
- Add `layout` as a new top-level YAML section (reference the layout spec)
- Update Section 9 Future Phases — move layouts from future to current
- Update Section 13 Notes for Implementer with layout API endpoint notes

### 6b — Update `docs/technical-guide.md`

Add a new "Layout Manager" section covering:
- The two confirmed API endpoints (GET and PUT)
- The tab expansion algorithm
- The auto-row generation rules
- The c-prefix handling for field names in layout payloads
- The `category` property on fields

### 6c — Update `docs/user-guide.md`

Add a "Layout Configuration" section to the "Writing YAML Program Files"
chapter covering:
- The `category` property on fields
- The `layout` block structure
- Panel with explicit rows vs category-based tabs
- The `dynamicLogicVisible` shorthand
- List layout columns

---

## Task 7 — Add Tests

### `tests/test_layout_manager.py`

Cover:
- `_build_payload()` for a simple panel with explicit rows
- `_build_payload()` for a panel with category-based tabs (tab expansion)
- Auto-row generation: 2 fields per row, wysiwyg full-width
- Auto-row generation: padding last row with `false`
- `dynamicLogicVisible` translation (natural name → c-prefixed)
- Field name c-prefix application in rows
- Tab inheritance of dynamicLogicVisible from parent panel
- HTTP 401 raises error and aborts
- HTTP 403 logs error and continues
- Successful apply → verify flow

### `tests/test_config_loader.py` additions

Cover:
- `category` property parsed on fields
- `layout` block parsed into `LayoutSpec`
- Panel with `rows` validated correctly
- Panel with `tabs` validated correctly
- Panel with both `rows` and `tabs` raises validation error
- Tab `category` not found in field list raises validation error
- List layout with `columns` parsed correctly

---

## Implementation Order

1. Task 1 — models.py
2. Task 2 — config_loader.py  
3. Task 7 — tests for config_loader additions (run and confirm passing)
4. Task 3 — layout_manager.py
5. Task 7 — tests for layout_manager (run and confirm passing)
6. Task 4 — run_worker.py
7. Task 5 — reporter.py
8. Task 6 — spec and guide updates

Confirm with me after step 3 (config_loader tests passing) and after step 5
(layout_manager tests passing) before proceeding further.

---

## Important Implementation Notes

### Entity Name Mapping
Layout API URLs use the EspoCRM internal entity name (C-prefixed). Reuse the
same `get_espo_entity_name()` function from `confirm_delete_dialog.py`. Consider
this a good opportunity to refactor that function into `core/entity_manager.py`
where it architecturally belongs — but only if you can do so without breaking
existing functionality. If refactoring adds risk, leave it in place and just
import from there.

### Native Entities
`Contact` and `Account` are native entities — no C-prefix on entity name in
layout API URLs. The existing entity name mapping handles this correctly.

### Full Layout Replacement
EspoCRM replaces the entire layout on each PUT. Always send the complete panel
array, never a partial update.

### Field Name C-Prefix in Layouts
Field names in layout row cells must use the c-prefixed internal name
(e.g., `cContactType`). Apply the same `_custom_field_name()` logic used in
`field_manager.py`. Native EspoCRM fields (e.g., `name`, `emailAddress`,
`phoneNumber`) do NOT get a c-prefix — only custom fields do.

### Distinguishing Native vs Custom Fields
A field is custom (needs c-prefix in layout) if it appears in the entity's
`fields` list in the YAML. Native fields referenced in explicit `rows` (e.g.,
`name`, `emailAddress`) should be passed through without prefix. The safest
approach: if a field name exists in the entity's YAML field definitions, apply
the prefix; otherwise pass through as-is.
