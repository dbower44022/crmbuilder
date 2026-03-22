# EspoCRM Implementation Program — Technical Specification

**Project:** Cleveland Business Mentors (CBM)  
**Version:** 1.4  
**Status:** Draft — Phase 1 (Entity Fields + Entity Management)  
**Target:** Claude Code implementation

---

## 1. Overview

This program automates the configuration of an EspoCRM instance by reading a declarative YAML program file and applying its contents via the EspoCRM REST API. It presents a PySide6 desktop UI that allows an administrator to select an EspoCRM instance profile and a reusable program file, then validate, run, and verify the deployment in sequence.

The program is designed to be idempotent — it can be run repeatedly and will only make changes where the current instance state differs from the desired spec. Program files are generic and reusable against any EspoCRM instance.

Phase 1 covers entity fields and custom entity management (create and delete). Future phases will add additional object types using the same architecture.

---

## 2. Application Structure

```
espocrm_impl/
├── main.py                  # Entry point — launches PySide6 application
├── ui/
│   ├── main_window.py       # Main application window
│   ├── instance_panel.py    # Instance profile management panel
│   └── program_panel.py     # Program file management panel
├── core/
│   ├── config_loader.py     # YAML loading and validation
│   ├── api_client.py        # EspoCRM REST API wrapper
│   ├── entity_manager.py    # Custom entity create/delete logic
│   ├── field_manager.py     # Field check/create/update/verify logic
│   ├── comparator.py        # Field state comparison logic
│   └── reporter.py          # Log and JSON report generation
├── data/
│   ├── instances/           # Instance profile storage (JSON files)
│   └── programs/            # YAML program files
└── reports/                 # Timestamped run reports (.log and .json)
```

### 2.1 Dependencies

```
PySide6       # Desktop UI framework
requests    # HTTP client
pyyaml      # YAML parsing
```

Targets Python 3.9+.

---

## 3. Desktop UI Design

The application opens as a single main window with a clean, professional layout. All interaction happens within this window.

### 3.1 Main Window Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  EspoCRM Implementation Tool                                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐  │
│  │  INSTANCE               │  │  PROGRAM FILE                   │  │
│  │                         │  │                                 │  │
│  │  ○ CBM Production       │  │  ○ cbm_contact_fields.yaml      │  │
│  │  ○ CBM Staging          │  │  ○ cbm_engagement_entity.yaml   │  │
│  │                         │  │  ○ base_config.yaml             │  │
│  │  [+ Add] [✎ Edit] [✕]  │  │                                 │  │
│  │                         │  │  [+ Add] [✎ Edit] [✕]          │  │
│  ├─────────────────────────┤  └─────────────────────────────────┘  │
│  │  URL:  _______________  │                                        │
│  │  Key:  ••••••••••••••   │  ┌─────────────────────────────────┐  │
│  │  [Save Instance]        │  │  [Validate] [Run] [Verify]      │  │
│  └─────────────────────────┘  └─────────────────────────────────┘  │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  OUTPUT                                                         ││
│  │                                                                 ││
│  │  [CHECK]  Contact.contactType ... EXISTS                        ││
│  │  [COMPARE] Contact.contactType ... DIFFERS (label, options)     ││
│  │  [UPDATE] Contact.contactType ... OK                            ││
│  │  [VERIFY] Contact.contactType ... VERIFIED                      ││
│  │                                                                 ││
│  └─────────────────────────────────────────────────────────────────┘│
│  [Clear Output]                                        [View Report] │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Instance Panel

Displays a list of saved instance profiles. Each profile stores:
- Display name (e.g., "CBM Production")
- EspoCRM URL
- API Key (stored in plain text in a local JSON file)

Selecting an instance auto-populates the URL and API Key fields below the list.

**Add Instance** opens a dialog prompting for name, URL, and API key.
**Edit Instance** opens the same dialog pre-populated with the selected instance's values.
**Delete Instance** prompts for confirmation before removing.
**Save Instance** saves any changes made to the URL or API Key fields directly.

Instance profiles are stored as individual JSON files in `data/instances/`.

### 3.3 Program File Panel

Displays a list of available YAML program files from the `data/programs/` directory.

**Add Program** opens the OS file picker to import a YAML file into `data/programs/`.
**Edit Program** opens the selected YAML file in the system's default text editor.
**Delete Program** prompts for confirmation before removing.

Program files are generic — they contain no instance-specific information and can be applied to any EspoCRM instance.

### 3.4 Action Buttons

Three buttons execute the workflow in sequence. Buttons are enabled/disabled based on state:

| Button | Enabled When | Action |
|---|---|---|
| **Validate** | Instance and program both selected | Parses and validates the YAML file; checks structure and required fields; does NOT contact the EspoCRM API |
| **Run** | Validate has passed | Applies the program to the selected instance; check → act → verify cycle per field |
| **Verify** | Run has completed | Re-reads the instance state and confirms all fields match the spec; read-only, makes no changes |

Button states:
- **Validate** is always available once both selections are made
- **Run** becomes available only after a successful Validate
- **Verify** becomes available after Run completes (whether or not errors occurred)
- All three buttons are disabled while any operation is in progress
- A spinner/progress indicator is shown during active operations

### 3.5 Output Panel

A scrollable, read-only text area using a monospace font that displays real-time output as operations execute. Output is color-coded:

| Color | Meaning |
|---|---|
| White / default | Informational messages |
| Green | Success (created, updated, verified) |
| Yellow | Warning (skipped, type conflict) |
| Red | Error or verification failure |
| Gray | No-change / skipped |

Output is not cleared between operations in the same session — the full history of a session is visible. The **Clear Output** button resets the panel.

### 3.6 View Report Button

After a Run or Verify operation, the **View Report** button becomes active. Clicking it opens the most recent `.log` report file in the system's default text viewer.

---

## 4. Instance Profile Storage

Instance profiles are stored as JSON files in `data/instances/`. One file per instance.

```json
{
  "name": "CBM Production",
  "url": "https://cleveland-business-mentors.espocloud.com",
  "api_key": "your-api-key-here"
}
```

Filenames are slugified from the instance name (e.g., `cbm_production.json`).

The API key is stored in plain text. This tool is intended for internal administrative use on secured machines.

---

## 5. YAML Program File Format

Program files are the machine-readable deployment specs. They live in `data/programs/` and contain no instance-specific information.

### 5.1 Top-Level Structure

```yaml
version: "1.0"
description: "CBM EspoCRM Configuration — Contact Fields"

entities:
  Contact:
    fields:
      - ...
```

### 5.2 Field Definition Schema

Each field entry under an entity's `fields` list supports the following properties:

| Property | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Internal field name (lowerCamelCase) |
| `type` | string | yes | EspoCRM field type (see 5.3) |
| `label` | string | yes | Display label shown in UI |
| `required` | boolean | no | Default: false |
| `default` | string | no | Default value |
| `readOnly` | boolean | no | Default: false |
| `audited` | boolean | no | Default: false |
| `options` | list | enum/multiEnum only | List of option values |
| `translatedOptions` | map | enum/multiEnum only | Display labels for each option value |
| `style` | map | enum/multiEnum only | Color style per option (null = default) |
| `isSorted` | boolean | enum/multiEnum only | Sort options alphabetically |
| `displayAsLabel` | boolean | enum/multiEnum only | Display as colored label badge |
| `min` | integer | int/float only | Minimum allowed value |
| `max` | integer | int/float only | Maximum allowed value |
| `maxLength` | integer | varchar only | Maximum character length |

### 5.3 Supported Field Types (Phase 1)

- `varchar` — single-line text
- `text` — multi-line text
- `wysiwyg` — rich text editor (HTML content)
- `enum` — single-select dropdown
- `multiEnum` — multi-select dropdown
- `bool` — checkbox / boolean
- `int` — integer
- `float` — decimal number
- `date` — date picker
- `datetime` — date + time picker
- `currency` — monetary value
- `url` — URL field
- `email` — email address
- `phone` — phone number

### 5.4 Example Program File

```yaml
version: "1.0"
description: "CBM EspoCRM Configuration — Contact Fields"

entities:
  Contact:
    fields:
      - name: contactType
        type: enum
        label: "Contact Type"
        required: false
        default: ""
        options:
          - Mentor
          - Client
        translatedOptions:
          Mentor: "Mentor"
          Client: "Client"
        style:
          Mentor: null
          Client: null

      - name: mentorStatus
        type: enum
        label: "Mentor Status"
        required: false
        default: ""
        options:
          - Provisional
          - Active
          - Inactive
          - Departed
        translatedOptions:
          Provisional: "Provisional"
          Active: "Active"
          Inactive: "Inactive"
          Departed: "Departed"
        style:
          Provisional: null
          Active: null
          Inactive: null
          Departed: null

      - name: isMentor
        type: bool
        label: "Is Mentor"

      - name: isCoMentor
        type: bool
        label: "Is Co-Mentor"

      - name: isSme
        type: bool
        label: "Is SME"
```

---

## 6. Processing Logic

### 6.1 Validate

Validates the selected YAML file without contacting the EspoCRM API:

- File parses as valid YAML
- Top-level `version`, `description`, and `entities` keys are present
- Each field entry has required properties: `name`, `type`, `label`
- Field types are from the supported list
- Enum/multiEnum fields have a non-empty `options` list
- No duplicate field names within the same entity

Output: pass with field/entity count summary, or fail with specific error messages for each issue found.

### 6.2 Run

For each field defined in the YAML program file, executes the following three-phase cycle:

**Phase 1 — Check**

```
GET /api/v1/Admin/fieldManager/{Entity}/{fieldName}
```

- HTTP 404 → field does not exist → proceed to Create
- HTTP 200 → field exists → compare to spec → Update if differs, Skip if matches

**Phase 2 — Act**

Create (field does not exist):
```
POST /api/v1/Admin/fieldManager/{Entity}
```
Payload: full field definition from YAML, plus `"isCustom": true`

Update (field exists but differs):
```
PUT /api/v1/Admin/fieldManager/{Entity}/{fieldName}
```
Payload: full field definition from YAML

Skip: no API call made if field already matches spec.

**Phase 3 — Verify**

After any Create or Update, issue a fresh GET to confirm the field now matches the spec. Record as Verified or Verification Failed.

### 6.3 Verify (Standalone)

Re-reads every field defined in the program file from the live instance and compares each to its spec. Makes no changes. Reports compliance status for every field — useful for confirming a deployment after the fact.

### 6.4 Field Comparison Rules

The following properties are compared between current state and desired spec:

- `type` — if differs, log warning and skip (type changes not supported)
- `label`
- `required`
- `default`
- `readOnly`
- `audited`
- `options` (enum/multiEnum — order matters)
- `translatedOptions` (enum/multiEnum)
- `style` (enum/multiEnum)

---

## 7. Error Handling

The program uses a **continue-and-log** strategy. A failure on one field does not stop processing of subsequent fields.

| Error Condition | Behavior |
|---|---|
| Network timeout or connection error | Log error, mark field as ERROR, continue |
| HTTP 401 Unauthorized | Log error, abort entire run |
| HTTP 403 Forbidden | Log error, mark field as ERROR, continue |
| HTTP 404 on GET | Treat as field does not exist, proceed to Create |
| HTTP 4xx on POST/PUT | Log error and response body, mark field as ERROR, continue |
| HTTP 5xx | Log error and response body, mark field as ERROR, continue |
| Type mismatch | Log warning, skip field, mark as SKIPPED_TYPE_CONFLICT |
| Verification failure after create/update | Log warning, mark as VERIFICATION_FAILED, continue |
| YAML parse error | Shown in output panel, Run button remains disabled |
| Missing required YAML fields | All validation errors shown in output panel, Run blocked |

---

## 8. Output and Reporting

### 8.1 Output Panel Messages

```
[VALIDATE] Parsing cbm_contact_fields.yaml ...
[VALIDATE] OK — 2 entities, 5 fields found

[CHECK]   Contact.contactType ... EXISTS
[COMPARE] Contact.contactType ... DIFFERS (label, options)
[UPDATE]  Contact.contactType ... OK
[VERIFY]  Contact.contactType ... VERIFIED

[CHECK]   Contact.isMentor ... NOT FOUND
[CREATE]  Contact.isMentor ... OK
[VERIFY]  Contact.isMentor ... VERIFIED

[CHECK]   Contact.mentorStatus ... EXISTS
[COMPARE] Contact.mentorStatus ... MATCHES
[SKIP]    Contact.mentorStatus ... NO CHANGES NEEDED

===========================================
RUN SUMMARY
===========================================
Total fields processed : 5
  Created              : 2
  Updated              : 1
  Skipped (no change)  : 1
  Verification failed  : 0
  Errors               : 1
===========================================
Reports written to:
  reports/cbm_crm_run_20260321_143022.log
  reports/cbm_crm_run_20260321_143022.json
===========================================
```

### 8.2 Log File (.log)

Human-readable timestamped report written to `reports/`. Contains run metadata (instance name, URL, program file, operation type, timestamp), full per-field narrative, and summary.

Filename: `cbm_crm_run_YYYYMMDD_HHMMSS.log`

### 8.3 JSON Report (.json)

Structured machine-readable report written to `reports/`.

```json
{
  "run_metadata": {
    "timestamp": "2026-03-21T14:30:22Z",
    "instance": "CBM Production",
    "espocrm_url": "https://cleveland-business-mentors.espocloud.com",
    "program_file": "cbm_contact_fields.yaml",
    "operation": "run"
  },
  "summary": {
    "total": 5,
    "created": 2,
    "updated": 1,
    "skipped": 1,
    "verification_failed": 0,
    "errors": 1
  },
  "results": [
    {
      "entity": "Contact",
      "field": "contactType",
      "status": "updated",
      "verified": true,
      "changes": ["label", "options"],
      "error": null
    },
    {
      "entity": "Contact",
      "field": "isMentor",
      "status": "created",
      "verified": true,
      "changes": null,
      "error": null
    }
  ]
}
```

Filename: `cbm_crm_run_YYYYMMDD_HHMMSS.json`

---

## 9. Entity Name Mapping

EspoCRM automatically applies a `c` prefix to all custom entity and field names to prevent naming conflicts with future core versions. The YAML program files use clean, natural names. The tool is responsible for translating between natural names and EspoCRM internal names.

### 9.1 Field Name Mapping

When the YAML specifies `name: contactType`, the tool:
- Uses `contactType` (no prefix) in POST payloads to `Admin/fieldManager` — EspoCRM adds the `c` prefix automatically on creation
- Uses `cContactType` (with prefix) in GET and PUT requests to `Admin/fieldManager/{entity}/cContactType`

Rule: strip any leading `c` from stored names when comparing to YAML spec names.

### 9.2 Entity Name Mapping

Custom entity names in YAML use natural names (e.g., `Engagement`). EspoCRM stores them with a `C` prefix (e.g., `CEngagement`).

The tool maintains an internal mapping applied at runtime:

| YAML Name | EspoCRM Internal Name |
|---|---|
| `Engagement` | `CEngagement` |
| `Session` | `CSessions` |
| `Workshop` | `CWorkshops` |
| `WorkshopAttendance` | `CWorkshopAttendee` |
| `NpsSurveyResponse` | `CNpsSurveyResponse` |

This mapping is hardcoded in `entity_manager.py` for Phase 1. A future enhancement could make it configurable per YAML file.

For native EspoCRM entities (`Contact`, `Account`), no mapping is applied — they are used as-is.

---

## 10. Entity Management

Phase 1 adds support for three entity-level operations in the YAML program file: **create**, **delete**, and **delete_and_create**. These are declared in a top-level `entities` block alongside the existing `fields` structure.

### 10.1 YAML Schema — Entity Block

```yaml
version: "1.0"
description: "CBM Full Rebuild"

entities:
  Engagement:
    action: delete_and_create     # "create", "delete", or "delete_and_create"
    type: Base                    # Entity type (see 10.2)
    labelSingular: "Engagement"
    labelPlural: "Engagements"
    stream: true
    fields:
      - name: status
        type: enum
        ...

  Contact:                        # No action — fields only
    fields:
      - name: contactType
        type: enum
        ...
```

**Supported actions:**
- `create` — Create the entity if it does not exist, then apply fields
- `delete` — Delete the entity if it exists (must not contain `fields`)
- `delete_and_create` — Delete the entity if it exists, recreate it, then apply fields. This is the preferred pattern for full rebuilds, as it avoids the duplicate YAML key problem that would arise from using separate `delete` and `create` blocks for the same entity name.

If `action` is omitted from an entity block, it defaults to field-only operations (no entity create/delete attempted). This preserves backward compatibility with existing YAML files that only define fields on native entities like `Contact` and `Account`.

### 10.2 Supported Entity Types

| Type | Description |
|---|---|
| `Base` | General-purpose entity with name and description fields |
| `Person` | Includes email, phone, first/last name, address fields |
| `Company` | Includes email, phone, billing/shipping address fields |
| `Event` | Includes date start/end, duration, status, parent fields |

### 10.3 Entity Create Properties

| Property | Type | Required | Description |
|---|---|---|---|
| `action` | string | yes | `"create"`, `"delete"`, or `"delete_and_create"` |
| `type` | string | create only | Entity type (see 10.2). Default: `Base` |
| `labelSingular` | string | create only | Singular display name |
| `labelPlural` | string | create only | Plural display name |
| `stream` | boolean | no | Enable Stream panel. Default: false |
| `disabled` | boolean | no | Mark entity as disabled. Default: false |

### 10.4 Processing Logic — Create

Check if entity exists:
```
GET /api/v1/Metadata?key=scopes.{CEntityName}
```

- If entity already exists → skip, log as SKIPPED
- If entity does not exist → POST to create

```
POST /api/v1/EntityManager/action/createEntity
```

Confirmed payload structure:
```json
{
  "name": "Engagement",
  "type": "Base",
  "labelSingular": "Engagement",
  "labelPlural": "Engagements",
  "stream": true,
  "disabled": false
}
```

Note: The `name` field uses the natural name (no C prefix). EspoCRM adds the C prefix automatically during creation.

After creation, trigger a cache rebuild, then proceed to field creation for all fields defined in the same entity block.

### 10.5 Processing Logic — Delete

```
POST /api/v1/EntityManager/action/removeEntity
```

Payload:
```json
{
  "name": "CEngagement"
}
```

Note: The `name` field uses the **C-prefixed** internal name. Both create and delete use POST (not PUT/DELETE methods).

Delete operations are **destructive and irreversible**. Any entity marked `action: delete` or `action: delete_and_create` triggers the confirmation dialog described in section 10.6 before any processing begins.

Delete removes the entity type and all its custom fields. It does not delete data records (those are handled by EspoCRM internally). After deletion, a cache rebuild is required.

### 10.6 Destructive Operation Confirmation Dialog

Before executing any run that contains one or more `action: delete` or `action: delete_and_create` entries, the program must pause and display a modal confirmation dialog. This dialog fires before any API calls are made — including non-destructive ones in the same program file.

The dialog presents two radio button options, allowing the user to choose between a safe field-update mode and a full destructive rebuild at runtime.

**Dialog content:**

```
┌──────────────────────────────────────────────────────┐
│  Delete Operations Detected                          │
├──────────────────────────────────────────────────────┤
│                                                      │
│  The program "cbm_full_rebuild.yaml" contains        │
│  DELETE operations for the following entities:       │
│                                                      │
│    • CEngagement  (delete and create)                │
│    • CSessions  (delete and create)                  │
│    • CWorkshops  (delete and create)                 │
│                                                      │
│  ○ Skip deletes — update fields only                 │
│    Safe for live instances with existing data.       │
│                                                      │
│  ○ Proceed with deletes — full rebuild               │
│    Destroys all data in listed entities.             │
│    Type DELETE to confirm: [____________]            │
│                                                      │
│                          [Cancel]  [Proceed]          │
└──────────────────────────────────────────────────────┘
```

**Behavior:**

- **"Skip deletes"** is selected by default when the dialog opens
- When "Skip deletes" is selected, the DELETE text field is hidden and the **Proceed** button is immediately enabled
- When "Proceed with deletes" is selected, the DELETE text field appears and the **Proceed** button is disabled until `DELETE` is typed exactly (case-sensitive)
- Clicking **Cancel** returns to the main window with no changes made
- The dialog lists the EspoCRM internal names (with `C` prefix) so the user sees exactly what will be affected

**Return values:**

The dialog returns one of three outcomes:

| Return Value | Meaning |
|---|---|
| `SKIP_DELETES` | User chose "Skip deletes" and clicked Proceed. No entity deletions are performed. Entities with `delete_and_create` are treated as `create` (create-if-not-exists). Field operations proceed normally for all entities. |
| `FULL_REBUILD` | User chose "Proceed with deletes", typed DELETE, and clicked Proceed. Full destructive rebuild: delete entities, rebuild cache, create entities, rebuild cache, apply fields. |
| `CANCELLED` | User clicked Cancel. No changes are made. Run is aborted. |

### 10.7 Cache Rebuild

After any run that includes entity creation or deletion, the program must trigger a cache rebuild:

```
POST /api/v1/Admin/rebuild
```

This ensures the new or removed entities are visible in the EspoCRM UI immediately. The rebuild is logged in the output panel and included in the run report.

---

## 11. Updated YAML Schema — Full Example

The `delete_and_create` action combines delete and create into a single entity block, avoiding the duplicate YAML key problem that would arise from separate `delete` and `create` blocks for the same entity name.

```yaml
version: "1.0"
description: "CBM Full Rebuild — All Custom Entities"

# WARNING: Contains delete operations. Confirmation required.
# This program deletes and recreates all custom entities,
# then applies field definitions.

entities:

  # Custom entities — delete and recreate in one block
  Engagement:
    action: delete_and_create
    type: Base
    labelSingular: "Engagement"
    labelPlural: "Engagements"
    stream: true
    fields:
      - name: status
        type: enum
        label: "Status"
        required: true
        default: "Submitted"
        options:
          - "Submitted"
          - "Active"
          - "Completed"
        ...

  Session:
    action: delete_and_create
    type: Base
    labelSingular: "Session"
    labelPlural: "Sessions"
    stream: true
    fields:
      - ...

  # Native entities — fields only, no action needed
  Contact:
    fields:
      - name: contactType
        type: enum
        label: "Contact Type"
        ...
```

---

## 12. Future Phases

| Phase | Object Type | EspoCRM Endpoint |
|---|---|---|
| 2 | Relationships | `Admin/entityManager/{entity}/relationships` (TBD) |
| 3 | Entity layouts (detail/edit/list) | `Admin/layouts/{entity}/{layoutType}` |
| 4 | Dynamic Logic rules | Embedded in field definitions (extend Phase 1) |
| 5 | Search presets / filters | `Admin/searchManager` (TBD) |
| 6 | Roles and permissions | `Role` entity via standard CRUD |

---

## 13. Notes for Implementer

- The `isCustom: true` flag must be included in all field POST payloads. EspoCRM uses this to store custom fields in the `custom/` directory.
- EspoCRM field names are stored in lowerCamelCase. The YAML `name` property must match this convention.
- The `Admin/fieldManager` and entity management endpoints require admin-level API user access. Role-based API users will receive 403.
- The target EspoCRM instance for CBM is hosted on EspoCRM Cloud (espocloud.com), version 9.3.3.
- **Entity management endpoints are not in the OpenAPI spec.** The confirmed endpoints (discovered via browser dev tools) are: `POST /api/v1/EntityManager/action/createEntity` (create) and `POST /api/v1/EntityManager/action/removeEntity` (delete). Both use POST. Create uses the natural name; delete uses the C-prefixed name. These are documented in `entity_manager.py`.
- After entity creation or deletion, always trigger `POST /api/v1/Admin/rebuild` before proceeding with field operations on the affected entity.
- All long-running operations (Run, Verify) must execute in a background thread to keep the UI responsive. Use PySide6's `QThread` or `QRunnable` with signals to post output messages back to the main thread.
- The output panel must use a monospace font for clean alignment of log-style messages.
- The `data/` and `reports/` directories should be created automatically on first launch if they do not exist.
- The confirmation dialog for destructive operations must be modal and block all other UI interaction until dismissed.
