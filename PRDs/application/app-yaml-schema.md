# CRM Builder — YAML Program File Schema

**Version:** 1.0
**Status:** Current
**Last Updated:** March 2026
**Applies To:** All YAML program files used by CRM Builder

---

## 1. Purpose

This document defines the schema for CRM Builder YAML program files —
the machine-readable configuration files that describe the desired state
of a CRM instance. All features that read or write YAML program files
must conform to this schema.

YAML program files are the single source of truth for CRM configuration.
They are CRM-agnostic at the requirements level and are translated into
platform-specific API calls at deployment time.

---

## 2. Design Principles

**Declarative.** A program file describes the desired end state, not a
sequence of steps. The tool determines what needs to change by comparing
the desired state to the current instance state.

**Idempotent.** Running the same program file multiple times produces
the same result. The tool only creates or updates objects where the
current state differs from the spec.

**Human-readable.** Program files are intended to be read and reviewed
by people, not just machines. Field descriptions, entity descriptions,
and comments are first-class citizens of the schema.

**No instance-specific information.** Program files contain no
credentials, URLs, or instance identifiers. The same file can be applied
to any compatible CRM instance.

**Natural names.** Program files use natural, human-readable names for
entities and fields. The tool handles any platform-specific prefixing
or naming transformations at deployment time.

---

## 3. Top-Level Structure

Every YAML program file has the following top-level structure. This
example shows all major sections — a file may include any combination
of these:

```yaml
version: "1.0"
content_version: "1.0.0"
description: "Human-readable description of what this file configures"

# Optional: source reference
# Source: PRD document name and section

entities:
  EntityName:
    description: "Why this entity exists and its PRD reference"
    action: delete_and_create   # omit for native entities
    type: Base
    labelSingular: "Entity Name"
    labelPlural: "Entity Names"
    stream: false
    fields:
      - name: fieldName
        type: enum
        label: "Field Label"
        description: "Why this field exists"
        category: "Tab Name"
        options:
          - "Value A"
          - "Value B"
    layout:
      detail:
        panels:
          - label: "Panel Label"
            tabBreak: true
            tabLabel: "Tab"
            rows:
              - [fieldName, null]
      list:
        columns:
          - field: fieldName
            width: 25

relationships:
  - name: relationshipName
    description: "Why this relationship exists and its PRD reference"
    entity: EntityName
    entityForeign: OtherEntity
    linkType: manyToOne
    link: linkName
    linkForeign: linkForeignName
    label: "Label"
    labelForeign: "Foreign Label"
```

### 3.1 Top-Level Properties

| Property | Type | Required | Description |
|---|---|---|---|
| `version` | string | yes | Schema version of this file format. Currently `"1.0"` |
| `content_version` | string | yes | Semantic version of this file's content (see Section 4) |
| `description` | string | yes | Human-readable description of what this file configures |
| `entities` | map | no | Map of entity name → entity definition (see Section 5). Each entity block contains `fields` (Section 6) and optionally `layout` (Section 7) |
| `relationships` | list | no | List of relationship definitions (see Section 8) |

A file may contain `entities`, `relationships`, or both. A file with
neither is valid but produces no output.

All program files are validated before any API calls are made. Validation
rules for each section are defined in Section 10.


---

## 4. Content Versioning

The `content_version` property uses semantic versioning (`MAJOR.MINOR.PATCH`)
to communicate the significance of changes to a program file.

| Change Type | Version Bump | Examples |
|---|---|---|
| Descriptions, comments, minor corrections | PATCH | `1.0.0 → 1.0.1` |
| New fields, new enum values, new relationships | MINOR | `1.0.0 → 1.1.0` |
| Fields removed, types changed, entities restructured | MAJOR | `1.0.0 → 2.0.0` |

`content_version` must be incremented whenever a file is changed. It is
displayed alongside the filename in the Program File panel so users can
confirm they are working with the correct version.

---

## 5. Entity Block

The `entities` map contains one entry per entity. The key is the
entity's natural name.

```yaml
entities:
  Contact:           # native entity — fields only
    description: >
      The Contact entity represents individuals tracked in the CRM.
    fields:
      - ...

  Engagement:        # custom entity — full definition
    description: >
      An Engagement represents an active mentoring relationship between
      a mentor Contact and a client organization Account.
    action: delete_and_create
    type: Base
    labelSingular: "Engagement"
    labelPlural: "Engagements"
    stream: true
    fields:
      - ...
    layout:
      ...
```

### 5.1 Entity Properties

| Property | Type | Required | Description |
|---|---|---|---|
| `description` | string | yes | Business rationale, role in data model, and PRD reference |
| `action` | string | no | Entity-level action (see Section 5.2). Default: none (fields only) |
| `type` | string | create only | Entity type: `Base`, `Person`, `Company`, or `Event` |
| `labelSingular` | string | create only | Singular display name shown in the CRM UI |
| `labelPlural` | string | create only | Plural display name shown in the CRM UI |
| `stream` | boolean | no | Enable the Stream (activity feed) panel. Default: `false` |
| `disabled` | boolean | no | Mark the entity as disabled. Default: `false` |
| `fields` | list | no | List of field definitions (see Section 6) |
| `layout` | map | no | Layout definitions (see Section 7) |

The `description` property is required on all entity blocks, including
native entities. It documents why the entity exists and where it is
defined in the PRD.

### 5.2 Entity Action Values

| Action | When to Use |
|---|---|
| *(omit)* | Native entities (Account, Contact) — field and layout operations only |
| `create` | Custom entities — create if not already present |
| `delete` | Remove a custom entity. No `fields` or `layout` allowed |
| `delete_and_create` | Delete and recreate a custom entity. Used for clean rebuilds |

`delete` and `delete_and_create` are destructive operations. They require
explicit user confirmation before execution (see `app-ui-patterns.md`,
Section 5.3).

### 5.3 Entity Types

| Type | Description |
|---|---|
| `Base` | General-purpose entity with name and description fields |
| `Person` | Includes first/last name, email, phone, and address fields |
| `Company` | Includes email, phone, billing/shipping address fields |
| `Event` | Includes date start/end, duration, status, and parent fields |

---

## 6. Field Definitions

Fields are defined in the `fields` list under an entity block.

```yaml
fields:
  - name: mentorStatus
    type: enum
    label: "Mentor Status"
    description: >
      Tracks the lifecycle stage of a mentor. Drives UI visibility
      for departure-related fields. See PRD Section 4.2.
    category: "Mentor Role & Capacity"
    required: false
    default: "Provisional"
    options:
      - "Provisional"
      - "Active"
      - "Inactive"
      - "Departed"
    translatedOptions:
      "Provisional": "Provisional"
      "Active": "Active"
      "Inactive": "Inactive"
      "Departed": "Departed"
    style:
      "Provisional": "info"
      "Active": "success"
      "Inactive": "default"
      "Departed": "danger"
```

### 6.1 Common Field Properties

These properties apply to all field types:

| Property | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Internal field name in lowerCamelCase. No c-prefix |
| `type` | string | yes | Field type (see Section 6.2) |
| `label` | string | yes | Display label shown in the CRM UI |
| `description` | string | recommended | Business rationale and PRD reference for this field |
| `category` | string | no | UI grouping used for layout tab assignment (see Section 7.4) |
| `required` | boolean | no | Whether the field is required. Default: `false` |
| `default` | string | no | Default value for the field |
| `readOnly` | boolean | no | Whether the field is read-only. Default: `false` |
| `audited` | boolean | no | Whether changes are tracked in the audit log. Default: `false` |

The `description` property is optional but strongly recommended on all
fields. Fields without a description are flagged in the documentation
generator output.

### 6.2 Supported Field Types

| Type | Display Name | Additional Properties |
|---|---|---|
| `varchar` | Text | `maxLength` |
| `text` | Text (multi-line) | — |
| `wysiwyg` | Rich Text | — |
| `bool` | Boolean | — |
| `int` | Integer | `min`, `max` |
| `float` | Decimal | `min`, `max` |
| `date` | Date | — |
| `datetime` | Date/Time | — |
| `currency` | Currency | — |
| `url` | URL | — |
| `email` | Email | — |
| `phone` | Phone | — |
| `enum` | Enum | `options`, `translatedOptions`, `style`, `isSorted`, `displayAsLabel` |
| `multiEnum` | Multi-select | `options`, `translatedOptions`, `style`, `isSorted` |

### 6.3 Enum and Multi-Select Properties

These properties apply only to `enum` and `multiEnum` fields:

| Property | Type | Required | Description |
|---|---|---|---|
| `options` | list | yes | Ordered list of allowed values |
| `translatedOptions` | map | no | Display label for each option value |
| `style` | map | no | Color style per option (see Section 6.4) |
| `isSorted` | boolean | no | Sort options alphabetically. Default: `false` |
| `displayAsLabel` | boolean | enum only | Display value as a colored badge. Default: `false` |

### 6.4 Enum Style Values

| Style | Display |
|---|---|
| `null` or omitted | Default (no color) |
| `"default"` | Gray |
| `"primary"` | Blue |
| `"success"` | Green |
| `"danger"` | Red |
| `"warning"` | Orange |
| `"info"` | Light blue |

### 6.5 Numeric Field Properties

These properties apply only to `int` and `float` fields:

| Property | Type | Description |
|---|---|---|
| `min` | integer | Minimum allowed value |
| `max` | integer | Maximum allowed value |

### 6.6 Text Field Properties

This property applies only to `varchar` fields:

| Property | Type | Description |
|---|---|---|
| `maxLength` | integer | Maximum character length |

### 6.7 Naming Conventions

Field names in YAML use lowerCamelCase without any platform-specific
prefix (e.g., `contactType`, not `cContactType`). The tool applies any
required prefix transformations at deployment time.

No two fields within the same entity may have the same `name`.

---

## 7. Layout Definitions

Layouts are defined under a `layout` key within an entity block. See
`features/feat-layouts.md` for the full layout specification.

### 7.1 Layout Types

```yaml
layout:
  detail:
    panels:
      - ...
  list:
    columns:
      - ...
```

| Layout Type | Description |
|---|---|
| `detail` | Fields shown when viewing a record. Panel and tab structure |
| `list` | Columns shown in the entity list view |

### 7.2 Detail Layout — Panel Structure

Each panel in a detail layout has the following properties:

| Property | Type | Required | Description |
|---|---|---|---|
| `label` | string | yes | Panel header label |
| `description` | string | no | Business rationale for this panel grouping |
| `tabBreak` | boolean | no | Render this panel as a tab. Default: `false` |
| `tabLabel` | string | if tabBreak | Short label shown on the tab |
| `style` | string | no | Panel accent color (same values as enum style, Section 6.4) |
| `hidden` | boolean | no | Whether the panel is hidden by default. Default: `false` |
| `dynamicLogicVisible` | object | no | Condition controlling panel visibility (see Section 7.3) |
| `rows` | list | no | Explicit field placement (see Section 7.5) |
| `tabs` | list | no | Category-based sub-tabs (see Section 7.4) |

A panel must have either `rows` or `tabs`, not both.

### 7.3 Dynamic Logic Visibility

Controls when a panel is visible based on a field value:

```yaml
dynamicLogicVisible:
  attribute: contactType    # field name — no prefix
  value: "Mentor"           # value to match
```

This defines an "equals" condition. When the named field equals the
specified value, the panel is shown; otherwise it is hidden.

Field names in `dynamicLogicVisible` use natural names without any
platform-specific prefix. The tool applies prefix transformations at
deployment time.

### 7.4 Category-Based Sub-Tabs

When a panel has `tabs`, each tab references a `category`. The tool
automatically collects all fields whose `category` matches and arranges
them into rows:

```yaml
tabs:
  - label: "Identity"
    category: "Mentor Identity & Contact"
  - label: "Skills"
    category: "Mentor Skills & Expertise"
```

Each tab's `category` value must match the `category` property on at
least one field in the entity's field list.

Fields within a category are placed two per row by default. Fields of
type `wysiwyg`, `text`, or `address` are placed full-width, one per row.

### 7.5 Explicit Rows

When a panel specifies `rows` directly, fields are placed exactly as
specified:

```yaml
rows:
  - [firstName, lastName]
  - [emailAddress, phoneNumber]
  - [address, null]         # null = empty cell
  - [description]           # full-width single field
```

Field names in rows use natural names without any platform-specific
prefix. `null` represents an empty cell used for alignment.

### 7.6 List Layout

List layouts define the columns shown in the entity list view:

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

| Property | Type | Required | Description |
|---|---|---|---|
| `field` | string | yes | Field name (natural name, no prefix) |
| `width` | integer | no | Column width as a percentage. Columns should sum to ~100 |

---

## 8. Relationship Definitions

Relationships are defined in a top-level `relationships` list, separate
from the `entities` block. See `features/feat-relationships.md` for the
full relationship specification.

```yaml
relationships:
  - name: duesToMentor
    description: >
      Links Dues records to the mentor Contact who paid them.
      See PRD Section 6.3.
    entity: Dues
    entityForeign: Contact
    linkType: manyToOne
    link: mentor
    linkForeign: duesRecords
    label: "Mentor"
    labelForeign: "Dues Records"
    audited: false
```

### 8.1 Relationship Properties

| Property | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Identifier for this relationship. Used in reports |
| `description` | string | yes | Business rationale and PRD reference |
| `entity` | string | yes | Primary entity (natural name) |
| `entityForeign` | string | yes | Foreign entity (natural name) |
| `linkType` | string | yes | `oneToMany`, `manyToOne`, or `manyToMany` |
| `link` | string | yes | Link name on the primary entity |
| `linkForeign` | string | yes | Link name on the foreign entity |
| `label` | string | yes | Panel label on the primary entity's detail view |
| `labelForeign` | string | yes | Panel label on the foreign entity's detail view |
| `relationName` | string | manyToMany only | Junction table name |
| `audited` | boolean | no | Track changes in audit log. Default: `false` |
| `auditedForeign` | boolean | no | Track changes on foreign side. Default: `false` |
| `action` | string | no | `skip` to document without deploying. Default: deploy |

### 8.2 Link Types

| Type | Meaning |
|---|---|
| `oneToMany` | One record of the primary entity relates to many of the foreign entity |
| `manyToOne` | Many records of the primary entity relate to one of the foreign entity |
| `manyToMany` | Many records on both sides. Requires `relationName` |

Entity names in relationship definitions use natural names without any
platform-specific prefix. The tool applies prefix transformations at
deployment time.

### 8.3 The `action: skip` Pattern

Relationships that were created manually on the CRM instance before the
YAML file was written can be documented with `action: skip`. The tool
records them in the report but makes no API calls. This ensures full
reproducibility — if the instance were rebuilt from scratch, all
relationships (including previously manual ones) would be created.

---

## 9. Comments and Documentation

YAML comments (lines beginning with `#`) are encouraged throughout
program files. Comments are especially valuable for:

- Explaining why a particular configuration choice was made
- Referencing the PRD section that defines a requirement
- Warning about known quirks or constraints
- Grouping related entities or fields with section headers

```yaml
# --- Custom Entities ---

Engagement:
  description: >
    ...

# --- Native Entities ---

Contact:
  description: >
    ...
```

---

## 10. Validation Rules

Program files are validated before any API calls are made. The following
rules apply to all program files:

**Top-level:**
- `version`, `content_version`, and `description` are required
- `version` must be a recognized schema version

**Entity-level:**
- `description` is required on all entity blocks
- `create` and `delete_and_create` require `type`, `labelSingular`,
  and `labelPlural`
- `type` must be one of: `Base`, `Person`, `Company`, `Event`
- `delete` must not contain `fields` or `layout`

**Field-level:**
- `name`, `type`, and `label` are required on every field
- `type` must be a supported field type (Section 6.2)
- `enum` and `multiEnum` fields must have a non-empty `options` list
- No two fields within the same entity may share the same `name`

**Layout-level:**
- Each panel must have `rows` or `tabs`, not both
- `tabBreak: true` requires `tabLabel`
- Each tab `category` must match the `category` of at least one field
  in the entity's field list
- Field names in explicit `rows` must exist in the entity's field list

**Relationship-level:**
- All required properties must be present (see Section 8.1)
- `manyToMany` relationships must include `relationName`

Validation errors are reported individually with enough detail for the
user to locate and fix each issue. Validation failures prevent the Run
action from proceeding.
