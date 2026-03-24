# CRM Builder — Layout Management Specification

**Version:** 1.0  
**Status:** Draft  
**Depends on:** CBM-SPEC-espocrm-impl.md v1.4

---

## 1. Overview

This document specifies the layout management extension to the EspoCRM
Implementation Tool. It covers the YAML schema for defining detail view
layouts, the API endpoints used to read and write layouts, the field
category concept, and the Claude Code implementation requirements.

Layout management is Phase 2 of the tool's capability roadmap (following
Phase 1 entity fields and entity management).

---

## 2. Concepts

### 2.1 Layout Types

EspoCRM supports several layout types per entity. Phase 2 covers:

| Layout Type | Description | API Name |
|---|---|---|
| Detail view | Fields shown when viewing a record | `detail` |
| Edit view | Fields shown when editing a record | `edit` |
| List view | Columns shown in the entity list | `list` |

Search filter presets (saved views) are a separate capability covered in
a future phase.

### 2.2 Panels

A detail/edit layout is an ordered array of **panels**. Each panel:
- Has a label (shown as the panel header or tab label)
- Contains an ordered list of **rows**
- Each row contains 1–4 **cells**, where each cell is a field name or
  `null` (empty cell, used for alignment)
- Can have an optional `dynamicLogicVisible` condition controlling
  visibility
- Can have an optional `style` (color accent)

### 2.3 Tabs

When panels have `tabBreak: true`, EspoCRM renders them as tabs across
the top of the detail view. Every panel in a tabbed layout should have
`tabBreak: true`. The `tabLabel` is the short label shown on the tab;
`customLabel` is the longer panel header shown when the tab is active.

A layout with no `tabBreak` panels renders as stacked sections.

### 2.4 Field Categories

A **category** is a named grouping assigned to a field in the YAML
definition. Categories serve two purposes:

1. **Documentation** — categories describe which logical section of the
   UI a field belongs to, making the YAML self-documenting
2. **Layout generation** — when a layout tab references a category, the
   tool automatically collects all fields with that category and places
   them in that tab, in the order they appear in the fields list

Categories eliminate the need to list field names twice (once in the
field definition and again in the layout). The field definition is the
single source of truth for both the field's properties and its UI
placement.

### 2.5 Rows and Columns

Each row in a panel can contain 1, 2, 3, or 4 cells. Cells are specified
as field names or `null` for an empty cell. EspoCRM renders cells
proportionally across the row width.

In YAML, rows are expressed as lists:
```yaml
rows:
  - [fieldA, fieldB]        # two-column row
  - [fieldC, null]          # left-aligned single field
  - [fieldD]                # full-width single field
  - [fieldE, fieldF, fieldG] # three-column row
```

---

## 3. API Endpoints

### 3.1 Read Layout

```
GET /api/v1/Layout/action/getOriginal?scope={Entity}&name={layoutType}
```

Returns the current layout as a JSON array of panel objects. Returns the
*original* (custom) layout. If no custom layout exists, returns the
default.

### 3.2 Save Layout

```
PUT /api/v1/{Entity}/layout/{layoutType}
```

Saves the layout. Payload is the full panel array (same structure as the
GET response). Returns the saved layout.

Note: GET and PUT use different URL patterns.

### 3.3 Panel Object Structure

```json
{
  "customLabel": "Panel Header",
  "tabBreak": true,
  "tabLabel": "Tab Label",
  "style": "default",
  "hidden": false,
  "noteText": null,
  "noteStyle": "info",
  "dynamicLogicVisible": null,
  "dynamicLogicStyled": null,
  "rows": [
    [{"name": "fieldName"}, {"name": "fieldName2"}],
    [{"name": "fieldName3"}, false]
  ]
}
```

| Property | Type | Description |
|---|---|---|
| `customLabel` | string | Panel header label |
| `tabBreak` | boolean | If true, this panel is a tab |
| `tabLabel` | string | Short tab label (used when tabBreak is true) |
| `style` | string | Panel accent color: `default`, `success`, `danger`, `warning`, `info`, `primary` |
| `hidden` | boolean | Whether the panel is hidden |
| `noteText` | string\|null | Optional note displayed in the panel |
| `noteStyle` | string | Note style: `info`, `warning`, `danger`, `success` |
| `dynamicLogicVisible` | object\|null | Condition controlling panel visibility |
| `dynamicLogicStyled` | object\|null | Condition controlling panel style |
| `rows` | array | Array of row arrays, each containing field objects or `false` |

### 3.4 Field Cell Object

```json
{"name": "cContactType"}
```

Field names in layout payloads use the **c-prefixed internal name** (e.g.,
`cContactType` not `contactType`). The tool must apply the same c-prefix
mapping used for field operations.

`false` in a row position means an empty cell (used for alignment).

---

## 4. YAML Schema — Layout Section

Layouts are defined in the same YAML program file as fields, under a
`layout` key within each entity block.

### 4.1 Top-Level Structure

```yaml
version: "1.0"
description: "CBM EspoCRM Configuration — Contact Layout"

entities:
  Contact:
    fields:
      - name: contactType
        type: enum
        label: "Contact Type"
        category: "Personal Information"
        ...

    layout:
      detail:
        panels:
          - label: "Personal Information"
            tabBreak: true
            tabLabel: "Overview"
            style: default
            rows:
              - [name, emailAddress]
              - [phoneNumber, address]
              - [contactType, null]

          - label: "Mentor Details"
            tabBreak: true
            tabLabel: "Mentor"
            style: default
            dynamicLogicVisible:
              attribute: contactType
              value: "Mentor"
            tabs:
              - label: "Identity & Contact"
                category: "Mentor Identity & Contact"
              - label: "Biographical"
                category: "Mentor Biographical & Professional"
              - label: "Skills"
                category: "Mentor Skills & Expertise"
              - label: "Capacity"
                category: "Mentor Role & Capacity"
              - label: "Administrative"
                category: "Mentor Administrative"
```

### 4.2 Panel Properties

| Property | Type | Required | Description |
|---|---|---|---|
| `label` | string | yes | Panel header label (`customLabel` in API) |
| `description` | string | no | Business rationale for this panel grouping |
| `tabBreak` | boolean | no | Default: false. Set true for tabbed layouts |
| `tabLabel` | string | no | Short tab label. Required if `tabBreak: true` |
| `style` | string | no | Default: `default` |
| `hidden` | boolean | no | Default: false |
| `dynamicLogicVisible` | object | no | Visibility condition (see 4.4) |
| `rows` | list | no | Explicit field rows (see 4.3) |
| `tabs` | list | no | Sub-tabs within this panel (see 4.5) |

A panel must have either `rows` or `tabs`, not both.

### 4.3 Explicit Rows

When a panel specifies `rows` directly, fields are placed exactly as
specified. Field names are the natural names from the YAML (without c-prefix —
the tool applies the prefix when building the API payload).

Use `null` for an empty cell:

```yaml
rows:
  - [firstName, lastName]
  - [emailAddress, phoneNumber]
  - [address, null]
  - [description]
```

### 4.4 Dynamic Logic Visible

Controls when a panel is visible. Supports a single condition for Phase 2:

```yaml
dynamicLogicVisible:
  attribute: contactType    # field name (natural, without c-prefix)
  value: "Mentor"           # value to match (equals condition)
```

This translates to the EspoCRM API format:
```json
{
  "conditionGroup": [
    {
      "type": "equals",
      "attribute": "cContactType",
      "value": "Mentor"
    }
  ]
}
```

### 4.5 Sub-Tabs (Category-Based)

When a panel has `tabs`, each tab references a `category`. The tool
collects all fields from the entity's field list whose `category` matches,
preserving their definition order, and builds the rows automatically.

```yaml
tabs:
  - label: "Identity & Contact"
    category: "Mentor Identity & Contact"
  - label: "Biographical"
    category: "Mentor Biographical & Professional"
```

Each tab becomes a separate panel in the API payload with `tabBreak: true`.
The first tab in a `tabs` list does NOT get `tabBreak: true` — it is
rendered as part of its parent panel. Subsequent tabs each get
`tabBreak: true`.

**Auto-row generation:** Fields within a category are placed two per row
by default. Fields of type `wysiwyg`, `text`, or `address` are placed
full-width (one per row). This default can be overridden by specifying
explicit `rows` on the tab instead of `category`.

### 4.6 Field Category Property

The `category` property is added to `FieldDefinition` in the YAML schema:

```yaml
- name: backgroundCheckCompleted
  type: bool
  label: "Background Check Completed"
  category: "Mentor Administrative"   # NEW
```

Category is optional. Fields without a category are excluded from
category-based tab auto-generation but can still be placed via explicit
`rows`.

---

## 5. Processing Logic

### 5.1 Validate

Layout validation checks (no API calls):
- Each panel has either `rows` or `tabs`, not both
- Each panel with `tabBreak: true` has a `tabLabel`
- Each tab `category` reference exists in the entity's field list
- No duplicate panel labels within an entity layout
- Field names in explicit `rows` exist in the entity's field list

### 5.2 Check

```
GET /api/v1/Layout/action/getOriginal?scope={EspoEntityName}&name=detail
```

Fetch the current layout and compare panel structure, field order, and
dynamic logic to the desired spec. Report differences.

### 5.3 Act

Build the full panel array from the YAML spec and PUT it:

```
PUT /api/v1/{EspoEntityName}/layout/detail
```

The payload is the complete panel array — EspoCRM replaces the entire
layout on each PUT, so partial updates are not supported. Always send
the full layout.

**Building the payload:**

1. For each panel in the YAML:
   - If panel has `rows`: translate field names to c-prefixed names,
     replace `null` with `false`
   - If panel has `tabs`: expand each tab into its own panel object
     (see 5.4)
2. Apply `dynamicLogicVisible` translation (natural name → c-prefixed)
3. Set all other panel properties from YAML

### 5.4 Tab Expansion

When a panel has `tabs`, expand as follows:

**Input (YAML):**
```yaml
- label: "Mentor Details"
  tabBreak: true
  tabLabel: "Mentor"
  dynamicLogicVisible:
    attribute: contactType
    value: "Mentor"
  tabs:
    - label: "Identity & Contact"
      category: "Mentor Identity & Contact"
    - label: "Biographical"
      category: "Mentor Biographical"
```

**Output (API payload — two panel objects):**
```json
[
  {
    "customLabel": "Identity & Contact",
    "tabBreak": true,
    "tabLabel": "Mentor",
    "style": "default",
    "hidden": false,
    "dynamicLogicVisible": {
      "conditionGroup": [
        {"type": "equals", "attribute": "cContactType", "value": "Mentor"}
      ]
    },
    "rows": [/* fields from Mentor Identity & Contact category */]
  },
  {
    "customLabel": "Biographical",
    "tabBreak": false,
    "tabLabel": null,
    "style": "default",
    "hidden": false,
    "dynamicLogicVisible": {
      "conditionGroup": [
        {"type": "equals", "attribute": "cContactType", "value": "Mentor"}
      ]
    },
    "rows": [/* fields from Mentor Biographical category */]
  }
]
```

Note:
- The first tab takes the parent panel's `tabBreak` and `tabLabel`
- Subsequent tabs have `tabBreak: false` (they are part of the same tab
  group, visually separated by EspoCRM's tab rendering)
- `dynamicLogicVisible` is inherited by all tabs from the parent panel

### 5.5 Auto-Row Generation

When building rows from a category:

1. Collect all fields with matching `category` in definition order
2. Group into rows of 2 fields each
3. Exception: `wysiwyg`, `text`, `address` type fields get their own
   full-width row (single field, no second cell)
4. If the last row has only one field and it is not full-width type,
   add `false` as the second cell

### 5.6 Verify

After saving, re-read the layout via GET and compare to the desired spec.
For each panel: verify label, tabBreak, tabLabel, dynamicLogicVisible,
and field names in rows (order matters).

### 5.7 Error Handling

| Error | Behavior |
|---|---|
| HTTP 401 | Abort entire run |
| HTTP 403 | Log error, mark layout as ERROR, continue |
| HTTP 4xx/5xx on PUT | Log error and response body, mark as ERROR, continue |
| Category not found in field list | Log validation error, block run |
| Network error | Log error, mark as ERROR, continue |

---

## 6. Application Structure Changes

### 6.1 New Module

Add `core/layout_manager.py`:
- `check(entity, layout_type, spec)` → ComparisonResult
- `apply(entity, layout_type, spec)` → bool
- `verify(entity, layout_type, spec)` → bool
- `_build_payload(spec, field_definitions)` → list[dict]
- `_expand_tabs(panel, field_definitions)` → list[dict]
- `_auto_rows(category, field_definitions)` → list[list]

### 6.2 Model Updates

Add to `FieldDefinition` in `models.py`:
```python
category: str | None = None   # UI grouping / tab category
```

Add `LayoutSpec` dataclass:
```python
@dataclass
class PanelSpec:
    label: str
    tabBreak: bool = False
    tabLabel: str | None = None
    style: str = "default"
    hidden: bool = False
    dynamicLogicVisible: dict | None = None
    rows: list | None = None      # explicit rows
    tabs: list | None = None      # sub-tab specs

@dataclass
class LayoutSpec:
    layout_type: str              # "detail", "edit", "list"
    panels: list[PanelSpec]
```

Add `layout` property to `EntityDefinition`:
```python
layout: dict[str, LayoutSpec] = field(default_factory=dict)
```

### 6.3 Config Loader Updates

Parse `layout` section from entity YAML block. Validate categories,
panel structure, and field references.

### 6.4 Run Worker Updates

After field operations for an entity, process its layout specs:
1. For each layout type defined (detail, edit, list):
   - Check current layout
   - If differs: PUT new layout
   - Verify result

### 6.5 Output Panel Messages

```
[LAYOUT]  Contact.detail ... CHECKING
[LAYOUT]  Contact.detail ... DIFFERS (panels, field order)
[LAYOUT]  Contact.detail ... UPDATED OK
[LAYOUT]  Contact.detail ... VERIFIED
```

---

## 7. Confirmed API Endpoints

| Operation | Method | URL |
|---|---|---|
| Read layout | GET | `/api/v1/Layout/action/getOriginal?scope={Entity}&name={type}` |
| Save layout | PUT | `/api/v1/{Entity}/layout/{type}` |

Note: Entity name in both URLs uses the EspoCRM internal name
(C-prefixed for custom entities, e.g., `CEngagement`).

---

## 8. List View Layout

List layouts follow a simpler structure — an array of column objects:

```json
[
  {"name": "name", "width": 20},
  {"name": "cStatus", "width": 15},
  {"name": "cStartDate", "width": 15}
]
```

YAML schema for list layout:

```yaml
layout:
  list:
    columns:
      - field: name
        width: 20
      - field: status
        width: 15
      - field: startDate
        width: 15
```

Width is a percentage (columns should sum to ~100). If widths are omitted,
EspoCRM distributes equally.

---

## 9. CBM Layout Definitions — Contact

Based on CBM-PRD-CRM-Implementation.docx Phase 3.

```yaml
layout:
  detail:
    panels:
      - label: "Personal Information"
        tabBreak: true
        tabLabel: "Overview"
        style: default
        rows:
          - [firstName, lastName]
          - [emailAddress, phoneNumber]
          - [address, null]
          - [linkedInProfile, preferredName]
          - [contactType, null]

      - label: "Client Details"
        tabBreak: true
        tabLabel: "Client"
        style: default
        dynamicLogicVisible:
          attribute: contactType
          value: "Client"
        tabs:
          - label: "Client Details"
            category: "Client Details"

      - label: "Mentor Details"
        tabBreak: true
        tabLabel: "Mentor"
        style: default
        dynamicLogicVisible:
          attribute: contactType
          value: "Mentor"
        tabs:
          - label: "Identity"
            category: "Mentor Identity & Contact"
          - label: "Biographical"
            category: "Mentor Biographical & Professional"
          - label: "Skills"
            category: "Mentor Skills & Expertise"
          - label: "Capacity"
            category: "Mentor Role & Capacity"
          - label: "Administrative"
            category: "Mentor Administrative"
```

---

## 10. Future Phases

| Phase | Capability |
|---|---|
| 2b | Edit view layouts (same schema as detail) |
| 2c | List view column definitions |
| 3 | Search filter presets / saved views |
| 4 | Relationships |
| 5 | Dynamic Logic on fields |
| 6 | Role-based access control |
