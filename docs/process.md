# EspoCRM Implementation Tool — Process Guide

**Audience:** Technical team members responsible for designing, building,
and maintaining CRM configurations using this tool.

**Scope:** The complete lifecycle — from requirements capture through YAML
authoring, deployment, verification, and ongoing maintenance.

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

**The YAML files are the single source of truth.** Every field, layout,
and relationship in EspoCRM must be defined in a YAML file before it is
deployed. The generated reference manual and the live EspoCRM instance are
both outputs — neither is edited directly to make configuration changes.

---

## 2. Repository Structure

The implementation tool repository contains:

```
espo-implementation-tool/
├── docs/                    # Process and technical documentation (this file)
├── PRDs/                    # Tool specs and design documents
├── data/
│   ├── instances/           # EspoCRM instance connection profiles
│   └── programs/            # YAML program files (one per entity group)
├── reports/                 # Run and verify report output
├── espo_impl/               # Tool source code
├── tools/                   # Utilities (doc generator)
└── tests/                   # Test suite
```

**Client configuration files live in a separate output repository** (e.g.,
`ClevelandBusinessMentoring`). The `data/programs/` directory in this repo
contains YAML files for active deployments. The client repo contains the same
YAML files plus generated artifacts (reference docs, reports).

---

## 3. Phase 1 — Requirements Capture (PRD)

### 3.1 What a PRD Must Cover

A Product Requirements Document (PRD) for a CRM module must answer the
following questions clearly enough that YAML can be written directly from it
without ambiguity:

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
| `{client}_relationships.yaml` | All relationships for a client |
| `{client}_full_rebuild.yaml` | Complete rebuild (delete + create all custom entities) |

For entity extensions (adding Partner fields to Account):
`{client}_{entity}_{module}_fields.yaml` — e.g., `cbm_partner_account_fields.yaml`

Keep individual entity files as the source of truth. The full rebuild file
is a deployment convenience only — it should not define fields not already
in individual files.

### 4.2 YAML Structure

Every YAML file has this top-level structure:

```yaml
version: "1.0"
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

### Content Versioning

Every YAML file has a `content_version` field using semantic versioning:

```yaml
content_version: "1.0.0"
```

Increment the version when making changes:

| Change | Version bump | Example |
|---|---|---|
| Description updates, comment fixes | PATCH | 1.0.0 → 1.0.1 |
| New fields added, enum values added | MINOR | 1.0.0 → 1.1.0 |
| Fields removed, types changed, entity restructured | MAJOR | 1.0.0 → 2.0.0 |

The version is displayed in the Program File panel, included in run/verify
report headers, and embedded in report filenames. This makes it easy to
confirm which version of a program file was used for a given deployment.

### 4.3 Entity Block

```yaml
entities:
  EntityName:
    description: >          # required — business rationale + PRD reference
      ...
    action: delete_and_create   # omit for native entities
    type: Base              # Base, Person, Company, Event
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

### 4.4 Field Definition

```yaml
- name: fieldName          # lowerCamelCase, no c-prefix
  type: varchar            # see supported types below
  label: "Display Label"
  description: >           # strongly encouraged — why does this field exist?
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
- `file` / `image` — file attachments
- `link` / `linkMultiple` — relationships (handled via `relationships` block)
- Formula fields (entity formula scripts)

### 4.5 Layout Definition

```yaml
layout:
  detail:
    panels:

      # Simple panel with explicit field rows
      - label: "Panel Label"
        tabBreak: true          # true = this panel is a tab
        tabLabel: "Tab Label"   # short tab name (required if tabBreak: true)
        style: default          # default, success, danger, warning, info, primary
        description: >          # optional — what this tab is for
          ...
        dynamicLogicVisible:    # optional — condition for showing this panel
          attribute: fieldName  # field that drives visibility (no c-prefix in YAML)
          value: "Value"
        rows:                   # explicit field placement
          - [fieldA, fieldB]    # two fields per row
          - [fieldC, null]      # null = empty cell

      # Tabbed panel with category-based sub-tabs
      - label: "Mentor Details"
        tabBreak: true
        tabLabel: "Mentor"
        dynamicLogicVisible:
          attribute: contactType
          value: "Mentor"
        tabs:
          - label: "Identity"      # sub-tab label
            category: "Mentor Identity & Contact"  # must match field categories

  list:
    columns:
      - field: name
        width: 20      # percentage (all columns should sum to ~100)
      - field: status
        width: 15
```

**Layout rules:**
- Each panel has either `rows` OR `tabs`, never both
- `tabBreak: true` requires `tabLabel`
- `category` on a tab must match the `category` property on at least one field
- Native fields in explicit rows (name, emailAddress, etc.) do not need a c-prefix — the tool handles this automatically
- `wysiwyg` and `text` fields in category tabs auto-generate as full-width rows

### 4.6 Relationship Definition

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
    label: "Panel Label"      # relationship panel label on primary entity
    labelForeign: "Panel Label"    # relationship panel label on foreign entity
    relationName: cJunctionTable   # required for manyToMany
    audited: false
    action: skip              # add this for pre-existing relationships
```

**Link naming conventions:**
- Use lowerCamelCase
- The foreign link name appears on the other entity's detail view panel
- For manyToMany, `relationName` is the database junction table name — prefix with `c` for custom: `cEngagementContact`
- For relationships that already exist in EspoCRM (created manually), add `action: skip` — the tool records them but does not attempt to create them

### 4.7 Descriptions

Descriptions are optional on fields but strongly encouraged. They appear in
the generated reference document and serve as the link between the PRD
requirement and the technical implementation.

**Good description:**
```yaml
description: >
  Tracks the mentor's progression through the CBM lifecycle. Drives access
  to assignment workflows and dashboard visibility. Controls which mentors
  appear in the Mentors Accepting Clients list view.
  Requirement: CBM-PRD-CRM-Mentor.docx Section 3.4.
```

**Bad description:**
```yaml
description: "Mentor status field."
```

Include the PRD reference so future maintainers can trace every field back
to its requirement.

### 4.8 TBD Fields

When enum values are not yet confirmed, mark them explicitly:

```yaml
description: >
  ...
  TBD: values to be confirmed with {stakeholder} before go-live.
```

Write the YAML with your best-guess values. The description flags it for
review. Do not leave the `options` list empty — that fails validation.

---

## 5. Phase 3 — Validation

Before deploying, validate the YAML:

1. Select the program file in the tool
2. Select the target instance
3. Click **Validate**

The tool parses the YAML for structural errors, then connects to EspoCRM
and shows a preview of what changes would be made (new fields, no-change
fields, etc.).

**Validation checks:**
- Required properties present (name, type, label on fields; description on entities)
- Field types are supported
- enum/multiEnum fields have non-empty options
- Entity blocks with `action: create` have type, labelSingular, labelPlural
- Layout panels have either `rows` or `tabs`, not both
- Tab categories match field categories defined in the same entity
- Relationship linkType is valid; manyToMany has relationName

Fix all errors before proceeding to Run.

---

## 6. Phase 4 — Deployment (Run)

### 6.1 First Deployment

For a new EspoCRM instance:

1. Deploy custom entities first using individual entity files
2. Deploy fields and layouts
3. Deploy relationships last (all entities must exist first)
4. Verify after each step

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
entities. The tool requires explicit confirmation before proceeding.

**Never run delete_and_create on a production instance with live data.**
Use individual field files (which only add/update fields, never delete
entities) for production updates.

### 6.3 Run Output

The tool processes operations in this order:
1. Entity deletions (if any)
2. Cache rebuild
3. Entity creations (if any)
4. Cache rebuild
5. Field operations (check → act → verify per field)
6. Layout operations (check → act → verify per layout)
7. Relationship operations (check → act → verify per relationship)

Color coding in the output panel:
- Green — created or verified successfully
- Yellow — skipped (already matches spec)
- Red — error

### 6.4 Reports

After each run, two report files are written to `reports/`:
- `{timestamp}_{instance}_{program}.log` — human-readable log
- `{timestamp}_{instance}_{program}.json` — machine-readable results

Click **View Report** to open the log file.

---

## 7. Phase 5 — Verification

After a run, click **Verify** to re-check all fields against the spec
without making any changes. Use this to:

- Confirm a deployment completed correctly
- Check whether manual changes have drifted from the spec
- Audit a live instance before making updates

Verification checks every field's type, required flag, options list, and
other properties against the YAML spec. It does not check layouts or
relationships (field-level only in the current version).

---

## 8. Phase 6 — Documentation

After deploying or updating YAML files, regenerate the reference document:

Click **Generate Docs** in the tool, or run from the command line:

```bash
uv run python tools/generate_docs.py \
  --programs data/programs/ \
  --output PRDs/Implementation Docs/
```

This produces:
- `PRDs/Implementation Docs/CBM-CRM-Reference.md` — Markdown version
- `PRDs/Implementation Docs/CBM-CRM-Reference.docx` — Word document

**Commit both files to the client repo alongside the updated YAML files.**
The reference document is a generated artifact — it is never edited manually.

---

## 9. Phase 7 — Maintenance

### 9.1 Adding a New Field

1. Add the field definition to the appropriate YAML file
2. Add `category` matching an existing layout tab, or add a new tab
3. Update the layout section if an explicit `rows` panel needs the new field
4. Run the tool — it will create the new field and re-apply the layout
5. Regenerate docs

### 9.2 Changing an Enum Value

Enum values can be updated by modifying the `options` list in the YAML.
The tool will update the field's options in EspoCRM on the next run.

**Caution:** Removing an enum value that exists on live records may cause
display issues in EspoCRM. Always add new values first, migrate data, then
remove old values.

### 9.3 Adding a New Entity

1. Create a new YAML file: `{client}_{entity}_fields.yaml`
2. Define the entity block with `action: delete_and_create`
3. Add all fields with categories and descriptions
4. Add layout (detail panels and list columns)
5. Add relationship definitions to the relationships YAML file
6. Deploy entity file first, then relationships file
7. Regenerate docs

### 9.4 Adding a New Module (Multiple Entities)

Follow the same pattern as the Partner module:

1. Write the PRD
2. Identify which entities are native extensions vs. new custom entities
3. Create one YAML file per entity (extensions and new entities separately)
4. Create a `{client}_{module}_relationships.yaml` file
5. Deploy entity files, then relationships
6. Regenerate docs

### 9.5 Handling PRD Changes

When the PRD changes:

1. Update the relevant YAML files
2. If enum values changed — update `options` lists
3. If fields were added — add to YAML and update layout
4. If fields were removed — **do not remove from YAML without a data migration plan**
5. If field types changed — contact EspoCRM admin; type changes may require field deletion and recreation
6. Run the tool — idempotent, only changes what differs
7. Regenerate docs and commit

---

## 10. What the Tool Does NOT Handle

Some EspoCRM configuration must be done manually in the Admin UI. Document
these manually-configured items in the YAML file's header comments.

**Currently requires manual configuration:**

| Item | Where in EspoCRM |
|---|---|
| File attachment fields | Entity Manager → Field Manager |
| Formula fields (calculated values) | Entity Manager → Formula |
| Dynamic Logic on individual fields | Entity Manager → Field → Dynamic Logic |
| Role-based access control | Administration → Roles |
| Workflow automation | Administration → Workflows |
| Email templates | Administration → Email Templates |
| Dashboard layouts | Administration → Dashboards |
| Search presets (saved views) | List View → Save Filter (manual per user) |
| Report definitions | Reports module |
| LimeSurvey integration | Administration → Integrations |

Future tool phases will automate some of these items. Until then, maintain
a manual configuration log in the client repo documenting each manually-
configured item, the date it was configured, and any relevant notes.

---

## 11. Troubleshooting

### Field Already Exists With Wrong Type

The tool will skip a field if it exists with a different type (type conflicts
are not auto-resolved). Delete the field manually in EspoCRM Entity Manager,
then run the tool to recreate it with the correct type.

### Relationship Already Exists

If a relationship was created manually and is not yet in the YAML, add it
to the relationships YAML with `action: skip`. This records it for
documentation without attempting to recreate it.

### Layout Not Applying

If layout changes are not taking effect:
1. Check the EspoCRM metadata cache — run **Administration → Rebuild**
2. Check the run report for layout operation errors
3. Verify the layout payload format using the EspoCRM network inspector

### Validation Passes But Run Fails

Check the run report for HTTP error details. Common causes:
- 401 — API key incorrect or expired
- 403 — API key does not have admin privileges
- 422 — Invalid payload (check the log for the response body)

### Duplicate Fields After Merge

The doc generator warns about duplicate fields when the same field appears
in both an individual entity file and the full rebuild file. These warnings
are harmless — the individual file's definition takes precedence. To resolve,
remove duplicate field definitions from `cbm_full_rebuild.yaml`.

---

## 12. Repo Conventions

### Commit Messages

```
feat: add Partner module YAML files
fix: correct mentorStatus enum values
update: regenerate CBM-CRM-Reference after adding Dues entity
docs: update process guide with relationship authoring notes
```

### Branch Strategy

- `main` — production-ready YAML and documentation
- Feature branches for new modules or significant changes
- Never commit directly to `main` with untested YAML

### What to Commit

Always commit together:
- Updated YAML files
- Regenerated `CBM-CRM-Reference.md` and `CBM-CRM-Reference.docx`
- Run/verify reports for significant deployments (optional, for audit trail)

Never commit:
- `data/instances/*.json` — contains API keys (in `.gitignore`)
- `reports/` — generated output, not source

---

## 13. Related Documents

| Document | Location | Purpose |
|---|---|---|
| User Guide | `docs/user-guide.md` | Tool installation and basic usage |
| Technical Guide | `docs/technical-guide.md` | Architecture and module reference |
| YAML Spec | `PRDs/CBM-SPEC-espocrm-impl.md` | Complete YAML schema reference |
| Layout Spec | `PRDs/CBM-SPEC-layout-management.md` | Layout API and schema |
| Relationship Spec | `PRDs/CBM-SPEC-relationship-management.md` | Relationship API and schema |
| Doc Generator Spec | `PRDs/CBM-SPEC-doc-generator.md` | Documentation generator design |

---

## 14. Known Production Deployment Notes

### CBM Production — Pre-Deployment Manual Steps

The following manual steps are required before running the tool against
the CBM Production instance. These are one-time fixes for fields that
were manually configured with the wrong type before the tool was built.

| Field | Entity | Action Required |
|---|---|---|
| `cTimeInOperation` | Account | Delete field manually in Entity Manager before running `cbm_account_fields.yaml`. It was created as `varchar` — the YAML defines it as `enum`. Deleting and recreating via the tool will lose any existing values on live records — export first. |

After completing each manual step, run the affected YAML file and verify
before proceeding to the next file.
