# EspoCRM Implementation Tool — Process Guide

**Audience:** Technical team members responsible for designing, building,
and maintaining CRM configurations using this tool.

**Scope:** The complete lifecycle — from requirements capture through YAML
authoring, deployment, verification, and ongoing maintenance.

**Deployment operations** — setting up instances, running files, and
promoting to production — are covered in the
[Deployment Guide](deployment-guide.md). This guide focuses on design,
authoring, and maintenance.

---

## 1. Overview

This tool manages EspoCRM configuration declaratively. The workflow is:

```
Requirements (PRD)
       ↓
YAML Program Files  ← single source of truth
       ↓        ↓
   Deploy      Generate Docs
  (EspoCRM)   (Reference Manual)
       ↓
    Verify
```

For step-by-step instructions on running the tool, deploying files to
a test instance, and promoting to production, see the
[Deployment Guide](deployment-guide.md).

**The YAML files are the single source of truth.** Every field, layout,
and relationship in EspoCRM must be defined in a YAML file before it is
deployed. The generated reference manual and the live EspoCRM instance are
both outputs — neither is edited directly to make configuration changes.

---

## 2. Repository Structure

### 2.1 Tool Repository

The implementation tool repository contains only the tool itself — no
client data:

```
espo-implementation-tool/
├── docs/          # Process, user, and technical documentation
├── PRDs/          # Tool specs and design documents
├── espo_impl/     # Tool source code
├── tools/         # Utilities (doc generator)
└── tests/         # Test suite
```

### 2.2 Client Repository

Each client has their own repository. It is the output of the tool —
populated from YAML files and generated artifacts:

```
ClevelandBusinessMentoring/     (example client repo)
├── PRDs/                       # Source PRD documents
├── programs/                   # YAML program files
├── Implementation Docs/        # Generated reference manual
└── reports/                    # Deployment run reports (optional)
```

### 2.3 Instance and Project Folder

Each EspoCRM instance in the tool is bound to a **project folder** — a
local directory containing all files for that client:

```
~/Projects/CBM/                 (example project folder)
├── programs/                   # YAML program files (loaded automatically)
├── Implementation Docs/        # Generated reference manual
└── reports/                    # Run/verify reports
```

When you select an instance, the Program File panel automatically shows
all YAML files in that instance's `programs/` directory. Reports and
generated docs are written to the same folder.

The project folder is typically the local clone of the client repository,
so committing and pushing keeps everything in sync.

---

## 3. Phase 1 — Requirements Capture (PRD)

### 3.1 What a PRD Must Cover

A Product Requirements Document (PRD) for a CRM module must answer the
following questions clearly enough that YAML can be written directly from
it without ambiguity:

**Entities:**
- What is this entity? What business problem does it solve?
- Is it a new custom entity or an extension of a native entity?
- What other entities does it link to, and in what direction?

**Fields:**
- What is each field called? (Display label and data type)
- Is it required?
- Who enters it — admin, mentor, client, or system?
- For enum/multi-select fields: what are all the allowed values?
- What business decision or process does this field support?

**Layouts:**
- How should fields be grouped into panels and tabs?
- Are any panels conditionally visible (Dynamic Logic)?
- What columns appear in list views?

**Relationships:**
- Which entities link to which?
- One-to-many or many-to-many?
- What label appears on each side's relationship panel?

### 3.2 PRD Format

PRDs are Word documents (`.docx`) stored in the client repository under
`PRDs/`. They follow CBM's existing PRD conventions:

- Section 1: Overview and platform decisions
- Section 2: Entity and field reference tables
- Section 3: Dropdown value reference (for enums with many values)
- Section 4: Process flows and lifecycle descriptions
- Section 5: Detailed requirements with priority ratings
- Section 6: Implementation notes and design decisions

**Implementation notes are critical.** Design decisions that affect YAML
(e.g., "Partners use the native Account entity" or "accountType replaces
companyRole") must be documented in the PRD before YAML is written.

### 3.3 Requirements Discovery Checklist

Before starting YAML, verify the PRD covers:

- [ ] All entities named and described
- [ ] All fields with type, required flag, and allowed values for enums
- [ ] Dynamic Logic conditions specified (which fields drive which panels)
- [ ] Relationship directions confirmed (which entity "owns" the link)
- [ ] TBD values flagged explicitly (so YAML can be written with placeholders)
- [ ] Any fields that must be configured manually (file attachments, formulas)
- [ ] Access control requirements noted (even if not yet implemented by tool)

---

## 4. Phase 2 — YAML Authoring

### 4.1 File Organization

One YAML file per logical group of fields. Convention:

| File | Contents |
|---|---|
| `{client}_{entity}_fields.yaml` | Fields and layout for one entity |
| `{client}_{entity}_{module}_fields.yaml` | Extension of a native entity for a module |
| `{client}_relationships.yaml` | All core relationships |
| `{client}_{module}_relationships.yaml` | Module-specific relationships |
| `{client}_full_rebuild.yaml` | Deployment convenience — delete+create all custom entities |

Keep individual entity files as the source of truth. The full rebuild file
is a deployment convenience only — it should not define fields not already
in individual files.

### 4.2 YAML Structure

Every YAML file has this top-level structure:

```yaml
version: "1.0"
content_version: "1.0.0"
description: "Short description of what this file configures"

# Source of truth: PRD document and section
# Any design notes or exceptions

entities:          # optional if file only has relationships
  EntityName:
    description: >
      Required. Why this entity exists, its role in the data model,
      and PRD reference. One paragraph.
    fields:
      - name: fieldName
        ...

relationships:     # optional if file only has entities
  - name: relName
    ...
```

### 4.3 Content Versioning

Every YAML file has a `content_version` field using semantic versioning.
Increment it whenever you make changes:

| Change | Version bump | Example |
|---|---|---|
| Description updates, comment fixes | PATCH | 1.0.0 → 1.0.1 |
| New fields or enum values added | MINOR | 1.0.0 → 1.1.0 |
| Fields removed, types changed, entity restructured | MAJOR | 1.0.0 → 2.0.0 |

The version is displayed in the Program File panel and embedded in report
filenames, making it easy to trace which version produced a given report.

### 4.4 Entity Block

```yaml
entities:
  EntityName:
    description: >       # required — business rationale + PRD reference
      ...
    action: delete_and_create   # omit for native entities
    type: Base           # Base, Person, Company, Event
    labelSingular: "Name"
    labelPlural: "Names"
    stream: true
    fields:
      - ...
    layout:
      detail:
        panels: [...]
      list:
        columns: [...]
```

**Action values:**
- Omit `action` for native entities (Account, Contact) — field operations only
- `delete_and_create` — for custom entities in production deployments
- `create` / `delete` — used in full rebuild files only

### 4.5 Field Definition

```yaml
- name: fieldName          # lowerCamelCase, no c-prefix
  type: varchar            # see supported types below
  label: "Display Label"
  description: >           # strongly encouraged
    Business rationale. What decision or process does this field support?
    Requirement: PRD-Document.docx Section X.
  required: true           # omit if false
  default: "value"         # omit if no default
  readOnly: true           # omit if false
  category: "Tab Name"     # required for layout tab grouping
  options:                 # enum/multiEnum only
    - "Value One"
    - "Value Two"
  min: 0                   # int/float only
  max: 100                 # int/float only
  maxLength: 255           # varchar only
```

**Supported field types:**

| YAML Type | Display | Notes |
|---|---|---|
| `varchar` | Text | Single-line, use `maxLength` |
| `text` | Text (multi-line) | Plain multi-line |
| `wysiwyg` | Rich Text | HTML editor |
| `enum` | Enum | Single-select dropdown |
| `multiEnum` | Multi-select | Multi-select dropdown |
| `bool` | Boolean | Checkbox |
| `int` | Integer | Use `min`/`max` |
| `float` | Decimal | Use `min`/`max` |
| `date` | Date | |
| `datetime` | Date/Time | |
| `currency` | Currency | |
| `url` | URL | |
| `email` | Email | |
| `phone` | Phone | |

**Not configurable by tool (manual EspoCRM config required):**
- File / image attachment fields
- Relationship link fields (handled via the `relationships` block)
- Formula fields (entity formula scripts)

**Reserved field names to avoid:**
- `description` — native field on all Base entities. Use a prefixed name
  instead (e.g., `activityDescription`, `workshopDescription`).
- `name` — native record label field on all entities

### 4.6 Layout Definition

```yaml
layout:
  detail:
    panels:

      # Category-based tabbed panel (fields grouped automatically)
      - label: "Mentor Details"
        tabBreak: true
        tabLabel: "Mentor"
        style: default
        description: >       # optional — what this panel is for
          ...
        dynamicLogicVisible: # optional — show/hide condition
          attribute: contactType   # field driving visibility (no c-prefix)
          value: "Mentor"
        tabs:
          - label: "Identity"
            category: "Mentor Identity & Contact"
          - label: "Skills"
            category: "Mentor Skills & Expertise"

      # Explicit rows panel (precise field placement)
      - label: "Overview"
        tabBreak: true
        tabLabel: "Overview"
        rows:
          - [name, website]
          - [organizationType, accountType]
          - [businessStage, null]    # null = empty cell

  list:
    columns:
      - field: name
        width: 25
      - field: status
        width: 15
```

**Layout rules:**
- Each panel has either `rows` OR `tabs`, never both
- `tabBreak: true` requires `tabLabel`
- Tab `category` must match the `category` on at least one field in the entity
- Native fields in explicit rows (name, emailAddress) pass through without
  c-prefix — the tool handles this automatically
- `wysiwyg` and `text` fields in category tabs auto-generate as full-width rows

### 4.7 Relationship Definition

```yaml
relationships:

  - name: uniqueRelName       # identifier for this relationship
    description: >            # strongly encouraged
      Why this relationship exists, what it enables.
      Requirement: PRD-Document.docx Section X.
    entity: PrimaryEntity     # natural name (no C-prefix)
    entityForeign: ForeignEntity
    linkType: manyToOne       # oneToMany, manyToOne, manyToMany
    link: linkName            # link name on primary entity
    linkForeign: linkForeignName   # link name on foreign entity
    label: "Panel Label"
    labelForeign: "Panel Label"
    relationName: cJunctionTable   # required for manyToMany
    audited: false
    action: skip              # add this for pre-existing relationships
```

**linkForeign c-prefix rule:**

When the foreign entity is a custom entity (C-prefixed in EspoCRM), the
`linkForeign` value must include the c-prefix. EspoCRM stores the foreign
link name with the c-prefix automatically.

- Foreign entity is custom: `linkForeign: cNpsSurveyResponses`
- Foreign entity is native (Account, Contact): `linkForeign: engagementContacts`

**Native entity primary side:**

When the primary entity is native (Account, Contact), EspoCRM auto-applies
a c-prefix to the `link` name. Specify the link name without a c-prefix
in the YAML — the tool's check and verify steps handle this automatically.

Example: specify `link: partnerLiaison` → EspoCRM stores it as
`cPartnerLiaison`. The tool checks for `cPartnerLiaison` automatically.

**Link naming conventions:**
- Use lowerCamelCase
- For manyToMany, `relationName` is the junction table name — prefix with `c`:
  `cEngagementContact`
- For relationships already created manually in EspoCRM, add `action: skip` —
  the tool records them without attempting to create them

### 4.8 Descriptions

Descriptions are optional on fields but strongly encouraged. They appear
in the generated reference document and serve as the traceable link between
the PRD requirement and the technical implementation.

**Good description:**
```yaml
description: >
  Tracks the mentor's progression through the CBM lifecycle. Drives access
  to assignment workflows and dashboard visibility. Controls which mentors
  appear in the Mentors Accepting Clients list view.
  Requirement: CBM-PRD-CRM-Mentor.docx Section 3.4.
```

**Insufficient description:**
```yaml
description: "Mentor status field."
```

Include the PRD reference so future maintainers can trace every field
back to its requirement.

### 4.9 TBD Fields

When enum values are not yet confirmed, flag them explicitly:

```yaml
description: >
  ...
  TBD: values to be confirmed with {stakeholder} before go-live.
```

Write the YAML with best-guess values. Do not leave the `options` list
empty — that fails validation.

---

## 5. Phase 3 — Validation

1. Select the instance in the tool
2. Select the program file
3. Click **Validate**

The tool parses the YAML for structural errors, then connects to EspoCRM
and previews planned changes.

**Validation checks:**
- Required properties present (name, type, label on fields; description on entities)
- Field types are supported
- enum/multiEnum fields have non-empty options
- Entity blocks with `action: create` have type, labelSingular, labelPlural
- Layout panels have either `rows` or `tabs`, not both
- Tab categories match field categories defined in the entity
- Relationship linkType is valid; manyToMany has relationName

Fix all errors before proceeding to Run.

---

## 6. Phase 4 — Deployment (Run)

### 6.1 First Deployment

For a new EspoCRM instance, deploy in this order:

1. Custom entity files (fields + layouts)
2. Native entity extension files
3. Relationship files (all entities must exist first)
4. Verify after each file

Recommended order for CBM:
```
cbm_engagement_fields.yaml
cbm_session_fields.yaml
cbm_nps_survey_fields.yaml
cbm_workshop_fields.yaml
cbm_workshop_attendance_fields.yaml
cbm_dues_fields.yaml
cbm_partner_agreement_fields.yaml
cbm_client_partner_association_fields.yaml
cbm_partner_activity_fields.yaml
cbm_contact_fields.yaml
cbm_account_fields.yaml
cbm_partner_account_fields.yaml
cbm_partner_contact_fields.yaml
cbm_relationships.yaml
cbm_partner_relationships.yaml
```

Or use `cbm_full_rebuild.yaml` to deploy all custom entities in one run.

### 6.2 Destructive Operations

Program files with `action: delete_and_create` will delete and recreate
entities. The tool requires explicit confirmation.

**Never run delete_and_create on a production instance with live data.**
Use individual entity files (which only add/update fields) for
production updates.

### 6.3 Run Output

Processing order:
1. Entity deletions → cache rebuild
2. Entity creations → cache rebuild
3. Field operations (check → act → verify per field)
4. Layout operations (check → act → verify per layout)
5. Relationship operations (check → act → verify per relationship)

Output color coding:
- Green — created or verified successfully
- Gray — no change needed
- Yellow — warning (skipped, type conflict)
- Red — error

### 6.4 Reports

After each run, two report files are written to the instance's `reports/`
directory:
- `{instance}_{operation}_{timestamp}_{version}.log` — human-readable
- `{instance}_{operation}_{timestamp}_{version}.json` — machine-readable

Click **View Report** to open the log file.

---

## 7. Phase 5 — Verification

Click **Verify** to re-check all fields against the spec without making
changes. Use this to:

- Confirm a deployment completed correctly
- Check whether manual changes have drifted from the spec
- Audit a live instance before making updates

**Current limitation:** Verify checks fields only. Layouts and
relationships are not re-verified by the Verify button — use Run for those
(it will detect no changes and skip them).

---

## 8. Phase 6 — Documentation

After deploying or updating YAML files, regenerate the reference document.

Click **Generate Docs** in the tool. Output is written to the instance's
`Implementation Docs/` directory:
- `CBM-CRM-Reference.md` — Markdown version
- `CBM-CRM-Reference.docx` — Word document

**Always regenerate and commit docs alongside YAML changes.** The reference
document is a generated artifact — never edit it manually.

---

## 9. Phase 7 — Maintenance

### 9.1 Adding a New Field

1. Add the field definition to the appropriate YAML file
2. Assign a `category` matching an existing layout tab, or add a new tab
3. Update the layout section if an explicit `rows` panel needs the new field
4. Bump `content_version` (MINOR)
5. Run the tool — creates the new field and re-applies the layout
6. Regenerate docs

### 9.2 Changing an Enum Value

Update the `options` list in the YAML. The tool will update the field's
options on the next run.

**Caution:** Removing an enum value that exists on live records may cause
display issues. Always add new values first, migrate data, then remove
old values.

### 9.3 Adding a New Entity

1. Create a new YAML file: `{client}_{entity}_fields.yaml`
2. Define the entity block with `action: delete_and_create`
3. Add all fields with categories and descriptions
4. Add layout (detail panels and list columns)
5. Add relationships to the appropriate relationships file
6. Deploy entity file first, then relationships
7. Regenerate docs

### 9.4 Adding a New Module (Multiple Entities)

Follow the same pattern as the Partner module:

1. Write the PRD
2. Identify which entities are native extensions vs. new custom entities
3. Create one YAML file per entity
4. Create a `{client}_{module}_relationships.yaml` file
5. Deploy entity files first, then relationships
6. Regenerate docs

### 9.5 Handling PRD Changes

1. Update the relevant YAML files
2. Bump `content_version` appropriately
3. If fields were removed — do not remove from YAML without a data migration plan
4. If field types changed — delete the field manually in EspoCRM first
5. Run the tool — idempotent, only changes what differs
6. Regenerate docs and commit

---

## 10. What the Tool Does NOT Handle

| Item | Where in EspoCRM |
|---|---|
| File attachment fields | Entity Manager → Field Manager |
| Formula fields (calculated values) | Entity Manager → Formula |
| Dynamic Logic on individual fields | Entity Manager → Field → Dynamic Logic |
| Role-based access control | Administration → Roles |
| Workflow automation | Administration → Workflows |
| Email templates | Administration → Email Templates |
| Dashboard layouts | Administration → Dashboards |
| Search presets (saved views) | List View → Save Filter |
| Report definitions | Reports module |
| LimeSurvey integration | Administration → Integrations |

Maintain a manual configuration log in the client repo documenting each
manually-configured item, the date configured, and any relevant notes.

---

## 11. Troubleshooting

### Field Already Exists With Wrong Type

The tool skips fields with type conflicts. Delete the field manually in
EspoCRM Entity Manager, then run the tool to recreate it. Export live
data from the field first — deletion destroys its data.

### Relationship VERIFY FAILED After Create

The relationship was likely created correctly. Check directly:
```
/api/v1/Metadata?key=entityDefs.{EspoEntityName}.links.{linkName}
```
For native entity primary sides, the link is stored with a c-prefix
(e.g., `partnerLiaison` → `cPartnerLiaison`).

### Relationship HTTP 409 on Create

EspoCRM rejected the link name. Common causes:
- The relationship already exists under the c-prefixed name
- The link name conflicts with a reserved EspoCRM field name

Check `entityDefs.{Entity}.links` via the Metadata API to see all
existing links. Try a different link name if there is a conflict.

### Layout Not Applying

1. Run Administration → Rebuild in EspoCRM
2. Check the run report for layout operation errors
3. Inspect the EspoCRM network traffic to see the API response

### Validation Passes But Run Fails

Check the run report for HTTP error details:
- 401 — API key incorrect or expired
- 403 — API key does not have admin access (use Basic auth)
- 409 — Conflict (relationship or field name collision)
- 422 — Invalid payload (check log for response body)

### Program File Panel Empty

Ensure the selected instance has a project folder configured with a
`programs/` subdirectory containing `.yaml` files.

---

## 12. Repo Conventions

### Commit Messages

```
feat: add Partner module YAML files
fix: correct mentorStatus enum values  
bump: cbm_contact_fields to v1.1.0 (added zipCode field)
docs: regenerate CBM-CRM-Reference after Partner module deployment
```

### Branch Strategy

- `main` — production-ready YAML and documentation
- Feature branches for new modules or significant changes
- Never commit untested YAML directly to `main`

### What to Commit (client repo)

Always commit together:
- Updated YAML files
- Regenerated `CBM-CRM-Reference.md` and `CBM-CRM-Reference.docx`

Optionally commit:
- Run/verify reports for significant deployments (audit trail)

Never commit:
- Instance connection profiles (contain API keys — stored locally only)

---

## 13. Related Documents

| Document | Location | Purpose |
|---|---|---|
| Deployment Guide | `docs/deployment-guide.md` | Step-by-step instance deployment and production promotion |
| User Guide | `docs/user-guide.md` | Tool installation and usage |
| Technical Guide | `docs/technical-guide.md` | Architecture and module reference |
| PRD | `PRDs/CBM-espocrm-impl-PRD.md` | Product requirements |
| YAML Spec | `PRDs/CBM-SPEC-espocrm-impl.md` | Complete YAML schema reference |
| Layout Spec | `PRDs/CBM-SPEC-layout-management.md` | Layout API and schema |
| Relationship Spec | `PRDs/CBM-SPEC-relationship-management.md` | Relationship API and schema |
| Doc Generator Spec | `PRDs/CBM-SPEC-doc-generator.md` | Documentation generator design |

---

## 14. Known Production Deployment Notes

### CBM Production — Pre-Deployment Manual Steps

The following manual steps are required before running the tool against
the CBM Production instance. These are one-time fixes for items
configured manually before the tool was built.

| Item | Entity | Action Required |
|---|---|---|
| `cTimeInOperation` | Account | Delete field manually in Entity Manager before running `cbm_account_fields.yaml`. It was created as `varchar` — the YAML defines it as `enum`. Export existing field values first. |
| `cDescription` on PartnerActivity | PartnerActivity | This field cannot be deleted (native Base entity field). The YAML uses `activityDescription` instead. No manual action needed — the tool creates `cActivityDescription` automatically. |

After completing each manual step, run the affected YAML file and verify
before proceeding to the next file.
