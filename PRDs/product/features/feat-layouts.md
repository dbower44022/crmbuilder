# CRM Builder — Layout Management

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Depends On:** app-yaml-schema.md, feat-entities.md, feat-fields.md

---

## 1. Purpose

This document defines the requirements for layout management in CRM
Builder — the configuration of how fields are arranged and presented
in the CRM user interface.

Layouts determine what users see when they view, edit, or browse
records. Good layout configuration groups related fields logically,
hides irrelevant fields based on context, and presents information
in the order that matches the organization's workflow.

---

## 2. Layout Types

CRM Builder manages two layout types per entity:

| Layout Type | Description |
|---|---|
| **Detail view** | The arrangement of fields when viewing or editing a single record. Organized into panels, tabs, and rows |
| **List view** | The columns displayed when browsing a list of records for an entity |

Both layout types are defined under the `layout` key within an entity
block in the YAML program file.

---

## 3. Detail View Concepts

### 3.1 Panels

A detail view is an ordered sequence of **panels**. Each panel:

- Has a label shown as the panel header
- Contains an ordered list of rows
- Each row contains one or more field cells
- May have a dynamic visibility condition controlling when it appears
- May be rendered as a tab (see Section 3.2)

### 3.2 Tabs

When a panel has `tabBreak: true`, the CRM renders it as a tab across
the top of the detail view. The `tabLabel` is the short label displayed
on the tab itself; the `label` is the longer header shown when the tab
is active.

A layout may mix tabbed and non-tabbed panels. In practice, layouts
are either fully tabbed or fully stacked — mixing the two is discouraged
as it produces inconsistent visual results.

### 3.3 Sub-Tabs

A panel may contain a set of sub-tabs using the `tabs` property. Each
sub-tab references a field category and the layout tool automatically
collects all fields with that category and arranges them into rows.

Sub-tabs allow a complex panel to be further organized without manually
listing every field in the layout definition. The field definition
itself (via the `category` property) determines which tab the field
appears in.

### 3.4 Rows and Cells

Each row within a panel contains one or more cells. A cell is either
a field name or an empty placeholder. Rows may contain one, two, three,
or four cells. The CRM distributes cell widths proportionally across
the row.

An empty cell (`null` in YAML) is used for alignment — for example,
to place a single field on the left half of a row while leaving the
right half blank.

### 3.5 Field Categories

A **category** is a named grouping assigned to a field in its field
definition. Categories serve two purposes:

1. **Documentation** — categories describe which logical section of
   the UI a field belongs to, making YAML files self-documenting
2. **Layout generation** — when a layout tab references a category,
   the tool automatically collects all fields with that category and
   arranges them into rows, in the order they appear in the field list

Categories eliminate the need to list every field name twice — once
in the field definition and again in the layout. The field definition
is the single source of truth for both the field's properties and its
default UI placement.

---

## 4. Dynamic Visibility

A panel may define a `dynamicLogicVisible` condition that controls
whether the panel is shown or hidden based on the value of another
field. When the condition is met, the panel is visible; when it is
not met, the panel is hidden.

CRM Builder supports a single equals condition per panel:

```yaml
dynamicLogicVisible:
  attribute: contactType    # field name — natural name, no prefix
  value: "Mentor"           # the panel is visible when this value is set
```

This is used to show context-relevant panels — for example, showing
mentor-specific panels only when a Contact's type is set to Mentor,
and client-specific panels only when the type is Client.

Dynamic visibility conditions cascade to sub-tabs. When a parent panel
has a visibility condition, all of its sub-tabs inherit the same
condition.

---

## 5. Auto-Row Generation

When a layout tab references a category rather than specifying explicit
rows, the tool generates rows automatically:

- Fields within the category are collected in the order they appear
  in the entity's field list
- Fields are placed two per row by default
- Fields of type `wysiwyg`, `text`, or `address` are placed full-width,
  one per row, because their content requires more horizontal space
- If the last row has only one normal-width field, an empty cell is
  added to complete the row

Auto-row generation means the layout reflects the field list order.
Reordering fields in the YAML field list changes their order in the
layout tab without requiring any layout definition changes.

---

## 6. Explicit Row Placement

When precise control over field placement is needed, a panel may
specify `rows` directly instead of using category-based auto-generation.
Explicit rows place fields exactly as specified:

```yaml
rows:
  - [firstName, lastName]
  - [emailAddress, phoneNumber]
  - [address, null]       # null = empty alignment cell
  - [description]         # single full-width field
```

Field names in explicit rows use natural names without any
platform-specific prefix.

A panel must use either `rows` or `tabs` — not both.

---

## 7. List View

The list view defines which columns appear when a user browses a list
of records for an entity, and how wide each column is.

```yaml
list:
  columns:
    - field: name
      width: 25
    - field: contactType
      width: 15
    - field: emailAddress
      width: 25
```

Column widths are specified as percentages. Columns should sum to
approximately 100. If widths are omitted, the CRM distributes column
widths equally.

---

## 8. Layout Operations

### 8.1 The Check → Compare → Act Cycle

Layout operations follow the same three-step cycle as field operations:

**Check** — the current layout is read from the CRM instance.

**Compare** — the current layout is compared to the desired spec.
Differences in panel structure, field order, tab labels, or dynamic
logic conditions all count as differences.

**Act** — if the layout differs, the full layout definition is written
to the CRM instance. The CRM replaces the entire layout on each write —
partial updates are not supported. The complete layout is always sent.

### 8.2 Layout Ordering

Layout operations are processed after all field operations for an
entity have completed. This ensures all fields referenced in the
layout exist before the layout is applied.

### 8.3 No Inline Verification

Layout operations do not perform inline verification after each write.
The standalone Verify action should be used to confirm layout state
after a Run.

---

## 9. Panel Description Property

Panels may include a `description` property explaining the business
rationale for the panel grouping. This property is used by the
documentation generator and has no effect on the CRM UI.

---

## 10. Output and Reporting

### 10.1 Output Panel Messages

Layout operations emit messages to the output panel following the
conventions in `app-ui-patterns.md`:

```
[LAYOUT]  Contact.detail ... CHECKING
[LAYOUT]  Contact.detail ... DIFFERS (panels, field order)
[LAYOUT]  Contact.detail ... UPDATED OK

[LAYOUT]  Contact.list ... CHECKING
[LAYOUT]  Contact.list ... MATCHES
[LAYOUT]  Contact.list ... SKIPPED (no changes needed)

[LAYOUT]  Engagement.detail ... CHECKING
[LAYOUT]  Engagement.detail ... ERROR (HTTP 403)
```

### 10.2 Summary Block

```
===========================================
LAYOUT SUMMARY
===========================================
Total layouts processed :  6
  Updated               :  2
  Skipped (no change)   :  3
  Errors                :  1
===========================================
```

### 10.3 Report Status Values

Layout results use the following status values in the JSON report:

| Status | Meaning |
|---|---|
| `updated` | Layout was successfully written to the CRM instance |
| `skipped` | Layout matches spec — no change needed |
| `error` | Operation failed due to an API or network error |

---

## 11. Validation Rules

The following rules are checked during Validate before any API calls
are made:

- Each panel must have either `rows` or `tabs`, not both
- A panel with `tabBreak: true` must have a `tabLabel`
- Each tab `category` must match the `category` of at least one field
  in the entity's field list
- Field names referenced in explicit `rows` must exist in the entity's
  field list
- No two panels within the same layout may have the same `label`

Validation failures are reported individually and prevent the Run
action from proceeding.

---

## 12. Future Considerations

- **Edit view layouts** — the edit view (shown when editing a record)
  follows the same schema as the detail view. Support for separate
  edit view definitions is planned.
- **Dynamic Logic on fields** — conditional required, visibility, and
  read-only rules on individual fields (not just panels) are planned.
  When implemented they will be defined as additional properties on
  the field definition.
- **Search presets / saved views** — named filtered views of entity
  lists are planned for a future phase. They will be defined in a
  separate feature spec.
- **Additional condition types** — dynamic visibility currently
  supports only an equals condition. Additional condition types
  (not-equals, contains, is-empty, etc.) are planned.
