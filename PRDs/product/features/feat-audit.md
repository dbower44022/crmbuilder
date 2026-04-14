# CRM Builder — CRM Audit

**Version:** 1.1
**Status:** Implemented
**Last Updated:** April 2026
**Depends On:** app-yaml-schema.md, feat-fields.md, feat-layouts.md, feat-relationships.md, feat-entities.md

---

## 1. Purpose

The Audit feature reads the current configuration of a live CRM instance
and produces a set of YAML program files that represent its state. This
gives teams a declarative starting point when adopting CRM Builder on an
instance that was configured manually, capturing a baseline before making
changes, or migrating configuration from one instance to another.

The output is identical in format to hand-authored program files
(see `app-yaml-schema.md`), so audited YAML can be immediately edited
and re-applied through the existing Configure engine.

---

## 2. Core Concepts

### 2.1 Source vs Target Instances

CRM Builder distinguishes between two instance roles:

| Role | Purpose | Operations Allowed |
|------|---------|-------------------|
| `source` | Read-only instance to audit | Audit |
| `target` | Instance to deploy and configure | Deploy, Configure |
| `both` | Same instance for audit and configuration | All operations |

Each instance profile carries a `role` field. Existing profiles default
to `target` when the field is introduced. Source-only instances do not
require a deployment configuration and are excluded from the Deploy and
Configure entry pickers.

All three roles use the same `InstanceProfile` model and are stored as
`{slug}.json` in `data/instances/`. The Instance panel displays a role
indicator for each entry so users can distinguish them at a glance.

### 2.2 Audit Scope

An audit discovers the following from the source instance:

| Object | What Is Captured |
|--------|-----------------|
| **Custom entities** | Entity type, labels, stream flag |
| **Custom fields** | All field properties (type, label, required, default, options, style, etc.) |
| **Native entity fields** | Custom fields added to native entities (Contact, Account, etc.) |
| **Detail layouts** | Panels, rows, tabs, field placement, dynamic logic |
| **List layouts** | Columns and widths |
| **Relationships** | Link type, link names, labels, related entities |

System fields (`id`, `createdAt`, `modifiedAt`, `assignedUserId`,
`createdById`, compound data fields) are excluded automatically. Native
fields that exist by virtue of entity type (e.g., `firstName`,
`lastName` on Person entities) are excluded unless explicitly requested.

### 2.3 Reverse Name Mapping

YAML program files use natural names with no platform prefix. The
configure engine applies the c-prefix at deployment time. The audit
reverses this:

| API Name | YAML Name | Rule |
|----------|-----------|------|
| `cContactType` | `contactType` | Strip leading `c`, lowercase next character |
| `CEngagement` | `Engagement` | Strip leading `C` from custom entity names |
| `Contact` | `Contact` | Native entity — no change |
| `firstName` | *(excluded)* | Native field on Person entity |

For entities with known name mappings (e.g., `CSessions` → `Session`),
the audit uses the inverse of the entity name map. For unknown custom
entities, it falls back to stripping the `C` prefix.

### 2.4 Output Artifacts

The audit produces two categories of output:

1. **YAML program files** — Written to
   `{project_folder}/programs/audit-{YYYYMMDD-HHMMSS}/`. One file per
   entity with custom fields, plus a `relationships.yaml` for all
   discovered relationships. Timestamped folders preserve audit history.

2. **Database records** — Entity, Field, FieldOption, Relationship,
   LayoutPanel, LayoutRow, LayoutTab, and ListColumn rows inserted into
   the client database with appropriate `is_native` flags.

---

## 3. Instance Role Management

### 3.1 Role Field

The `InstanceProfile` model gains a `role` field with three possible
values: `source`, `target`, or `both`. The field is stored in the
instance JSON file alongside existing fields.

### 3.2 Instance Dialog Changes

The Add/Edit Instance dialog includes a role selector (radio group)
below the authentication fields:

- **Source** — This instance will be audited (read-only operations)
- **Target** — This instance will receive deployments and configurations
- **Both** — This instance supports all operations

The default selection for new instances is `target` to preserve existing
behavior.

### 3.3 Instance Panel Changes

The Instance panel displays a role badge next to each instance name:

| Role | Badge |
|------|-------|
| `source` | `[SRC]` |
| `target` | `[TGT]` |
| `both` | `[S+T]` |

### 3.4 Entry Visibility by Role

| Sidebar Entry | Visible Roles |
|---------------|---------------|
| Instances | All |
| Deploy | `target`, `both` |
| Configure | `target`, `both` |
| **Audit** | `source`, `both` |
| Run History | All |
| Output | All |

When the active instance's role excludes an entry, the entry shows an
explanatory message (consistent with the never-disable-buttons pattern)
rather than being hidden or grayed out.

---

## 4. Audit Operations

### 4.1 Discovery Phase

The audit begins by querying the CRM Metadata API for all entity scopes.
Each scope is classified:

1. **Custom entity** — `isCustom == true` in scope metadata. Included
   with `action: create` in the YAML output.
2. **Native entity with custom fields** — Known entity (Contact,
   Account, etc.) that has fields with the c-prefix. Included without
   an `action` field, listing only custom fields.
3. **System entity** — Not customizable or purely internal (Preferences,
   AuthToken, ScheduledJob, etc.). Excluded from output.

### 4.2 Field Extraction

For each included entity, the audit fetches all field definitions and
classifies each field:

| Classification | Rule | Action |
|----------------|------|--------|
| Custom field | Name starts with `c` + uppercase, or `isCustom == true` | Include, strip c-prefix |
| Native field | Exists by default on the entity type | Exclude (unless option enabled) |
| System field | In the system fields exclusion set | Always exclude |

**System fields exclusion set:**

```
id, deleted, createdAt, modifiedAt, createdById, createdByName,
modifiedById, modifiedByName, assignedUserId, assignedUserName,
teamsIds, teamsNames, followersIds, followersNames,
emailAddressData, phoneNumberData, addressMap
```

**Person-type native fields** (excluded on Person entities):

```
salutationName, firstName, lastName, middleName, name,
emailAddress, phoneNumber, addressStreet, addressCity,
addressState, addressCountry, addressPostalCode, description
```

Extracted field properties map directly to the YAML field schema:

| API Property | YAML Property | Notes |
|-------------|---------------|-------|
| `type` | `type` | Direct mapping |
| `label` | `label` | May require translation API fallback |
| `required` | `required` | Boolean |
| `default` | `default` | String or null |
| `readOnly` | `readOnly` | Boolean |
| `audited` | `audited` | Boolean |
| `options` | `options` | Enum/multiEnum only |
| `translatedOptions` | `translatedOptions` | If differs from options |
| `style` | `style` | Enum/multiEnum badge colors |
| `isSorted` | `isSorted` | Enum/multiEnum |
| `displayAsLabel` | `displayAsLabel` | Enum/multiEnum |
| `maxLength` | `maxLength` | Varchar |
| `min` | `min` | Numeric types |
| `max` | `max` | Numeric types |

Properties that are documentation-only in the YAML schema (`description`,
`tooltip`, `category`, `optionDescriptions`) are not available from the
API and are omitted from audit output. Users fill these in manually.

### 4.3 Layout Extraction

**Detail layouts** are read from the Layout API and reverse-mapped:

1. Each panel's `customLabel` becomes the panel `label`
2. Row field names are reverse-mapped (strip c-prefix for custom fields)
3. `false` entries in rows (empty cells) become `null`
4. `tabBreak`, `tabLabel`, `style`, `hidden` properties are preserved
5. `dynamicLogicVisible` is reverse-mapped from the full conditionGroup
   format to the YAML shorthand (`{attribute: fieldName, value: "Value"}`)

**List layouts** are simpler: each column's field name is reverse-mapped
and its `width` is preserved.

### 4.4 Relationship Discovery

Relationships are discovered by reading all link definitions across
audited entities:

1. For each entity, fetch all links from the Metadata API
2. Classify each link by its `type` property:
   - `hasMany` with foreign `belongsTo` → `oneToMany`
   - `belongsTo` with foreign `hasMany` → `manyToOne`
   - `hasMany` with `relationName` → `manyToMany`
3. Deduplicate: each relationship appears on both participating entities.
   Track recorded pairs using sorted entity+link tuples.
4. Reverse-map entity names and link names (strip C/c-prefix as needed)
5. Recover labels from the translation system or Admin API where possible

### 4.5 YAML Generation

Each entity produces a YAML file following the `app-yaml-schema.md`
format exactly:

```yaml
version: "1.0"
content_version: "1.0.0"
description: >
  Audit snapshot of Contact captured from https://crm.example.com
  on 2026-04-14T10:30:00Z.

entities:
  Contact:
    fields:
      - name: contactType
        type: multiEnum
        label: "Contact Type"
        required: true
        options:
          - "Mentor"
          - "Mentee"
        style:
          Mentor: success
          Mentee: primary

    layout:
      detail:
        panels:
          - label: "Overview"
            rows:
              - [contactType, null]
              - [status, region]
      list:
        columns:
          - field: contactType
            width: 20
```

The relationships file collects all discovered relationships:

```yaml
version: "1.0"
content_version: "1.0.0"
description: >
  Relationships audit snapshot captured from https://crm.example.com
  on 2026-04-14T10:30:00Z.

relationships:
  - name: contactToDues
    entity: Contact
    entityForeign: Dues
    linkType: oneToMany
    link: duesRecords
    linkForeign: contact
    label: "Dues Records"
    labelForeign: "Contact"
```

**YAML output style requirements:**
- Block style for multi-line strings and descriptions
- Flow style avoided for lists (use block sequence)
- Keys ordered to match `app-yaml-schema.md` conventions
- No trailing whitespace; single newline at end of file

### 4.6 Database Record Insertion

After YAML files are written, the audit inserts corresponding records
into the client database:

| Table | Source | Key Fields |
|-------|--------|------------|
| `Entity` | Scope metadata | name, type, is_native, label_singular, label_plural |
| `Field` | Field metadata | entity_id, name, type, label, is_native, required |
| `FieldOption` | Enum options | field_id, value, label, sort_order, style |
| `Relationship` | Link metadata | entity_id, foreign_entity_id, link_type, link, link_foreign |
| `LayoutPanel` | Detail layout | entity_id, label, sort_order, tab_break, tab_label |
| `LayoutRow` | Panel rows | panel_id, sort_order, field_left, field_right |
| `LayoutTab` | Tab definitions | entity_id, label, category |
| `ListColumn` | List layout | entity_id, field_name, width, sort_order |

Records are checked for existence before insertion (idempotent).
A `ConfigurationRun` record is created with `operation: 'audit'` to
provide an audit trail.

---

## 5. Output and Reporting

### 5.1 Output Panel Messages

The audit emits progress messages to the Output entry:

```
[AUDIT]    Discovering entities ...
[AUDIT]    Found 8 custom entities, 3 native entities with custom fields
[AUDIT]    Contact — extracting 12 custom fields ...
[AUDIT]    Contact — reading detail layout (3 panels, 14 rows)
[AUDIT]    Contact — reading list layout (8 columns)
[AUDIT]    Engagement — extracting 6 custom fields ...
[AUDIT]    Discovering relationships ...
[AUDIT]    Found 15 relationships (8 after deduplication)
[AUDIT]    Writing YAML files to programs/audit-20260414-103000/ ...
[AUDIT]    Inserting database records ...
```

### 5.2 Summary Block

```
===========================================
AUDIT SUMMARY
===========================================
Source instance         : CBM Production
Source URL              : https://crm.cbmentors.org
Audit timestamp         : 2026-04-14 10:30:00

Entities discovered     : 11
  Custom entities       :  8
  Native with customs   :  3
Custom fields extracted : 67
Detail layouts captured : 11
List layouts captured   : 11
Relationships found     :  8

YAML files written      : 12
  Entity files          : 11
  Relationship file     :  1
Database records        : 142

Output folder           : programs/audit-20260414-103000/
===========================================
```

### 5.3 Report Status Values

| Status | Meaning |
|--------|---------|
| `discovered` | Entity or relationship found in source CRM |
| `extracted` | Fields or layout successfully read from API |
| `written` | YAML file generated successfully |
| `inserted` | Database record created |
| `skipped` | System entity or field excluded by classification rules |
| `warning` | Non-fatal issue (e.g., label not found in translation API) |
| `error` | API call failed; object could not be read |

---

## 6. Validation Rules

The following rules are applied during audit execution:

- Source instance must have a valid URL and credentials
- Connection to the source instance is tested before starting
- Entity names must be resolvable through the reverse name map or
  C-prefix stripping
- Fields with unrecognized types are included with a `# WARNING`
  comment in the YAML output
- Relationships referencing entities outside the audit scope are
  included but marked with a comment noting the foreign entity was
  not audited
- Output folder must not exist (timestamp ensures uniqueness); if it
  does, the audit aborts with an error rather than overwriting

---

## 7. Error Handling

| Error | Behavior |
|-------|----------|
| Connection failure | Abort audit, display connection error message |
| Authentication failure (401) | Abort audit, suggest checking API key |
| Single entity metadata failure | Log warning, skip entity, continue |
| Single field read failure | Log warning, skip field, continue |
| Layout API failure | Log warning, omit layout section for entity, continue |
| Relationship read failure | Log warning, skip relationship, continue |
| File write failure | Abort audit, display filesystem error |
| Database insert failure | Log error, continue (YAML files already written) |

The audit follows a best-effort strategy: individual object failures
produce warnings but do not abort the entire operation. Only connection,
authentication, and filesystem errors are fatal.

---

## 8. UI Integration

### 8.1 Sidebar Entry

The Audit feature adds a new entry to the Deployment window sidebar
between Run History and Output:

```
Instances | Deploy | Configure | Run History | Audit | Output
```

The Audit entry contains:

1. **Source instance picker** — Dropdown filtered to instances with
   role `source` or `both`. Shows instance name and URL.
2. **Scope options** — Checkboxes (all checked by default):
   - Include custom entity fields
   - Include native entity custom fields
   - Include detail layouts
   - Include list layouts
   - Include relationships
3. **Include native fields checkbox** — Unchecked by default. When
   checked, native fields on native entities are included in output.
4. **Start Audit button** — Initiates the audit. Follows the
   never-disable pattern: if no source instance is selected, clicking
   shows an explanatory message.
5. **Last audit info** — Shows timestamp and output folder of the most
   recent audit for the selected source instance.

### 8.2 Progress Dialog

A modal progress dialog appears during audit execution:

- Progress bar showing entity-level progress (e.g., "Entity 4 of 11")
- Scrolling log of `[AUDIT]` messages
- Cancel button to abort the audit (best-effort cleanup of partial files)

### 8.3 Post-Audit Actions

After a successful audit, the user is offered:

- **Open output folder** — Opens the timestamped audit folder in the
  system file manager
- **View in Configure** — Switches to the Configure entry where the
  new YAML files are visible in the program list (if a target instance
  is also selected)

---

## 9. Implementation Reference

All seven development phases are complete. This section documents the
final file inventory and key implementation details.

### 9.1 File Inventory

| Layer | File | Purpose |
|-------|------|---------|
| Model | `espo_impl/core/models.py` | `InstanceRole` enum (`source`, `target`, `both`) and `role` field on `InstanceProfile` |
| Model | `espo_impl/ui/instance_dialog.py` | Radio button group (Target / Source / Both) in Add/Edit Instance dialog |
| Model | `espo_impl/ui/instance_panel.py` | Role badges `[SRC]`/`[TGT]`/`[S+T]` in list, JSON serialization of `role` field |
| API | `espo_impl/core/api_client.py` | Four new methods: `get_all_scopes()`, `get_entity_full_metadata()`, `get_all_links()`, `get_language_translations()` |
| Core | `espo_impl/core/audit_utils.py` | Reverse c-prefix mapping, entity/field classification enums, system field exclusion sets |
| Core | `espo_impl/core/audit_manager.py` | `AuditManager` orchestrator — entity discovery, field/layout extraction, relationship dedup, YAML serialization |
| DB | `espo_impl/core/audit_db.py` | `insert_audit_records()` — idempotent insertion of Entity, Field, FieldOption, Relationship, LayoutPanel, LayoutRow, ListColumn records |
| DB | `automation/db/client_schema.py` | `ConfigurationRun` CHECK constraint updated to allow `'audit'` operation |
| DB | `automation/db/migrations.py` | `_client_v7` migration — rebuilds `ConfigurationRun` table for updated CHECK |
| Worker | `espo_impl/workers/audit_worker.py` | `AuditWorker(QThread)` — background thread with `output_line`, `progress`, `finished_ok`, `finished_error` signals |
| UI | `automation/ui/deployment/audit_entry.py` | `AuditEntry` sidebar widget + `AuditProgressDialog` modal |
| UI | `automation/ui/deployment/deployment_window.py` | Audit registered as 5th sidebar entry (`_IDX_AUDIT = 4`) |

### 9.2 Architecture Decisions

**Instance role on InstanceProfile, not a separate model.** The `role`
field was added directly to `InstanceProfile` rather than creating a
separate source-instance model. Existing JSON files without a `role`
key load as `target` — no migration script required.

**audit_db.py as a separate module.** Database insertion logic was
extracted from `AuditManager` into `espo_impl/core/audit_db.py` to
keep the manager focused on API orchestration and YAML generation.
The manager calls `insert_audit_records()` via a lazy import after
YAML files are written.

**AuditProgressDialog embedded in audit_entry.py.** Rather than a
separate `audit_progress.py` file, the progress dialog is co-located
with the entry widget since it is only used from that entry. This
matches the principle of keeping related code together.

**ConfigurationRun table rebuild for 'audit' operation.** SQLite
cannot ALTER CHECK constraints, so `_client_v7` uses the 12-step
table redefinition pattern (same approach as `_master_v3`) to rebuild
`ConfigurationRun` with the updated CHECK allowing `'audit'`.

**Deduplication via frozenset.** Relationship deduplication uses
`frozenset({entity.link, foreign.link})` to ensure each relationship
pair is recorded exactly once regardless of which side is encountered
first.

### 9.3 Key Classes and Functions

**`InstanceRole`** (`models.py`) — Enum with values `SOURCE`,
`TARGET`, `BOTH`. Default on `InstanceProfile` is `TARGET`.

**`AuditManager`** (`audit_manager.py`) — Orchestrator class.
Constructor accepts `EspoAdminClient`, `AuditOptions`, and a progress
callback `(str, str) -> None`. Main entry point is
`run_audit(output_dir, db_conn=None, instance_id=None)`.

**`AuditOptions`** (`audit_manager.py`) — Dataclass with six boolean
toggles controlling what the audit captures. All default to `True`
except `include_native_fields` which defaults to `False`.

**`AuditReport`** (`audit_manager.py`) — Aggregate results dataclass
containing `entities`, `relationships`, `files_written`, `errors`,
`warnings`.

**`classify_entity(scope_name, scope_meta)`** (`audit_utils.py`) —
Returns `EntityClass.CUSTOM`, `NATIVE`, or `SYSTEM`. Uses
`_SYSTEM_SCOPES` set (60+ internal entity names) and `NATIVE_ENTITIES`
from `confirm_delete_dialog.py`.

**`classify_field(field_name, field_meta, entity_type)`**
(`audit_utils.py`) — Returns `FieldClass.CUSTOM`, `NATIVE`, or
`SYSTEM`. Uses `SYSTEM_FIELDS` set, c-prefix heuristic, and
per-entity-type native field sets (`NATIVE_PERSON_FIELDS`,
`NATIVE_COMPANY_FIELDS`, `NATIVE_EVENT_FIELDS`, `NATIVE_BASE_FIELDS`).

**`insert_audit_records(conn, report, instance_id)`**
(`audit_db.py`) — Inserts all DB records from an `AuditReport`.
Returns total records inserted. Idempotent: checks for existing
records by natural key before each INSERT.

**`AuditWorker`** (`audit_worker.py`) — QThread subclass. Tests
connection before starting. Opens optional DB connection from path.
Emits formatted summary block on completion.

**`AuditEntry`** (`audit_entry.py`) — Sidebar widget with source
instance info group, six scope checkboxes, Start Audit and Open
Output Folder buttons. `refresh()` follows the standard
`(conn, instance, project_folder, has_instances)` signature.

**`AuditProgressDialog`** (`audit_entry.py`) — Modal dialog with
indeterminate progress bar, color-coded log output, and Cancel/Close
buttons. Mirrors log lines to `OutputEntry` if provided.

### 9.4 Sidebar Entry Registration

The Deployment window sidebar now has six entries:

```
_ENTRIES = ["Instances", "Deploy", "Configure", "Run History", "Audit", "Output"]

_IDX_INSTANCES   = 0
_IDX_DEPLOY      = 1
_IDX_CONFIGURE   = 2
_IDX_RUN_HISTORY = 3
_IDX_AUDIT       = 4
_IDX_OUTPUT      = 5
```

The Audit entry is refreshed with the same context signature as
Configure and Run History:
`refresh(conn, instance, project_folder, has_instances)`.

### 9.5 Database Migration

Client schema version 7 (`_client_v7` in `migrations.py`) rebuilds
the `ConfigurationRun` table to update the `operation` CHECK
constraint from `('run', 'verify')` to `('run', 'verify', 'audit')`.
The migration is idempotent — if the table does not exist (pre-v5
databases), it is skipped and v5 will create it with the correct
CHECK on first creation.

---

## 10. Future Considerations

- **Migration workflow** — Select a source instance and a target
  instance, audit the source, review/edit the YAML, then configure the
  target. The Audit entry could surface both pickers.
- **Differential audit** — Compare a previous audit snapshot to the
  current CRM state and highlight what changed.
- **Selective entity audit** — Let users pick which entities to audit
  rather than auditing everything.
- **Data record export** — Extend the audit to capture record data
  (not just schema), producing CSV or import-ready files.
- **Audit-to-Configure pipeline** — After auditing, automatically
  populate the Configure program list and offer a one-click
  "apply to target" workflow.
