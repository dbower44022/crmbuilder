# CRM Builder — User Guide

**Version:** 2.1  
**Last Updated:** March 2026  
**Changelog:** See end of document.

## What This Tool Does

The CRM Builder automates the configuration of EspoCRM
instances. Instead of manually creating fields, layouts, and relationships
through the EspoCRM admin UI, you write declarative YAML files describing
the desired configuration and the tool applies them via the EspoCRM REST API.

The tool is **idempotent** — running the same file repeatedly only makes
changes where the instance differs from the spec.

---

## Installation

### Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js (for Word document generation)

### Setup

```bash
cd crmbuilder
uv sync
```

### Launch

```bash
uv run crmbuilder
```

---

## Quick Start

1. **Add an instance** — Click **+ Add** in the Instance panel
2. **Enter connection details** — Name, URL, auth credentials, project folder
3. **Select the instance** — The Program File panel loads your YAML files
4. **Select a program file** — Click it in the list
5. **Validate** — Checks YAML structure and previews planned changes
6. **Run** — Applies the configuration
7. **Verify** — Confirms everything matches the spec
8. **Generate Docs** — Produces the reference manual

---

## Application Layout

```
+---------------------------+  +-------------------------------+
|  INSTANCE                 |  |  PROGRAM FILE                 |
|                           |  |                               |
|  > CBM Test               |  |  cbm_contact_fields  v1.0.0  |
|    CBM Production         |  |  cbm_account_fields  v1.0.0  |
|                           |  |  cbm_relationships   v1.3.0  |
|  [+ Add] [Edit] [Delete]  |  |                               |
|                           |  |  [+ Add] [Edit] [Delete]     |
|  URL: https://cbm...      |  +-------------------------------+
|  Folder: ~/Projects/CBM   |
|                           |  [Validate]  [Run]  [Verify]
+---------------------------+
+--------------------------------------------------------------+
|  OUTPUT                                                      |
|  [VERIFY] Contact.contactType ... VERIFIED                   |
|  [VERIFY] Contact.mentorStatus ... VERIFIED                  |
+--------------------------------------------------------------+
[Clear Output]  [Generate Docs]                  [View Report]
```

---

## Managing Instances

### Adding an Instance

1. Click **+ Add** in the Instance panel
2. Fill in:
   - **Name** — Display name (e.g., "CBM Test")
   - **URL** — EspoCRM base URL
   - **Auth Method** — API Key, HMAC, or Basic
   - **Credentials** — API key or username/password
   - **Project Folder** — Click **Browse** to select the client folder
3. Click **Save**

The tool creates `programs/`, `reports/`, and `Implementation Docs/`
subdirectories inside the project folder automatically.

### Authentication Methods

| Method | When to Use |
|---|---|
| **API Key** | API Users with admin access |
| **HMAC** | API Users using HMAC authentication |
| **Basic** | Regular admin users; recommended for EspoCRM Cloud |

**EspoCRM Cloud users:** Use **Basic** authentication with your admin
credentials. Cloud API Users cannot be granted the admin access required
for field and entity management endpoints.

### Project Folder

Each instance is bound to a project folder:

```
~/Projects/CBM/
├── programs/            ← YAML program files (loaded automatically)
├── Implementation Docs/ ← generated reference manual
└── reports/             ← run/verify reports
```

Selecting an instance automatically loads its program files. Reports and
generated docs are written to the same folder.

---

## Managing Program Files

Program files are YAML files in your project folder's `programs/`
directory. They appear in the Program File panel automatically when you
select an instance.

Each file shows its `content_version` alongside the filename so you can
confirm you're working with the latest version.

### Adding a File

Click **+ Add** and select a `.yaml` file. It is copied into the
`programs/` directory.

### Editing a File

Select a file and click **Edit**. Opens in your system's default text
editor.

---

## Workflow: Validate → Run → Verify

### Validate

Click **Validate** after selecting an instance and program file.

1. Parses the YAML for structural errors
2. Connects to the instance and previews planned changes
3. Shows a summary of what will be created, updated, or left unchanged

The Run button enables after successful validation.

### Run

Click **Run** to deploy the configuration.

**If the program contains delete operations**, a confirmation dialog appears:

- **Skip deletes** (default) — creates new entities and applies field
  changes only. Safe for instances with live data.
- **Proceed with deletes** — deletes and recreates entities. Requires
  typing DELETE to confirm. All data in the listed entities is lost.

**Processing order:**
1. Entity deletions → cache rebuild
2. Entity creations → cache rebuild
3. Field operations (check → create/update → verify per field)
4. Layout operations (check → apply → verify per layout)
5. Relationship operations (check → create → verify per relationship)

**Output colors:**

| Color | Meaning |
|---|---|
| Green | Created, updated, or verified successfully |
| Gray | No change needed |
| Yellow | Warning (skipped, type conflict) |
| Red | Error |

### Verify

Click **Verify** to re-check all fields against the spec without making
changes. Use after a Run to confirm deployment, or at any time to check
whether manual changes have drifted from the spec.

Note: Verify currently checks fields only. Layouts and relationships
are not re-verified by the Verify button — use Run for those.

---

## Generate Docs

Click **Generate Docs** to produce the reference manual from all YAML
files in the project folder's `programs/` directory.

Output files in `Implementation Docs/` (named after the instance):
- `{Instance Name}-CRM-Reference.md` — Markdown version
- `{Instance Name}-CRM-Reference.docx` — Word document

For example, an instance named "CBM Demo CRM" produces
`CBM Demo CRM-CRM-Reference.md` and `CBM Demo CRM-CRM-Reference.docx`.

The **Generate Docs** button is enabled when the selected instance has
a project folder with at least one `.yaml` file in `programs/`. If no
project folder is configured, the output panel shows a message asking
you to edit the instance and add one.

Regenerate the docs whenever YAML files are updated. Commit both the
updated YAML files and the regenerated docs to the client repository.

---

## Reports

After each Run or Verify, two report files are written to the project
folder's `reports/` directory (or `reports/` in the tool directory if
no project folder is configured):

- **`.log`** — Human-readable text report
- **`.json`** — Machine-readable structured report

Filename format: `{instance}_{operation}_{timestamp}_{version}.log`

Example: `cbm_test_run_20260323_155604_v1_0_0.log`

Click **View Report** to open the most recent log file.

---

## Writing YAML Program Files

### File Structure

```yaml
version: "1.0"
content_version: "1.0.0"
description: "What this file configures"

# Source: PRD document and section

entities:
  EntityName:
    description: >
      Required. Why this entity exists, its role in the data model,
      and PRD reference.
    fields:
      - name: fieldName
        type: varchar
        label: "Display Label"
        description: "Why this field exists. PRD reference."
        category: "Tab Name"

relationships:
  - name: relName
    ...
```

### content_version

Increment `content_version` when you change a file:

| Change | Bump |
|---|---|
| Description or comment fixes | PATCH (1.0.0 → 1.0.1) |
| New fields or enum values added | MINOR (1.0.0 → 1.1.0) |
| Fields removed, types changed | MAJOR (1.0.0 → 2.0.0) |

### Entity Blocks

```yaml
entities:
  Engagement:                     # natural name — no C-prefix
    description: >
      Required entity description with PRD reference.
    action: delete_and_create     # omit for native entities
    type: Base
    labelSingular: "Engagement"
    labelPlural: "Engagements"
    stream: true
    fields: [...]
    layout: {...}
```

**Action values:**

| Action | When to Use |
|---|---|
| *(omit)* | Native entities (Account, Contact) — fields only |
| `delete_and_create` | Custom entities — clean rebuild |
| `create` | Custom entities — first-time only |
| `delete` | Remove an entity (no fields allowed) |

### Field Definitions

```yaml
- name: mentorStatus       # lowerCamelCase, no c-prefix
  type: enum
  label: "Mentor Status"
  description: >
    Why this field exists. What decision it supports. PRD reference.
  category: "Mentor Role & Capacity"
  required: true
  default: "Submitted"
  readOnly: false
  options:
    - "Submitted"
    - "Active"
    - "Inactive"
  translatedOptions:
    "Submitted": "Submitted"
    "Active": "Active"
    "Inactive": "Inactive"
  style:
    "Submitted": "info"
    "Active": "success"
    "Inactive": "default"
```

**Supported field types:**

| Type | Description | Extra Properties |
|---|---|---|
| `varchar` | Single-line text | `maxLength` |
| `text` | Multi-line plain text | |
| `wysiwyg` | Rich text (HTML editor) | |
| `enum` | Single-select dropdown | `options`, `style`, `isSorted` |
| `multiEnum` | Multi-select dropdown | `options`, `style` |
| `bool` | Checkbox | |
| `int` | Integer | `min`, `max` |
| `float` | Decimal | `min`, `max` |
| `date` | Date picker | |
| `datetime` | Date and time | |
| `currency` | Monetary value | |
| `url` | URL | |
| `email` | Email address | |
| `phone` | Phone number | |

**Enum styles:** `null` (default), `"default"` (gray), `"primary"` (blue),
`"success"` (green), `"danger"` (red), `"warning"` (orange), `"info"` (light blue)

### Layout Definitions

```yaml
layout:
  detail:
    panels:

      # Category-based tab (fields grouped automatically)
      - label: "Mentor Details"
        tabBreak: true
        tabLabel: "Mentor"
        description: "Visible only when Contact Type = Mentor."
        dynamicLogicVisible:
          attribute: contactType   # no c-prefix in YAML
          value: "Mentor"
        tabs:
          - label: "Identity"
            category: "Mentor Identity & Contact"
          - label: "Skills"
            category: "Mentor Skills & Expertise"

      # Explicit rows (precise field placement)
      - label: "Overview"
        tabBreak: true
        tabLabel: "Overview"
        rows:
          - [name, website]
          - [organizationType, accountType]
          - [businessStage, null]   # null = empty cell

  list:
    columns:
      - field: name
        width: 25
      - field: contactType
        width: 15
```

**Layout rules:**
- Each panel has either `rows` OR `tabs`, not both
- `tabBreak: true` requires `tabLabel`
- Tab `category` must match at least one field's `category`
- wysiwyg and text fields in category tabs auto-generate as full-width rows
- Native field names in rows (name, emailAddress) pass through without prefix

### Relationship Definitions

```yaml
relationships:

  # New relationship to create
  - name: duesToMentor
    description: >
      Links Dues records to the mentor Contact. PRD reference.
    entity: Dues             # natural name — no C-prefix
    entityForeign: Contact
    linkType: manyToOne
    link: mentor
    linkForeign: duesRecords
    label: "Mentor"
    labelForeign: "Dues Records"
    audited: false

  # Pre-existing relationship (skip creation)
  - name: engagementToSessions
    entity: Engagement
    entityForeign: Session
    linkType: oneToMany
    link: engagementSessionses
    linkForeign: sessionEngagement
    label: "Sessions"
    labelForeign: "Engagement"
    action: skip
```

**Link types:**

| Type | Meaning |
|---|---|
| `oneToMany` | One primary → many foreign |
| `manyToOne` | Many primary → one foreign |
| `manyToMany` | Many both ways (requires `relationName`) |

**Important — linkForeign c-prefix rule:**
When the foreign entity is a custom entity (C-prefix), the `linkForeign`
value must also include the c-prefix. Example: if the foreign link on
`CEngagement` is named `npsSurveyResponses`, specify
`linkForeign: cNpsSurveyResponses`.

When the primary entity is native (Account, Contact), specify the `link`
name without a c-prefix. EspoCRM will auto-apply it and the tool handles
this correctly.

---

## Naming Conventions

EspoCRM automatically adds a `c` prefix to custom entity and field names.
You never add this prefix in your YAML — the tool handles it:

- Custom entity: `Engagement` → stored as `CEngagement`
- Custom field: `contactType` → stored as `cContactType`

You only add the c-prefix explicitly when:
- Specifying `linkForeign` values for custom entity foreign sides
- Referencing native fields in layout rows (no prefix needed there)

---

## Troubleshooting

### HTTP 403 on all operations
Your API user lacks admin access. Switch to **Basic** authentication
with your admin username and password.

### TYPE CONFLICT on a field
The field exists with a different type than specified in the YAML. The
tool skips it. To resolve: manually delete the field in EspoCRM Entity
Manager, then run the YAML file to recreate it correctly. Note: deleting
a field destroys its data — export records first on production.

### VERIFY FAILED after relationships
This may be a cosmetic bug in the verify step for certain relationship
types. Check that the relationship actually exists via:
`/api/v1/Metadata?key=entityDefs.{Entity}.links.{linkName}`

### Program file panel is empty
Ensure the selected instance has a project folder configured, and that
the `programs/` subdirectory contains `.yaml` files.

### Generate Docs shows an error
Ensure Node.js is installed for Word document generation. The Markdown
output does not require Node.js.

### Confirmation dialog on Run
Your program file contains `action: delete_and_create` or `action: delete`.
Choose **Skip deletes** for safe field-only updates on live instances.
Only choose **Proceed with deletes** on test instances or when doing
a clean rebuild with no live data.
---

## Changelog

| Version | Date | Changes |
|---|---|---|
| 2.1 | March 2026 | Renamed to CRM Builder |
| 2.0 | March 2026 | Complete rewrite — added project folder concept, content versioning, layout and relationship configuration, Generate Docs button, updated troubleshooting |
| 1.0 | Early 2026 | Initial release covering field management only |
