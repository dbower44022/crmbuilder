# CRM Builder — User Guide

**Version:** 5.1
**Last Updated:** 05-02-26 18:15

---

## What CRM Builder Does

CRM Builder is a desktop application for designing, configuring, and
maintaining CRM systems. It guides you through defining your
organization's requirements, deploys those requirements to a CRM
instance, and keeps the configuration in sync as your needs evolve.

The core workflow is:

1. **Define requirements** — AI-assisted interviews capture what your
   CRM needs to track and how
2. **Select a CRM** — your requirements are scored against available
   platforms and a recommendation is made
3. **Deploy an instance** — CRM Builder provisions a new instance or
   connects to an existing one
4. **Audit an existing instance** — read the current configuration
   of a live CRM and produce YAML files as a starting point
5. **Configure** — fields, layouts, and relationships are deployed
   from declarative YAML files
6. **Verify and maintain** — configuration is checked against the
   spec at any time; changes are managed through the same workflow

The current release focuses on Steps 3–6 for EspoCRM. Steps 1 and 2
are under development.

---

## Installation

### Prerequisites

- Python 3.12 or later
- [uv](https://docs.astral.sh/uv/) package manager

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

## Application Layout

```
┌─────────────────────────┐  ┌─────────────────────────────────┐
│  INSTANCE               │  │  PROGRAM FILE                   │
│                         │  │                                 │
│  > CBM Test             │  │  cbm_contact_fields  v1.0.0    │
│    CBM Production       │  │  cbm_relationships   v1.3.0    │
│                         │  │                                 │
│  [+ Add] [Edit] [Delete]│  │  [+ Add] [Edit] [Delete]        │
│                         │  └─────────────────────────────────┘
│  URL: https://cbm...    │
│  Folder: ~/Projects/CBM │  [Validate]  [Run]  [Verify]
└─────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│  OUTPUT                                                     │
│  [CHECK]   Contact.contactType ... EXISTS                   │
│  [UPDATE]  Contact.contactType ... OK                       │
│  [VERIFY]  Contact.contactType ... VERIFIED                 │
└─────────────────────────────────────────────────────────────┘
[Clear Output] [Preview YAML] [View Report] | [Generate Docs] [Open Reference Docs] | [Import Data]
```

The bottom bar is organized into three groups:

| Group | Buttons | What They Do |
|---|---|---|
| Output utilities | Clear Output, Preview YAML, View Report | Local actions — no API calls |
| Documentation | Generate Docs, Open Reference Docs | Produce or open the reference manual |
| Data | Import Data | Import records into the CRM instance |

---

## Managing Instances

### Adding an Instance

An instance profile stores the connection details for a CRM instance.

1. Click **+ Add** in the Instance panel
2. Fill in:
   - **Name** — display name (e.g., "CBM Production")
   - **URL** — the CRM instance base URL
   - **Auth Method** — see Authentication Methods below
   - **Credentials** — API key, or username and password
   - **Role** — see Instance Roles below
   - **Project Folder** — click **Browse** to select the client
     folder on your filesystem
3. Click **Save**

CRM Builder creates `programs/`, `reports/`, and `Implementation Docs/`
subdirectories inside the project folder automatically.

### Instance Roles

Each instance has a role that determines which operations are available:

| Role | Badge | Operations | When to Use |
|------|-------|-----------|-------------|
| **Target** | `[TGT]` | Deploy, Configure | Default — instances you manage and configure |
| **Source** | `[SRC]` | Audit | Existing instances you want to read from |
| **Both** | `[S+T]` | All | Same instance for auditing and configuring |

The instance list shows a role badge next to each name so you can
tell at a glance which is which.

**When do you need a Source instance?** When you want to audit an
existing CRM that was configured manually — or migrate configuration
from one instance to another. The audit reads the CRM's current
fields, layouts, and relationships and produces YAML files you can
edit and apply elsewhere.

Existing instances created before this feature default to **Target**.

### Authentication Methods

| Method | When to Use |
|---|---|
| **API Key** | API users with admin access |
| **HMAC** | API users requiring per-request signatures |
| **Basic** | Admin username and password — required for EspoCRM Cloud, where API users cannot be granted admin access |

### Project Folder

Each instance is associated with a project folder on your local
filesystem:

```
~/Projects/CBM/
├── programs/             ← YAML program files (loaded automatically)
├── Implementation Docs/  ← generated reference manual
└── reports/              ← run and verify reports
```

Selecting an instance automatically loads its program files. Reports
and generated documentation are written to the same folder.

### Deployment Record (Self-Hosted Instances)

Self-hosted EspoCRM instances (those deployed via the Setup Wizard
to a DigitalOcean Droplet) have a per-instance Deployment Record
`.docx` capturing the as-deployed state — Droplet identification,
hardware, OS, EspoCRM and component versions, TLS certificate, SSH
access, credentials inventory by reference, and deployment history.

The Deployment Record is produced automatically on every successful
deploy and lands at:

```
{project_folder}/PRDs/deployment/{INSTANCE_CODE}-Instance-Deployment-Record.docx
```

To regenerate it on demand (after an upgrade, after a configuration
change, or for an instance that predates the feature), select the
instance, open the **Deployment** tab, and click **Generate Deployment
Record**.

For full details — including the new wizard step that collects
documentation inputs, the regeneration dialog, and the backfill flow
for instances added before this feature shipped — see the
**EspoCRM Server Deployment Guide** (`docs/user-deployment.md`).

---

## Managing Program Files

Program files are YAML files in your project folder's `programs/`
directory. They appear in the Program File panel automatically when
you select an instance. Each file shows its `content_version`
alongside the filename.

**+ Add** — opens the OS file picker to import a YAML file into the
`programs/` directory.

**Edit** — opens the selected file in your system's default text editor.

**Delete** — removes the file after confirmation.

---

## Preview YAML

Click **Preview YAML** after selecting a program file to open an
interactive grid showing all fields defined in that YAML file.

The grid displays one row per field with all field properties as
columns — entity, field name, internal name, type, label, category,
required, description, and enum values. You can:

- **Sort** by any column — click a column header to sort ascending
  or descending
- **Search** — type in the search box to filter the grid to matching
  rows
- **Review descriptions** — the full field description is shown,
  not truncated

Preview YAML makes no API calls. It reads only from the local YAML
file and works without an instance connection.

**When to use it:**
- Before running Validate on a large YAML file, to confirm the
  fields look correct
- To cross-reference with the generated reference manual
- To check category assignments before reviewing the layout
- To share a quick overview of planned fields with a stakeholder
  without generating the full reference manual

---

## View Report

Click **View Report** to open the most recent run, verify, or import
report log file in your system's default text viewer.

Report files are stored in the project folder's `reports/` directory.
Each run produces both a `.log` (human-readable) and a `.json`
(machine-readable) file. **View Report** opens the `.log` file.

---



### Validate

Click **Validate** after selecting both an instance and a program file.

Validate parses the YAML for structural errors and previews all planned
changes without contacting the CRM. It shows what will be created,
updated, or left unchanged.

The Run button becomes available after a successful Validate.

### Run

Click **Run** to deploy the configuration to the selected instance.

**If the program contains delete operations**, a confirmation dialog
appears listing the entities that will be permanently deleted. Type
`DELETE` to confirm and click **Proceed**, or click **Cancel** to
return without making any changes.

**Processing order within a Run:**
1. Entity deletions → cache rebuild
2. Entity creations → cache rebuild
3. Field operations (check → create/update per field)
4. Layout operations (check → apply per layout)
5. Relationship operations (check → create per relationship)

**Output colors:**

| Color | Meaning |
|---|---|
| Green | Created, updated, or verified successfully |
| Gray | No change needed — already correct |
| Yellow | Warning — skipped due to conflict, or duplicate detected |
| Red | Error — operation failed |

### Verify

Click **Verify** to re-check all fields against the spec without
making changes. Use after a Run to confirm deployment, or at any
time to check whether manual changes have caused configuration drift.

---

## Generate Docs

Click **Generate Docs** to produce a CRM Implementation Reference
manual from all YAML files in the project folder's `programs/`
directory.

### What It Produces

Two files are written to the `Implementation Docs/` folder:

- `{Instance Name}-CRM-Reference.md` — Markdown version for
  version control and developer reference
- `{Instance Name}-CRM-Reference.docx` — Word document for
  stakeholders and administrators

Both files are always identical in content. The Word document uses
professional formatting suitable for sharing with clients.

### Who It Is For

The reference manual serves two audiences:

**Administrators** use it as a technical reference — looking up
field internal names, understanding layout structure, and confirming
what has been deployed.

**Stakeholders** use it to review and approve the CRM configuration
before deployment or after changes — confirming that the fields,
values, and layout match their requirements.

The document is written to be readable by both. Field descriptions
are shown in full beneath each field definition so stakeholders can
understand the business purpose of each field without needing CRM
or technical knowledge.

### What the Document Contains

```
Title Page
Table of Contents
1. Introduction
2. Entities          — one section per entity with description and properties
3. Fields            — one section per entity with full field definitions
4. Layouts           — panel and tab structure for each entity
5. List Views        — column definitions for entity list views
6. Filters           — placeholder (planned)
7. Relationships     — placeholder with relationship inventory
8. Processes         — placeholder (planned)
Appendix A           — complete enum value lists for large dropdowns
Appendix B           — deployment status summary for all entities
```

**Section 3 — Fields** is the most detailed section. Each field is
shown in a two-row format:

- **Row 1** — field name, internal name, type, required, category,
  and notes (including enum values for small dropdowns)
- **Row 2** — the field's full description in readable prose,
  spanning the full width of the table

This format allows stakeholders to scan field names quickly while
having the business rationale immediately available below each field.

### How to Use It

**During requirements review** — share the Word document with
stakeholders before deploying to a production instance. Ask them
to confirm that the fields, values, and descriptions match their
expectations. Update the YAML files based on their feedback, then
regenerate.

**After deployment** — use the document as a reference for training
administrators and users on what the CRM tracks and why.

**When requirements change** — after updating YAML files and running
the changes, regenerate the document and commit the updated version
to the repository alongside the YAML changes.

### Keeping It Up to Date

The reference manual is always generated from the YAML files —
**never edit it manually**. To update the document, update the YAML
files and click Generate Docs again.

Commit both the updated YAML files and the regenerated document to
your repository together. This keeps the document in sync with the
deployed configuration.

### Requirements

**Generate Docs requires a project folder to be configured.** If no
project folder is set, the output panel shows a message prompting
you to edit the instance and add one.

The project folder must contain at least one `.yaml` file in its
`programs/` directory.

---

## Importing Data

Click **Import Data** to open the four-step import wizard. This imports
records from a JSON file into an EspoCRM entity.

### Step 1 — Setup

1. Click **Browse** to select a JSON file
2. Choose the **Entity Type** (currently Contact)
3. Optionally add **Fixed-Value Fields** — field/value pairs applied
   to every imported record (e.g., set `Contact Type = Mentor` for
   an entire mentor import batch)

### Step 2 — Field Mapping

Map each JSON field key to a CRM field. The tool auto-maps common
fields (Email → emailAddress, Phone → phoneNumber, etc.).

- Set a field to `(skip)` to exclude it from the import
- At least one field must be mapped to proceed
- Fields used as fixed values in Step 1 are not available here

The **Unmapped Fields** panel below the table shows fields set to
skip — these are informational only; you are not required to map
every field.

### Step 3 — Preview

The tool checks each record against the CRM without making any
changes and shows the planned action for each:

| Action | Meaning |
|---|---|
| **CREATE** | No matching record found — will create |
| **UPDATE** | Existing record found — will fill empty fields only |
| **SKIP** | Existing record found — all mapped fields already have values |
| **ERROR** | No email address — record cannot be matched |

Records are matched by email address. **Existing non-empty field
values are never overwritten.**

### Step 4 — Execute

The import runs with real-time progress output. A summary and report
files are produced on completion.

### Automatic Data Handling

- **Phone numbers** — cleaned to E.164 format
  (`(216) 555-1234` → `+12165551234`)
- **First/Last name** — derived from the display name (salutations
  like Mr./Ms./Dr. are stripped); falls back to parsing from the
  email address
- **Boolean fixed values** — `"true"` / `"false"` strings are
  converted to the correct boolean type
- **Empty values** — empty string values are excluded from the import

---

## Auditing an Existing CRM

The Audit feature reads the current configuration of a live CRM
instance and produces YAML program files — the same format used by
Configure. This gives you a starting point when:

- Adopting CRM Builder on a CRM that was configured manually
- Capturing a baseline before making changes
- Migrating configuration from one CRM instance to another

### Before You Start

1. Create an instance profile for the CRM you want to audit (see
   Managing Instances above)
2. Set its **Role** to **Source** (or **Both** if you also plan to
   configure it)
3. Ensure the instance URL and credentials are correct — the audit
   needs read access to the CRM's Metadata API

### Running an Audit

1. Open the **Deployment** tab
2. Select the source instance from the picker at the top
3. Click **Audit** in the sidebar
4. Review the **Source Instance** info panel to confirm the correct
   CRM is selected
5. Adjust the **Audit Scope** checkboxes if needed:

| Option | Default | What It Does |
|--------|---------|-------------|
| Custom entity fields | On | Include custom fields on custom entities |
| Native entity custom fields | On | Include custom fields added to Contact, Account, etc. |
| Detail layouts | On | Capture detail view panel/row/tab structure |
| List layouts | On | Capture list view column definitions |
| Relationships | On | Discover links between entities |
| Include native fields | Off | Include built-in fields (firstName, etc.) that normally exist by default |

6. Click **Start Audit**

### What Happens During the Audit

A progress dialog appears showing real-time output:

```
[AUDIT]    Connecting to https://crm.example.com ...
[AUDIT]    Connection successful.
[AUDIT]    Discovering entities ...
[AUDIT]    Found 8 custom entities, 3 native entities with custom fields
[AUDIT]    Contact — extracting 12 custom fields ...
[AUDIT]    Contact — 12 fields extracted
[AUDIT]    Contact — detail layout (3 panels, 14 rows)
[AUDIT]    Contact — list layout (8 columns)
[AUDIT]    Engagement — extracting 6 custom fields ...
[AUDIT]    Discovering relationships ...
[AUDIT]    Found 8 relationships
[AUDIT]    Writing YAML files to audit-20260414-103000/ ...
[AUDIT]    Inserting database records ...
[AUDIT]    Audit complete — 12 files written, 142 DB records.
```

The audit follows a best-effort strategy: if a single entity or field
fails to read, the audit logs a warning and continues with the rest.
Only connection failures or filesystem errors stop the audit entirely.

### What the Audit Produces

**YAML files** are written to a timestamped folder inside your
project's `programs/` directory:

```
~/Projects/CBM/programs/audit-20260414-103000/
├── Contact.yaml           # Native entity with custom fields
├── Engagement.yaml        # Custom entity
├── Dues.yaml              # Custom entity
├── Session.yaml           # Custom entity
└── relationships.yaml     # All discovered relationships
```

Each entity file follows the standard YAML program file format
(see Writing YAML Program Files). You can immediately open, edit,
and re-apply these files through the Configure workflow.

**Database records** are also inserted into the client database
(Entity, Field, FieldOption, Relationship, and Layout rows) for use
by the Requirements tab and other CRM Builder features.

### After the Audit

- Click **Open Output Folder** to view the generated YAML files in
  your file manager
- Switch to the **Configure** sidebar entry — the new YAML files
  appear in the program file list
- Edit the YAML files to add descriptions, adjust field options, or
  remove fields you don't need
- Run the files against a target instance to replicate or modify the
  configuration

### How Names Are Translated

The CRM stores custom names with platform prefixes (`cContactType`,
`CEngagement`). The audit reverses these to natural names
(`contactType`, `Engagement`) — the same names you would write in
YAML by hand.

| What the CRM Stores | What the YAML Shows | Rule |
|---------------------|---------------------|------|
| `cContactType` | `contactType` | Strip `c`, lowercase next letter |
| `CEngagement` | `Engagement` | Strip `C` from custom entity |
| `CSessions` | `Session` | Known name mapping (plural → singular) |
| `Contact` | `Contact` | Native entity — unchanged |

Fields that exist by default on every entity of that type (like
`firstName` on Contact) are excluded unless you check the
**Include native fields** option.

### What Is Not Captured

Some information exists only in your YAML source files and is not
stored in the CRM's configuration:

- **Field descriptions** — business rationale and PRD references
- **Field tooltips** — hover text for end users
- **Field categories** — the tab grouping label
- **Option descriptions** — explanations of individual enum values

After auditing, you'll want to add these documentation properties
manually. They are important for the generated reference manual and
for stakeholder review.

### Migration Workflow

To migrate configuration from one CRM to another:

1. Create the source CRM as a **Source** instance
2. Create the target CRM as a **Target** instance (or deploy a new
   one through the Deploy workflow)
3. Run an audit on the source instance
4. Review and edit the generated YAML files
5. Select the target instance and run the YAML files through Configure
6. Verify the target instance matches the expected configuration

---

## Reports

After each Run, Verify, or Import, two report files are written to
the project folder's `reports/` directory:

- **`.log`** — human-readable text report
- **`.json`** — machine-readable structured report

Filename format: `{instance}_{operation}_{timestamp}.{ext}`

Example: `cbm_production_run_20260323_155604.log`

Click **View Report** to open the most recent log file.

---

## Writing YAML Program Files

### File Structure

```yaml
version: "1.0"
content_version: "1.0.0"
description: "What this file configures"

entities:
  EntityName:
    description: >
      Why this entity exists, its role in the data model,
      and PRD reference.
    fields:
      - name: fieldName
        type: enum
        label: "Display Label"
        description: "Why this field exists"
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
  Engagement:                       # natural name — no C-prefix
    description: >
      Required. Business purpose, role in data model, PRD reference.
    action: delete_and_create       # omit for native entities
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
| `create` | Custom entities — first time only |
| `delete` | Remove an entity |

### Field Definitions

```yaml
- name: mentorStatus        # lowerCamelCase, no c-prefix
  type: enum
  label: "Mentor Status"
  description: >
    Why this field exists. What it supports. PRD reference.
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

**Supported field types:**

| Type | Description |
|---|---|
| `varchar` | Single-line text |
| `text` | Multi-line plain text |
| `wysiwyg` | Rich text (HTML editor) |
| `bool` | Checkbox |
| `int` | Integer |
| `float` | Decimal |
| `date` | Date picker |
| `datetime` | Date and time |
| `currency` | Monetary value |
| `url` | URL |
| `email` | Email address |
| `phone` | Phone number |
| `enum` | Single-select dropdown |
| `multiEnum` | Multi-select dropdown |

**Enum style values:** `null` (default), `"default"` (gray),
`"primary"` (blue), `"success"` (green), `"danger"` (red),
`"warning"` (orange), `"info"` (light blue)

### Layout Definitions

```yaml
layout:
  detail:
    panels:

      # Explicit rows — precise field placement
      - label: "Overview"
        tabBreak: true
        tabLabel: "Overview"
        rows:
          - [firstName, lastName]
          - [emailAddress, phoneNumber]
          - [address, null]       # null = empty alignment cell

      # Category-based tab — fields grouped automatically
      - label: "Mentor Details"
        tabBreak: true
        tabLabel: "Mentor"
        dynamicLogicVisible:
          attribute: contactType  # no c-prefix in YAML
          value: "Mentor"
        tabs:
          - label: "Identity"
            category: "Mentor Identity & Contact"
          - label: "Skills"
            category: "Mentor Skills & Expertise"

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
- Fields in category tabs appear in the order they appear in the
  field list — reorder the field list to reorder the tab layout
- `wysiwyg` and `text` fields in category tabs are placed full-width

### Relationship Definitions

```yaml
relationships:

  # New relationship — will be created by the tool
  - name: duesToMentor
    description: >
      Links Dues records to the mentor Contact. PRD reference.
    entity: Dues
    entityForeign: Contact
    linkType: manyToOne
    link: mentor
    linkForeign: duesRecords
    label: "Mentor"
    labelForeign: "Dues Records"

  # Pre-existing relationship — skip creation
  - name: engagementToSessions
    description: >
      Links Engagement to its Sessions. Created manually. PRD ref.
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

### Filtered Tabs (Left-Nav Filtered Views)

A **filtered tab** is a top-level entry in EspoCRM's left navigation
that opens a pre-filtered list view of an entity. It is the right
choice when a particular slice of records — "My Open Engagements",
"Active Mentors", "Stalled Tasks" — deserves its own permanent place
in the nav rather than living as one option in a dropdown.

Filtered tabs differ from **saved views** (which appear as filter
choices inside an entity's existing list view): a saved view changes
what the user sees on the entity's main list page, while a filtered
tab is a separate destination in the left nav.

**Requires the EspoCRM Advanced Pack extension.** Filtered tabs are
built on EspoCRM's Report Filter feature, which ships with Advanced
Pack. Without Advanced Pack the tab cannot be created automatically;
the tool will still generate the supporting files and tell you where
to find them so you can complete the install manually.

#### Declaring a Filtered Tab

`filteredTabs:` is a sibling of `fields:` on the entity:

```yaml
entities:
  Engagement:
    description: >
      Active mentoring relationships. PRD reference.
    filteredTabs:

      - id: my-open
        scope: MyOpenEngagements          # PascalCase, globally unique
        label: "My Open Engagements"      # appears in the left nav
        navOrder: 4                        # optional; lower = earlier
        filter:
          all:
            - { field: status,         op: equals, value: "Open" }
            - { field: assignedUserId, op: equals, value: "$user" }

      - id: stalled
        scope: StalledEngagements
        label: "Stalled Engagements"
        filter:
          all:
            - { field: status,         op: equals,   value: "Open" }
            - { field: lastActivityAt, op: lessThan, value: "lastNDays:30" }
    fields:
      - ...
```

**Properties:**

| Property | Required | Description |
|---|---|---|
| `id` | yes | Stable identifier; unique within the entity |
| `scope` | yes | PascalCase name (e.g., `MyOpenEngagements`). Used as the metadata filename. **Must be unique across the entire program file** — EspoCRM scope names share one global namespace |
| `label` | yes | What the user sees in the left nav and Tab List |
| `filter` | yes | Filter criteria, same syntax as saved views (Section 5.6 of the schema spec) |
| `navOrder` | no | Position hint for the Tab List |
| `acl` | no | One of `boolean`, `team`, `strict`. Default: `boolean` |

**Two helpful filter idioms:**

- `value: "$user"` — resolves to the *current viewing user* at request
  time. Use this for "My …" tabs so each user sees their own records.
- Relative-date tokens — `today`, `yesterday`, `thisMonth`,
  `lastMonth`, `lastNDays:N`, `nextNDays:N` (e.g. `value: "lastNDays:30"`
  for "anything older than 30 days ago"). These are resolved to fixed
  dates at deploy time. To get a perpetually-sliding window, create
  the Report Filter manually with EspoCRM's built-in date types
  instead.

#### What the Tool Does on Run

For every filtered tab in your YAML, the tool:

1. Looks for an existing Report Filter on the target instance with the
   same name. If found, the existing one is reused.
2. If not found, creates the Report Filter via the EspoCRM REST API
   and captures its id.
3. Writes a deploy bundle to:
   ```
   {project_folder}/reports/filtered_tabs/{run_ts}/
   ```
   containing the three EspoCRM metadata files needed to register the
   scope as a navigable tab, plus a `README.txt` with install steps
   and a `manifest.json` index.

The bundle's directory structure mirrors EspoCRM's
`custom/Espo/Custom/Resources/` so you can copy it on top of the
server.

#### Finishing the Install (Operator Steps)

EspoCRM does not let the metadata files be written over its REST API,
so two manual steps remain after Run completes:

1. **Copy the bundle onto the server.** From a workstation that can
   reach the EspoCRM server:
   ```
   scp -r reports/filtered_tabs/<run_ts>/* \
     root@<host>:/var/www/espocrm/data/custom/Espo/Custom/Resources/
   ```
   (Adjust the destination for your install layout. The bundle's
   `README.txt` repeats this command.)

2. **Rebuild and add to the Tab List.** In the EspoCRM admin UI:
   - **Administration → Rebuild** (wait for it to finish)
   - **Administration → User Interface → Tab List**
   - Click **Add**, find each of your new labels, and drag into the
     desired position
   - Save and hard-refresh the browser

If a label does not appear in the Tab List after rebuilding, run
**Administration → Clear Cache** and hard-refresh.

#### When Advanced Pack Is Not Installed

If the target instance does not have Advanced Pack, the Run output
shows a `[NOT SUPPORTED]` line for each tab and the bundle is still
written — but the `clientDefs/<Scope>.json` file contains a
placeholder:

```json
"defaultFilter": "REPLACE_WITH_reportFilter<id>"
```

To finish the install, create the Report Filter manually
(**Administration → Report Filters → Create Report Filter**), copy
its id from the URL bar, replace the placeholder string in the
clientDef file, and proceed with the steps above.

---

## Naming Conventions

You never add platform-specific prefixes in your YAML — CRM Builder
handles them automatically:

- Custom entity `Engagement` → stored in EspoCRM as `CEngagement`
- Custom field `contactType` → stored as `cContactType`

You write natural names. The tool translates.

---

## Troubleshooting

### HTTP 403 on all operations
Your API user lacks admin access. Switch to **Basic** authentication
with your admin username and password. EspoCRM Cloud requires Basic
auth for admin operations.

### TYPE CONFLICT on a field
The field exists in EspoCRM with a different type than specified in
the YAML. The tool skips it. To resolve: manually delete the field
in the EspoCRM Entity Manager, then run the YAML file to recreate it
correctly.

**Warning:** deleting a field destroys its data. Export records before
doing this on a production instance.

### VERIFY FAILED after relationships
This may be a cosmetic issue in the verify step for certain
relationship types. Check that the relationship actually exists in
EspoCRM directly before investigating further.

### Program file panel is empty
Ensure the selected instance has a project folder configured and that
the `programs/` subdirectory contains `.yaml` files.

### Generate Docs shows an error
Check that the instance has a project folder configured. The output
panel message will indicate the specific problem.

### HTTP 400 during import
Check the output log for the specific error message from EspoCRM.
Common causes: a field is mapped to a read-only field, a phone number
format is rejected, or a required field is missing. The log shows
every field and value sent for each record.

### Import shows all records as ERROR
Every record needs an email address for matching. Ensure a JSON field
is mapped to `emailAddress` or that `emailAddress` is set as a fixed
value.

### Confirmation dialog on Run
Your program file contains `action: delete_and_create` or
`action: delete`. Type `DELETE` to confirm and click **Proceed**
only on test instances or when doing a clean rebuild with no live
data. Click **Cancel** to safely abort.

### Filtered tab does not appear in the left nav after running
Filtered tabs need two manual steps after Run completes that the tool
cannot perform over the EspoCRM REST API:

1. Copy the bundle from `reports/filtered_tabs/<run_ts>/` onto the
   server's `custom/Espo/Custom/Resources/` directory
2. **Administration → Rebuild**, then add the label in
   **Administration → User Interface → Tab List**

The Run output shows a `MANUAL CONFIGURATION REQUIRED` block listing
each filtered tab and the bundle path. If the rebuild has been done
but the label still does not appear in the Tab List, run
**Administration → Clear Cache** and hard-refresh the browser.

### Filtered tab marked NOT SUPPORTED in the Run output
The target EspoCRM instance does not have the **Advanced Pack**
extension installed. Advanced Pack is required for the Report Filter
that drives the tab. The tool still writes the deploy bundle, but the
`clientDefs/<Scope>.json` file contains the placeholder
`REPLACE_WITH_reportFilter<id>`. Either install Advanced Pack and
re-run, or create the Report Filter by hand
(**Administration → Report Filters → Create Report Filter**), copy
its id from the URL, replace the placeholder, and finish the install
manually.

---

## Accessing Your CRM After Deployment

Once CRM Builder has deployed the configuration to your CRM instance,
your administrator can log in to the CRM directly using a web browser.

### Finding Your Instance URL

The instance URL is stored in the instance profile in CRM Builder.
Select the instance in the Instance panel — the URL is displayed
in the URL field below the instance list.

For EspoCRM Cloud instances, the URL typically looks like:
```
https://your-organization.espocloud.com
```

### Logging In

Open the instance URL in any modern web browser. You will see the
EspoCRM login screen.

Log in with the same credentials stored in the instance profile:

| Auth Method | Username | Password |
|---|---|---|
| Basic | The username you entered in CRM Builder | The password you entered in CRM Builder |
| API Key | Your admin username | Your admin password (not the API key) |
| HMAC | Your admin username | Your admin password (not the API key or secret) |

**Note:** The API Key and HMAC credentials stored in CRM Builder are
used for the API connection only. To log into the CRM web interface,
always use your admin username and password.

### First Login

On your first login to a newly provisioned EspoCRM instance, the
system may prompt you to:
- Change your password
- Set your timezone and language preferences
- Complete an initial setup wizard (EspoCRM Cloud only)

Complete these steps before inviting other users or making manual
changes in the CRM UI.

### Adding Users

CRM Builder manages CRM configuration (fields, layouts, relationships,
roles) but does not create CRM user accounts. After logging in as
administrator, create user accounts for your staff through the EspoCRM
administration panel:

**Administration → Users → Create User**

Assign the appropriate roles to each user based on what CRM Builder
has deployed. Role names will match those defined in your YAML program
files.

### Verifying the Configuration

After logging in, it is good practice to run **Verify** in CRM Builder
to confirm the deployed configuration matches the spec before handing
the system over to users.

---

## Recovery Tools

The Deployment Dashboard includes a **Recovery & Reset** button that
opens the Recovery Tools dialog. This provides two operations for
recovering from common deployment problems without starting over from
scratch.

### Reset Admin Credentials

Use this when you are locked out of the CRM admin account — forgotten
password, expired session, or credentials that were changed manually
and lost.

This operation resets the admin username and password directly in the
database. All CRM data, configuration, custom fields, and
customizations are left completely intact.

**Steps:**

1. Open the Deployment Dashboard for the target instance
2. Click **Recovery & Reset**
3. Select **Reset Admin Credentials**
4. Enter:
   - **New admin username**
   - **New admin password**
   - **Confirm new admin password**
5. Click **Reset Credentials**
6. Confirm when prompted
7. The tool connects via SSH and executes the credential reset
8. On success, a summary panel displays the new username — log in to
   verify access

The password and confirm password fields must match. If they do not,
clicking Reset Credentials shows a message explaining the mismatch.

After a successful reset, CRM Builder updates the stored deployment
configuration with the new credentials.

### Full Database Reset

Use this when you need to start over with a completely clean CRM
instance — for example, after extensive testing with disposable data,
or when a configuration has gone wrong in a way that is easier to
rebuild than fix.

**This permanently destroys all data in the CRM.** All records, custom
fields, relationships, and configuration are deleted and cannot be
recovered.

**Steps:**

1. Open the Deployment Dashboard for the target instance
2. Click **Recovery & Reset**
3. Select **Full Database Reset**
4. Read the red warning panel carefully
5. Type **RESET** (case-sensitive) in the confirmation field
6. Click **Proceed with Full Reset**
7. Confirm the final dialog: **I Understand — Delete Everything**
8. The reset sequence runs automatically:
   - Stops and removes all CRM Docker containers and volumes
   - Removes the installation directory
   - Re-runs the EspoCRM installation (Phase 2)
   - Runs post-install configuration (Phase 3)
   - Runs verification checks (Phase 4)
9. Verification results are displayed on completion

If any step fails, the operation halts immediately and the error is
shown in the log window. Do not attempt to use the instance until the
issue is resolved — re-run the full deployment from the Deployment
Dashboard if needed.

**After a successful reset**, CRM Builder automatically restores the
API connection so you can start running program files immediately:

1. The tool creates a new API user (`crmbuilder-api`) on the fresh
   EspoCRM instance using the admin credentials from the deployment
   configuration
2. The instance profile is updated with the new API key
3. A confirmation message is displayed in the log window

You do **not** need to create a new instance in CRM Builder, and you
do **not** need to manually create an API user or update credentials.
The URL, project folder, and deployment configuration are all still
valid. Just re-run your YAML program files to restore your custom
fields, layouts, and relationships.

If automatic API user creation fails (rare — typically only if the
CRM is slow to initialize), CRM Builder falls back to switching the
instance profile to Basic auth using the admin credentials. You can
create an API user manually later through the EspoCRM administration
panel if you prefer API key authentication.

**Tip for test environments:** If you prefer to skip API key
management entirely, configure your test instance with **Basic** auth
using the admin username and password. These credentials are passed
to the installer on every reset and work immediately — no post-reset
steps required at all.

### Recovery Logs

Every recovery operation writes a detailed log file to
`data/recovery_logs/` in addition to the live output in the log window.

Log files are named:
```
recovery-YYYY-MM-DD-HH-MM-SS.log
```

Each log file records:
- Timestamp, instance name, operation type, server IP, and domain
- Each step with its start time, result (OK or FAILED), and any
  error details
- Final result summary

The log file path is displayed in the UI when the operation completes.
Passwords are never included in log files.

---

## Troubleshooting

### HTTP 403 on all operations
Your API user lacks admin access. Switch to **Basic** authentication
with your admin username and password. EspoCRM Cloud requires Basic
auth for admin operations.

### TYPE CONFLICT on a field
The field exists in EspoCRM with a different type than specified in
the YAML. The tool skips it. To resolve: manually delete the field
in the EspoCRM Entity Manager, then run the YAML file to recreate it
correctly.

**Warning:** deleting a field destroys its data. Export records before
doing this on a production instance.

### VERIFY FAILED after relationships
This may be a cosmetic issue in the verify step for certain
relationship types. Check that the relationship actually exists in
EspoCRM directly before investigating further.

### Program file panel is empty
Ensure the selected instance has a project folder configured and that
the `programs/` subdirectory contains `.yaml` files.

### Generate Docs shows an error
Check that the instance has a project folder configured. The output
panel message will indicate the specific problem.

### HTTP 400 during import
Check the output log for the specific error message from EspoCRM.
Common causes: a field is mapped to a read-only field, a phone number
format is rejected, or a required field is missing. The log shows
every field and value sent for each record.

### Import shows all records as ERROR
Every record needs an email address for matching. Ensure a JSON field
is mapped to `emailAddress` or that `emailAddress` is set as a fixed
value.

### Confirmation dialog on Run
Your program file contains `action: delete_and_create` or
`action: delete`. Type `DELETE` to confirm and click **Proceed**
only on test instances or when doing a clean rebuild with no live
data. Click **Cancel** to safely abort.

### Audit shows "Connection failed"
Verify the source instance URL and credentials. The audit needs the
same level of API access as Configure — an admin API key or Basic
auth with admin credentials. Try editing the instance and
re-entering the credentials.

### Audit produces empty YAML files
The CRM may have no custom fields. If all fields are native
(built-in), the audit has nothing to capture unless you check
**Include native fields** in the scope options.

### Audit is missing some entities
The audit excludes system entities (Preferences, AuthToken,
ScheduledJob, etc.) that are internal to the CRM platform. Only
customizable entities — custom entities and native entities like
Contact and Account — are included.

### Audit YAML fails validation when run through Configure
Some field types or configurations returned by the CRM may not
match the supported YAML schema. Check the YAML file for fields
with unusual types and adjust them manually.

### Recovery — SSH connection fails
Verify that the instance's deployment configuration has the correct
IP address and SSH key path. The SSH key must be accessible on your
local machine at the path stored in the deploy config. Test the
connection from your terminal: `ssh -i /path/to/key user@ip`.

### Recovery — credential reset succeeds but login fails
EspoCRM may cache authentication. Clear the browser cache and try
again. If the problem persists, try a Full Database Reset to
reinstall the instance from scratch.

### Recovery — Full Database Reset fails mid-sequence
The instance may be in a partially torn-down state. Return to the
Deployment Dashboard and run a full deployment starting from Phase 1.
Check the recovery log file (path shown in the UI) for the specific
step that failed.

### Recovery — "Could not create API user automatically"
This means the Full Database Reset completed but the automatic API
user creation failed. CRM Builder has switched your instance profile
to Basic auth as a fallback — you can run program files immediately.
To switch back to API key auth later: log into EspoCRM, go to
Administration → API Users, create a new API user with admin access,
then edit the instance in CRM Builder and enter the new API key.

---



| Version | Date | Changes |
|---|---|---|
| 5.1 | 05-02-26 18:15 | Added a "Deployment Record (Self-Hosted Instances)" subsection under Managing Instances → Project Folder, cross-referencing the EspoCRM Server Deployment Guide for the full feature documentation. |
| 5.0 | April 2026 | Added CRM Audit feature (auditing existing instances, instance roles, migration workflow) |
| 4.1 | April 2026 | Added Recovery Tools section (Reset Admin Credentials, Full Database Reset) and related troubleshooting entries |
| 4.0 | March 2026 | Rewritten for new documentation structure. Updated to reflect project folder model, content versioning, layout and relationship configuration, import wizard, and Generate Docs |
| 3.0 | March 2026 | Added data import wizard |
| 2.1 | March 2026 | Renamed to CRM Builder |
| 2.0 | March 2026 | Added project folder, content versioning, layout and relationship configuration, Generate Docs |
| 1.0 | Early 2026 | Initial release — field management only |
