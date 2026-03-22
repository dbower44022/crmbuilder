# EspoCRM Implementation Tool — User Guide

## What This Tool Does

The EspoCRM Implementation Tool automates the configuration of an EspoCRM instance. Instead of manually creating fields and entities through the EspoCRM admin UI, you write a declarative YAML file that describes the desired configuration, and the tool applies it via the EspoCRM REST API.

The tool is **idempotent** — you can run the same program file repeatedly and it will only make changes where the current instance state differs from your specification.

---

## Installation

### Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) package manager

### Setup

```bash
cd espo-implementation-tool
uv sync
```

### Launch

```bash
uv run espo-impl
```

The application window opens. On first launch, the `data/instances/`, `data/programs/`, and `reports/` directories are created automatically.

---

## Quick Start

1. **Add an instance** — Click "+ Add" in the Instance panel, enter your EspoCRM URL and credentials
2. **Add a program file** — Click "+ Add" in the Program File panel and select a YAML file
3. **Select both** — Click the instance name and the program file name
4. **Validate** — Parses the YAML for structural errors, then connects to the selected instance to preview what changes would be made. Requires the instance to be reachable.
5. **Run** — Click "Run" to apply the configuration

---

## Application Layout

```
+---------------------------+  +-------------------------------+
|  INSTANCE                 |  |  PROGRAM FILE                 |
|                           |  |                               |
|  > CBM Production         |  |  > cbm_contact_fields.yaml    |
|    CBM Staging            |  |    cbm_full_rebuild.yaml      |
|                           |  |                               |
|  [+ Add] [Edit] [Delete]  |  |  [+ Add] [Edit] [Delete]     |
|                           |  +-------------------------------+
|  URL: https://cbm.espo... |
|  Key: ****************    |  [Validate]  [Run]  [Verify]
+---------------------------+  +-------------------------------+
|  OUTPUT                                                      |
|                                                              |
|  [VALIDATE] OK — 7 entities, 67 fields found                 |
|  [CHECK]   Contact.contactType ... EXISTS                    |
|  [SKIP]    Contact.contactType ... NO CHANGES NEEDED         |
|                                                              |
+--------------------------------------------------------------+
[Clear Output]                                   [View Report]
```

---

## Managing Instances

### Adding an Instance

1. Click **"+ Add"** in the Instance panel
2. Fill in:
   - **Name** — A display name (e.g., "CBM Production")
   - **URL** — Your EspoCRM base URL (e.g., `https://your-instance.espocloud.com`)
   - **Auth Method** — Choose one of three methods (see below)
   - **Credentials** — API key/username and secret/password
3. Click **Save**

### Authentication Methods

| Method | API Key / Username Field | Secret / Password Field | When to Use |
|--------|--------------------------|------------------------|-------------|
| **API Key** | EspoCRM API key | (not used) | For API Users with admin access |
| **HMAC** | HMAC API key | HMAC secret key | For API Users using HMAC auth |
| **Basic** | Admin username | Admin password | For regular admin users (recommended for EspoCRM Cloud) |

**Recommendation for EspoCRM Cloud:** Use **Basic** authentication with your admin login credentials. EspoCRM Cloud API Users cannot be granted true admin access, which is required for the Admin/fieldManager and EntityManager endpoints.

### Editing and Deleting Instances

- Select an instance from the list
- Click **Edit** to modify its settings
- Click **Delete** to remove it (with confirmation prompt)

Instance profiles are stored as JSON files in `data/instances/`. API keys and passwords are stored in plain text — this tool is intended for use on secured administrator machines.

---

## Managing Program Files

### Importing a Program File

1. Click **"+ Add"** in the Program File panel
2. Select a `.yaml` or `.yml` file from the file picker
3. The file is copied into `data/programs/`

### Editing a Program File

Select a program file and click **Edit**. The file opens in your system's default text editor.

### Deleting a Program File

Select a program file and click **Delete** (with confirmation prompt).

---

## Workflow: Validate, Run, Verify

### Step 1: Validate

Click **Validate** after selecting both an instance and a program file.

**What happens:**
1. The YAML file is parsed and checked for structural errors
2. If valid, the tool connects to the instance and previews what changes would be made
3. The output panel shows a summary of planned actions:

```
[VALIDATE] OK — 7 entities, 67 fields found
[VALIDATE] Checking instance for planned changes ...

===========================================
PLANNED CHANGES
===========================================
  Contact.contactType — no changes needed
  Contact.mentorStatus — UPDATE (options)
  Contact.roleAtBusiness — CREATE (varchar, "Role at Business")
===========================================
  To create : 1
  To update : 1
  No change : 1
===========================================
```

The **Run** button becomes enabled after successful validation.

### Step 2: Run

Click **Run** to apply the program file to the instance.

**If the program contains delete operations**, a confirmation dialog appears. You must type `DELETE` (case-sensitive) and click **Proceed** before any changes are made.

**Execution order:**
1. Delete entities marked for deletion
2. Cache rebuild
3. Create entities marked for creation
4. Cache rebuild
5. Create/update fields for all entities

**Output during execution:**
```
=== ENTITY DELETIONS ===
[CHECK]   Entity Engagement (CEngagement) ...
[DELETE]  CEngagement ... OK
[REBUILD] Cache rebuild complete

=== ENTITY CREATION ===
[CHECK]   Entity Engagement (CEngagement) ...
[CREATE]  CEngagement ... OK
[REBUILD] Cache rebuild complete

=== FIELD OPERATIONS ===
[CHECK]   Contact.contactType ...
[CHECK]   Contact.contactType ... EXISTS
[COMPARE] Contact.contactType ... MATCHES
[SKIP]    Contact.contactType ... NO CHANGES NEEDED

[CHECK]   Contact.roleAtBusiness ...
[CHECK]   Contact.roleAtBusiness ... NOT FOUND
[CREATE]  Contact.roleAtBusiness ... OK
```

Reports are written to `reports/` as both `.log` (human-readable) and `.json` (machine-readable) files.

### Step 3: Verify

Click **Verify** after a run completes. This performs a read-only check — it re-reads every field from the instance and confirms they match the specification. No changes are made.

```
[VERIFY]  Contact.contactType ... VERIFIED
[VERIFY]  Contact.mentorStatus ... VERIFIED
[VERIFY]  Contact.roleAtBusiness ... VERIFIED
```

**Tip:** Wait a few seconds after Run before clicking Verify. EspoCRM may need time to rebuild its internal cache.

---

## Writing YAML Program Files

### Basic Structure

```yaml
version: "1.0"
description: "My EspoCRM Configuration"

entities:
  Contact:
    fields:
      - name: myField
        type: varchar
        label: "My Field"
```

### Entity Actions

Entities can have an optional `action` that controls entity-level operations:

| Action | Behavior |
|--------|----------|
| *(omitted)* | Fields only — no entity create/delete |
| `create` | Create the entity if it doesn't exist, then apply fields |
| `delete` | Delete the entity (must not have a `fields` section) |
| `delete_and_create` | Delete if exists, recreate, then apply fields |

**Example: Create a custom entity with fields**
```yaml
entities:
  Engagement:
    action: create
    type: Base
    labelSingular: "Engagement"
    labelPlural: "Engagements"
    stream: true
    fields:
      - name: status
        type: enum
        label: "Status"
        options:
          - Active
          - Closed
```

**Example: Full rebuild (delete and recreate)**
```yaml
entities:
  Engagement:
    action: delete_and_create
    type: Base
    labelSingular: "Engagement"
    labelPlural: "Engagements"
    stream: true
    fields:
      - name: status
        type: enum
        ...
```

**Example: Add fields to a native entity (no action needed)**
```yaml
entities:
  Contact:
    fields:
      - name: isMentor
        type: bool
        label: "Is Mentor"
```

### Entity Types

| Type | Description |
|------|-------------|
| `Base` | General-purpose entity with name and description |
| `Person` | Includes email, phone, name, address fields |
| `Company` | Includes email, phone, billing/shipping address |
| `Event` | Includes date start/end, duration, status |

### Supported Field Types

| Type | Description | Special Properties |
|------|-------------|-------------------|
| `varchar` | Single-line text | `maxLength` |
| `text` | Multi-line plain text | |
| `wysiwyg` | Rich text editor (HTML) | |
| `enum` | Single-select dropdown | `options`, `translatedOptions`, `style`, `isSorted` |
| `multiEnum` | Multi-select dropdown | `options`, `translatedOptions`, `style` |
| `bool` | Checkbox | |
| `int` | Integer number | `min`, `max` |
| `float` | Decimal number | `min`, `max` |
| `date` | Date picker | |
| `datetime` | Date + time picker | |
| `currency` | Monetary value | |
| `url` | URL field | |
| `email` | Email address | |
| `phone` | Phone number | |

### Field Properties

| Property | Type | Required | Description |
|----------|------|----------|-------------|
| `name` | string | Yes | Internal field name (lowerCamelCase) |
| `type` | string | Yes | Field type (see table above) |
| `label` | string | Yes | Display label in the UI |
| `required` | boolean | No | Whether the field is mandatory |
| `default` | string | No | Default value |
| `readOnly` | boolean | No | Whether the field is read-only |
| `audited` | boolean | No | Whether changes are tracked |
| `options` | list | Enum/multiEnum | List of option values |
| `translatedOptions` | map | Enum/multiEnum | Display labels for each option |
| `style` | map | Enum/multiEnum | Color style per option |
| `isSorted` | boolean | Enum/multiEnum | Sort options alphabetically |
| `displayAsLabel` | boolean | Enum/multiEnum | Display as colored badge |
| `min` | integer | No | Minimum allowed value (int/float fields) |
| `max` | integer | No | Maximum allowed value (int/float fields) |
| `maxLength` | integer | No | Maximum character length (varchar fields) |

### Enum Field Example

```yaml
- name: mentorStatus
  type: enum
  label: "Mentor Status"
  required: false
  default: ""
  isSorted: false
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
    "Provisional": null
    "Active": "success"
    "Inactive": "danger"
    "Departed": null
```

### Available Styles for Enum Options

- `null` or omitted — Default (no color)
- `"default"` — Gray
- `"primary"` — Blue
- `"success"` — Green
- `"danger"` — Red
- `"warning"` — Yellow/Orange
- `"info"` — Light blue

---

## Entity and Field Naming

EspoCRM automatically adds a prefix to custom entity and field names:

- **Custom entities:** `Engagement` becomes `CEngagement` internally
- **Custom fields:** `contactType` becomes `cContactType` internally

**You do not need to add these prefixes in your YAML files.** Write natural names and the tool handles the translation automatically.

---

## Reports

After each Run or Verify operation, two report files are generated in the `reports/` directory:

- **`.log`** — Human-readable text report with timestamps and summaries
- **`.json`** — Machine-readable structured report

Click **View Report** to open the most recent `.log` file in your system text viewer.

**Filename format:** `{instance_slug}_{operation}_{timestamp}.log`

Example: `cbm_production_run_20260321_143022.log`

---

## Output Panel Colors

| Color | Meaning |
|-------|---------|
| White | Informational messages |
| Green | Success (created, updated, verified, rebuild complete) |
| Yellow | Warnings (skipped, type conflict, cancelled) |
| Red | Errors (API failures, verification failures) |
| Gray | No change needed |

Output is preserved across operations within the same session. Click **Clear Output** to reset.

---

## Error Handling

The tool uses a **continue-and-log** strategy. A failure on one field does not stop processing of subsequent fields.

| Error | Behavior |
|-------|----------|
| YAML parse error | Shown in output, Run button stays disabled |
| Missing required YAML fields | All errors shown, Run blocked |
| HTTP 401 (Unauthorized) | Entire run aborted |
| HTTP 403 (Forbidden) | Field marked as error, processing continues |
| HTTP 409 (Conflict) | Field exists under different name, falls back to update |
| HTTP 500+ (Server error) | Field marked as error, processing continues |
| Network timeout | Field marked as error, processing continues |
| Type mismatch | Field skipped with warning |

---

## Troubleshooting

### "HTTP 403 Forbidden" on all fields
Your API user doesn't have admin access. Use **Basic** authentication with your regular EspoCRM admin credentials instead.

### "HTTP 409 Conflict" on field creation
The field already exists under its c-prefixed name. The tool will automatically fall back to updating the field.

### Fields show "NOT FOUND" but exist in EspoCRM
Custom fields are stored with a `c` prefix. The tool tries the c-prefixed name first. If both lookups fail, the field may have been created through a different mechanism.

### Verification fails after successful Run
EspoCRM's cache may not have updated yet. Wait a few seconds and click **Verify** again.

### Confirmation dialog appears before Run
Your program file contains entity delete operations (`action: delete` or `action: delete_and_create`). Type `DELETE` to confirm, or click Cancel to abort.
